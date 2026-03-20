# voice/__init__.py - API PRINCIPAL DO MÓDULO DE VOZ
"""
Módulo de voz da EVE - Speech-to-Text e Text-to-Speech.

Uso simples:
    from voice import listen, speak

    # Ouvir
    text = listen()
    print(f"Você disse: {text}")

    # Falar
    speak("Olá! Eu sou a EVE.")

Uso avançado:
    from voice import VoiceListener, SpeechToText, TextToSpeech

    # Captura personalizada
    listener = VoiceListener()
    audio = listener.listen_once()

    # Transcrição
    stt = SpeechToText()
    result = stt.transcribe(audio)

    # Síntese
    tts = TextToSpeech(engine="piper")
    tts.synthesize("Olá!", play=True)

Integração com Discord:
    from voice import create_voice_bot

    bot = create_voice_bot()
    bot.run()
"""

__version__ = "1.0.0"
__author__ = "EVE AI Team"

import logging
from pathlib import Path
from typing import Optional, Callable

# Configura logging
logger = logging.getLogger("eve.voice")
logger.setLevel(logging.INFO)

# ═══════════════════════════════════════════════════════════════════
# IMPORTA COMPONENTES PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════

from . import config

# Classes principais
from .listener import VoiceListener, list_microphones, record_audio
from .speech_to_text import SpeechToText, transcribe as _transcribe
from .text_to_speech import TextToSpeech, speak as _speak

# Utilitários
from .audio_utils import (
    VoiceActivityDetector,
    normalize_audio,
    reduce_noise,
    trim_silence,
    save_audio,
    load_audio
)

# Discord (importação condicional)
try:
    from .discord_voice import DiscordVoiceBot, create_voice_bot
    DISCORD_AVAILABLE = True
except (ImportError, AttributeError) as e:
    DISCORD_AVAILABLE = False
    logger.warning("⚠️ Integração com Discord não disponível (use eve_discord_bot.py diretamente)")

# Discord STT - Sistema de escuta de voz
try:
    from .discord_integration import (
        listen_from_discord,
        stop_listening,
        pause_listening,
        resume_listening,
        get_active_listener,
        is_creator_speaking,
        is_admin_speaking,
        has_role
    )
    from .stt.models import VoiceInput
    from .stt.discord_listener import DiscordVoiceListener
    from .permissions import permission_manager
    DISCORD_STT_AVAILABLE = True
except (ImportError, AttributeError) as e:
    DISCORD_STT_AVAILABLE = False
    logger.warning("⚠️ Discord STT não disponível (instale discord.py e faster-whisper)")

# FastTTS - TTS otimizado para baixa latencia
try:
    from .fast_tts import FastTTS, DiscordFastTTS, get_fast_tts, get_discord_tts
    FAST_TTS_AVAILABLE = True
except ImportError:
    FAST_TTS_AVAILABLE = False
    logger.warning("⚠️ FastTTS não disponível")

# ═══════════════════════════════════════════════════════════════════
# API SIMPLIFICADA
# ═══════════════════════════════════════════════════════════════════

# Instâncias globais (lazy loading)
_listener_instance: Optional[VoiceListener] = None
_stt_instance: Optional[SpeechToText] = None
_tts_instance: Optional[TextToSpeech] = None


def listen(
    timeout: Optional[float] = None,
    save_to: Optional[Path] = None,
    return_audio: bool = False
) -> Optional[str]:
    """
    Ouve o microfone e retorna o texto transcrito.

    Esta é a função mais simples para capturar voz:
    - Detecta automaticamente quando você começa a falar
    - Para de gravar quando detecta silêncio
    - Transcreve e retorna o texto

    Args:
        timeout: Tempo máximo de espera (None = infinito)
        save_to: Salvar áudio gravado (opcional)
        return_audio: Se True, retorna tupla (text, audio)

    Returns:
        Texto transcrito ou None se timeout/erro
        Se return_audio=True, retorna (text, audio)

    Exemplo:
        >>> text = listen()
        >>> print(f"Você disse: {text}")
    """
    global _listener_instance, _stt_instance

    # Inicializa componentes se necessário
    if _listener_instance is None:
        _listener_instance = VoiceListener()

    if _stt_instance is None:
        _stt_instance = SpeechToText()

    # Captura áudio
    logger.info("🎙️ Aguardando fala...")
    audio = _listener_instance.listen_once(timeout=timeout, save_to=save_to)

    if audio is None:
        return None

    # Transcreve
    logger.info("🔄 Transcrevendo...")
    result = _stt_instance.transcribe(audio)
    text = result.get("text", "").strip()

    if text:
        logger.info(f"✅ Transcrição: {text}")
    else:
        logger.warning("⚠️ Nenhum texto detectado")

    if return_audio:
        return (text, audio)
    return text


def speak(
    text: str,
    engine: str = "edge",
    play: bool = True,
    save_to: Optional[Path] = None,
    rate: float = 1.0,
    volume: float = 1.0
):
    """
    Fala um texto usando TTS.

    Esta é a função mais simples para síntese de voz:
    - Gera áudio a partir do texto
    - Reproduz automaticamente (se play=True)

    Args:
        text: Texto para falar
        engine: Engine de TTS ("piper", "coqui", "gtts", "pyttsx3")
        play: Se deve reproduzir o áudio
        save_to: Salvar áudio gerado (opcional)
        rate: Taxa de fala (0.5 = metade, 2.0 = dobro)
        volume: Volume (0.0-1.0)

    Exemplo:
        >>> speak("Olá! Eu sou a EVE.")
        >>> speak("Teste", engine="pyttsx3", rate=1.5)
    """
    global _tts_instance

    # Recria instância se engine mudou
    if _tts_instance is None or _tts_instance.engine_name != engine:
        _tts_instance = TextToSpeech(engine=engine, rate=rate, volume=volume)

    # Sintetiza
    logger.info(f"🔊 Falando: {text[:50]}...")
    _tts_instance.synthesize(text, save_to=save_to, play=play)


