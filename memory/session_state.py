# memory/session_state.py
"""
Estado de sessao da EVE.
Captura "onde estamos agora" de forma explicita.

Principio: Estado explicito, nao inferido de historico.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json


class SessionPhase(Enum):
    """Fases de uma sessao"""
    GREETING = "greeting"           # Inicio, saudacao
    EXPLORATION = "exploration"     # Usuario explorando, perguntas soltas
    FOCUSED = "focused"             # Focado em um topico
    TASK_EXECUTION = "task"         # Executando tarefa especifica
    REVIEW = "review"               # Revisando resultado
    CLOSING = "closing"             # Encerrando


class TopicType(Enum):
    """Tipos de topico"""
    CODE = "code"                   # Programacao, debug
    LEARNING = "learning"           # Aprendizado, explicacoes
    PLANNING = "planning"           # Planejamento, organizacao
    CREATIVE = "creative"           # Criativo, escrita
    FACTUAL = "factual"             # Perguntas fatuais
    PERSONAL = "personal"           # Conversa pessoal
    TASK = "task"                   # Execucao de tarefa
    UNKNOWN = "unknown"


@dataclass
class TopicInfo:
    """Informacoes sobre o topico atual"""
    type: TopicType
    name: str                       # Nome descritivo
    keywords: List[str]             # Palavras-chave relacionadas
    started_at: datetime
    message_count: int = 0
    subtopics: List[str] = field(default_factory=list)

    def duration_minutes(self) -> float:
        """Duracao em minutos"""
        return (datetime.now() - self.started_at).total_seconds() / 60


@dataclass
class PendingAction:
    """Acao pendente na sessao"""
    id: str
    description: str
    created_at: datetime
    priority: int = 1               # 1=baixa, 2=media, 3=alta
    context: Dict[str, Any] = field(default_factory=dict)

    def age_minutes(self) -> float:
        """Idade em minutos"""
        return (datetime.now() - self.created_at).total_seconds() / 60


class SessionState:
    """
    Estado atual da sessao.

    Captura de forma explicita:
    - Fase atual (greeting, focused, task, etc.)
    - Topico em discussao
    - Acoes pendentes
    - Contexto relevante
    """

    def __init__(self):
        self._session_start = datetime.now()
        self._phase = SessionPhase.GREETING
        self._current_topic: Optional[TopicInfo] = None
        self._topic_history: List[TopicInfo] = []
        self._pending_actions: List[PendingAction] = []
        self._message_count = 0
        self._last_message_time: Optional[datetime] = None
        self._context_data: Dict[str, Any] = {}
        self._action_counter = 0

    # =========================================================================
    # PHASE MANAGEMENT
    # =========================================================================

    def update_phase(self, phase: SessionPhase, reason: str = None):
        """Atualiza fase da sessao"""
        old_phase = self._phase
        self._phase = phase
        self._context_data['last_phase_change'] = {
            'from': old_phase.value,
            'to': phase.value,
            'reason': reason,
            'at': datetime.now().isoformat()
        }

    def get_phase(self) -> SessionPhase:
        """Retorna fase atual"""
        return self._phase

    def infer_phase(self) -> SessionPhase:
        """
        Infere fase baseado em sinais.
        Usado quando nao ha mudanca explicita.
        """
        # Sessao muito curta = greeting
        if self._message_count < 2:
            return SessionPhase.GREETING

        # Tem acoes pendentes = task
        if self._pending_actions:
            return SessionPhase.TASK_EXECUTION

        # Topico focado por mais de 3 mensagens = focused
        if self._current_topic and self._current_topic.message_count > 3:
            return SessionPhase.FOCUSED

        # Gap grande = pode estar encerrando
        if self._last_message_time:
            gap = (datetime.now() - self._last_message_time).total_seconds() / 60
            if gap > 30:
                return SessionPhase.CLOSING

        return SessionPhase.EXPLORATION

    # =========================================================================
    # TOPIC MANAGEMENT
    # =========================================================================

    def set_topic(
        self,
        topic_type: TopicType,
        name: str,
        keywords: List[str] = None
    ):
        """Define topico atual"""
        # Arquivar topico anterior
        if self._current_topic:
            self._topic_history.append(self._current_topic)
            # Limitar historico
            if len(self._topic_history) > 10:
                self._topic_history = self._topic_history[-10:]

        self._current_topic = TopicInfo(
            type=topic_type,
            name=name,
            keywords=keywords or [],
            started_at=datetime.now()
        )

    def get_topic(self) -> Optional[TopicInfo]:
        """Retorna topico atual"""
        return self._current_topic

    def add_subtopic(self, subtopic: str):
        """Adiciona subtopico"""
        if self._current_topic:
            if subtopic not in self._current_topic.subtopics:
                self._current_topic.subtopics.append(subtopic)

    def detect_topic_type(self, text: str) -> TopicType:
        """
        Detecta tipo de topico do texto.
        Regras explicitas, nao ML.
        """
        text_lower = text.lower()

        # Code indicators
        code_keywords = [
            'codigo', 'code', 'funcao', 'function', 'classe', 'class',
            'bug', 'erro', 'error', 'python', 'javascript', 'programar',
            'implementar', 'debugar', 'compilar', 'rodar', 'executar'
        ]
        if any(kw in text_lower for kw in code_keywords):
            return TopicType.CODE

        # Learning indicators
        learning_keywords = [
            'como funciona', 'explique', 'explain', 'o que e', 'what is',
            'aprend', 'learn', 'entender', 'understand', 'ensine', 'teach'
        ]
        if any(kw in text_lower for kw in learning_keywords):
            return TopicType.LEARNING

        # Planning indicators
        planning_keywords = [
            'planejar', 'plan', 'organizar', 'organize', 'estruturar',
            'passos', 'steps', 'roadmap', 'cronograma', 'tarefas'
        ]
        if any(kw in text_lower for kw in planning_keywords):
            return TopicType.PLANNING

        # Creative indicators
        creative_keywords = [
            'escrever', 'write', 'criar', 'create', 'historia', 'story',
            'ideia', 'idea', 'inventar', 'imaginar'
        ]
        if any(kw in text_lower for kw in creative_keywords):
            return TopicType.CREATIVE

        # Factual indicators
        factual_keywords = [
            'quanto', 'how much', 'quando', 'when', 'onde', 'where',
            'qual', 'which', 'quem', 'who'
        ]
        if any(kw in text_lower for kw in factual_keywords):
            return TopicType.FACTUAL

        # Personal indicators
        personal_keywords = [
            'voce', 'you', 'sinto', 'feel', 'acho', 'think',
            'gosto', 'like', 'odeio', 'hate', 'meu', 'my'
        ]
        if any(kw in text_lower for kw in personal_keywords):
            return TopicType.PERSONAL

        return TopicType.UNKNOWN

    # =========================================================================
    # PENDING ACTIONS
    # =========================================================================

    def add_pending_action(
        self,
        description: str,
        priority: int = 1,
        context: Dict = None
    ) -> str:
        """
        Adiciona acao pendente.

        Returns:
            ID da acao
        """
        self._action_counter += 1
        action_id = f"action_{self._action_counter}"

        action = PendingAction(
            id=action_id,
            description=description,
            created_at=datetime.now(),
            priority=priority,
            context=context or {}
        )

        self._pending_actions.append(action)

        # Ordenar por prioridade
        self._pending_actions.sort(key=lambda a: -a.priority)

        return action_id

    def complete_action(self, action_id: str) -> bool:
        """Marca acao como completa"""
        for i, action in enumerate(self._pending_actions):
            if action.id == action_id:
                self._pending_actions.pop(i)
                return True
        return False

    def get_pending_actions(self, priority: int = None) -> List[PendingAction]:
        """Retorna acoes pendentes"""
        if priority:
            return [a for a in self._pending_actions if a.priority == priority]
        return self._pending_actions.copy()

    def get_next_action(self) -> Optional[PendingAction]:
        """Retorna proxima acao (maior prioridade)"""
        if self._pending_actions:
            return self._pending_actions[0]
        return None

    # =========================================================================
    # MESSAGE TRACKING
    # =========================================================================

    def record_message(self, is_user: bool = True):
        """Registra uma mensagem"""
        self._message_count += 1
        self._last_message_time = datetime.now()

        if self._current_topic:
            self._current_topic.message_count += 1

    def get_message_count(self) -> int:
        """Total de mensagens na sessao"""
        return self._message_count

    def time_since_last_message(self) -> Optional[float]:
        """Minutos desde ultima mensagem"""
        if self._last_message_time:
            return (datetime.now() - self._last_message_time).total_seconds() / 60
        return None

    # =========================================================================
    # CONTEXT DATA
    # =========================================================================

    def set_context(self, key: str, value: Any):
        """Define dado de contexto"""
        self._context_data[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Obtem dado de contexto"""
        return self._context_data.get(key, default)

    def clear_context(self, key: str = None):
        """Limpa contexto"""
        if key:
            self._context_data.pop(key, None)
        else:
            self._context_data.clear()

    # =========================================================================
    # SUMMARY & EXPORT
    # =========================================================================

    def get_context_summary(self) -> str:
        """
        Gera resumo do contexto atual.
        Util para incluir em prompts.
        """
        parts = []

        # Fase
        parts.append(f"Fase: {self._phase.value}")

        # Topico
        if self._current_topic:
            duration = self._current_topic.duration_minutes()
            parts.append(
                f"Topico: {self._current_topic.name} "
                f"({self._current_topic.type.value}, {duration:.0f}min)"
            )
            if self._current_topic.subtopics:
                parts.append(f"Subtopicos: {', '.join(self._current_topic.subtopics[:3])}")

        # Acoes pendentes
        if self._pending_actions:
            high_priority = [a for a in self._pending_actions if a.priority == 3]
            if high_priority:
                parts.append(f"Acoes urgentes: {len(high_priority)}")
            parts.append(f"Acoes pendentes: {len(self._pending_actions)}")

        # Duracao
        session_duration = (datetime.now() - self._session_start).total_seconds() / 60
        parts.append(f"Sessao: {session_duration:.0f}min, {self._message_count} msgs")

        return " | ".join(parts)

    def get_state_dict(self) -> Dict:
        """Exporta estado como dicionario"""
        return {
            'session_start': self._session_start.isoformat(),
            'phase': self._phase.value,
            'topic': {
                'type': self._current_topic.type.value,
                'name': self._current_topic.name,
                'duration_min': self._current_topic.duration_minutes(),
                'message_count': self._current_topic.message_count,
                'subtopics': self._current_topic.subtopics
            } if self._current_topic else None,
            'pending_actions': [
                {
                    'id': a.id,
                    'description': a.description,
                    'priority': a.priority,
                    'age_min': a.age_minutes()
                }
                for a in self._pending_actions
            ],
            'message_count': self._message_count,
            'session_duration_min': (datetime.now() - self._session_start).total_seconds() / 60
        }

    def to_json(self) -> str:
        """Serializa para JSON"""
        return json.dumps(self.get_state_dict(), ensure_ascii=False, indent=2)

    # =========================================================================
    # RESET
    # =========================================================================

    def reset(self):
        """Reseta estado da sessao"""
        self.__init__()


# =============================================================================
# INSTANCIA GLOBAL
# =============================================================================

_session_state: Optional[SessionState] = None


def get_session_state() -> SessionState:
    """Retorna instancia global do estado de sessao"""
    global _session_state
    if _session_state is None:
        _session_state = SessionState()
    return _session_state


def reset_session():
    """Reseta sessao global"""
    global _session_state
    _session_state = SessionState()
