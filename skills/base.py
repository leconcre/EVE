# skills/base.py
"""
Classe base para Skills da EVE.
Skills são capacidades modulares desacopladas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import re


class SkillType(Enum):
    """Tipo de skill baseado em dependência de modelo"""
    PURE = "pure"                    # Sem modelo, lógica pura
    MODEL_OPTIONAL = "model_optional" # Pode usar modelo, mas funciona sem
    MODEL_REQUIRED = "model_required" # Requer modelo para funcionar


class SkillPriority(Enum):
    """Prioridade de execução da skill"""
    CRITICAL = 1    # Sempre executar primeiro
    HIGH = 2        # Preferência alta
    NORMAL = 3      # Padrão
    LOW = 4         # Só se nada mais servir


@dataclass
class SkillTrigger:
    """Define quando uma skill deve ser ativada"""
    # Keywords que ativam a skill
    keywords: List[str] = field(default_factory=list)

    # Padrões regex
    patterns: List[str] = field(default_factory=list)

    # Intents que ativam (IntentType.name)
    intents: List[str] = field(default_factory=list)

    # Extensões de arquivo que ativam
    file_types: List[str] = field(default_factory=list)

    # Confiança mínima para ativar
    min_confidence: float = 0.5


@dataclass
class SkillResult:
    """Resultado da execução de uma skill"""
    success: bool
    output: Any                          # str, dict, ou estruturado

    # Se True, skill precisa que o modelo processe output
    needs_model: bool = False

    # Prompt para o modelo (se needs_model=True)
    model_prompt: Optional[str] = None

    # Artefatos gerados (código, arquivos, etc)
    artifacts: List[Dict] = field(default_factory=list)

    # Metadados extras
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Mensagem de erro (se success=False)
    error: Optional[str] = None

    # Sugestão de followup
    suggested_followup: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'output': str(self.output) if self.output else None,
            'needs_model': self.needs_model,
            'artifacts_count': len(self.artifacts),
            'error': self.error
        }


class Skill(ABC):
    """
    Classe base para todas as skills.

    Uma skill é uma capacidade específica da EVE.
    Ela sabe quando deve ser ativada e como executar.

    IMPORTANTE:
    - skill_type default é PURE (sem modelo)
    - A skill decide se precisa de modelo
    - Priorizar resolver sem modelo quando possível
    """

    # =========================================================================
    # METADADOS (sobrescrever nas subclasses)
    # =========================================================================

    name: str = "base_skill"
    description: str = "Skill base - não usar diretamente"
    version: str = "1.0.0"
    author: str = "EVE"

    # =========================================================================
    # CONFIGURAÇÃO (sobrescrever conforme necessário)
    # =========================================================================

    # Tipo da skill - DEFAULT É PURE (sem modelo)
    skill_type: SkillType = SkillType.PURE

    # Prioridade de execução
    priority: SkillPriority = SkillPriority.NORMAL

    # Modelo preferido (se skill_type != PURE)
    preferred_model: Optional[str] = None
    preferred_capability: Optional[str] = None

    # Timeout em segundos
    timeout_seconds: int = 60

    # Tags para busca
    tags: List[str] = []

    def __init__(self):
        self.trigger = self._build_trigger()
        self._is_loaded = False
        self._compiled_patterns: List[re.Pattern] = []

        # Compilar patterns
        for pattern in self.trigger.patterns:
            try:
                self._compiled_patterns.append(
                    re.compile(pattern, re.IGNORECASE)
                )
            except re.error:
                pass

    # =========================================================================
    # MÉTODOS ABSTRATOS (implementar nas subclasses)
    # =========================================================================

    @abstractmethod
    def _build_trigger(self) -> SkillTrigger:
        """Define os gatilhos desta skill"""
        pass

    @abstractmethod
    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """
        Executa a skill.

        Args:
            user_input: Entrada do usuário
            context: Contexto da conversa e memória

        Returns:
            SkillResult com o resultado

        IMPORTANTE:
        - Skill decide se precisa de modelo
        - Se precisar, retorna needs_model=True com model_prompt
        - O orquestrador então chama o modelo
        """
        pass

    # =========================================================================
    # MÉTODOS DE MATCHING
    # =========================================================================

    def matches(self, user_input: str, intent: str = None) -> float:
        """
        Verifica se esta skill deve ser ativada.
        Retorna score de 0.0 a 1.0
        """
        score = 0.0
        text_lower = user_input.lower()

        # Check keywords
        keyword_matches = sum(
            1 for kw in self.trigger.keywords
            if kw.lower() in text_lower
        )
        if keyword_matches > 0:
            score += min(keyword_matches * 0.2, 0.6)

        # Check patterns (regex)
        for pattern in self._compiled_patterns:
            if pattern.search(text_lower):
                score += 0.3
                break  # Só conta uma vez

        # Check intent
        if intent and intent.upper() in [i.upper() for i in self.trigger.intents]:
            score += 0.4

        return min(score, 1.0)

    def can_handle(self, user_input: str, intent: str = None) -> bool:
        """Verifica se skill pode lidar com a entrada"""
        return self.matches(user_input, intent) >= self.trigger.min_confidence

    # =========================================================================
    # LIFECYCLE HOOKS
    # =========================================================================

    def on_load(self):
        """Chamado quando a skill é carregada"""
        self._is_loaded = True

    def on_unload(self):
        """Chamado quando a skill é descarregada"""
        self._is_loaded = False

    def on_before_execute(self, user_input: str, context: Dict):
        """Hook antes da execução"""
        pass

    def on_after_execute(self, result: SkillResult):
        """Hook depois da execução"""
        pass

    # =========================================================================
    # HELPERS
    # =========================================================================

    def requires_model(self) -> bool:
        """Verifica se skill requer modelo"""
        return self.skill_type == SkillType.MODEL_REQUIRED

    def is_pure(self) -> bool:
        """Verifica se skill é pura (sem modelo)"""
        return self.skill_type == SkillType.PURE

    def get_info(self) -> Dict[str, Any]:
        """Retorna informações da skill"""
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'type': self.skill_type.value,
            'priority': self.priority.value,
            'keywords': self.trigger.keywords[:5],
            'tags': self.tags
        }

    def __repr__(self) -> str:
        return f"Skill({self.name}, type={self.skill_type.value})"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_skill_result(
    success: bool = True,
    output: Any = None,
    error: str = None,
    needs_model: bool = False,
    model_prompt: str = None,
    **metadata
) -> SkillResult:
    """Helper para criar SkillResult"""
    return SkillResult(
        success=success,
        output=output,
        error=error,
        needs_model=needs_model,
        model_prompt=model_prompt,
        metadata=metadata
    )


def skill_error(message: str) -> SkillResult:
    """Helper para criar resultado de erro"""
    return SkillResult(
        success=False,
        output=None,
        error=message
    )


def skill_success(output: Any, **metadata) -> SkillResult:
    """Helper para criar resultado de sucesso"""
    return SkillResult(
        success=True,
        output=output,
        metadata=metadata
    )


def skill_needs_model(prompt: str, partial_output: Any = None) -> SkillResult:
    """Helper para indicar que precisa de modelo"""
    return SkillResult(
        success=True,
        output=partial_output,
        needs_model=True,
        model_prompt=prompt
    )
