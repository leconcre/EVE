"""
voice/stt/discord_listener.py - Captura de Áudio REAL usando discord-ext-voice-recv

IMPORTANTE: Este módulo usa discord-ext-voice-recv (extensão para discord.py)!
A extensão adiciona suporte a AudioSink para RECEBER áudio.

Mudança: Anteriormente usava py-cord (erro 4006), agora usa discord.py + voice-recv
"""

import asyncio
from typing import Optional, Dict, Callable
import discord
from discord.ext import voice_recv
from discord.opus import Decoder as OpusDecoder
from io import BytesIO
import logging
from datetime import datetime, timedelta
import numpy as np
import threading
import time

from .models import VoiceInput, AudioChunk
from .user_tracker import UserTracker
from .vad import DiscordVAD
from .transcriber import AudioTranscriber
from ..permissions import permission_manager

logger = logging.getLogger("eve_discord.listener")

# Timeout para cleanup de buffers órfãos (segundos)
BUFFER_TIMEOUT_SECONDS = 30.0


class VoiceRecordingSink(voice_recv.AudioSink):
    """
    Sink personalizado para discord-ext-voice-recv que captura áudio por usuário.

    IMPORTANTE: Esta classe usa a API de AudioSink do discord-ext-voice-recv.
    Cada usuário tem seu próprio buffer de áudio.
    """

    def __init__(
        self,
        user_tracker: UserTracker,
        vad: DiscordVAD,
        transcriber: AudioTranscriber,
        on_transcription: Optional[Callable] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        """
        Inicializa sink de gravação.

        Args:
            user_tracker: Rastreador de usuários
            vad: Detector de atividade de voz
            transcriber: Transcritor de áudio
            on_transcription: Callback async quando transcrição pronta
            loop: Event loop do asyncio (necessário para thread-safety)
        """
        super().__init__()
        self.user_tracker = user_tracker
        self.vad = vad
        self.transcriber = transcriber
        self.on_transcription = on_transcription

        # Event loop para chamadas thread-safe
        self._loop = loop or asyncio.get_event_loop()

        # Lock para acesso thread-safe aos buffers
        self._lock = threading.RLock()

        # Buffers de áudio por usuário {user_id: BytesIO}
        self._audio_buffers: Dict[int, BytesIO] = {}

        # Timestamp da última atividade por usuário
        self._last_activity: Dict[int, datetime] = {}

        # Controle de processamento em andamento
        self._processing: Dict[int, bool] = {}

        # Decodificador Opus para decodificar manualmente (evita erros de corrupted stream)
        self._opus_decoder = OpusDecoder()

        # Configurações - OTIMIZADAS para resposta rapida
        self.min_audio_duration = 0.3  # Mínimo 0.3s (permite "oi" rapido)
        self.max_silence_duration = 0.8  # 0.8s de silêncio para finalizar (era 1.5s)
        self.sample_rate = 48000  # Discord usa 48kHz

        # Flag para pausar escuta (quando EVE está falando)
        self._paused = False

        # Contador para debug
        self._write_calls_since_resume = 0

        # Task de cleanup periódico
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = True

        logger.info("✅ VoiceRecordingSink inicializado (discord-ext-voice-recv)")

    def pause(self):
        """Pausa a escuta e limpa todos os buffers."""
        self._paused = True
        with self._lock:
            # Fecha e limpa buffers para evitar processar áudio antigo
            for buffer in self._audio_buffers.values():
                buffer.close()
            self._audio_buffers.clear()
            self._last_activity.clear()
        # Contador para debug
        self._write_calls_since_resume = 0
        logger.info("⏸️ Sink pausado - buffers limpos")

    def resume(self):
        """Retoma a escuta."""
        self._paused = False
        self._write_calls_since_resume = 0
        logger.info("▶️ Sink retomado - aguardando áudio...")

    def start_cleanup_task(self):
        """Inicia task de cleanup periódico de buffers órfãos."""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.run_coroutine_threadsafe(
                    self._periodic_cleanup(),
                    self._loop
                ).result(timeout=1.0)
            except Exception as e:
                logger.warning(f"Não foi possível iniciar cleanup task: {e}")

    async def _periodic_cleanup(self):
        """Limpa buffers órfãos periodicamente."""
        while self._running:
            await asyncio.sleep(10.0)  # Verifica a cada 10 segundos
            self._cleanup_stale_buffers()

    def _cleanup_stale_buffers(self):
        """Remove buffers que ficaram órfãos (sem atividade por muito tempo)."""
        now = datetime.now()
        stale_users = []

        with self._lock:
            for user_id, last_activity in list(self._last_activity.items()):
                age = (now - last_activity).total_seconds()
                if age > BUFFER_TIMEOUT_SECONDS:
                    stale_users.append(user_id)

            for user_id in stale_users:
                if user_id in self._audio_buffers:
                    self._audio_buffers[user_id].close()
                    del self._audio_buffers[user_id]
                if user_id in self._last_activity:
                    del self._last_activity[user_id]
                if user_id in self._processing:
                    del self._processing[user_id]
                logger.debug(f"🧹 Buffer órfão removido: user_id={user_id}")

    @voice_recv.AudioSink.listener()
    def on_voice_member_disconnect(self, member: discord.Member, ssrc: Optional[int]):
        """Callback quando um membro desconecta do voice."""
        logger.debug(f"Membro desconectou: {member.display_name}")
        # Limpa buffer do usuário que desconectou
        user_id = member.id
        with self._lock:
            if user_id in self._audio_buffers:
                self._audio_buffers[user_id].close()
                del self._audio_buffers[user_id]
            if user_id in self._last_activity:
                del self._last_activity[user_id]
            if user_id in self._processing:
                del self._processing[user_id]

    def wants_opus(self) -> bool:
        """
        Retorna False para receber PCM já decodificado pela biblioteca.

        Isso é mais simples e a biblioteca nova (0.5.3a180) deve lidar
        melhor com a decodificação.
        """
        return False

    def write(self, user: discord.User, data: voice_recv.VoiceData):
        """
        Callback chamado pelo discord-ext-voice-recv quando há novos dados de áudio.

        IMPORTANTE: Este método é chamado automaticamente pela extensão
        para cada chunk de áudio recebido de cada usuário.
        Este método é THREAD-SAFE usando locks.

        Args:
            user: discord.User ou discord.Member
            data: voice_recv.VoiceData contendo áudio PCM (wants_opus=False)
        """
        # Ignora áudio se pausado (EVE está falando)
        if self._paused:
            return

        # Debug: log primeiras chamadas após resume
        self._write_calls_since_resume += 1
        if self._write_calls_since_resume == 1:
            logger.info("📡 Primeiro pacote de áudio recebido após resume")
        elif self._write_calls_since_resume == 50:
            logger.info("📡 50 pacotes de áudio recebidos - escuta funcionando")

        # Extrai user_id
        user_id = user.id

        # Verifica se temos este usuário rastreado
        if user_id not in self.user_tracker.get_all_users():
            # Tenta adicionar
            if hasattr(user, 'guild'):  # Se for Member
                self.user_tracker.add_user(user)

        # Com wants_opus=False, já recebemos PCM decodificado
        try:
            # Obtém dados PCM do pacote
            pcm_data = data.pcm if hasattr(data, 'pcm') else bytes(data)
            if pcm_data is None or len(pcm_data) == 0:
                return
        except Exception as e:
            # Ignora pacotes com problema
            return

        # Verifica se tem voz usando VAD
        has_voice = self.vad.is_voice(pcm_data)

        should_process = False

        # Acesso thread-safe aos buffers
        with self._lock:
            if has_voice:
                # Cria buffer se não existir
                if user_id not in self._audio_buffers:
                    self._audio_buffers[user_id] = BytesIO()
                    username = self.user_tracker.get_username(user_id)
                    logger.info(f"🎤 Iniciando captura de áudio: {username} (ID: {user_id})")

                # Adiciona dados ao buffer
                self._audio_buffers[user_id].write(pcm_data)
                self._last_activity[user_id] = datetime.now()

            else:
                # Silêncio detectado
                if user_id in self._audio_buffers:
                    # Verifica se passou tempo suficiente de silêncio
                    if user_id in self._last_activity:
                        silence_duration = (datetime.now() - self._last_activity[user_id]).total_seconds()

                        if silence_duration >= self.max_silence_duration:
                            # Evita processar múltiplas vezes o mesmo buffer
                            if user_id not in self._processing or not self._processing[user_id]:
                                self._processing[user_id] = True
                                should_process = True

        # Fora do lock para evitar deadlock com o event loop
        if should_process:
            asyncio.run_coroutine_threadsafe(
                self._process_user_audio(user_id),
                self._loop
            )

    async def _process_user_audio(self, user_id: int):
        """
        Processa áudio capturado de um usuário.

        Args:
            user_id: ID do usuário Discord
        """
        buffer = None
        audio_data = None

        try:
            # Acesso thread-safe ao buffer
            with self._lock:
                if user_id not in self._audio_buffers:
                    return

                # Obtém dados do buffer
                buffer = self._audio_buffers[user_id]
                audio_data = buffer.getvalue()

                # Fecha e remove buffer
                buffer.close()
                del self._audio_buffers[user_id]
                if user_id in self._last_activity:
                    del self._last_activity[user_id]

            # Verifica duração mínima
            # Discord: 48kHz, stereo (2 canais), 16-bit (2 bytes)
            duration = len(audio_data) / (self.sample_rate * 2 * 2)

            if duration < self.min_audio_duration:
                logger.info(f"⚠️ Áudio muito curto ({duration:.2f}s < {self.min_audio_duration}s), ignorando")
                return

            username = self.user_tracker.get_username(user_id)
            logger.info(f"📝 Processando {duration:.2f}s de áudio de: {username}")

            # Transcreve áudio
            result = self.transcriber.transcribe(audio_data, self.sample_rate)

            # Filtra transcrições vazias ou alucinações do Whisper
            text = result["text"].strip()

            # Lista de alucinações comuns do Whisper quando não entende o áudio
            hallucinations = [
                "", "...", ".", "..", "....",
                "(música)", "[música]", "(Música)", "[Música]",
                "(aplausos)", "[aplausos]", "(Aplausos)", "[Aplausos]",
                "(silêncio)", "[silêncio]", "(Silêncio)", "[Silêncio]",
                "Legendas pela comunidade Amara.org",
                "Obrigado por assistir!",
                "Inscreva-se no canal",
                "♪", "♫"
            ]

            if not text or text in hallucinations or len(text) < 2:
                logger.info(f"⚠️ Transcrição inválida ou alucinação: '{text}', ignorando")
                return

            # Obtém informações do usuário
            member = self.user_tracker.get_user(user_id)
            if not member:
                logger.warning(f"Usuário {user_id} não encontrado no rastreador")
                return

            # Obtém permissões
            perms = permission_manager.get_permissions(member)

            # Obtém roles
            roles = [role.name for role in member.roles if role.name != "@everyone"]

            # Cria VoiceInput
            voice_input = VoiceInput(
                user_id=user_id,
                username=username,
                text=result["text"],
                confidence=result["confidence"],
                timestamp=datetime.now(),
                is_creator=perms.is_creator,
                is_admin=perms.is_admin,
                roles=roles,
                audio_duration=duration,
                language=result["language"]
            )

            # Log
            creator_tag = " [CREATOR]" if voice_input.is_creator else ""
            admin_tag = " [ADMIN]" if voice_input.is_admin and not voice_input.is_creator else ""
            logger.info(f"✅ {voice_input.username}{creator_tag}{admin_tag}: {voice_input.text}")

            # Chama callback
            if self.on_transcription:
                await self.on_transcription(voice_input)

        except Exception as e:
            logger.error(f"Erro ao processar áudio do usuário {user_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reseta flag de processamento (thread-safe)
            with self._lock:
                if user_id in self._processing:
                    self._processing[user_id] = False

    def cleanup(self):
        """Limpa recursos do sink."""
        self._running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

        with self._lock:
            # Fecha todos os buffers
            for buffer in self._audio_buffers.values():
                try:
                    buffer.close()
                except Exception:
                    pass
            self._audio_buffers.clear()
            self._last_activity.clear()
            self._processing.clear()
        logger.debug("Sink limpo")


class DiscordVoiceListener:
    """
    Sistema completo de escuta de voz no Discord usando discord-ext-voice-recv.

    Esta classe orquestra a captura, identificação e transcrição de voz.

    IMPORTANTE: Requer discord.py + discord-ext-voice-recv instalados!
    """

    def __init__(
        self,
        transcriber: Optional[AudioTranscriber] = None,
        on_transcription: Optional[Callable] = None
    ):
        """
        Inicializa listener.

        Args:
            transcriber: Transcritor de áudio (opcional)
            on_transcription: Callback async quando transcrição pronta
        """
        self.user_tracker = UserTracker()
        # VAD mais sensível para capturar voz (threshold baixo)
        self.vad = DiscordVAD(energy_threshold=0.003)

        # Transcritor
        if transcriber is None:
            logger.info("Criando transcritor padrão (small, pt, cpu)...")
            self.transcriber = AudioTranscriber(
                model_size="small",
                language="pt",
                device="cpu"
            )
        else:
            self.transcriber = transcriber

        self.on_transcription = on_transcription
        self._sink: Optional[VoiceRecordingSink] = None
        self._voice_client: Optional[voice_recv.VoiceRecvClient] = None

        logger.info("DiscordVoiceListener inicializado (discord-ext-voice-recv)")

    async def start_listening(self, voice_client: voice_recv.VoiceRecvClient):
        """
        Inicia escuta em um canal de voz usando discord-ext-voice-recv.

        Args:
            voice_client: VoiceRecvClient conectado ao canal
        """
        if not voice_client.is_connected():
            raise RuntimeError("Voice client não está conectado ao canal!")

        self._voice_client = voice_client

        # Atualiza rastreamento de usuários do canal
        if voice_client.channel:
            self.user_tracker.update_from_channel(voice_client.channel)
            logger.info(f"Rastreando {len(self.user_tracker.get_all_users())} usuários")

        # Cria sink personalizado (com event loop para thread-safety)
        self._sink = VoiceRecordingSink(
            user_tracker=self.user_tracker,
            vad=self.vad,
            transcriber=self.transcriber,
            on_transcription=self.on_transcription,
            loop=asyncio.get_running_loop()
        )

        # IMPORTANTE: discord-ext-voice-recv usa listen() com o sink
        try:
            voice_client.listen(self._sink)

            logger.info(f"✅ ESCUTANDO canal: {voice_client.channel.name}")
            logger.info(f"   Usuários no canal: {[m.display_name for m in voice_client.channel.members if not m.bot]}")

        except Exception as e:
            logger.error(f"Erro ao iniciar escuta: {e}")
            raise

    async def stop_listening(self):
        """Para a escuta."""
        if self._voice_client and self._voice_client.is_listening():
            self._voice_client.stop_listening()
            logger.info("⏹️ Escuta interrompida")

        if self._sink:
            self._sink.cleanup()

    def update_users(self):
        """Atualiza lista de usuários no canal."""
        if self._voice_client and self._voice_client.channel:
            self.user_tracker.update_from_channel(self._voice_client.channel)
            logger.debug("Lista de usuários atualizada")
