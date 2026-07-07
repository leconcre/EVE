# memory/layered_memory.py
"""
Sistema de memória em camadas da EVE.
Short-term, Summarized, Long-term e Preferences.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Callable
from collections import deque
from pathlib import Path
import json
import os
import tempfile
import re
import threading

from .cleaner import MemoryCleaner, CleanerConfig
from .summarizer import HeuristicSummarizer, ConversationSummary


@dataclass
class MemoryEntry:
    """Entrada individual de memória (long-term)"""
    content: str
    timestamp: datetime
    category: str
    importance: float = 0.5         # 0.0 a 1.0
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    source: str = 'extraction'      # extraction, user_stated, inferred

    def to_dict(self) -> Dict:
        return {
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category,
            'importance': self.importance,
            'access_count': self.access_count,
            'tags': self.tags,
            'source': self.source
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        return cls(
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            category=data['category'],
            importance=data.get('importance', 0.5),
            access_count=data.get('access_count', 0),
            tags=data.get('tags', []),
            source=data.get('source', 'extraction')
        )


@dataclass
class UserPreference:
    """Preferência do usuário"""
    key: str
    value: Any
    confidence: float = 0.5         # Quão certo estamos
    last_confirmed: datetime = field(default_factory=datetime.now)
    source: str = 'inferred'        # explicit, inferred, observed

    def to_dict(self) -> Dict:
        return {
            'key': self.key,
            'value': self.value,
            'confidence': self.confidence,
            'last_confirmed': self.last_confirmed.isoformat(),
            'source': self.source
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'UserPreference':
        return cls(
            key=data['key'],
            value=data['value'],
            confidence=data.get('confidence', 0.5),
            last_confirmed=datetime.fromisoformat(data.get('last_confirmed', datetime.now().isoformat())),
            source=data.get('source', 'inferred')
        )


class LayeredMemory:
    """
    Sistema de memória em 4 camadas.

    Camadas:
    1. SHORT-TERM: Buffer de mensagens recentes (em memória)
    2. SUMMARIZED: Contexto resumido da conversa
    3. LONG-TERM: Fatos importantes extraídos (persistido)
    4. PREFERENCES: Preferências do usuário (persistido)

    Princípios:
    - Sem embeddings externos
    - Heurísticas simples e rápidas
    - Persistência JSON
    - Decisões explícitas sobre salvar/esquecer
    """

    # Configurações padrão
    SHORT_TERM_SIZE = 10
    SUMMARY_TRIGGER = 5           # Resumir a cada N mensagens
    SUMMARY_MAX_TOKENS = 500
    LONG_TERM_MAX = 200
    LONG_TERM_TTL_DAYS = 30
    IMPORTANCE_THRESHOLD = 0.4    # Mínimo para ir para long-term

    # Categorias de memória long-term
    CATEGORIES = [
        'user_info',      # Nome, profissão, etc
        'projects',       # Projetos mencionados
        'preferences',    # Gostos e preferências
        'technical',      # Conhecimentos técnicos
        'problems',       # Problemas relatados
        'achievements',   # Conquistas
        'context'         # Contexto geral
    ]

    def __init__(
        self,
        persistence_path: str = 'data/eve_memory_v2.json',
        cleaner_config: CleanerConfig = None
    ):
        self.persistence_path = Path(persistence_path)
        self._lock = threading.RLock()  # RLock permite que a mesma thread adquira o lock várias vezes sem travar

        # Componentes
        self._cleaner = MemoryCleaner(cleaner_config or CleanerConfig())
        self._summarizer = HeuristicSummarizer()

        # === CAMADA 1: Short-term (em memória) ===
        self.short_term: deque = deque(maxlen=self.SHORT_TERM_SIZE)

        # === CAMADA 2: Contexto resumido ===
        self.summarized_context: Optional[ConversationSummary] = None
        self.summary_timestamp: Optional[datetime] = None
        self._messages_since_summary = 0

        # === CAMADA 3: Long-term (persistido) ===
        self.long_term: Dict[str, List[MemoryEntry]] = {
            cat: [] for cat in self.CATEGORIES
        }

        # === CAMADA 4: Preferências (persistido) ===
        self.preferences: Dict[str, UserPreference] = {}

        # Cache de respostas
        self.response_cache: Dict[str, Tuple[str, datetime]] = {}
        self._cache_max = 50

        # Estatísticas
        self._stats = {
            'extractions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'cleanups': 0
        }

        # Carregar estado persistido
        self._load()

    # =========================================================================
    # OPERAÇÕES DE ADIÇÃO
    # =========================================================================

    def add_exchange(
        self,
        user_input: str,
        assistant_response: str,
        metadata: Optional[Dict] = None,
        cacheable: bool = False
    ):
        """
        Adiciona uma troca de mensagens.
        Ponto de entrada principal.

        Args:
            cacheable: se True, a resposta pode ser cacheada e reutilizada
                fora do contexto desta conversa (ver core.cache_policy).
                O padrão False evita que respostas contextuais como
                "sim" ou "continue" sejam replayadas em outra conversa.
        """
        with self._lock:
            now = datetime.now()

            # 1. Sempre vai para short-term
            exchange = {
                'user': user_input,
                'assistant': assistant_response,
                'timestamp': now.isoformat(),
                'metadata': metadata or {}
            }
            self.short_term.append(exchange)

            # 2. Verificar se precisa resumir
            self._messages_since_summary += 1
            if self._messages_since_summary >= self.SUMMARY_TRIGGER:
                self._update_summary()

            # 3. Extrair informações importantes
            self._extract_and_store(user_input, now)

            # 4. Atualizar preferências observadas
            self._update_preferences_from_text(user_input)

            # 5. Cache de resposta (se curta e independente de contexto)
            if cacheable and len(assistant_response) < 200:
                self._cache_response(user_input, assistant_response)

            # 6. Salvar
            self._save()

    def add_fact(
        self,
        content: str,
        category: str,
        importance: float = 0.5,
        tags: List[str] = None,
        source: str = 'user_stated'
    ) -> bool:
        """
        Adiciona fato diretamente à memória longa.
        Útil para informações explícitas do usuário.
        """
        if category not in self.CATEGORIES:
            return False

        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now(),
            category=category,
            importance=importance,
            tags=tags or [],
            source=source
        )

        return self._add_to_long_term(category, entry)

    def set_preference(
        self,
        key: str,
        value: Any,
        confidence: float = 0.8,
        source: str = 'explicit'
    ):
        """Define preferência do usuário"""
        with self._lock:
            self.preferences[key] = UserPreference(
                key=key,
                value=value,
                confidence=confidence,
                last_confirmed=datetime.now(),
                source=source
            )
            self._save()

    # =========================================================================
    # EXTRAÇÃO AUTOMÁTICA
    # =========================================================================

    EXTRACTION_PATTERNS = {
        'user_info': [
            (r'(?:meu nome é|me chamo|sou o|sou a)\s+(\w+)', 0.95, ['nome']),
            (r'(?:trabalho como|sou)\s+(desenvolvedor|programador|engenheiro|designer|analista)[\w\s]*', 0.8, ['profissão']),
            (r'(?:tenho|faço)\s+(\d+)\s+anos', 0.7, ['idade']),
            (r'(?:moro em|sou de)\s+(.+?)(?:\.|,|$)', 0.6, ['localização']),
        ],
        'projects': [
            (r'(?:meu projeto|trabalhando em|desenvolvendo)\s+(.+?)(?:\.|,|$)', 0.7, ['projeto']),
            (r'(?:estou criando|fazendo)\s+(?:um|uma)\s+(.+?)(?:\.|,|$)', 0.6, ['projeto']),
            (r'(?:o projeto se chama|nome do projeto é)\s+(.+?)(?:\.|,|$)', 0.8, ['projeto', 'nome']),
        ],
        'preferences': [
            (r'(?:adoro|amo|gosto muito de|prefiro)\s+(.+?)(?:\.|,|$)', 0.6, ['gosto']),
            (r'(?:odeio|detesto|não gosto de|não suporto)\s+(.+?)(?:\.|,|$)', 0.6, ['desgosto']),
            (r'(?:minha? (?:linguagem|lang) favorita?|uso mais)\s+(?:é\s+)?(\w+)', 0.85, ['linguagem']),
            (r'(?:meu editor|uso|prefiro)\s+(vscode|vim|neovim|emacs|sublime|atom)', 0.7, ['editor']),
        ],
        'technical': [
            (r'(?:uso|trabalho com|programo em|conheço)\s+(python|javascript|typescript|c\+\+|java|rust|go)', 0.7, ['linguagem']),
            (r'(?:experiência com|conheço bem)\s+(.+?)(?:\.|,|$)', 0.6, ['skill']),
            (r'(?:aprendi|estou aprendendo)\s+(.+?)(?:\.|,|$)', 0.5, ['aprendizado']),
        ],
        'problems': [
            (r'(?:tenho um problema|erro|bug)(?:\s+(?:com|no|na))?\s+(.+?)(?:\.|$)', 0.6, ['problema']),
            (r'(?:não consigo|não está funcionando)\s+(.+?)(?:\.|$)', 0.6, ['problema']),
        ],
        'achievements': [
            (r'(?:consegui|finalizei|terminei|completei)\s+(.+?)(?:\.|,|!|$)', 0.7, ['conquista']),
            (r'(?:funcionou|deu certo|resolvido)\s*[!.]?', 0.5, ['resolução']),
        ]
    }

    def _extract_and_store(self, text: str, timestamp: datetime):
        """Extrai informações importantes e armazena"""
        extractions = self._extract_facts(text)

        for category, content, importance, tags in extractions:
            if importance >= self.IMPORTANCE_THRESHOLD:
                entry = MemoryEntry(
                    content=content,
                    timestamp=timestamp,
                    category=category,
                    importance=importance,
                    tags=tags,
                    source='extraction'
                )
                if self._add_to_long_term(category, entry):
                    self._stats['extractions'] += 1

    def _extract_facts(self, text: str) -> List[Tuple[str, str, float, List[str]]]:
        """
        Extrai fatos do texto usando padrões.
        Retorna: [(categoria, conteúdo, importância, tags)]
        """
        extractions = []
        text_lower = text.lower()

        for category, patterns in self.EXTRACTION_PATTERNS.items():
            for pattern, importance, tags in patterns:
                try:
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    for match in matches:
                        content = match if isinstance(match, str) else match[0] if match else ''
                        content = content.strip()

                        # Validar extração
                        if content and len(content) > 2 and len(content) < 200:
                            # Verificar se não é lixo
                            if not self._cleaner.is_garbage(content):
                                extractions.append((category, content, importance, tags.copy()))
                except re.error:
                    continue

        return extractions

    def _add_to_long_term(self, category: str, entry: MemoryEntry) -> bool:
        """Adiciona entrada à memória longa com verificações"""
        # 1. Verificar se deve extrair
        if not self._cleaner.should_extract(entry.content, category):
            return False

        # 2. Verificar duplicata
        existing_contents = [e.content for e in self.long_term.get(category, [])]
        if self._cleaner.is_duplicate(entry.content, existing_contents):
            return False

        # 3. Adicionar
        if category not in self.long_term:
            self.long_term[category] = []

        self.long_term[category].append(entry)
        return True

    # =========================================================================
    # OPERAÇÕES DE CONSULTA
    # =========================================================================

    def get_short_term(self) -> List[Dict]:
        """Retorna buffer de curto prazo"""
        with self._lock:
            return list(self.short_term)

    def get_summary(self, use_llm: bool = False) -> ConversationSummary:
        """Retorna resumo da conversa"""
        with self._lock:
            # Atualizar se necessário
            if self.summarized_context is None or self._messages_since_summary > 0:
                self._update_summary(use_llm=use_llm)
            return self.summarized_context or ConversationSummary()

    def get_preferences(self) -> Dict[str, Any]:
        """Retorna preferências com confiança > 0.5"""
        with self._lock:
            return {
                k: v.value for k, v in self.preferences.items()
                if v.confidence > 0.5
            }

    def get_all_preferences(self) -> Dict[str, UserPreference]:
        """Retorna todas as preferências"""
        with self._lock:
            return self.preferences.copy()

    def get_important_facts(self, top_k: int = 10) -> List[MemoryEntry]:
        """Retorna fatos mais importantes"""
        with self._lock:
            all_entries = []
            for entries in self.long_term.values():
                all_entries.extend(entries)

            # Ordenar por importância
            all_entries.sort(key=lambda e: e.importance, reverse=True)
            return all_entries[:top_k]

    def search_long_term(
        self,
        query: str,
        top_k: int = 5,
        category: str = None
    ) -> List[MemoryEntry]:
        """
        Busca na memória longa usando similaridade simples.
        Sem embeddings - usa palavras-chave e tags.
        """
        with self._lock:
            query_words = set(query.lower().split())
            scored_entries = []

            categories = [category] if category else self.long_term.keys()

            for cat in categories:
                entries = self.long_term.get(cat, [])
                for entry in entries:
                    score = self._calculate_relevance(entry, query_words)
                    if score > 0:
                        scored_entries.append((score, entry))
                        # Incrementar contador de acesso
                        entry.access_count += 1

            # Ordenar por score
            scored_entries.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored_entries[:top_k]]

    def _calculate_relevance(
        self,
        entry: MemoryEntry,
        query_words: set
    ) -> float:
        """
        Calcula relevância sem embeddings.

        Fatores:
        - Palavras em comum (peso 2)
        - Match de tags (peso 3)
        - Recência (decay)
        - Importância original
        - Frequência de acesso (bonus)
        """
        score = 0.0
        entry_words = set(entry.content.lower().split())

        # 1. Palavras em comum
        common = query_words & entry_words
        score += len(common) * 2

        # 2. Tags em comum
        entry_tags = set(t.lower() for t in entry.tags)
        tag_matches = query_words & entry_tags
        score += len(tag_matches) * 3

        # 3. Recência (5% decay por dia)
        age_days = (datetime.now() - entry.timestamp).days
        recency_factor = 0.95 ** min(age_days, 60)
        score *= recency_factor

        # 4. Importância
        score *= (0.5 + entry.importance)

        # 5. Frequência de acesso
        score += min(entry.access_count * 0.1, 1.0)

        return score

    def get_context(
        self,
        query: Optional[str] = None,
        layers: List[str] = None
    ) -> Dict[str, Any]:
        """
        Recupera contexto de múltiplas camadas.

        Args:
            query: Query opcional para busca
            layers: Camadas a incluir ['short', 'summary', 'long', 'preferences']
        """
        with self._lock:
            if layers is None:
                layers = ['short', 'summary', 'long', 'preferences']

            context = {}

            if 'short' in layers:
                context['recent'] = self.get_short_term()

            if 'summary' in layers:
                summary = self.get_summary()
                if not summary.is_empty():
                    context['summary'] = summary.text

            if 'long' in layers:
                if query:
                    context['relevant_facts'] = [
                        e.to_dict() for e in self.search_long_term(query)
                    ]
                else:
                    context['important_facts'] = [
                        e.to_dict() for e in self.get_important_facts(5)
                    ]

            if 'preferences' in layers:
                context['preferences'] = self.get_preferences()

            return context

    # =========================================================================
    # CACHE DE RESPOSTAS
    # =========================================================================

    def get_cached_response(self, prompt: str) -> Optional[str]:
        """Busca resposta em cache"""
        normalized = self._normalize_for_cache(prompt)

        if normalized in self.response_cache:
            response, timestamp = self.response_cache[normalized]
            # Verificar expiração (7 dias)
            if datetime.now() - timestamp < timedelta(days=7):
                self._stats['cache_hits'] += 1
                return response

            # Expirado
            del self.response_cache[normalized]

        self._stats['cache_misses'] += 1
        return None

    def _cache_response(self, prompt: str, response: str):
        """Adiciona resposta ao cache"""
        # Limpar cache se muito grande
        if len(self.response_cache) >= self._cache_max:
            # Remover mais antigos
            sorted_cache = sorted(
                self.response_cache.items(),
                key=lambda x: x[1][1]
            )
            for key, _ in sorted_cache[:10]:
                del self.response_cache[key]

        normalized = self._normalize_for_cache(prompt)
        self.response_cache[normalized] = (response, datetime.now())

    def _normalize_for_cache(self, text: str) -> str:
        """Normaliza texto para chave de cache"""
        return ' '.join(text.lower().split())[:100]

    # =========================================================================
    # RESUMO
    # =========================================================================

    def _update_summary(self, use_llm: bool = False):
        """Atualiza o contexto resumido"""
        messages = list(self.short_term)

        if len(messages) < 2:
            return

        self.summarized_context = self._summarizer.summarize(
            messages,
            max_length=self.SUMMARY_MAX_TOKENS,
            use_llm=use_llm
        )
        self.summary_timestamp = datetime.now()
        self._messages_since_summary = 0

    def set_llm_summarizer(self, fn: Callable):
        """Define função LLM para resumo opcional"""
        self._summarizer.set_llm_summarizer(fn)

    # =========================================================================
    # PREFERÊNCIAS
    # =========================================================================

    def _update_preferences_from_text(self, text: str):
        """Atualiza preferências observadas do texto"""
        text_lower = text.lower()

        # Detectar linguagem preferida
        languages = ['python', 'javascript', 'typescript', 'java', 'c++', 'rust', 'go']
        for lang in languages:
            if f'gosto de {lang}' in text_lower or f'prefiro {lang}' in text_lower:
                self._update_preference('linguagem', lang, 0.8, 'observed')
            elif f'uso {lang}' in text_lower or f'programo em {lang}' in text_lower:
                self._update_preference('linguagem', lang, 0.6, 'observed')

        # Detectar editor preferido
        editors = ['vscode', 'vim', 'neovim', 'emacs', 'sublime']
        for editor in editors:
            if editor in text_lower:
                self._update_preference('editor', editor, 0.6, 'observed')

    def _update_preference(
        self,
        key: str,
        value: Any,
        confidence: float,
        source: str
    ):
        """Atualiza preferência existente ou cria nova"""
        if key in self.preferences:
            existing = self.preferences[key]
            # Aumentar confiança se valor igual
            if existing.value == value:
                existing.confidence = min(existing.confidence + 0.1, 1.0)
                existing.last_confirmed = datetime.now()
            elif confidence > existing.confidence:
                # Substituir se nova confiança maior
                self.preferences[key] = UserPreference(
                    key=key, value=value, confidence=confidence,
                    source=source
                )
        else:
            self.preferences[key] = UserPreference(
                key=key, value=value, confidence=confidence, source=source
            )

    # =========================================================================
    # MANUTENÇÃO
    # =========================================================================

    def cleanup(self) -> Dict[str, int]:
        """Executa limpeza da memória"""
        with self._lock:
            stats = {'before': 0, 'after': 0, 'removed': 0}

            for entries in self.long_term.values():
                stats['before'] += len(entries)

            # Aplicar limites e dedupe
            self.long_term = self._cleaner.enforce_limits(self.long_term)

            for entries in self.long_term.values():
                stats['after'] += len(entries)

            stats['removed'] = stats['before'] - stats['after']
            self._stats['cleanups'] += 1

            if stats['removed'] > 0:
                self._save()

            return stats

    def clear_short_term(self):
        """Limpa buffer de curto prazo"""
        with self._lock:
            self.short_term.clear()
            self.summarized_context = None
            self._messages_since_summary = 0

    def clear_all(self):
        """Limpa toda a memória"""
        with self._lock:
            self.short_term.clear()
            self.summarized_context = None
            self._messages_since_summary = 0
            self.long_term = {cat: [] for cat in self.CATEGORIES}
            self.preferences.clear()
            self.response_cache.clear()
            self._save()

    # =========================================================================
    # PERSISTÊNCIA
    # =========================================================================

    def _save(self):
        """Salva estado em arquivo JSON"""
        data = {
            'version': '2.0',
            'saved_at': datetime.now().isoformat(),
            'long_term': {
                cat: [e.to_dict() for e in entries]
                for cat, entries in self.long_term.items()
            },
            'preferences': {
                k: v.to_dict() for k, v in self.preferences.items()
            },
            'response_cache': {
                k: {'response': v[0], 'timestamp': v[1].isoformat()}
                for k, v in self.response_cache.items()
            },
            'stats': self._stats
        }

        temp_name = None
        try:
            # Escrita atômica para evitar corrupção de dados se o programa travar
            dir_name = os.path.dirname(str(self.persistence_path))
            # Se dir_name for vazio, usar diretório atual
            if not dir_name:
                dir_name = '.'

            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8', suffix='.tmp') as tf:
                json.dump(data, tf, indent=2, ensure_ascii=False)
                tf.flush()
                os.fsync(tf.fileno())  # Garante que dados foram escritos no disco
                temp_name = tf.name

            # Substitui o arquivo original apenas se a escrita foi bem sucedida
            os.replace(temp_name, str(self.persistence_path))
            temp_name = None  # Evita cleanup no finally se sucesso

        except (IOError, OSError) as e:
            print(f"[Memory] Erro ao salvar: {e}")
        except Exception as e:
            print(f"[Memory] Erro inesperado ao salvar: {e}")
        finally:
            # Cleanup do arquivo temporário em caso de erro
            if temp_name and os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass

    def _load(self):
        """Carrega estado de arquivo JSON"""
        if not self.persistence_path.exists():
            return

        try:
            with open(self.persistence_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Carregar long-term
            if 'long_term' in data:
                for cat, entries in data['long_term'].items():
                    if cat in self.long_term:
                        self.long_term[cat] = [
                            MemoryEntry.from_dict(e) for e in entries
                        ]

            # Carregar preferências
            if 'preferences' in data:
                for key, pref_data in data['preferences'].items():
                    self.preferences[key] = UserPreference.from_dict(pref_data)

            # Carregar cache
            if 'response_cache' in data:
                for key, cache_data in data['response_cache'].items():
                    self.response_cache[key] = (
                        cache_data['response'],
                        datetime.fromisoformat(cache_data['timestamp'])
                    )

            # Carregar stats
            if 'stats' in data:
                self._stats.update(data['stats'])

        except (IOError, json.JSONDecodeError) as e:
            print(f"[Memory] Erro ao carregar: {e}")

    # =========================================================================
    # ESTATÍSTICAS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da memória"""
        total_entries = sum(len(entries) for entries in self.long_term.values())

        return {
            'short_term_count': len(self.short_term),
            'long_term_count': total_entries,
            'long_term_by_category': {
                cat: len(entries) for cat, entries in self.long_term.items()
            },
            'preferences_count': len(self.preferences),
            'cache_count': len(self.response_cache),
            'cache_hit_rate': (
                self._stats['cache_hits'] /
                max(self._stats['cache_hits'] + self._stats['cache_misses'], 1)
            ),
            'total_extractions': self._stats['extractions'],
            'total_cleanups': self._stats['cleanups'],
            'has_summary': self.summarized_context is not None
        }

    def get_session_state(self) -> Dict[str, Any]:
        """Retorna estado da sessão atual"""
        return {
            'messages_count': len(self.short_term),
            'messages_since_summary': self._messages_since_summary,
            'has_summary': self.summarized_context is not None,
            'summary_age_minutes': (
                int((datetime.now() - self.summary_timestamp).total_seconds() / 60)
                if self.summary_timestamp else None
            )
        }
