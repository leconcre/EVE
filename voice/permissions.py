"""
voice/permissions.py - Sistema de Permissões para Discord

Rastreia criador e administradores do bot.
"""

from typing import Optional
import discord
from dataclasses import dataclass

# ID do criador (Leconcre)
CREATOR_ID = None  # Será definido dinamicamente no primeiro uso


@dataclass
class UserPermissions:
    """Permissões de um usuário."""
    user_id: int
    username: str
    is_creator: bool = False
    is_admin: bool = False
    is_moderator: bool = False


class PermissionManager:
    """Gerencia permissões de usuários no Discord."""

    def __init__(self, creator_username: str = "Leconcre"):
        """
        Inicializa gerenciador de permissões.

        Args:
            creator_username: Nome do usuário criador
        """
        self.creator_username = creator_username
        self._creator_id: Optional[int] = None

    def set_creator_id(self, user_id: int):
        """Define ID do criador."""
        global CREATOR_ID
        self._creator_id = user_id
        CREATOR_ID = user_id

    def get_permissions(self, member: discord.Member) -> UserPermissions:
        """
        Obtém permissões de um membro.

        Args:
            member: Membro do Discord

        Returns:
            UserPermissions com permissões do usuário
        """
        # Verifica se é o criador
        is_creator = False
        if self._creator_id is None:
            # Primeira vez: verifica pelo nome
            if member.name == self.creator_username or member.display_name == self.creator_username:
                self.set_creator_id(member.id)
                is_creator = True
        else:
            is_creator = member.id == self._creator_id

        # Verifica se é admin (permissão administrator ou owner)
        is_admin = member.guild_permissions.administrator or member.guild.owner_id == member.id

        # Verifica se é moderador (permissões de moderação)
        is_moderator = (
            member.guild_permissions.kick_members or
            member.guild_permissions.ban_members or
            member.guild_permissions.manage_messages
        )

        return UserPermissions(
            user_id=member.id,
            username=member.display_name or member.name,
            is_creator=is_creator,
            is_admin=is_admin,
            is_moderator=is_moderator
        )

    def is_creator(self, member: discord.Member) -> bool:
        """Verifica se membro é o criador."""
        perms = self.get_permissions(member)
        return perms.is_creator

    def is_admin(self, member: discord.Member) -> bool:
        """Verifica se membro é admin."""
        perms = self.get_permissions(member)
        return perms.is_admin or perms.is_creator

    def is_moderator(self, member: discord.Member) -> bool:
        """Verifica se membro é moderador."""
        perms = self.get_permissions(member)
        return perms.is_moderator or perms.is_admin or perms.is_creator


# Instância global
permission_manager = PermissionManager(creator_username="Leconcre")
