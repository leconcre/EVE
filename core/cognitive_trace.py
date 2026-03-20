# core/cognitive_trace.py
"""
Sistema de Cognitive Trace da EVE.
Registra decisoes, justificativas e alternativas de forma estruturada.

Permite responder perguntas como:
- "Por que voce escolheu esse modelo?"
- "Por que usou essa skill?"
- "Por que ignorou aquela memoria?"
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
import json
import uuid
import threading

from core.feature_flags import FLAGS


class TraceCategory(Enum):
    """Categorias de trace"""
    DECISION = "decision"       # Brain decisions
    SKILL = "skill"             # Skill selection/execution
    MEMORY = "memory"           # Memory operations
    MODEL = "model"             # Model selection/calls
    PLANNING = "planning"       # Plan creation/execution
    CONTEXT = "context"         # Context collection
    ERROR = "error"             # Errors and failures


@dataclass
class TraceEntry:
    """Uma entrada no trace cognitivo"""
    id: str
    timestamp: datetime
    category: TraceCategory
    action: str                 # O que aconteceu
    reason: str                 # Por que aconteceu
    inputs: Dict[str, Any]      # Dados de entrada
    outputs: Dict[str, Any]     # Resultados
    alternatives: List[Dict]    # Opcoes nao escolhidas
    confidence: float
    duration_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Converte para dicionario"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'action': self.action,
            'reason': self.reason,
            'inputs': self._sanitize(self.inputs),
            'outputs': self._sanitize(self.outputs),
            'alternatives': self.alternatives[:3],
            'confidence': self.confidence,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata
        }

    def to_jsonl(self) -> str:
        """Serializa para JSONL"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def _sanitize(self, data: Dict) -> Dict:
        """Remove dados sensiveis e trunca strings longas"""
        if not isinstance(data, dict):
            return data

        sanitized = {}
        sensitive_keys = ['api_key', 'password', 'token', 'secret', 'key']

        for k, v in data.items():
            # Pular chaves sensiveis
            if any(sens in k.lower() for sens in sensitive_keys):
                continue

            # Truncar strings longas
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + '...'
            elif isinstance(v, dict):
                v = self._sanitize(v)
            elif isinstance(v, list) and len(v) > 10:
                v = v[:10] + ['...']

            sanitized[k] = v

        return sanitized


