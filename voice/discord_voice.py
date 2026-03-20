# voice/discord_voice.py - INTEGRAÇÃO COM DISCORD
"""
Bot de voz para Discord que permite à EVE ouvir e falar em canais de voz.

Funcionalidades:
- Entrar/sair de canais de voz
- Ouvir usuários no canal
- Transcrever fala automaticamente
- Responder usando TTS
- Comandos de controle
"""

import asyncio
import numpy as np
import logging
from typing import Optional, Callable
from pathlib import Path
import io
import wave

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("⚠️ discord.py não disponível - integração Discord desabilitada")

from . import config
from .speech_to_text import SpeechToText
from .text_to_speech import TextToSpeech
from .audio_utils import VoiceActivityDetector, normalize_audio, bytes_to_audio

logger = logging.getLogger("eve.voice.discord")


# ═══════════════════════════════════════════════════════════════════
# CLASSE DE SINK PARA CAPTURA DE ÁUDIO
# ═══════════════════════════════════════════════════════════════════

if DISCORD_AVAILABLE:
    class VoiceSink(discord.sinks.Sink):
        """
        Sink customizado para capturar áudio do Discord.

        Captura áudio de usuários no canal de voz e detecta quando param de falar.
        """

        def __init__(self, callback: Callable, vad: VoiceActivityDetector):
            """
            Inicializa o sink.

            Args:
                callback: Função chamada quando usuário termina de falar
                vad: Detector de atividade de voz
            """
            super().__init__()
            self.callback = callback
            self.vad = vad
            self.audio_data = {}  # user_id -> lista de chunks
            self.silence_counters = {}  # user_id -> contador de silêncio

            logger.info("VoiceSink inicializado")

        def write(self, data: bytes, user: int):
            """
            Chamado quando há dados de áudio de um usuário.

            Args:
                data: Bytes de áudio (PCM)
                user: ID do usuário
            """
            # Inicializa buffers se necessário
            if user not in self.audio_data:
                self.audio_data[user] = []
                self.silence_counters[user] = 0

            # Converte bytes para array NumPy
            audio_chunk = np.frombuffer(data, dtype=np.int16)

            # Detecta voz
            has_speech = self.vad.is_speech(audio_chunk)

            if has_speech:
                # Voz detectada - adiciona ao buffer e reseta silêncio
                self.audio_data[user].append(audio_chunk)
                self.silence_counters[user] = 0
            elif len(self.audio_data[user]) > 0:
                # Silêncio depois de falar
                self.audio_data[user].append(audio_chunk)
                self.silence_counters[user] += 1

                # Se silêncio foi longo o suficiente, processa
                silence_chunks = int(config.SILENCE_DURATION * config.SAMPLE_RATE / len(audio_chunk))
                if self.silence_counters[user] >= silence_chunks:
                    self._process_user_audio(user)

        def _process_user_audio(self, user: int):
            """
            Processa áudio completo de um usuário.

            Args:
                user: ID do usuário
            """
            if user not in self.audio_data or len(self.audio_data[user]) == 0:
                return

            # Concatena todos os chunks
            audio = np.concatenate(self.audio_data[user])

            # Limpa buffer
            self.audio_data[user] = []
            self.silence_counters[user] = 0

            # Normaliza
            audio_float = audio.astype(np.float32) / 32768.0
            audio_float = normalize_audio(audio_float)

            # Chama callback em thread async
            asyncio.create_task(self.callback(user, audio_float))

        def cleanup(self):
            """Limpa recursos."""
            self.audio_data.clear()
            self.silence_counters.clear()


# ═══════════════════════════════════════════════════════════════════
# BOT DE VOZ PARA DISCORD
# ═══════════════════════════════════════════════════════════════════

