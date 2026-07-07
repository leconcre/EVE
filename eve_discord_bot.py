# eve_discord_bot.py - BOT DISCORD COM EVE E VOZ (discord-ext-voice-recv)
"""
Bot do Discord que integra:
- EVE (IA)
- Voz Francisca (Edge TTS) - EVE fala
- Sistema STT (Whisper) - EVE ouve

IMPORTANTE: Este bot usa discord.py + discord-ext-voice-recv!
A extensão discord-ext-voice-recv adiciona suporte a recebimento de áudio.

Mudança: Substituiu py-cord (erro 4006) por discord.py + voice-recv

Instalação:
    pip uninstall py-cord discord -y
    pip install discord.py[voice] discord-ext-voice-recv faster-whisper numpy

Comandos:
    !join - Entrar no canal de voz
    !listen - Começar a OUVIR (ativa STT)
    !stop_listen - Parar de ouvir
    !leave - Sair do canal
    !eve [texto] - Modo texto (antigo)

Uso:
    python eve_discord_bot.py
"""

import os
import asyncio
import discord
from discord.ext import commands, voice_recv
from pathlib import Path
import logging

# Carrega variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

# Importa EVE, TTS e STT
from core.eve import Eve
from voice.text_to_speech import TextToSpeech

# Importa FastTTS otimizado (mais rapido)
try:
    from voice.fast_tts import DiscordFastTTS, get_discord_tts
    FAST_TTS_AVAILABLE = True
except ImportError:
    FAST_TTS_AVAILABLE = False
    print("⚠️ FastTTS não disponível - usando TTS padrão")

# Importa sistema de escuta de voz
try:
    from voice import (
        listen_from_discord,
        stop_listening,
        pause_listening,
        resume_listening,
        VoiceInput,
        permission_manager
    )
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False
    logger = logging.getLogger("eve_discord")
    logger.warning("⚠️ Sistema STT não disponível")

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eve_discord")

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = "!"

if not TOKEN:
    print("❌ ERRO: Token do Discord não encontrado!")
    print("\nCrie um arquivo .env com:")
    print("DISCORD_BOT_TOKEN=seu_token_aqui")
    exit(1)

# ═══════════════════════════════════════════════════════════════════
# BOT
# ═══════════════════════════════════════════════════════════════════

# Intents necessários para voz
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True  # Necessário para identificar usuários em voice

# Cria bot
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Inicializa EVE e TTS
eve = None
tts = None

# Controle de escuta
listening_active = False

# Flag para evitar que EVE ouça ela mesma durante TTS
eve_is_speaking = False

# Pasta para áudios
AUDIO_DIR = Path("discord_audios")
AUDIO_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# EVENTOS
# ═══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    """Evento quando bot fica online."""
    global eve, tts

    print()
    print("=" * 60)
    print("EVE DISCORD BOT - INICIADO")
    print("=" * 60)
    print(f"✅ Logado como: {bot.user.name}")
    print(f"✅ ID: {bot.user.id}")
    print(f"✅ Servidores: {len(bot.guilds)}")
    print()

    # on_ready dispara de novo em reconexões — não recarrega EVE/TTS
    if eve is not None:
        print("♻️ Reconectado - EVE já carregada")
        return

    # Carrega EVE fora do event loop (a inicialização é pesada)
    print("Carregando EVE...")
    eve = await asyncio.to_thread(Eve)
    print("✅ EVE carregada!")

    # Configura TTS com Francisca
    print("Configurando voz (Francisca)...")
    if FAST_TTS_AVAILABLE:
        # Usar FastTTS otimizado (velocidade normal, com cache para respostas rapidas)
        tts = get_discord_tts(rate="+0%", voice="pt-BR-FranciscaNeural")
        print("✅ FastTTS configurado (cache ativo, velocidade normal)")
    else:
        # Fallback para TTS padrao
        tts = TextToSpeech(engine="edge", voice_model="pt-BR-FranciscaNeural")
        print("✅ Voz configurada (TTS padrão)")

    # Sistema de voz pronto
    print()
    print("✅ Sistema de voz pronto!")
    print("💡 Use !join para conectar ao canal de voz")
    print("💡 Use !listen para ativar STT (Speech-to-Text)")

    print()
    print("Comandos disponíveis:")
    print("  !eve <pergunta>    - Perguntar algo")
    print("  !falar <texto>     - EVE fala algo")
    print("  !join              - Entrar no canal de voz")
    print("  !leave             - Sair do canal")
    print("  !listen            - EVE começa a ouvir (STT)")
    print("  !memoria           - Ver/limpar o que EVE lembra")
    print("  !status            - Status dos sistemas")
    print("  !help              - Ajuda")
    print()
    print("=" * 60)
    print()


