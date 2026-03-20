# skills/__init__.py
"""
Sistema de Skills da EVE.
Skills são capacidades modulares que podem resolver tarefas com ou sem modelo.
"""

from .base import (
    Skill,
    SkillType,
    SkillTrigger,
    SkillResult,
    SkillPriority
)

from .registry import SkillRegistry

__all__ = [
    'Skill',
    'SkillType',
    'SkillTrigger',
    'SkillResult',
    'SkillPriority',
    'SkillRegistry'
]
