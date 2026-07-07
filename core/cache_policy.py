# core/cache_policy.py
"""
Política de cache de respostas.

Decide se um prompt é "independente de contexto" — ou seja, se a resposta
pode ser reaproveitada com segurança em outra conversa.

Evita o bug de respostas curtas como "sim", "continue" ou "e depois?"
serem cacheadas e reaparecerem fora de contexto.
"""

import re

# Prefixo de atribuição de falante usado pelo bot do Discord
# (ex.: "[Lucas diz]: oi") — removido antes de analisar o prompt
_SPEAKER_PREFIX = re.compile(r'^\[[^\]]{1,60}\]:?\s*')

# Saudações e perguntas fixas — sempre seguras para cache
GREETINGS = {
    "oi", "olá", "ola", "hi", "hello",
    "bom dia", "boa tarde", "boa noite",
    "tudo bem", "tudo bem?", "como vai", "como vai?",
    "quem é você", "quem é você?", "quem e voce", "quem e voce?",
    "o que você faz", "o que você faz?",
}

# Continuações e reações — dependem do contexto anterior, NUNCA cachear
CONTINUATIONS = {
    "sim", "não", "nao", "ok", "okay", "blz", "beleza", "claro", "isso",
    "exato", "entendi", "valeu", "obrigado", "obrigada", "legal", "massa",
    "show", "top", "continue", "continua", "mais", "e depois", "e depois?",
    "por que", "por quê", "por que?", "por quê?", "pq", "pq?",
    "como assim", "como assim?", "vai", "pode", "pode ser", "faz isso",
    "manda", "de novo", "denovo",
}

# Termos que indicam referência ao contexto da conversa atual
_CONTEXT_REFERENCES = (
    "isso", "aquilo", "esse", "essa", "nesse", "nessa", "desse", "dessa",
    "acima", "anterior", "você disse", "voce disse", "você falou",
    "voce falou", "o código", "o codigo", "sobre ele", "sobre ela",
)

# Inícios típicos de continuação de conversa
_CONTINUATION_STARTS = (
    "e ", "mas ", "então ", "entao ", "continue", "continua", "aí ", "ai ",
)


def is_cacheable_prompt(prompt: str) -> bool:
    """
    Retorna True se a resposta para este prompt puder ser cacheada
    e reutilizada com segurança fora do contexto da conversa atual.
    """
    if not prompt:
        return False

    normalized = " ".join(prompt.lower().split())
    normalized = _SPEAKER_PREFIX.sub('', normalized)

    if normalized in GREETINGS:
        return True

    if normalized in CONTINUATIONS:
        return False

    # Prompts muito curtos tendem a ser reações dependentes de contexto
    if len(normalized) < 15:
        return False

    if normalized.startswith(_CONTINUATION_STARTS):
        return False

    if any(ref in normalized for ref in _CONTEXT_REFERENCES):
        return False

    return True