# ═══════════════════════════════════════════════════════════════════
# COMANDOS DE TEXTO
# ═══════════════════════════════════════════════════════════════════

@bot.command(name="eve", help="Perguntar algo para a EVE")
async def perguntar_eve(ctx, *, pergunta: str):
    """Comando para perguntar algo à EVE."""
    if not eve:
        await ctx.send("❌ EVE ainda não está pronta!")
        return

    # Auto-join: Se usuário está em canal e bot não está, entra automaticamente
    if ctx.author.voice and not ctx.voice_client:
        channel = ctx.author.voice.channel
        try:
            await channel.connect(cls=voice_recv.VoiceRecvClient)
            await ctx.send(f"🎤 Entrei no canal: {channel.name}")
            logger.info(f"Auto-join no canal: {channel.name}")
        except Exception as e:
            logger.error(f"Erro ao entrar automaticamente: {e}")

    # Mostra que está processando
    async with ctx.typing():
        # Processa com EVE em thread separada — chamada síncrona aqui
        # bloquearia o event loop inteiro (heartbeat, voz, outros comandos)
        logger.info(f"Pergunta de {ctx.author}: {pergunta}")

        # Atribui quem está falando: num servidor várias pessoas conversam
        # com a EVE e o histórico é compartilhado — sem isso ela mistura
        # as pessoas ("meu nome é X" de um vira nome de todos)
        prompt = f"[{ctx.author.display_name} diz]: {pergunta}"

        resposta = await asyncio.to_thread(eve.generate_response, prompt)
        texto = resposta.get('text', '')

        if not texto:
            await ctx.send("❌ Desculpe, não consegui processar sua pergunta.")
            return

        # Envia resposta no chat
        # Discord tem limite de 2000 caracteres
        prefixo = "🤖 **EVE:** "
        if len(prefixo) + len(texto) > 2000:
            # Divide em partes (a primeira leva o prefixo)
            tamanho = 2000 - len(prefixo)
            partes = [texto[i:i+tamanho] for i in range(0, len(texto), tamanho)]
            for i, parte in enumerate(partes):
                await ctx.send(f"{prefixo}{parte}" if i == 0 else parte)
        else:
            await ctx.send(f"{prefixo}{texto}")

        # Gera áudio se tiver em canal de voz
        if ctx.voice_client:
            await gerar_e_falar(ctx, texto)


@bot.command(name="memoria", help="Mostra o que EVE lembra (!memoria limpar para apagar)")
async def memoria(ctx, acao: str = None):
    """Mostra ou limpa a memória da EVE."""
    if not eve:
        await ctx.send("❌ EVE ainda não está pronta!")
        return

    if acao and acao.lower() in ("limpar", "clear", "apagar"):
        if eve.layered_memory:
            eve.layered_memory.clear_all()
        if eve.memory:
            eve.memory.clear_memory()
        eve.clear_conversation_history()
        await ctx.send("🧹 Memória limpa! Começando do zero.")
        logger.info(f"Memória limpa por {ctx.author}")
        return

    linhas = ["🧠 **O que eu lembro:**"]
    if eve.layered_memory:
        stats = eve.layered_memory.get_stats()
        linhas.append(f"- {stats['long_term_count']} fatos de longo prazo")
        linhas.append(f"- {stats['preferences_count']} preferências")
        linhas.append(f"- {stats['short_term_count']} mensagens recentes na sessão")

        facts = eve.layered_memory.get_important_facts(top_k=5)
        if facts:
            linhas.append("\n**Fatos mais importantes:**")
            for f in facts:
                linhas.append(f"• {f.content[:100]} _({f.category})_")
    else:
        linhas.append("- (memória em camadas desativada)")

    linhas.append("\nUse `!memoria limpar` para apagar tudo.")
    await ctx.send("\n".join(linhas)[:2000])


@bot.command(name="status", help="Mostra status dos sistemas da EVE")
async def status(ctx):
    """Mostra o status dos componentes da EVE."""
    if not eve:
        await ctx.send("❌ EVE ainda não está pronta!")
        return

    stats = await asyncio.to_thread(eve.get_stats)
    groq_ok = "✅" if stats.get("groq_available") else "❌"
    web_ok = "✅" if stats.get("web_search_available") else "❌"
    brain_ok = "✅" if stats.get("brain_v2_available") else "❌"
    msgs = stats.get("conversation_messages", 0)
    ouvindo = "🎧 sim" if listening_active else "🔇 não"
    em_voz = "🔊 sim" if bot.voice_clients else "❌ não"

    await ctx.send(
        "⚙️ **Status da EVE**\n"
        f"- Groq (nuvem): {groq_ok}\n"
        f"- Busca web: {web_ok}\n"
        f"- Brain V2: {brain_ok}\n"
        f"- Mensagens na sessão: {msgs}\n"
        f"- Em canal de voz: {em_voz}\n"
        f"- Escutando voz: {ouvindo}"
    )