class CognitiveTracer:
    """
    Sistema de trace cognitivo.

    Registra decisoes, justificativas e alternativas
    de forma estruturada e queryable.
    """

    def __init__(
        self,
        log_path: str = "eve_cognitive_trace.jsonl",
        max_entries: int = 1000,
        enabled: bool = True
    ):
        self.log_path = Path(log_path)
        self.max_entries = max_entries
        self.enabled = enabled and FLAGS.ENABLE_COGNITIVE_TRACE
        self._session_traces: List[TraceEntry] = []
        self._lock = threading.Lock()
        self._session_id = self._generate_session_id()

    def _generate_id(self) -> str:
        """Gera ID unico para trace"""
        return f"trace_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}"

    def _generate_session_id(self) -> str:
        """Gera ID de sessao"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # =========================================================================
    # METODOS DE TRACE
    # =========================================================================

    def trace_decision(
        self,
        intent: str,
        capability: str,
        skill: Optional[str],
        confidence: float,
        alternatives: List[Dict],
        duration_ms: int,
        metadata: Dict = None
    ):
        """Registra uma decisao do Brain"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.DECISION,
            action=f"intent:{intent}",
            reason=self._build_decision_reason(intent, capability, skill),
            inputs={
                'input_preview': metadata.get('input_preview', '') if metadata else '',
            },
            outputs={
                'intent': intent,
                'capability': capability,
                'skill': skill,
            },
            alternatives=alternatives,
            confidence=confidence,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

        self._log(entry)

    def trace_skill_selection(
        self,
        selected: str,
        candidates: List[Dict],
        reason: str,
        duration_ms: int = 0
    ):
        """Registra selecao de skill"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.SKILL,
            action=f"selected:{selected}",
            reason=reason,
            inputs={'candidates_count': len(candidates)},
            outputs={'selected': selected},
            alternatives=candidates[:3],
            confidence=candidates[0].get('score', 0) if candidates else 0,
            duration_ms=duration_ms
        )

        self._log(entry)

    def trace_skill_execution(
        self,
        skill_name: str,
        success: bool,
        duration_ms: int,
        error: str = None
    ):
        """Registra execucao de skill"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.SKILL,
            action=f"executed:{skill_name}",
            reason="Skill selecionada pelo Brain",
            inputs={'skill': skill_name},
            outputs={'success': success, 'error': error},
            alternatives=[],
            confidence=1.0 if success else 0.0,
            duration_ms=duration_ms
        )

        self._log(entry)

    def trace_model_choice(
        self,
        selected_model: str,
        reason: str,
        alternatives: List[str],
        cost_consideration: str = None
    ):
        """Registra escolha de modelo"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.MODEL,
            action=f"selected:{selected_model}",
            reason=reason,
            inputs={'alternatives': alternatives},
            outputs={'model': selected_model},
            alternatives=[{'model': m} for m in alternatives],
            confidence=1.0,
            duration_ms=0,
            metadata={'cost_note': cost_consideration} if cost_consideration else {}
        )

        self._log(entry)

    def trace_memory_operation(
        self,
        operation: str,  # 'save', 'forget', 'retrieve', 'dedupe', 'summarize'
        target: str,
        reason: str,
        affected_count: int = 1,
        metadata: Dict = None
    ):
        """Registra operacao de memoria"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.MEMORY,
            action=f"{operation}:{target}",
            reason=reason,
            inputs={'target': target},
            outputs={'affected_count': affected_count},
            alternatives=[],
            confidence=1.0,
            duration_ms=0,
            metadata=metadata or {}
        )

        self._log(entry)

    def trace_planning(
        self,
        action: str,  # 'created', 'step_completed', 'paused', 'resumed'
        plan_id: str,
        details: Dict,
        reason: str = None
    ):
        """Registra operacao de planejamento"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.PLANNING,
            action=f"{action}:{plan_id}",
            reason=reason or f"Plan {action}",
            inputs={'plan_id': plan_id},
            outputs=details,
            alternatives=[],
            confidence=1.0,
            duration_ms=0
        )

        self._log(entry)

    def trace_error(
        self,
        error_type: str,
        message: str,
        context: Dict = None
    ):
        """Registra erro"""
        if not self.enabled:
            return

        entry = TraceEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            category=TraceCategory.ERROR,
            action=f"error:{error_type}",
            reason=message,
            inputs=context or {},
            outputs={'error': message},
            alternatives=[],
            confidence=0.0,
            duration_ms=0
        )

        self._log(entry)

    # =========================================================================
    # EXPLAINABILITY
    # =========================================================================

    def get_explanation(self, query: str) -> str:
        """
        Responde perguntas sobre decisoes recentes.

        Exemplos:
        - "Por que voce escolheu esse modelo?"
        - "Por que usou essa skill?"
        - "Por que ignorou aquela memoria?"
        """
        query_lower = query.lower()
        recent = self._session_traces[-20:]  # Ultimas 20

        # Pergunta sobre modelo
        if any(kw in query_lower for kw in ['modelo', 'model', 'groq', 'ollama']):
            model_traces = [t for t in recent if t.category == TraceCategory.MODEL]
            if model_traces:
                last = model_traces[-1]
                alts = [a.get('model', '?') for a in last.alternatives]
                return (
                    f"Escolhi {last.outputs.get('model', '?')} porque: {last.reason}\n"
                    f"Alternativas consideradas: {alts}"
                )

        # Pergunta sobre skill
        if any(kw in query_lower for kw in ['skill', 'habilidade', 'ferramenta']):
            skill_traces = [t for t in recent if t.category == TraceCategory.SKILL]
            if skill_traces:
                last = skill_traces[-1]
                return (
                    f"Acao: {last.action}\n"
                    f"Motivo: {last.reason}\n"
                    f"Resultado: {last.outputs}"
                )

        # Pergunta sobre memoria
        if any(kw in query_lower for kw in ['memoria', 'lembr', 'esquec', 'salv']):
            mem_traces = [t for t in recent if t.category == TraceCategory.MEMORY]
            if mem_traces:
                return self._format_memory_explanation(mem_traces[-5:])

        # Pergunta sobre decisao/intent
        if any(kw in query_lower for kw in ['decid', 'escolh', 'intent', 'por que']):
            decision_traces = [t for t in recent if t.category == TraceCategory.DECISION]
            if decision_traces:
                last = decision_traces[-1]
                return (
                    f"Ultima decisao: {last.action}\n"
                    f"Motivo: {last.reason}\n"
                    f"Confianca: {last.confidence:.0%}"
                )

        # Pergunta sobre plano
        if any(kw in query_lower for kw in ['plano', 'tarefa', 'passo', 'etapa']):
            plan_traces = [t for t in recent if t.category == TraceCategory.PLANNING]
            if plan_traces:
                return self._format_planning_explanation(plan_traces[-5:])

        # Fallback: ultima acao
        if recent:
            last = recent[-1]
            return (
                f"Ultima acao: {last.action}\n"
                f"Categoria: {last.category.value}\n"
                f"Motivo: {last.reason}"
            )

        return "Nao tenho registros recentes para explicar."

    def _format_memory_explanation(self, traces: List[TraceEntry]) -> str:
        """Formata explicacao de operacoes de memoria"""
        lines = ["Operacoes de memoria recentes:"]
        for t in traces:
            lines.append(f"  - {t.action}: {t.reason}")
        return "\n".join(lines)

    def _format_planning_explanation(self, traces: List[TraceEntry]) -> str:
        """Formata explicacao de planejamento"""
        lines = ["Status do planejamento:"]
        for t in traces:
            lines.append(f"  - {t.action}: {t.outputs}")
        return "\n".join(lines)

    def _build_decision_reason(
        self,
        intent: str,
        capability: str,
        skill: Optional[str]
    ) -> str:
        """Constroi justificativa para decisao"""
        parts = [f"Intent detectada: {intent}"]

        if capability:
            parts.append(f"Capacidade necessaria: {capability}")

        if skill:
            parts.append(f"Skill selecionada: {skill}")

        return ". ".join(parts)

    # =========================================================================
    # QUERIES
    # =========================================================================

    def get_recent(
        self,
        category: TraceCategory = None,
        limit: int = 10
    ) -> List[TraceEntry]:
        """Retorna traces recentes"""
        traces = self._session_traces

        if category:
            traces = [t for t in traces if t.category == category]

        return traces[-limit:]

    def get_by_id(self, trace_id: str) -> Optional[TraceEntry]:
        """Busca trace por ID"""
        for t in self._session_traces:
            if t.id == trace_id:
                return t
        return None

    def get_session_summary(self) -> Dict:
        """Retorna resumo da sessao"""
        by_category = {}
        for t in self._session_traces:
            cat = t.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            'session_id': self._session_id,
            'total_traces': len(self._session_traces),
            'by_category': by_category,
            'errors': len([t for t in self._session_traces if t.category == TraceCategory.ERROR])
        }

    # =========================================================================
    # PERSISTENCIA
    # =========================================================================

    def _log(self, entry: TraceEntry):
        """Persiste entrada"""
        with self._lock:
            self._session_traces.append(entry)

            # Limitar memoria
            if len(self._session_traces) > self.max_entries:
                self._session_traces = self._session_traces[-self.max_entries:]

            # Debug log
            if FLAGS.DEBUG_COGNITIVE_TRACE:
                print(f"[TRACE] {entry.category.value}: {entry.action}")

            # Append to file
            try:
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(entry.to_jsonl() + '\n')
            except IOError as e:
                # Log error but don't crash - traces are also kept in memory
                if FLAGS.DEBUG_COGNITIVE_TRACE:
                    print(f"[TRACE] Erro ao persistir trace: {e}")

    def clear_session(self):
        """Limpa traces da sessao"""
        with self._lock:
            self._session_traces.clear()
            self._session_id = self._generate_session_id()

    def export_session(self) -> List[Dict]:
        """Exporta sessao como lista de dicts"""
        return [t.to_dict() for t in self._session_traces]


# =============================================================================
# INSTANCIA GLOBAL (Thread-Safe Singleton)
# =============================================================================

_tracer_instance: Optional[CognitiveTracer] = None
_tracer_lock = threading.Lock()


def get_tracer() -> CognitiveTracer:
    """
    Retorna instancia global do tracer (thread-safe).

    Usa double-checked locking para evitar race conditions.
    """
    global _tracer_instance
    if _tracer_instance is None:
        with _tracer_lock:
            # Double-check dentro do lock
            if _tracer_instance is None:
                _tracer_instance = CognitiveTracer()
    return _tracer_instance


def trace_decision(*args, **kwargs):
    """Shortcut para trace_decision"""
    get_tracer().trace_decision(*args, **kwargs)


def trace_model(*args, **kwargs):
    """Shortcut para trace_model_choice"""
    get_tracer().trace_model_choice(*args, **kwargs)


def trace_skill(*args, **kwargs):
    """Shortcut para trace_skill_selection"""
    get_tracer().trace_skill_selection(*args, **kwargs)


def trace_memory(*args, **kwargs):
    """Shortcut para trace_memory_operation"""
    get_tracer().trace_memory_operation(*args, **kwargs)


def explain(query: str) -> str:
    """Shortcut para get_explanation"""
    return get_tracer().get_explanation(query)
