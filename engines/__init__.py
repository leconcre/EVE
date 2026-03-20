# engines/__init__.py
"""
EVE AI Engines Package
Backends de IA disponíveis: Ollama (local) e Groq (cloud)
"""

from .groq_engine import GroqEngine
from .ollama_engine import OllamaEngine

__all__ = ['GroqEngine', 'OllamaEngine']