@bot.command(name="falar", help="EVE fala um texto")
async def falar(ctx, *, texto: str):
    """Comando para EVE falar algo."""
    # Verifica se bot está em canal de voz
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("❌ Use !join primeiro para eu entrar no canal de voz!")
        return

    await ctx.send(f"🔊 Falando: {texto[:50]}...")
    logger.info(f"Comando !falar: {texto[:100]}")

    try:
        await gerar_e_falar(ctx, texto)
        await ctx.send("✅ Áudio reproduzido!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao falar: {e}")
        logger.error(f"Erro no comando falar: {e}")


# ═══════════════════════════════════════════════════════════════════
# COMANDOS DE VOZ
# ═══════════════════════════════════════════════════════════════════

@bot.command(name="join", help="EVE entra no canal de voz")
async def join(ctx):
    """Comando para entrar no canal de voz usando VoiceRecvClient."""
    # Verifica se usuário está em canal
    if not ctx.author.voice:
        await ctx.send("❌ Você precisa estar em um canal de voz!")
        return

    channel = ctx.author.voice.channel

    try:
        # Desconecta primeiro se já estiver conectado
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(0.5)

        # Conecta ao canal usando VoiceRecvClient (discord-ext-voice-recv)
        voice_client = await channel.connect(
            cls=voice_recv.VoiceRecvClient,
            timeout=10.0,
            reconnect=True
        )

        await ctx.send(f"✅ Conectado ao canal: {channel.name}")
        logger.info(f"✅ Conectado com sucesso ao canal: {channel.name} (VoiceRecvClient)")

    except discord.errors.ClientException as e:
        logger.error(f"ClientException ao conectar: {e}")
        await ctx.send("❌ Erro: Já estou conectado em outro lugar. Use !leave primeiro.")

    except asyncio.TimeoutError:
        logger.error("Timeout ao conectar ao canal de voz")
        await ctx.send("❌ Timeout ao conectar. Tente novamente em alguns segundos.")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao conectar: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Erro ao conectar: {error_msg}")


@bot.command(name="leave", help="EVE sai do canal de voz")
async def leave(ctx):
    """Comando para sair do canal de voz."""
    global listening_active

    # Para escuta se estiver ativa
    if listening_active and STT_AVAILABLE:
        await stop_listening()
        listening_active = False

    if not ctx.voice_client:
        await ctx.send("❌ Não estou em nenhum canal de voz!")
        return

    await ctx.voice_client.disconnect()
    await ctx.send("👋 Saindo do canal de voz...")
    logger.info("Desconectado do canal de voz")


