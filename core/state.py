# core/state.py
"""
Sistema de estado interno da EVE.
Estado computacional (não emocional) que influencia tom e comportamento.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from collections import deque
import json
from pathlib import Path


class MoodType(Enum):
    """
    Estados de humor computacional.
    Baseado em métricas objetivas, não emoções.
    """
    NEUTRAL = "neutral"       # Estado padrão
    ENGAGED = "engaged"       # Usuário interagindo ativamente
    FOCUSED = "focused"       # Trabalhando em tarefa complexa (código)
    HELPFUL = "helpful"       # Usuário precisando de ajuda
    RESERVED = "reserved"     # Respostas curtas do usuário
    TEACHING = "teaching"     # Explicando conceitos


@dataclass
class MoodState:
    """Estado de humor atual"""
    mood: MoodType
    intensity: float          # 0.0 a 1.0
    since: datetime
    reason: str

    def to_dict(self) -> Dict:
        return {
            'mood': self.mood.value,
            'intensity': self.intensity,
            'since': self.since.isoformat(),
            'reason': self.reason
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MoodState':
        return cls(
            mood=MoodType(data['mood']),
            intensity=data['intensity'],
            since=datetime.fromisoformat(data['since']),
            reason=data['reason']
        )


@dataclass
class InteractionMetrics:
    """Métricas de uma interação"""
    timestamp: datetime
    user_length: int
    response_length: int
    has_question: bool
    has_code: bool
    has_error: bool
    success: bool
    response_time_ms: int
    model_used: Optional[str] = None
    skill_used: Optional[str] = None


@dataclass
class ResponseModifiers:
    """Modificadores aplicados às respostas baseado no estado"""
    verbosity: str = 'normal'      # 'concise', 'normal', 'detailed'
    tone: str = 'neutral'          # 'formal', 'neutral', 'casual'
    proactivity: str = 'normal'    # 'low', 'normal', 'high'
    emoji_level: str = 'minimal'   # 'none', 'minimal', 'moderate'
    explanation_depth: str = 'normal'  # 'brief', 'normal', 'thorough'

    def to_dict(self) -> Dict:
        return {
            'verbosity': self.verbosity,
            'tone': self.tone,
            'proactivity': self.proactivity,
            'emoji_level': self.emoji_level,
            'explanation_depth': self.explanation_depth
        }


class InternalState:
    """
    Estado interno da EVE.

    Princípios:
    - Estado é computacional, não emocional
    - Baseado em métricas objetivas
    - Influencia tom, não conteúdo factual
    - Histórico limitado para eficiência
    """

    HISTORY_SIZE = 20  # Últimas interações mantidas

    def __init__(self, persistence_path: Optional[str] = None):
        self.persistence_path = persistence_path

        # Estado atual
        self.current_mood = MoodState(
            mood=MoodType.NEUTRAL,
            intensity=0.5,
            since=datetime.now(),
            reason="startup"
        )

        # Históricos
        self._interaction_history: deque = deque(maxlen=self.HISTORY_SIZE)
        self._mood_history: List[MoodState] = []

        # Sessão
        self._session_start = datetime.now()
        self._last_interaction = datetime.now()

        # Métricas agregadas
        self._total_exchanges = 0
        self._successful_helps = 0
        self._satisfaction_signals = 0
        self._frustration_signals = 0
        self._code_interactions = 0
        self._question_count = 0

        # Carregar estado persistido
        if persistence_path:
            self._load()

    def update(
        self,
        user_input: str,
        response: str,
        success: bool = True,
        response_time_ms: int = 0,
        model_used: str = None,
        skill_used: str = None
    ):
        """
        Atualiza estado baseado na interação.
        Deve ser chamado após cada troca de mensagens.
        """
        now = datetime.now()

        # Criar métricas da interação
        metrics = InteractionMetrics(
            timestamp=now,
            user_length=len(user_input),
            response_length=len(response),
            has_question='?' in user_input,
            has_code='```' in user_input or '```' in response or 'def ' in user_input,
            has_error=self._detect_error_context(user_input),
            success=success,
            response_time_ms=response_time_ms,
            model_used=model_used,
            skill_used=skill_used
        )

        self._interaction_history.append(metrics)
        self._last_interaction = now
        self._total_exchanges += 1

        # Atualizar contadores
        if metrics.has_code:
            self._code_interactions += 1
        if metrics.has_question:
            self._question_count += 1

        # Detectar sinais
        if self._detect_satisfaction(user_input):
            self._satisfaction_signals += 1
            self._successful_helps += 1
        if self._detect_frustration(user_input):
            self._frustration_signals += 1

        # Recalcular mood
        new_mood = self._compute_mood()
        if new_mood.mood != self.current_mood.mood:
            self._mood_history.append(self.current_mood)
            self.current_mood = new_mood

        # Persistir se configurado
        if self.persistence_path:
            self._save()

    def _compute_mood(self) -> MoodState:
        """Computa mood baseado em métricas recentes"""
        if len(self._interaction_history) < 2:
            return self.current_mood

        recent = list(self._interaction_history)[-5:]

        # Calcular métricas
        avg_user_length = sum(m.user_length for m in recent) / len(recent)
        avg_response_time = sum(m.response_time_ms for m in recent) / len(recent)
        question_ratio = sum(1 for m in recent if m.has_question) / len(recent)
        code_ratio = sum(1 for m in recent if m.has_code) / len(recent)
        error_ratio = sum(1 for m in recent if m.has_error) / len(recent)

        # Calcular delay entre interações
        time_diffs = []
        for i in range(1, len(recent)):
            diff = (recent[i].timestamp - recent[i-1].timestamp).total_seconds()
            time_diffs.append(diff)
        avg_delay = sum(time_diffs) / len(time_diffs) if time_diffs else 30

        # === DECISÃO DE MOOD ===

        # FOCUSED: Muita atividade de código
        if code_ratio > 0.6:
            return MoodState(
                mood=MoodType.FOCUSED,
                intensity=min(code_ratio + 0.2, 1.0),
                since=datetime.now(),
                reason="high_code_activity"
            )

        # HELPFUL: Muitas perguntas ou erros
        if question_ratio > 0.5 or error_ratio > 0.3:
            intensity = 0.6 + (question_ratio * 0.2) + (error_ratio * 0.2)
            return MoodState(
                mood=MoodType.HELPFUL,
                intensity=min(intensity, 1.0),
                since=datetime.now(),
                reason="user_needs_help"
            )

        # TEACHING: Perguntas conceituais (mensagens longas com ?)
        if avg_user_length > 100 and question_ratio > 0.4:
            return MoodState(
                mood=MoodType.TEACHING,
                intensity=0.7,
                since=datetime.now(),
                reason="conceptual_questions"
            )

        # ENGAGED: Interação rápida e ativa
        if avg_delay < 30 and avg_user_length > 30:
            return MoodState(
                mood=MoodType.ENGAGED,
                intensity=min(0.5 + (1 - avg_delay/60) * 0.3, 1.0),
                since=datetime.now(),
                reason="active_conversation"
            )

        # RESERVED: Respostas curtas e lentas
        if avg_user_length < 20 and avg_delay > 60:
            return MoodState(
                mood=MoodType.RESERVED,
                intensity=0.4,
                since=datetime.now(),
                reason="sparse_interaction"
            )

        # NEUTRAL: Padrão
        return MoodState(
            mood=MoodType.NEUTRAL,
            intensity=0.5,
            since=datetime.now(),
            reason="normal_interaction"
        )

    def get_response_modifiers(self) -> ResponseModifiers:
        """
        Retorna modificadores para a resposta baseados no estado.
        O sistema usa isso para ajustar tom e verbosidade.
        """
        modifiers = ResponseModifiers()
        mood = self.current_mood.mood
        intensity = self.current_mood.intensity

        if mood == MoodType.FOCUSED:
            modifiers.verbosity = 'concise'
            modifiers.tone = 'formal'
            modifiers.proactivity = 'low'
            modifiers.explanation_depth = 'brief'

        elif mood == MoodType.ENGAGED:
            modifiers.verbosity = 'normal'
            modifiers.tone = 'casual' if intensity > 0.7 else 'neutral'
            modifiers.proactivity = 'high'

        elif mood == MoodType.HELPFUL:
            modifiers.verbosity = 'detailed'
            modifiers.tone = 'neutral'
            modifiers.proactivity = 'high'
            modifiers.explanation_depth = 'thorough'

        elif mood == MoodType.TEACHING:
            modifiers.verbosity = 'detailed'
            modifiers.tone = 'neutral'
            modifiers.explanation_depth = 'thorough'

        elif mood == MoodType.RESERVED:
            modifiers.verbosity = 'concise'
            modifiers.proactivity = 'low'

        return modifiers

    def get_prompt_instruction(self) -> str:
        """
        Retorna instrução para o prompt baseada no estado.
        Pode ser adicionada ao system prompt.
        """
        modifiers = self.get_response_modifiers()
        instructions = []

        if modifiers.verbosity == 'concise':
            instructions.append("Seja conciso e direto ao ponto.")
        elif modifiers.verbosity == 'detailed':
            instructions.append("Forneça explicações detalhadas quando útil.")

        if modifiers.tone == 'formal':
            instructions.append("Mantenha tom técnico e objetivo.")
        elif modifiers.tone == 'casual':
            instructions.append("Use tom amigável e descontraído.")

        if modifiers.proactivity == 'high':
            instructions.append("Sugira melhorias e próximos passos proativamente.")
        elif modifiers.proactivity == 'low':
            instructions.append("Responda apenas o que foi perguntado.")

        if modifiers.explanation_depth == 'thorough':
            instructions.append("Explique o raciocínio por trás das soluções.")
        elif modifiers.explanation_depth == 'brief':
            instructions.append("Vá direto à solução sem explicações extensas.")

        return " ".join(instructions) if instructions else ""

    def _detect_satisfaction(self, text: str) -> bool:
        """Detecta sinais de satisfação do usuário"""
        satisfaction_signals = [
            'obrigado', 'valeu', 'brigado', 'thanks',
            'perfeito', 'excelente', 'ótimo', 'muito bom',
            'funcionou', 'resolveu', 'deu certo', 'era isso',
            'entendi', 'faz sentido', 'show', 'massa'
        ]
        text_lower = text.lower()
        return any(signal in text_lower for signal in satisfaction_signals)

    def _detect_frustration(self, text: str) -> bool:
        """Detecta sinais de frustração do usuário"""
        frustration_signals = [
            'não funciona', 'não funcionou', 'ainda não',
            'de novo', 'mesmo erro', 'não entendi',
            'confuso', 'não faz sentido', 'errado',
            'pior', 'desisto', 'esquece'
        ]
        text_lower = text.lower()
        return any(signal in text_lower for signal in frustration_signals)

    def _detect_error_context(self, text: str) -> bool:
        """Detecta se usuário está falando sobre erros"""
        error_indicators = [
            'erro', 'error', 'exception', 'traceback',
            'falha', 'failed', 'bug', 'problema',
            'não funciona', 'quebrou', 'crash'
        ]
        text_lower = text.lower()
        return any(ind in text_lower for ind in error_indicators)

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do estado"""
        session_duration = datetime.now() - self._session_start

        return {
            'current_mood': self.current_mood.mood.value,
            'mood_intensity': round(self.current_mood.intensity, 2),
            'mood_reason': self.current_mood.reason,
            'mood_since': self.current_mood.since.isoformat(),
            'session_duration_minutes': int(session_duration.total_seconds() / 60),
            'total_exchanges': self._total_exchanges,
            'satisfaction_signals': self._satisfaction_signals,
            'frustration_signals': self._frustration_signals,
            'code_interactions': self._code_interactions,
            'question_count': self._question_count,
            'successful_helps': self._successful_helps,
            'mood_changes': len(self._mood_history)
        }

    def get_session_summary(self) -> str:
        """Retorna resumo da sessão para logging"""
        stats = self.get_stats()
        return (
            f"Sessão: {stats['session_duration_minutes']}min, "
            f"{stats['total_exchanges']} trocas, "
            f"Mood: {stats['current_mood']} ({stats['mood_intensity']}), "
            f"Satisfação: {stats['satisfaction_signals']}, "
            f"Código: {stats['code_interactions']}"
        )

    def reset_session(self):
        """Reseta estado da sessão (mantém histórico)"""
        self._session_start = datetime.now()
        self._last_interaction = datetime.now()
        self._interaction_history.clear()
        self.current_mood = MoodState(
            mood=MoodType.NEUTRAL,
            intensity=0.5,
            since=datetime.now(),
            reason="session_reset"
        )

    def _save(self):
        """Salva estado em arquivo"""
        if not self.persistence_path:
            return

        data = {
            'current_mood': self.current_mood.to_dict(),
            'session_start': self._session_start.isoformat(),
            'total_exchanges': self._total_exchanges,
            'satisfaction_signals': self._satisfaction_signals,
            'frustration_signals': self._frustration_signals,
            'code_interactions': self._code_interactions,
            'question_count': self._question_count,
            'successful_helps': self._successful_helps
        }

        try:
            path = Path(self.persistence_path)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def _load(self):
        """Carrega estado de arquivo"""
        if not self.persistence_path:
            return

        path = Path(self.persistence_path)
        if not path.exists():
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'current_mood' in data:
                self.current_mood = MoodState.from_dict(data['current_mood'])

            self._total_exchanges = data.get('total_exchanges', 0)
            self._satisfaction_signals = data.get('satisfaction_signals', 0)
            self._frustration_signals = data.get('frustration_signals', 0)
            self._code_interactions = data.get('code_interactions', 0)
            self._question_count = data.get('question_count', 0)
            self._successful_helps = data.get('successful_helps', 0)

        except (IOError, json.JSONDecodeError):
            pass


