"""
voice/stt/models.py - Estruturas de Dados para STT

Define VoiceInput e outras estruturas relacionadas.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class VoiceInput:
    """
    Entrada de voz capturada do Discord.

    Attributes:
        user_id: ID do usuário Discord
        username: Nome de exibição do usuário
        text: Texto transcrito da fala
        confidence: Confiança da transcrição (0.0 a 1.0)
        timestamp: Momento da captura
        is_creator: Se o usuário é o criador do bot
        is_admin: Se o usuário é admin do servidor
        roles: Lista de roles do usuário
        audio_duration: Duração do áudio em segundos
        language: Idioma detectado
    """
    user_id: int
    username: str
    text: str
    confidence: float = 0.0
    timestamp: datetime = None
    is_creator: bool = False
    is_admin: bool = False
    roles: List[str] = None
    audio_duration: float = 0.0
    language: str = "pt"

    def __post_init__(self):
        """Inicializa campos padrão."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.roles is None:
            self.roles = []

    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "text": self.text,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "is_creator": self.is_creator,
            "is_admin": self.is_admin,
            "roles": self.roles,
            "audio_duration": self.audio_duration,
            "language": self.language
        }

    def __str__(self) -> str:
        """Representação em string."""
        creator_tag = " [CREATOR]" if self.is_creator else ""
        admin_tag = " [ADMIN]" if self.is_admin else ""
        return f"[{self.username}{creator_tag}{admin_tag}]: {self.text}"


@dataclass
class AudioChunk:
    """
    Chunk de áudio capturado.

    Attributes:
        user_id: ID do usuário
        audio_data: Dados de áudio (bytes)
        timestamp: Momento da captura
        sample_rate: Taxa de amostragem
    """
    user_id: int
    audio_data: bytes
    timestamp: datetime = None
    sample_rate: int = 48000  # Discord usa 48kHz

    def __post_init__(self):
        """Inicializa timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
