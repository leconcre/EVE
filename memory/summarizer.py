# memory/summarizer.py
"""
Sistema de resumo heurístico para memória.
Gera resumos SEM usar LLM - baseado em heurísticas e extração de entidades.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from collections import Counter
import re


@dataclass
class ConversationSummary:
    """Resumo estruturado da conversa"""
    # Tópicos detectados
    topics: List[str] = field(default_factory=list)

    # Estado atual
    current_project: Optional[str] = None
    open_problems: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    # Entidades mencionadas
    entities: Dict[str, List[str]] = field(default_factory=dict)

    # Tarefas em andamento
    ongoing_tasks: List[str] = field(default_factory=list)

    # Estatísticas
    message_count: int = 0
    code_blocks: int = 0
    questions_asked: int = 0
    errors_discussed: int = 0

    # Texto resumido (para usar no prompt)
    text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'topics': self.topics,
            'current_project': self.current_project,
            'open_problems': self.open_problems,
            'decisions_made': self.decisions_made,
            'next_steps': self.next_steps,
            'entities': self.entities,
            'ongoing_tasks': self.ongoing_tasks,
            'message_count': self.message_count,
            'code_blocks': self.code_blocks,
            'questions_asked': self.questions_asked,
            'errors_discussed': self.errors_discussed,
            'text': self.text
        }

    def is_empty(self) -> bool:
        return self.message_count == 0


class HeuristicSummarizer:
    """
    Gerador de resumo SEM usar LLM.
    Usa heurísticas, padrões e extração de entidades.
    """

    # =========================================================================
    # PADRÕES DE TÓPICOS
    # =========================================================================

    TOPIC_PATTERNS = {
        'codigo': [
            'código', 'função', 'classe', 'programa', 'script',
            'bug', 'erro', 'debug', 'implementar', 'criar'
        ],
        'projeto': [
            'projeto', 'app', 'aplicação', 'sistema', 'feature',
            'desenvolver', 'construir', 'arquitetura'
        ],
        'aprendizado': [
            'como', 'por que', 'explique', 'aprend', 'entend',
            'o que é', 'qual a diferença', 'exemplo'
        ],
        'configuracao': [
            'config', 'instalar', 'setup', 'ambiente', 'dependência',
            'pip', 'npm', 'docker', 'variável'
        ],
        'debug': [
            'erro', 'bug', 'problema', 'não funciona', 'falha',
            'exception', 'traceback', 'crash', 'fix'
        ],
        'design': [
            'design', 'arquitetura', 'padrão', 'estrutura',
            'organizar', 'refatorar', 'melhorar'
        ],
        'dados': [
            'banco', 'database', 'sql', 'json', 'api',
            'dados', 'query', 'tabela', 'modelo'
        ],
        'interface': [
            'interface', 'ui', 'tela', 'botão', 'formulário',
            'frontend', 'design', 'layout'
        ]
    }

    # =========================================================================
    # PADRÕES DE ENTIDADES (Regex)
    # =========================================================================

    ENTITY_PATTERNS = {
        'linguagem': r'\b(python|javascript|typescript|c\+\+|java|rust|go|php|ruby|kotlin|swift|c#|scala)\b',
        'framework': r'\b(react|vue|angular|django|flask|fastapi|express|nextjs|spring|laravel|rails)\b',
        'ferramenta': r'\b(git|docker|vscode|vim|neovim|npm|pip|conda|ollama|groq|kubernetes|nginx)\b',
        'arquivo': r'[\w\-]+\.(py|js|ts|tsx|jsx|cpp|c|h|java|rs|go|json|yaml|yml|md|txt|html|css|sql)',
        'erro': r'(Error|Exception|Traceback|Failed|error:|warning:|ERRO|FALHA)',
        'biblioteca': r'\b(numpy|pandas|tensorflow|pytorch|requests|axios|lodash|react-router|redux)\b',
    }

    # =========================================================================
    # INDICADORES DE ESTADO
    # =========================================================================

    PROBLEM_INDICATORS = [
        'erro', 'problema', 'bug', 'não consigo', 'não funciona',
        'falha', 'quebrou', 'travou', 'exception', 'não está'
    ]

    DECISION_INDICATORS = [
        'vou usar', 'decidi', 'escolhi', 'vamos com', 'então',
        'melhor usar', 'prefiro', 'optei por', 'vou fazer'
    ]

    NEXT_STEP_INDICATORS = [
        'próximo', 'depois', 'agora vou', 'falta', 'preciso',
        'ainda preciso', 'vou precisar', 'tenho que'
    ]

    PROJECT_INDICATORS = [
        'meu projeto', 'estou fazendo', 'trabalhando em',
        'criando', 'desenvolvendo', 'construindo'
    ]

    TASK_INDICATORS = [
        'estou tentando', 'quero fazer', 'preciso implementar',
        'trabalhando em', 'focado em', 'fazendo'
    ]

    def __init__(self, llm_summarizer: Callable = None):
        """
        Args:
            llm_summarizer: Função opcional para resumo com LLM.
                           Assinatura: fn(prompt: str) -> str
        """
        self._llm_summarizer = llm_summarizer
        self._entity_patterns_compiled = {
            k: re.compile(v, re.IGNORECASE)
            for k, v in self.ENTITY_PATTERNS.items()
        }

    def set_llm_summarizer(self, fn: Callable):
        """Define função LLM para resumo opcional"""
        self._llm_summarizer = fn

    def summarize(
        self,
        messages: List[Dict],
        max_length: int = 500,
        use_llm: bool = False
    ) -> ConversationSummary:
        """
        Gera resumo da conversa.

        Args:
            messages: Lista de dicts com 'user' e 'assistant'
            max_length: Tamanho máximo do texto resumido
            use_llm: Se True e disponível, usa LLM para melhor qualidade

        Returns:
            ConversationSummary com resumo estruturado
        """
        if not messages:
            return self._empty_summary()

        # Tentar LLM se solicitado e disponível
        if use_llm and self._llm_summarizer:
            try:
                return self._llm_summary(messages, max_length)
            except Exception:
                pass  # Fallback para heurística

        # Resumo heurístico
        return self._heuristic_summary(messages, max_length)

    def _heuristic_summary(
        self,
        messages: List[Dict],
        max_length: int
    ) -> ConversationSummary:
        """Gera resumo usando heurísticas"""
        # Extrair textos do usuário
        user_texts = []
        assistant_texts = []

        for msg in messages:
            if isinstance(msg, dict):
                if 'user' in msg:
                    user_texts.append(msg['user'])
                if 'assistant' in msg:
                    assistant_texts.append(msg['assistant'])

        all_user_text = ' '.join(user_texts).lower()
        all_text = ' '.join(user_texts + assistant_texts).lower()

        # 1. Extrair tópicos
        topics = self._extract_topics(all_user_text)

        # 2. Extrair entidades
        entities = self._extract_entities(all_text)

        # 3. Detectar estado atual
        current_project = self._detect_project(user_texts)
        open_problems = self._detect_problems(user_texts)
        decisions = self._detect_decisions(user_texts)
        next_steps = self._detect_next_steps(user_texts)
        ongoing_tasks = self._detect_ongoing_tasks(user_texts)

        # 4. Estatísticas
        code_blocks = sum(
            1 for t in assistant_texts
            if '```' in t
        )
        questions = sum(1 for t in user_texts if '?' in t)
        errors = sum(
            1 for t in user_texts
            if any(ind in t.lower() for ind in ['erro', 'error', 'exception', 'bug'])
        )

        # 5. Gerar texto
        summary_text = self._generate_text(
            topics=topics,
            entities=entities,
            current_project=current_project,
            open_problems=open_problems,
            decisions=decisions,
            next_steps=next_steps,
            ongoing_tasks=ongoing_tasks,
            max_length=max_length
        )

        return ConversationSummary(
            topics=topics,
            current_project=current_project,
            open_problems=open_problems,
            decisions_made=decisions,
            next_steps=next_steps,
            entities=entities,
            ongoing_tasks=ongoing_tasks,
            message_count=len(messages),
            code_blocks=code_blocks,
            questions_asked=questions,
            errors_discussed=errors,
            text=summary_text
        )

    def _extract_topics(self, text: str) -> List[str]:
        """Extrai tópicos por frequência de keywords"""
        topic_scores = Counter()

        for topic, keywords in self.TOPIC_PATTERNS.items():
            for kw in keywords:
                count = text.count(kw)
                topic_scores[topic] += count

        # Top 3 tópicos com score > 0
        return [
            topic for topic, score in topic_scores.most_common(3)
            if score > 0
        ]

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extrai entidades com regex"""
        entities = {}

        for entity_type, pattern in self._entity_patterns_compiled.items():
            matches = pattern.findall(text)
            if matches:
                # Unique, preservando ordem, lowercase
                unique = list(dict.fromkeys(m.lower() for m in matches))
                entities[entity_type] = unique[:5]  # Max 5 por tipo

        return entities

    def _detect_project(self, texts: List[str]) -> Optional[str]:
        """Detecta projeto atual mencionado"""
        for text in reversed(texts):  # Mais recente primeiro
            text_lower = text.lower()
            for indicator in self.PROJECT_INDICATORS:
                if indicator in text_lower:
                    # Extrair próximas palavras após indicador
                    idx = text_lower.find(indicator)
                    after = text[idx + len(indicator):idx + len(indicator) + 80]
                    # Limpar
                    project = after.strip()
                    # Pegar até primeiro ponto ou vírgula
                    for sep in ['.', ',', '?', '!', '\n']:
                        if sep in project:
                            project = project.split(sep)[0]
                    project = project.strip()
                    if len(project) > 3 and len(project) < 100:
                        return project[:80]
        return None

    def _detect_problems(self, texts: List[str]) -> List[str]:
        """Detecta problemas mencionados"""
        problems = []

        for text in texts[-10:]:  # Últimas 10 mensagens
            text_lower = text.lower()
            for indicator in self.PROBLEM_INDICATORS:
                if indicator in text_lower:
                    # Extrair contexto
                    idx = text_lower.find(indicator)
                    start = max(0, idx - 10)
                    end = min(len(text), idx + 100)
                    context = text[start:end].strip()

                    # Limpar contexto
                    context = re.sub(r'\s+', ' ', context)
                    if context and len(context) > 15:
                        problems.append(context[:120])
                    break

        # Remover duplicatas mantendo ordem
        seen = set()
        unique_problems = []
        for p in problems:
            p_norm = p.lower()[:50]
            if p_norm not in seen:
                seen.add(p_norm)
                unique_problems.append(p)

        return unique_problems[-3:]  # Máx 3

    def _detect_decisions(self, texts: List[str]) -> List[str]:
        """Detecta decisões tomadas"""
        decisions = []

        for text in texts:
            text_lower = text.lower()
            for indicator in self.DECISION_INDICATORS:
                if indicator in text_lower:
                    idx = text_lower.find(indicator)
                    context = text[idx:idx + 80].strip()
                    # Pegar até primeiro ponto
                    if '.' in context:
                        context = context.split('.')[0]
                    if context and len(context) > 10:
                        decisions.append(context[:100])
                    break

        return decisions[-3:]  # Máx 3

    def _detect_next_steps(self, texts: List[str]) -> List[str]:
        """Detecta próximos passos mencionados"""
        steps = []

        for text in texts[-5:]:  # Últimas 5 mensagens
            text_lower = text.lower()
            for indicator in self.NEXT_STEP_INDICATORS:
                if indicator in text_lower:
                    idx = text_lower.find(indicator)
                    context = text[idx:idx + 80].strip()
                    if '.' in context:
                        context = context.split('.')[0]
                    if context and len(context) > 10:
                        steps.append(context[:100])
                    break

        return steps[-3:]  # Máx 3

    def _detect_ongoing_tasks(self, texts: List[str]) -> List[str]:
        """Detecta tarefas em andamento"""
        tasks = []

        for text in texts[-5:]:
            text_lower = text.lower()
            for indicator in self.TASK_INDICATORS:
                if indicator in text_lower:
                    idx = text_lower.find(indicator)
                    context = text[idx:idx + 60].strip()
                    if context and len(context) > 10:
                        tasks.append(context[:80])
                    break

        return tasks[-3:]

    def _generate_text(
        self,
        topics: List[str],
        entities: Dict[str, List[str]],
        current_project: Optional[str],
        open_problems: List[str],
        decisions: List[str],
        next_steps: List[str],
        ongoing_tasks: List[str],
        max_length: int
    ) -> str:
        """Gera texto do resumo"""
        parts = []

        # Projeto atual
        if current_project:
            parts.append(f"Projeto: {current_project}")

        # Tópicos
        if topics:
            parts.append(f"Tópicos: {', '.join(topics)}")

        # Entidades principais
        if entities.get('linguagem'):
            parts.append(f"Linguagens: {', '.join(entities['linguagem'])}")
        if entities.get('ferramenta'):
            parts.append(f"Ferramentas: {', '.join(entities['ferramenta'][:3])}")
        if entities.get('framework'):
            parts.append(f"Frameworks: {', '.join(entities['framework'][:3])}")

        # Tarefas em andamento
        if ongoing_tasks:
            parts.append(f"Em andamento: {ongoing_tasks[-1][:60]}")

        # Problemas
        if open_problems:
            parts.append(f"Problemas ({len(open_problems)}): {open_problems[-1][:60]}...")

        # Decisões
        if decisions:
            parts.append(f"Decisão recente: {decisions[-1][:60]}")

        # Próximos passos
        if next_steps:
            parts.append(f"Próximo: {next_steps[-1][:60]}")

        text = '\n'.join(parts)
        return text[:max_length]

    def _llm_summary(
        self,
        messages: List[Dict],
        max_length: int
    ) -> ConversationSummary:
        """Gera resumo usando LLM (melhor qualidade)"""
        # Preparar conversa para o prompt
        conversation_lines = []
        for msg in messages[-10:]:  # Últimas 10
            if isinstance(msg, dict):
                user = msg.get('user', '')[:150]
                if user:
                    conversation_lines.append(f"Usuário: {user}")

        conversation = "\n".join(conversation_lines)

        prompt = f"""Analise esta conversa e extraia em formato JSON:
{{
    "topics": ["tópico1", "tópico2"],
    "current_project": "nome do projeto ou null",
    "open_problems": ["problema1"],
    "decisions_made": ["decisão1"],
    "next_steps": ["próximo passo"],
    "summary": "resumo em uma frase"
}}

Conversa:
{conversation}

Retorne APENAS o JSON, sem explicações."""

        try:
            response = self._llm_summarizer(prompt)

            # Tentar parsear JSON
            import json
            # Encontrar JSON na resposta
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                return ConversationSummary(
                    topics=data.get('topics', []),
                    current_project=data.get('current_project'),
                    open_problems=data.get('open_problems', []),
                    decisions_made=data.get('decisions_made', []),
                    next_steps=data.get('next_steps', []),
                    message_count=len(messages),
                    text=data.get('summary', '')[:max_length]
                )
        except Exception:
            pass

        # Fallback para heurística
        return self._heuristic_summary(messages, max_length)

    def _empty_summary(self) -> ConversationSummary:
        """Retorna resumo vazio"""
        return ConversationSummary(text="Sem contexto de conversa.")

    # =========================================================================
    # UTILITÁRIOS
    # =========================================================================

    def extract_key_points(
        self,
        text: str,
        max_points: int = 5
    ) -> List[str]:
        """
        Extrai pontos-chave de um texto.
        Útil para resumir mensagens longas.
        """
        # Dividir em sentenças
        sentences = re.split(r'[.!?]\s+', text)

        # Pontuar sentenças por importância
        scored = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20:
                continue

            score = 0
            sent_lower = sent.lower()

            # Indicadores de importância
            if any(w in sent_lower for w in ['importante', 'principal', 'essencial']):
                score += 2
            if any(w in sent_lower for w in ['porque', 'motivo', 'razão']):
                score += 1
            if any(w in sent_lower for w in ['resultado', 'conclusão', 'então']):
                score += 1
            if '?' in sent:
                score += 1

            # Comprimento razoável
            words = len(sent.split())
            if 10 <= words <= 30:
                score += 1

            scored.append((score, sent))

        # Ordenar por score e retornar top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [sent for _, sent in scored[:max_points]]

    def merge_summaries(
        self,
        summaries: List[ConversationSummary]
    ) -> ConversationSummary:
        """
        Mescla múltiplos resumos em um só.
        Útil para resumir conversas muito longas.
        """
        if not summaries:
            return self._empty_summary()

        if len(summaries) == 1:
            return summaries[0]

        merged = ConversationSummary()

        # Mesclar tópicos (unique)
        all_topics = []
        for s in summaries:
            all_topics.extend(s.topics)
        merged.topics = list(dict.fromkeys(all_topics))[:5]

        # Projeto mais recente
        for s in reversed(summaries):
            if s.current_project:
                merged.current_project = s.current_project
                break

        # Problemas mais recentes
        all_problems = []
        for s in summaries:
            all_problems.extend(s.open_problems)
        merged.open_problems = all_problems[-3:]

        # Decisões mais recentes
        all_decisions = []
        for s in summaries:
            all_decisions.extend(s.decisions_made)
        merged.decisions_made = all_decisions[-3:]

        # Próximos passos (só os mais recentes)
        for s in reversed(summaries):
            if s.next_steps:
                merged.next_steps = s.next_steps[:2]
                break

        # Mesclar entidades
        merged_entities = {}
        for s in summaries:
            for entity_type, values in s.entities.items():
                if entity_type not in merged_entities:
                    merged_entities[entity_type] = []
                merged_entities[entity_type].extend(values)

        for entity_type in merged_entities:
            merged_entities[entity_type] = list(dict.fromkeys(
                merged_entities[entity_type]
            ))[:5]
        merged.entities = merged_entities

        # Estatísticas somadas
        merged.message_count = sum(s.message_count for s in summaries)
        merged.code_blocks = sum(s.code_blocks for s in summaries)
        merged.questions_asked = sum(s.questions_asked for s in summaries)
        merged.errors_discussed = sum(s.errors_discussed for s in summaries)

        # Gerar texto do merge
        merged.text = self._generate_text(
            topics=merged.topics,
            entities=merged.entities,
            current_project=merged.current_project,
            open_problems=merged.open_problems,
            decisions=merged.decisions_made,
            next_steps=merged.next_steps,
            ongoing_tasks=[],
            max_length=500
        )

        return merged