# =============================================================================
# APLICADORES DE ESTADO
# =============================================================================

def apply_state_to_response(
    response: str,
    modifiers: ResponseModifiers,
    max_length: int = None
) -> str:
    """
    Aplica modificadores de estado à resposta.
    Nota: Ajustes mais profundos devem ser feitos no prompt.
    """
    # Ajustar verbosidade (post-hoc)
    if modifiers.verbosity == 'concise' and max_length:
        # Truncar se muito longo
        if len(response) > max_length:
            # Tentar cortar em parágrafo
            paragraphs = response.split('\n\n')
            truncated = []
            current_length = 0
            for p in paragraphs:
                if current_length + len(p) > max_length:
                    break
                truncated.append(p)
                current_length += len(p)
            if truncated:
                response = '\n\n'.join(truncated)

    return response


def get_state_context_for_prompt(state: InternalState) -> str:
    """
    Retorna contexto de estado para incluir no prompt.
    """
    stats = state.get_stats()
    modifiers = state.get_response_modifiers()

    context_parts = []

    # Instruções baseadas no mood
    instruction = state.get_prompt_instruction()
    if instruction:
        context_parts.append(f"[Estilo de resposta: {instruction}]")

    # Contexto de sessão (se relevante)
    if stats['code_interactions'] > 3:
        context_parts.append("[Sessão focada em código]")
    if stats['question_count'] > 5:
        context_parts.append("[Usuário em modo aprendizado]")
    if stats['frustration_signals'] > 0:
        context_parts.append("[Atenção: sinais de dificuldade detectados]")

    return "\n".join(context_parts) if context_parts else ""