@bot.command(name="listen", help="EVE começa a ouvir o canal de voz")
async def start_listen(ctx):
    """Inicia escuta de voz no canal."""
    global listening_active

    if not STT_AVAILABLE:
        await ctx.send("❌ Sistema de escuta não está disponível! Instale: pip install faster-whisper")
        return

    # Verifica se já está escutando
    if listening_active:
        await ctx.send("⚠️ Já estou escutando o canal!")
        return

    # Verifica se está em canal de voz
    if not ctx.voice_client:
        # Tenta entrar no canal do usuário
        if not ctx.author.voice:
            await ctx.send("❌ Entre em um canal de voz primeiro, ou use !join")
            return

        channel = ctx.author.voice.channel
        await channel.connect(cls=voice_recv.VoiceRecvClient)
        await ctx.send(f"✅ Conectado ao canal: {channel.name}")

        # Aguarda conexão estar completa
        await asyncio.sleep(1)

    # Verifica se conexão está ativa
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("❌ Erro: não consegui conectar ao canal de voz!")
        return

    try:
        # Inicia escuta
        await ctx.send("🎧 Iniciando sistema de escuta... (isso pode levar alguns segundos)")

        # IMPORTANTE: Truque do silêncio - Discord não envia áudio se o bot não enviar nada
        # Tocamos um frame de silêncio para "acordar" a conexão UDP bidirecional
        try:
            # Gera um frame de silêncio PCM (20ms de áudio a 48kHz, estéreo, 16-bit)
            silence_frame = b'\x00' * (48000 * 2 * 2 // 50)  # 20ms de silêncio

            class SilenceSource(discord.AudioSource):
                def __init__(self):
                    self.played = False

                def read(self):
                    if not self.played:
                        self.played = True
                        return silence_frame
                    return b''

                def is_opus(self):
                    return False

            # Toca silêncio brevemente para ativar conexão
            ctx.voice_client.play(SilenceSource())
            await asyncio.sleep(0.5)  # Espera o silêncio ser enviado
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            logger.info("✅ Truque do silêncio aplicado - conexão UDP ativada")
        except Exception as e:
            logger.warning(f"Não foi possível aplicar truque do silêncio: {e}")

        await listen_from_discord(
            ctx.voice_client,
            on_transcription=on_user_spoke,
            model_size="medium"  # Bom equilíbrio entre precisão e velocidade
        )

        listening_active = True

        await ctx.send(
            "✅ **Sistema de escuta ativado!**\n"
            "🎤 Agora posso ouvir e transcrever o que você fala.\n"
            "💬 Suas falas serão processadas automaticamente.\n"
            "⏹️ Use `!stop_listen` para parar."
        )

        logger.info("✅ Sistema de escuta ativado")

    except Exception as e:
        logger.error(f"Erro ao iniciar escuta: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Erro ao iniciar escuta: {e}")


@bot.command(name="stop_listen", help="EVE para de ouvir o canal de voz")
async def stop_listen_cmd(ctx):
    """Para a escuta de voz."""
    global listening_active

    if not STT_AVAILABLE:
        await ctx.send("❌ Sistema de escuta não disponível!")
        return

    if not listening_active:
        await ctx.send("⚠️ Não estou escutando no momento!")
        return

    try:
        await stop_listening()
        listening_active = False

        await ctx.send("⏹️ Sistema de escuta desativado.")
        logger.info("Sistema de escuta desativado")

    except Exception as e:
        logger.error(f"Erro ao parar escuta: {e}")
        await ctx.send(f"❌ Erro ao parar escuta: {e}")


# ═══════════════════════════════════════════════════════════════════
# CALLBACK DE VOZ
# ═══════════════════════════════════════════════════════════════════

async def on_user_spoke(voice_input: VoiceInput):
    """
    Callback chamado quando um usuário fala no canal de voz.

    Args:
        voice_input: Dados da entrada de voz
    """
    global eve_is_speaking

    if not eve:
        return

    # Ignora se EVE está processando/falando
    if eve_is_speaking:
        logger.debug(f"Ignorando entrada - EVE está processando/falando")
        return

    try:
        # IMPORTANTE: Marca que EVE está ocupada ANTES de processar
        # Isso evita que novas entradas sejam processadas enquanto gera resposta
        eve_is_speaking = True
        if STT_AVAILABLE:
            pause_listening()

        # Log da entrada
        creator_tag = " [CREATOR]" if voice_input.is_creator else ""
        admin_tag = " [ADMIN]" if voice_input.is_admin else ""
        logger.info(f"🎤 {voice_input.username}{creator_tag}{admin_tag}: {voice_input.text}")

        # Processa com EVE em thread separada (não bloqueia o event loop,
        # que precisa continuar cuidando do áudio e do heartbeat)
        # Atribui quem falou para a EVE não misturar as pessoas do canal
        prompt = f"[{voice_input.username} diz]: {voice_input.text}"
        response = await asyncio.to_thread(eve.generate_response, prompt)
        response_text = response.get('text', '')

        if not response_text:
            # Se não há resposta, libera escuta
            eve_is_speaking = False
            if STT_AVAILABLE:
                resume_listening()
            return

        logger.info(f"🤖 EVE: {response_text[:100]}...")

        # Encontra canal de voz para responder
        voice_client = None
        for vc in bot.voice_clients:
            if vc.is_connected():
                voice_client = vc
                break

        if not voice_client:
            logger.warning("Não há cliente de voz conectado para responder")
            eve_is_speaking = False
            if STT_AVAILABLE:
                resume_listening()
            return

        # Fala a resposta (a função gerencia o resume_listening quando terminar)
        await gerar_e_falar_voice_client(voice_client, response_text)

    except Exception as e:
        # Em caso de erro, libera escuta
        eve_is_speaking = False
        if STT_AVAILABLE:
            resume_listening()
        logger.error(f"Erro ao processar voz: {e}")
        import traceback
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════

async def gerar_e_falar(ctx, texto: str):
    """
    Gera áudio com TTS e reproduz no Discord.

    Args:
        ctx: Contexto do comando
        texto: Texto para falar
    """
    if not ctx.voice_client:
        await ctx.send("❌ Não estou em um canal de voz!")
        return

    await gerar_e_falar_voice_client(ctx.voice_client, texto)


async def gerar_e_falar_voice_client(voice_client, texto: str):
    """
    Gera áudio com TTS e reproduz no Discord usando voice_client diretamente.

    Args:
        voice_client: Cliente de voz do Discord
        texto: Texto para falar
    """
    global eve_is_speaking

    if not tts:
        logger.error("❌ TTS não está configurado!")
        raise Exception("TTS não configurado")

    if not voice_client or not voice_client.is_connected():
        logger.error("❌ Voice client não conectado!")
        raise Exception("Voice client não conectado")

    try:
        # Nota: eve_is_speaking e pause_listening já foram chamados
        # em on_user_spoke, então não precisamos chamar novamente aqui.
        # Apenas garantimos que está True para chamadas diretas (ex: !falar)
        if not eve_is_speaking:
            eve_is_speaking = True
            if STT_AVAILABLE:
                pause_listening()

        # Gera áudio MP3
        audio_file = AUDIO_DIR / "temp_discord.mp3"
        logger.info(f"🎵 Gerando áudio: {texto[:50]}...")

        # Sintetiza com TTS (FastTTS e async, TTS padrao e sync)
        if FAST_TTS_AVAILABLE and hasattr(tts, 'speak'):
            # FastTTS - metodo async direto
            audio_file = await tts.speak(texto)
        else:
            # TTS padrao - roda em thread
            await asyncio.to_thread(tts.synthesize, texto, save_to=audio_file, play=False)

        # Verifica se arquivo foi criado
        if not audio_file.exists():
            logger.error("❌ Arquivo de áudio não foi criado!")
            eve_is_speaking = False
            if STT_AVAILABLE:
                resume_listening()
            raise Exception("Arquivo de áudio não criado")

        logger.info(f"✅ Áudio gerado: {audio_file} ({audio_file.stat().st_size} bytes)")

        # Para o áudio atual se estiver tocando
        if voice_client.is_playing():
            logger.info("⏹️ Parando áudio anterior...")
            voice_client.stop()
            await asyncio.sleep(0.5)

        # Event para saber quando terminou
        audio_finished = asyncio.Event()

        # Toca áudio com callback para saber quando terminou
        def after_play(error):
            global eve_is_speaking
            if error:
                logger.error(f"❌ Erro durante reprodução: {error}")
            else:
                logger.info("✅ Áudio reproduzido completamente")
            # Marca que EVE parou de falar
            eve_is_speaking = False
            # Retoma escuta
            if STT_AVAILABLE:
                resume_listening()
            # Sinaliza que terminou
            asyncio.run_coroutine_threadsafe(
                _set_event(audio_finished),
                bot.loop
            )

        logger.info("▶️ Reproduzindo áudio no Discord...")
        source = discord.FFmpegPCMAudio(str(audio_file))
        voice_client.play(source, after=after_play)

        # Aguarda o áudio terminar completamente
        await audio_finished.wait()

        # Pequena pausa extra para garantir que o buffer de áudio foi limpo
        await asyncio.sleep(0.5)

        logger.info("🔊 Áudio finalizado, escuta ativa novamente")

    except Exception as e:
        # Garante que a flag seja resetada em caso de erro
        eve_is_speaking = False
        # Retoma escuta
        if STT_AVAILABLE:
            resume_listening()
        logger.error(f"❌ Erro ao gerar/reproduzir áudio: {e}")
        import traceback
        traceback.print_exc()
        raise


async def _set_event(event: asyncio.Event):
    """Helper para setar evento de forma thread-safe."""
    event.set()


# ═══════════════════════════════════════════════════════════════════
# TRATAMENTO DE ERROS
# ═══════════════════════════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    """Trata erros de comandos."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argumento faltando! Use: `{PREFIX}help {ctx.command}`")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Comando não encontrado! Use `{PREFIX}help` para ver comandos.")
    else:
        logger.error(f"Erro no comando {ctx.command}: {error}")
        await ctx.send(f"❌ Erro: {error}")


# ═══════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Iniciando EVE Discord Bot...")
    print("Pressione Ctrl+C para parar")
    print()

    try:
        # bot.run() captura o Ctrl+C internamente e retorna após o cleanup,
        # então o shutdown da EVE fica no finally (sempre executa)
        bot.run(TOKEN)
    except Exception as e:
        print(f"\n❌ Erro ao iniciar bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n\n👋 Encerrando bot...")
        if eve:
            eve.shutdown()
            print("✅ Memória e estado da EVE salvos.")
