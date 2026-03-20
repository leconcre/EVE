"""
voice/stt/user_tracker.py - Rastreamento de Usuários Discord

Mapeia user_id → Member para identificação de quem está falando.
"""

from typing import Dict, Optional
import discord
import logging

logger = logging.getLogger("eve_discord.user_tracker")


class UserTracker:
    """
    Rastreia usuários em canais de voz.

    Mantém mapeamento de user_id para discord.Member.
    """

    def __init__(self):
        """Inicializa rastreador."""
        self._users: Dict[int, discord.Member] = {}

    def add_user(self, member: discord.Member):
        """
        Adiciona usuário ao rastreamento.

        Args:
            member: Membro do Discord
        """
        self._users[member.id] = member
        logger.debug(f"Usuário adicionado: {member.display_name} (ID: {member.id})")

    def remove_user(self, user_id: int):
        """
        Remove usuário do rastreamento.

        Args:
            user_id: ID do usuário
        """
        if user_id in self._users:
            member = self._users[user_id]
            logger.debug(f"Usuário removido: {member.display_name} (ID: {user_id})")
            del self._users[user_id]

    def get_user(self, user_id: int) -> Optional[discord.Member]:
        """
        Obtém membro pelo ID.

        Args:
            user_id: ID do usuário

        Returns:
            discord.Member ou None se não encontrado
        """
        return self._users.get(user_id)

    def get_username(self, user_id: int) -> str:
        """
        Obtém nome do usuário.

        Args:
            user_id: ID do usuário

        Returns:
            Nome de exibição ou "Unknown User"
        """
        member = self.get_user(user_id)
        if member:
            return member.display_name or member.name
        return f"Unknown User ({user_id})"

    def clear(self):
        """Remove todos os usuários."""
        self._users.clear()
        logger.debug("Todos os usuários foram removidos")

    def get_all_users(self) -> Dict[int, discord.Member]:
        """Retorna todos os usuários rastreados."""
        return self._users.copy()

    def update_from_channel(self, channel: discord.VoiceChannel):
        """
        Atualiza rastreamento com todos os membros de um canal.

        Args:
            channel: Canal de voz
        """
        self.clear()
        for member in channel.members:
            if not member.bot:  # Ignora outros bots
                self.add_user(member)
        logger.info(f"Rastreando {len(self._users)} usuários no canal: {channel.name}")
