# skills/builtin/__init__.py
"""
Skills built-in da EVE.
"""

from typing import List, Type
from ..base import Skill

# Importar skills
from .file_operations import FileOperationsSkill
from .log_analyzer import LogAnalyzerSkill
from .code_generator import CodeGeneratorSkill
from .text_summarizer import TextSummarizerSkill
from .calculator import CalculatorSkill
from .datetime_skill import DateTimeSkill


def get_builtin_skills() -> List[Type[Skill]]:
    """Retorna lista de classes de skills builtin"""
    return [
        FileOperationsSkill,
        LogAnalyzerSkill,
        CodeGeneratorSkill,
        TextSummarizerSkill,
        CalculatorSkill,
        DateTimeSkill,
    ]


__all__ = [
    'get_builtin_skills',
    'FileOperationsSkill',
    'LogAnalyzerSkill',
    'CodeGeneratorSkill',
    'TextSummarizerSkill',
    'CalculatorSkill',
    'DateTimeSkill',
]
