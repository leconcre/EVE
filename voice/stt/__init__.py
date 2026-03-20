"""
voice/stt/ - Speech-to-Text para Discord

Módulo completo para captura e transcrição de áudio do Discord.
"""

from .models import VoiceInput
from .discord_listener import DiscordVoiceListener

__all__ = ["VoiceInput", "DiscordVoiceListener"]