class DiscordVoiceBot:
    """
    Bot de Discord com capacidades de voz.

    Permite à EVE ouvir e falar em canais de voz do Discord.
    """

    def __init__(
        self,
        token: str = config.DISCORD_TOKEN,
        prefix: str = config.DISCORD_COMMAND_PREFIX,
        on_transcription: Optional[Callable] = None
    ):
        """
        Inicializa o bot de voz.

        Args:
            token: Token do bot Discord
            prefix: Prefixo de comandos
            on_transcription: Callback chamado quando transcreve áudio
        """
        if not DISCORD_AVAILABLE:
            raise RuntimeError("discord.py não está instalado. Instale com: pip install discord.py[voice]")

        if not token:
            raise ValueError(
                "Token do Discord não configurado.\n"
                "Defina a variável de ambiente DISCORD_BOT_TOKEN"
            )

        self.token = token
        self.on_transcription = on_transcription

        # Cria bot com intents necessários
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True

        self.bot = commands.Bot(command_prefix=prefix, intents=intents)

        # Componentes de voz
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.vad = VoiceActivityDetector()

        # Estado
        self.voice_client = None
        self.current_sink = None

        # Registra comandos e eventos
        self._register_commands()
        self._register_events()

        logger.info("✅ DiscordVoiceBot inicializado")

    def _register_events(self):
        """Registra eventos do bot."""

        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Bot conectado como {self.bot.user}")
            logger.info(f"Guilds: {len(self.bot.guilds)}")

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Detecta mudanças no estado de voz."""
            # Se o bot ficou sozinho no canal, sai
            if self.voice_client and self.voice_client.channel:
                if len(self.voice_client.channel.members) == 1:
                    logger.info("Canal vazio - saindo...")
                    await self.voice_client.disconnect()
                    self.voice_client = None

    def _register_commands(self):
        """Registra comandos do bot."""

        @self.bot.command(name="join", help="EVE entra no canal de voz")
        async def join(ctx):
            """Comando para entrar no canal de voz."""
            if not ctx.author.voice:
                await ctx.send("❌ Você precisa estar em um canal de voz!")
                return

            channel = ctx.author.voice.channel

            try:
                self.voice_client = await channel.connect()
                await ctx.send(f"✅ Conectada ao canal: {channel.name}")
                logger.info(f"Conectado ao canal: {channel.name}")

                # Inicia escuta
                await self._start_listening(ctx)

            except Exception as e:
                logger.error(f"Erro ao conectar: {e}")
                await ctx.send(f"❌ Erro ao conectar: {e}")

        @self.bot.command(name="leave", help="EVE sai do canal de voz")
        async def leave(ctx):
            """Comando para sair do canal de voz."""
            if not self.voice_client:
                await ctx.send("❌ Não estou em nenhum canal!")
                return

            await self.voice_client.disconnect()
            self.voice_client = None
            await ctx.send("👋 Saindo do canal de voz...")
            logger.info("Desconectado do canal de voz")

        @self.bot.command(name="speak", help="EVE fala um texto")
        async def speak(ctx, *, text: str):
            """Comando para fazer a EVE falar."""
            if not self.voice_client:
                await ctx.send("❌ Não estou em um canal de voz! Use !join primeiro.")
                return

            try:
                await ctx.send(f"🔊 Falando: {text[:50]}...")
                await self._speak_in_channel(text)
                await ctx.send("✅ Pronto!")

            except Exception as e:
                logger.error(f"Erro ao falar: {e}")
                await ctx.send(f"❌ Erro: {e}")

        @self.bot.command(name="listen", help="EVE começa a ouvir")
        async def listen(ctx):
            """Comando para iniciar escuta."""
            if not self.voice_client:
                await ctx.send("❌ Não estou em um canal de voz!")
                return

            await ctx.send("👂 Escutando...")
            await self._start_listening(ctx)

        @self.bot.command(name="stop", help="EVE para de ouvir")
        async def stop(ctx):
            """Comando para parar escuta."""
            if self.current_sink:
                await self._stop_listening()
                await ctx.send("⏹️ Parei de ouvir")
            else:
                await ctx.send("❌ Não estou ouvindo")

    async def _start_listening(self, ctx):
        """
        Inicia a escuta no canal de voz.

        Args:
            ctx: Contexto do comando
        """
        if not self.voice_client:
            return

        try:
            # Cria callback para processar áudio
            async def on_user_speech(user_id: int, audio: np.ndarray):
                try:
                    # Transcreve
                    logger.info(f"Transcrevendo áudio de {user_id}...")
                    result = self.stt.transcribe(audio)
                    text = result.get("text", "").strip()

                    if text:
                        logger.info(f"Transcrição: {text}")

                        # Envia no chat
                        user = self.bot.get_user(user_id)
                        username = user.name if user else f"User {user_id}"
                        await ctx.send(f"**{username}:** {text}")

                        # Chama callback externo se definido
                        if self.on_transcription:
                            await self.on_transcription(user_id, text, ctx)

                except Exception as e:
                    logger.error(f"Erro ao processar áudio: {e}")

            # Cria sink
            self.current_sink = VoiceSink(callback=on_user_speech, vad=self.vad)

            # Inicia gravação
            self.voice_client.start_recording(
                self.current_sink,
                self._recording_callback,
                ctx
            )

            logger.info("Escuta iniciada")

        except Exception as e:
            logger.error(f"Erro ao iniciar escuta: {e}")
            raise

    async def _stop_listening(self):
        """Para a escuta."""
        if self.voice_client and self.voice_client.is_recording():
            self.voice_client.stop_recording()
            self.current_sink = None
            logger.info("Escuta parada")

    async def _recording_callback(self, sink, ctx):
        """
        Callback chamado quando gravação termina.

        Args:
            sink: Sink usado
            ctx: Contexto
        """
        logger.info("Gravação finalizada")

    async def _speak_in_channel(self, text: str):
        """
        Fala no canal de voz usando TTS.

        Args:
            text: Texto para falar
        """
        if not self.voice_client:
            return

        try:
            # Gera áudio
            logger.info(f"Gerando TTS: {text[:50]}...")
            audio = self.tts.synthesize(text)

            if audio is None:
                logger.error("Falha ao gerar TTS")
                return

            # Salva temporariamente
            temp_file = config.CACHE_DIR / "discord_tts.wav"
            from .audio_utils import save_audio
            save_audio(audio, temp_file, config.SAMPLE_RATE)

            # Reproduz no Discord
            if self.voice_client.is_playing():
                self.voice_client.stop()

            audio_source = discord.FFmpegPCMAudio(str(temp_file))
            self.voice_client.play(audio_source)

            # Aguarda terminar
            while self.voice_client.is_playing():
                await asyncio.sleep(0.1)

            logger.info("TTS reproduzido com sucesso")

        except Exception as e:
            logger.error(f"Erro ao falar no canal: {e}")
            raise

    def run(self):
        """Inicia o bot (bloqueante)."""
        logger.info("Iniciando bot...")
        try:
            self.bot.run(self.token)
        except Exception as e:
            logger.error(f"Erro ao executar bot: {e}")
            raise

    async def start(self):
        """Inicia o bot (async)."""
        logger.info("Iniciando bot (async)...")
        try:
            await self.bot.start(self.token)
        except Exception as e:
            logger.error(f"Erro ao executar bot: {e}")
            raise

    async def close(self):
        """Fecha o bot."""
        if self.voice_client:
            await self.voice_client.disconnect()
        await self.bot.close()
        logger.info("Bot fechado")


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

def create_voice_bot(
    token: Optional[str] = None,
    on_transcription: Optional[Callable] = None
) -> DiscordVoiceBot:
    """
    Cria um bot de voz para Discord (função de conveniência).

    Args:
        token: Token do bot (usa variável de ambiente se None)
        on_transcription: Callback para transcrições

    Returns:
        Instância de DiscordVoiceBot
    """
    if token is None:
        token = config.DISCORD_TOKEN

    return DiscordVoiceBot(token=token, on_transcription=on_transcription)


# ═══════════════════════════════════════════════════════════════════
# EXEMPLO DE USO
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Exemplo de callback
    async def on_message(user_id, text, ctx):
        # Aqui você integraria com a EVE
        logger.info(f"Processando mensagem de {user_id}: {text}")

        # Exemplo: responde automaticamente
        if "eve" in text.lower():
            response = "Sim, estou aqui! Como posso ajudar?"
            bot = ctx.bot
            await bot.get_cog('VoiceBot')._speak_in_channel(response)

    # Cria e inicia bot
    print("Iniciando bot de voz do Discord...")
    bot = create_voice_bot(on_transcription=on_message)
    bot.run()
