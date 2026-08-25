# core/errors.py
"""
Exceções compartilhadas do motor EVE.
"""


class GenerationAborted(Exception):
    """
    Levantada pelo stream_callback para interromper uma geração em
    andamento (botão "parar" da interface). Os pontos de streaming
    (core/router.py e engines/groq_engine.py) re-lançam esta exceção
    em vez de engoli-la como fazem com erros comuns de callback.
    """
    pass
