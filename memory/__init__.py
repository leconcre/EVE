# memory/__init__.py
"""
Sistema de memória em camadas da EVE.
Gerencia short-term, long-term, resumos e preferências.
"""

from .layered_memory import (
    LayeredMemory,
    MemoryEntry,
    UserPreference
)

from .cleaner import (
    MemoryCleaner,
    CleanerConfig
)

from .summarizer import (
    HeuristicSummarizer,
    ConversationSummary
)

__all__ = [
    'LayeredMemory',
    'MemoryEntry',
    'UserPreference',
    'MemoryCleaner',
    'CleanerConfig',
    'HeuristicSummarizer',
    'ConversationSummary'
]
