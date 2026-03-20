# memory/cleaner.py
"""
Sistema de limpeza de memória.
Anti-lixo, deduplicação e eviction.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Set, Optional, Dict, Any, TYPE_CHECKING
import re
import unicodedata

if TYPE_CHECKING:
    from .layered_memory import MemoryEntry


@dataclass
class CleanerConfig:
    """Configuração do limpador de memória"""
    # Limites por categoria
    max_per_category: int = 50
    max_total: int = 200

    # TTL (dias)
    default_ttl_days: int = 30
    important_ttl_days: int = 90

    # Scores mínimos
    min_importance: float = 0.3
    min_length: int = 10
    max_length: int = 500

    # Dedupe
    similarity_threshold: float = 0.8

    # Blacklist
    enable_blacklist: bool = True


class MemoryCleaner:
    """
    Sistema de limpeza de memória.
    Anti-lixo + Dedupe + Eviction.
    """

    # =========================================================================
    # BLACKLIST - Padrões que NÃO devem ser salvos
    # =========================================================================

    BLACKLIST_PATTERNS = [
        # Respostas genéricas curtas
        r'^(sim|não|ok|certo|entendi|legal|beleza|blz)$',
        r'^(tá|ta|tudo bem|tranquilo|suave)$',

        # Saudações e despedidas
        r'^(obrigado|valeu|brigado|vlw|thanks).*$',
        r'^(oi|olá|opa|eai|fala|hey|hi).*$',
        r'^(tchau|bye|flw|até|adeus).*$',
        r'^(bom dia|boa tarde|boa noite)$',

        # Perguntas muito genéricas
        r'^o que.*\?$',
        r'^como.*\?$',
        r'^por que.*\?$',
        r'^quando.*\?$',

        # Padrões de estrutura pobre
        r'^(um|uma|o|a|os|as)\s+\w+$',     # Artigo + palavra única
        r'^\d+$',                            # Só números
        r'^https?://',                       # URLs
        r'^[^a-záéíóúãõâêîôûç]+$',           # Sem letras (só símbolos)

        # Respostas de confirmação
        r'^(pode ser|pode|vamos|bora|ok|s|n)$',
        r'^(sim|não|talvez|acho que sim|acho que não)$',

        # Mensagens de sistema
        r'^\[.*\]$',                         # [MODO CÓDIGO] etc
        r'^```',                             # Bloco de código sozinho
    ]

    # =========================================================================
    # STOPWORDS PT-BR para normalização
    # =========================================================================

    STOPWORDS = {
        # Artigos
        'a', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
        # Preposições
        'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'nas', 'nos',
        'para', 'pra', 'por', 'pela', 'pelo', 'pelas', 'pelos',
        'com', 'sem', 'sob', 'sobre', 'entre', 'até', 'desde',
        # Conjunções
        'e', 'ou', 'mas', 'porém', 'contudo', 'então', 'pois',
        'que', 'se', 'quando', 'como', 'porque', 'embora',
        # Pronomes
        'eu', 'tu', 'ele', 'ela', 'nós', 'vós', 'eles', 'elas',
        'me', 'te', 'se', 'nos', 'vos', 'lhe', 'lhes',
        'meu', 'minha', 'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas',
        'seu', 'sua', 'seus', 'suas', 'nosso', 'nossa', 'nossos', 'nossas',
        'este', 'esta', 'estes', 'estas', 'esse', 'essa', 'esses', 'essas',
        'aquele', 'aquela', 'aqueles', 'aquelas', 'isto', 'isso', 'aquilo',
        # Advérbios comuns
        'não', 'sim', 'muito', 'mais', 'menos', 'bem', 'mal',
        'já', 'ainda', 'sempre', 'nunca', 'também', 'só', 'apenas',
        'aqui', 'ali', 'lá', 'cá', 'onde', 'aonde',
        'agora', 'hoje', 'ontem', 'amanhã', 'depois', 'antes',
        # Verbos auxiliares
        'ser', 'estar', 'ter', 'haver', 'ir', 'vir',
        'é', 'são', 'foi', 'eram', 'será', 'seria',
        'está', 'estão', 'estava', 'estavam',
        'tem', 'têm', 'tinha', 'tinham',
        # Outros
        'ao', 'aos', 'à', 'às', 'dum', 'duma',
        'num', 'numa', 'nuns', 'numas',
    }

    def __init__(self, config: CleanerConfig = None):
        self.config = config or CleanerConfig()
        self._blacklist_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.BLACKLIST_PATTERNS
        ]

    # =========================================================================
    # ANTI-LIXO
    # =========================================================================

    def is_garbage(self, content: str) -> bool:
        """
        Verifica se conteúdo é lixo e não deve ser salvo.

        Retorna True se:
        - Muito curto ou muito longo
        - Match em blacklist
        - Muito repetitivo
        - Sem conteúdo significativo
        """
        if not content:
            return True

        content = content.strip()

        # Muito curto
        if len(content) < self.config.min_length:
            return True

        # Muito longo (provavelmente código ou log)
        if len(content) > self.config.max_length:
            return True

        # Match em blacklist
        if self.config.enable_blacklist:
            for pattern in self._blacklist_compiled:
                if pattern.match(content):
                    return True

        # Muito repetitivo (mesma palavra 3+ vezes em texto curto)
        words = content.lower().split()
        if words and len(words) < 15:
            from collections import Counter
            word_counts = Counter(w for w in words if w not in self.STOPWORDS)
            if word_counts:
                most_common_count = word_counts.most_common(1)[0][1]
                if most_common_count >= 3:
                    return True

        # Sem palavras significativas
        significant_words = [w for w in words if w not in self.STOPWORDS and len(w) > 2]
        if len(significant_words) < 2:
            return True

        return False

    def should_extract(self, content: str, category: str) -> bool:
        """
        Decide se deve extrair conteúdo para memória longa.

        Critérios mais rigorosos que is_garbage.
        """
        if self.is_garbage(content):
            return False

        # Conteúdo mínimo útil por categoria
        min_significant_words = {
            'user_info': 2,      # "meu nome é Lucas"
            'projects': 3,       # "meu projeto de IA"
            'preferences': 2,    # "gosto de Python"
            'technical': 3,      # "uso VSCode para programar"
            'problems': 4,       # "tenho um erro no código"
            'achievements': 3,   # "terminei o projeto"
        }

        words = content.lower().split()
        significant = [w for w in words if w not in self.STOPWORDS and len(w) > 2]

        min_required = min_significant_words.get(category, 3)
        return len(significant) >= min_required

    # =========================================================================
    # NORMALIZAÇÃO E DEDUPE
    # =========================================================================

    def normalize(self, text: str) -> str:
        """
        Normaliza texto para comparação de similaridade.

        - Lowercase
        - Remove acentos
        - Remove stopwords
        - Remove pontuação
        - Ordena palavras (para comparação independente de ordem)
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Remove acentos
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')

        # Remove pontuação
        text = re.sub(r'[^\w\s]', '', text)

        # Remove stopwords e palavras muito curtas
        words = [
            w for w in text.split()
            if w not in self.STOPWORDS and len(w) > 2
        ]

        # Ordenar para comparação independente de ordem
        return ' '.join(sorted(set(words)))

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similaridade de Jaccard entre dois textos normalizados.

        Jaccard = |A ∩ B| / |A ∪ B|
        """
        norm1 = self.normalize(text1)
        norm2 = self.normalize(text2)

        set1 = set(norm1.split())
        set2 = set(norm2.split())

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def is_duplicate(
        self,
        new_content: str,
        existing_contents: List[str]
    ) -> bool:
        """
        Verifica se conteúdo é duplicata de algum existente.
        """
        for existing in existing_contents:
            similarity = self.jaccard_similarity(new_content, existing)
            if similarity >= self.config.similarity_threshold:
                return True
        return False

    def find_duplicates(
        self,
        entries: List['MemoryEntry']
    ) -> List[Set[int]]:
        """
        Encontra grupos de entradas duplicadas.
        Retorna lista de sets com índices de duplicatas.
        """
        n = len(entries)
        duplicate_groups = []
        processed = set()

        for i in range(n):
            if i in processed:
                continue

            group = {i}
            for j in range(i + 1, n):
                if j in processed:
                    continue

                similarity = self.jaccard_similarity(
                    entries[i].content,
                    entries[j].content
                )
                if similarity >= self.config.similarity_threshold:
                    group.add(j)
                    processed.add(j)

            if len(group) > 1:
                duplicate_groups.append(group)
            processed.add(i)

        return duplicate_groups

    def deduplicate(
        self,
        entries: List['MemoryEntry']
    ) -> List['MemoryEntry']:
        """
        Remove duplicatas, mantendo a entrada mais recente.
        """
        if not entries:
            return []

        # Ordenar por timestamp (mais recente primeiro)
        sorted_entries = sorted(
            entries,
            key=lambda e: e.timestamp,
            reverse=True
        )

        seen_normalized: Set[str] = set()
        unique = []

        for entry in sorted_entries:
            normalized = self.normalize(entry.content)

            # Verificar similaridade com já vistos
            is_dup = False
            for seen in seen_normalized:
                similarity = self._quick_similarity(normalized, seen)
                if similarity >= self.config.similarity_threshold:
                    is_dup = True
                    break

            if not is_dup:
                seen_normalized.add(normalized)
                unique.append(entry)

        # Restaurar ordem cronológica (mais antigo primeiro)
        return list(reversed(unique))

    def _quick_similarity(self, norm1: str, norm2: str) -> float:
        """Similaridade rápida usando sets pré-computados"""
        set1 = set(norm1.split())
        set2 = set(norm2.split())

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    # =========================================================================
    # EVICTION
    # =========================================================================

    def compute_eviction_score(self, entry: 'MemoryEntry') -> float:
        """
        Calcula score para eviction.
        MENOR score = evictar primeiro.

        Fatores:
        - Importância original (40%)
        - Recência (30%)
        - Frequência de acesso (30%)
        """
        now = datetime.now()
        age_days = (now - entry.timestamp).days

        # Importância (0-1)
        importance_score = entry.importance

        # Recência (decay exponencial, 0-1)
        # 5% decay por dia, 0.95^30 ≈ 0.21 após 1 mês
        recency_score = 0.95 ** min(age_days, 90)

        # Frequência de acesso (normalizado, 0-1)
        # Cap em 10 acessos
        access_score = min(entry.access_count / 10, 1.0)

        # Score composto
        score = (
            importance_score * 0.4 +
            recency_score * 0.3 +
            access_score * 0.3
        )

        return score

    def select_for_eviction(
        self,
        entries: List['MemoryEntry'],
        target_count: int
    ) -> List['MemoryEntry']:
        """
        Seleciona entradas para remover até atingir target_count.
        Retorna lista de entradas a serem removidas.
        """
        if len(entries) <= target_count:
            return []

        # Calcular scores
        scored = [(self.compute_eviction_score(e), e) for e in entries]
        scored.sort(key=lambda x: x[0])  # Menor score primeiro

        # Selecionar para eviction (os de menor score)
        to_remove_count = len(entries) - target_count
        return [entry for _, entry in scored[:to_remove_count]]

    def should_evict(self, entry: 'MemoryEntry') -> bool:
        """
        Decide se uma entrada específica deve ser evictada.
        Baseado em TTL e acesso.
        """
        now = datetime.now()
        age = now - entry.timestamp

        # Entradas explícitas do usuário nunca são evictadas automaticamente
        if entry.source == 'user_stated':
            return False

        # TTL baseado em importância
        ttl_days = (
            self.config.important_ttl_days
            if entry.importance >= 0.7
            else self.config.default_ttl_days
        )

        # Evictar se muito antiga e não acessada
        if age > timedelta(days=ttl_days):
            if entry.access_count < 2:
                return True

        # Evictar se importância muito baixa e antiga
        if entry.importance < 0.3 and age > timedelta(days=7):
            return True

        return False

    # =========================================================================
    # APLICAÇÃO DE LIMITES
    # =========================================================================

    def enforce_limits(
        self,
        memory: Dict[str, List['MemoryEntry']]
    ) -> Dict[str, List['MemoryEntry']]:
        """
        Aplica todos os limites de memória:
        1. Dedupe por categoria
        2. Limite por categoria
        3. Limite total
        """
        cleaned = {}
        total = 0

        for category, entries in memory.items():
            # 1. Dedupe
            entries = self.deduplicate(entries)

            # 2. Remover entradas que devem ser evictadas por TTL
            entries = [e for e in entries if not self.should_evict(e)]

            # 3. Limite por categoria
            if len(entries) > self.config.max_per_category:
                to_evict = self.select_for_eviction(
                    entries,
                    self.config.max_per_category
                )
                evict_ids = {id(e) for e in to_evict}
                entries = [e for e in entries if id(e) not in evict_ids]

            cleaned[category] = entries
            total += len(entries)

        # 4. Limite total (se necessário)
        if total > self.config.max_total:
            cleaned = self._enforce_total_limit(cleaned)

        return cleaned

    def _enforce_total_limit(
        self,
        memory: Dict[str, List['MemoryEntry']]
    ) -> Dict[str, List['MemoryEntry']]:
        """Aplica limite total evictando proporcionalmente"""
        # Coletar todas as entradas com categoria
        all_entries = []
        for category, entries in memory.items():
            for entry in entries:
                all_entries.append((category, entry))

        # Calcular quantos remover
        total = len(all_entries)
        to_remove = total - self.config.max_total

        if to_remove <= 0:
            return memory

        # Ordenar por score de eviction
        scored = [
            (self.compute_eviction_score(entry), category, entry)
            for category, entry in all_entries
        ]
        scored.sort(key=lambda x: x[0])  # Menor primeiro

        # Marcar para remoção
        evict_ids = set()
        for i in range(min(to_remove, len(scored))):
            evict_ids.add(id(scored[i][2]))

        # Reconstruir dicionário
        result = {}
        for category, entries in memory.items():
            result[category] = [
                e for e in entries
                if id(e) not in evict_ids
            ]

        return result

    def get_cleanup_stats(
        self,
        before: Dict[str, List['MemoryEntry']],
        after: Dict[str, List['MemoryEntry']]
    ) -> Dict[str, Any]:
        """Retorna estatísticas da limpeza"""
        before_count = sum(len(entries) for entries in before.values())
        after_count = sum(len(entries) for entries in after.values())

        by_category = {}
        for category in set(before.keys()) | set(after.keys()):
            b = len(before.get(category, []))
            a = len(after.get(category, []))
            by_category[category] = {'before': b, 'after': a, 'removed': b - a}

        return {
            'total_before': before_count,
            'total_after': after_count,
            'total_removed': before_count - after_count,
            'by_category': by_category
        }
