"""
voice/discord_integration.py - Integração Simplificada do Discord STT

Função principal para escutar usuários no Discord.
"""

from typing import Optional, Callable
import discord
from discord import VoiceClient
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .stt.discord_listener import DiscordVoiceListener
from .stt.transcriber import AudioTranscriber
from .stt.models import VoiceInput

logger = logging.getLogger("eve_discord.integration")

# Instância global do listener
_global_listener: Optional[DiscordVoiceListener] = None
_cached_transcriber: Optional[AudioTranscriber] = None

# Thread pool para carregar modelo sem bloquear
_executor = ThreadPoolExecutor(max_workers=1)


def _create_transcriber(model_size: str) -> AudioTranscriber:
    """Cria transcritor em thread separada (evita bloquear event loop)."""
    global _cached_transcriber
    if _cached_transcriber is None:
        logger.info(f"Carregando modelo Whisper '{model_size}' em background...")
        _cached_transcriber = AudioTranscriber(
            model_size=model_size,
            language="pt",
            device="cpu"
        )
    else:
        logger.info("Usando modelo Whisper em cache.")
    return _cached_transcriber


async def listen_from_discord(
    voice_client: VoiceClient,
    on_transcription: Callable[[VoiceInput], None],
    model_size: str = "small"
) -> DiscordVoiceListener:
    """
    Inicia escuta de voz no Discord.

    Captura áudio de usuários, identifica quem está falando e transcreve.

    Args:
        voice_client: Cliente de voz conectado ao canal
        on_transcription: Callback async(voice_input) chamado quando alguém fala
        model_size: Tamanho do modelo Whisper ("tiny", "small", "medium", "large-v3")

    Returns:
        DiscordVoiceListener configurado e em execução

    Example:
        ```python
        async def on_user_spoke(voice_input: VoiceInput):
            print(f"{voice_input.username}: {voice_input.text}")
            if voice_input.is_creator:
                print("  ^ Este é o criador!")

        # No comando do bot
        @bot.command()
        async def listen(ctx):
            if ctx.voice_client:
                listener = await listen_from_discord(
                    ctx.voice_client,
                    on_user_spoke
                )
                await ctx.send("✅ Escutando canal de voz!")
        ```
    """
    global _global_listener

    # Cria transcritor em thread separada (não bloqueia Discord heartbeat)
    loop = asyncio.get_running_loop()
    transcriber = await loop.run_in_executor(_executor, _create_transcriber, model_size)

    # Cria listener
    listener = DiscordVoiceListener(
        transcriber=transcriber,
        on_transcription=on_transcription
    )

    # Inicia escuta
    await listener.start_listening(voice_client)

    # Salva referência global
    _global_listener = listener

    return listener


async def stop_listening():
    """Para a escuta global."""
    global _global_listener
    if _global_listener:
        await _global_listener.stop_listening()
        _global_listener = None
        logger.info("Escuta interrompida")


def get_active_listener() -> Optional[DiscordVoiceListener]:
    """Retorna listener ativo, se houver."""
    return _global_listener


def pause_listening():
    """
    Pausa a escuta e limpa buffers.

    Usar antes de EVE falar para evitar que ela ouça ela mesma.
    """
    global _global_listener
    if _global_listener and _global_listener._sink:
        _global_listener._sink.pause()
        logger.debug("Escuta pausada e buffers limpos")


def resume_listening():
    """
    Retoma a escuta após EVE terminar de falar.
    """
    global _global_listener
    if _global_listener and _global_listener._sink:
        _global_listener._sink.resume()
        logger.debug("Escuta retomada")


# Funções auxiliares para verificar permissões em VoiceInput

def is_creator_speaking(voice_input: VoiceInput) -> bool:
    """Verifica se quem falou é o criador."""
    return voice_input.is_creator


def is_admin_speaking(voice_input: VoiceInput) -> bool:
    """Verifica se quem falou é admin."""
    return voice_input.is_admin or voice_input.is_creator


def has_role(voice_input: VoiceInput, role_name: str) -> bool:
    """Verifica se quem falou tem uma role específica."""
    return role_name in voice_input.roles