def cleanup():
    """
    Libera recursos do módulo de voz.

    Deve ser chamado ao finalizar o programa.
    """
    global _listener_instance

    if _listener_instance is not None:
        _listener_instance.cleanup()
        _listener_instance = None

    logger.info("✅ Recursos de voz liberados")


# ═══════════════════════════════════════════════════════════════════
# INTEGRAÇÃO RÁPIDA COM EVE
# ═══════════════════════════════════════════════════════════════════

def create_voice_loop(eve_instance, engine: str = "piper"):
    """
    Cria um loop de voz simples com a EVE.

    Uso:
        from core.eve import Eve
        from voice import create_voice_loop

        eve = Eve()
        create_voice_loop(eve)

    Args:
        eve_instance: Instância da EVE
        engine: Engine de TTS

    Isso criará um loop infinito:
    1. Ouve sua voz
    2. Processa com EVE
    3. Responde falando
    """
    logger.info("🎙️ Iniciando loop de voz com EVE...")
    logger.info("Pressione Ctrl+C para parar")

    try:
        while True:
            # Ouve
            text = listen()

            if text:
                print(f"\n👤 Você: {text}")

                # Processa com EVE
                response = eve_instance.generate_response(text)
                response_text = response.get("text", "")

                if response_text:
                    print(f"🤖 EVE: {response_text}\n")

                    # Fala
                    speak(response_text, engine=engine)
            else:
                logger.warning("Nenhum texto capturado, tentando novamente...")

    except KeyboardInterrupt:
        logger.info("\n👋 Encerrando loop de voz...")
    finally:
        cleanup()


# ═══════════════════════════════════════════════════════════════════
# EXPORTA API PÚBLICA
# ═══════════════════════════════════════════════════════════════════

__all__ = [
    # Funções simples
    "listen",
    "speak",
    "cleanup",
    "create_voice_loop",

    # Classes principais
    "VoiceListener",
    "SpeechToText",
    "TextToSpeech",
    "VoiceActivityDetector",

    # Utilitários
    "list_microphones",
    "record_audio",
    "normalize_audio",
    "reduce_noise",
    "trim_silence",
    "save_audio",
    "load_audio",

    # Configuração
    "config",

    # Discord (se disponível)
    "DiscordVoiceBot" if DISCORD_AVAILABLE else None,
    "create_voice_bot" if DISCORD_AVAILABLE else None,

    # Discord STT (se disponível)
    "listen_from_discord" if DISCORD_STT_AVAILABLE else None,
    "stop_listening" if DISCORD_STT_AVAILABLE else None,
    "pause_listening" if DISCORD_STT_AVAILABLE else None,
    "resume_listening" if DISCORD_STT_AVAILABLE else None,
    "get_active_listener" if DISCORD_STT_AVAILABLE else None,
    "is_creator_speaking" if DISCORD_STT_AVAILABLE else None,
    "is_admin_speaking" if DISCORD_STT_AVAILABLE else None,
    "has_role" if DISCORD_STT_AVAILABLE else None,
    "VoiceInput" if DISCORD_STT_AVAILABLE else None,
    "DiscordVoiceListener" if DISCORD_STT_AVAILABLE else None,
    "permission_manager" if DISCORD_STT_AVAILABLE else None,

    # FastTTS (se disponível)
    "FastTTS" if FAST_TTS_AVAILABLE else None,
    "DiscordFastTTS" if FAST_TTS_AVAILABLE else None,
    "get_fast_tts" if FAST_TTS_AVAILABLE else None,
    "get_discord_tts" if FAST_TTS_AVAILABLE else None,
]

# Remove None da lista
__all__ = [item for item in __all__ if item is not None]


# ═══════════════════════════════════════════════════════════════════
# INFORMAÇÕES DO MÓDULO
# ═══════════════════════════════════════════════════════════════════

def get_info():
    """Retorna informações sobre o módulo de voz."""
    info = {
        "version": __version__,
        "components": {
            "listener": _listener_instance is not None,
            "stt": _stt_instance is not None,
            "tts": _tts_instance is not None,
        },
        "discord_available": DISCORD_AVAILABLE,
        "config": {
            "whisper_model": config.WHISPER_MODEL,
            "sample_rate": config.SAMPLE_RATE,
            "language": config.WHISPER_LANGUAGE,
        }
    }

    if _stt_instance:
        info["stt_info"] = _stt_instance.get_model_info()

    if _tts_instance:
        info["tts_info"] = _tts_instance.get_engine_info()

    return info


# ═══════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════

logger.info(f"📦 Módulo de voz EVE v{__version__} carregado")
logger.info(f"   Sample rate: {config.SAMPLE_RATE}Hz")
logger.info(f"   Whisper model: {config.WHISPER_MODEL}")
logger.info(f"   Discord: {'✅ Disponível' if DISCORD_AVAILABLE else '❌ Não disponível'}")
logger.info(f"   Discord STT: {'✅ Disponível' if DISCORD_STT_AVAILABLE else '❌ Não disponível'}")
logger.info(f"   FastTTS: {'✅ Disponível' if FAST_TTS_AVAILABLE else '❌ Não disponível'}")
