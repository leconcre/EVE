# core/planner.py
"""
Sistema de planejamento da EVE.
Decompoe tarefas complexas em passos executaveis.

Principio: Decomposicao explicita com regras claras.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import re
import threading

from memory.task_memory import Task, TaskStep, TaskComplexity, TaskStatus, get_task_memory


class StepType(Enum):
    """Tipos de passo"""
    SKILL = "skill"                 # Executar skill
    MODEL = "model"                 # Chamar modelo
    USER_INPUT = "user_input"       # Aguardar input do usuario
    DECISION = "decision"           # Ponto de decisao
    VALIDATION = "validation"       # Validar resultado anterior


@dataclass
class PlannedStep:
    """Um passo planejado"""
    description: str
    step_type: StepType
    skill_name: Optional[str] = None
    requires_model: bool = False
    model_capability: Optional[str] = None
    depends_on: List[int] = field(default_factory=list)  # Indices de passos
    validation_rule: Optional[str] = None
    context_needed: List[str] = field(default_factory=list)  # Chaves de contexto
    estimated_complexity: float = 0.5  # 0-1


@dataclass
class ExecutionPlan:
    """Um plano de execucao"""
    id: str
    goal: str
    complexity: TaskComplexity
    steps: List[PlannedStep]
    created_at: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    estimated_total_complexity: float = 0.0
    can_parallelize: bool = False
    requires_user_confirmation: bool = False

    def step_count(self) -> int:
        """Numero de passos"""
        return len(self.steps)

    def to_task(self) -> Task:
        """Converte para Task executavel"""
        task_memory = get_task_memory()
        return task_memory.create_task(
            description=self.goal,
            complexity=self.complexity,
            steps=[s.description for s in self.steps],
            priority=2 if self.estimated_total_complexity > 0.7 else 1,
            context=self.context
        )


class Planner:
    """
    Sistema de planejamento.

    Decompoe tarefas complexas em passos executaveis
    usando regras explicitas, nao ML.
    """

    # =========================================================================
    # REGRAS DE DECOMPOSICAO
    # =========================================================================

    DECOMPOSITION_RULES = {
        'code_creation': {
            'patterns': [
                r'(?:crie|escreva|implemente|faca).*(?:codigo|funcao|classe|script)',
                r'(?:programa|aplicacao|sistema).*(?:que|para)',
            ],
            'steps': [
                {'desc': 'Entender requisitos', 'type': StepType.MODEL, 'cap': 'analysis'},
                {'desc': 'Definir estrutura', 'type': StepType.MODEL, 'cap': 'code_strong'},
                {'desc': 'Implementar codigo', 'type': StepType.MODEL, 'cap': 'code_strong'},
                {'desc': 'Revisar e validar', 'type': StepType.VALIDATION},
            ],
            'complexity': TaskComplexity.MULTI_STEP
        },
        'code_fix': {
            'patterns': [
                r'(?:conserte|corrija|arrume|fix).*(?:bug|erro|problema)',
                r'(?:nao funciona|esta quebrado|deu erro)',
            ],
            'steps': [
                {'desc': 'Identificar o erro', 'type': StepType.MODEL, 'cap': 'analysis'},
                {'desc': 'Localizar causa raiz', 'type': StepType.MODEL, 'cap': 'code_strong'},
                {'desc': 'Aplicar correcao', 'type': StepType.MODEL, 'cap': 'code_strong'},
                {'desc': 'Testar correcao', 'type': StepType.VALIDATION},
            ],
            'complexity': TaskComplexity.MULTI_STEP
        },
        'explanation': {
            'patterns': [
                r'(?:explique|explica).*(?:como|por que|o que)',
                r'(?:me ensine|ensina).*(?:sobre|como)',
            ],
            'steps': [
                {'desc': 'Identificar conceito', 'type': StepType.MODEL, 'cap': 'analysis'},
                {'desc': 'Elaborar explicacao', 'type': StepType.MODEL, 'cap': 'chat_quality'},
            ],
            'complexity': TaskComplexity.SIMPLE
        },
        'research': {
            'patterns': [
                r'(?:pesquise|busque|encontre).*(?:sobre|informacoes)',
                r'(?:qual|quais).*(?:melhor|melhores|opcoes)',
            ],
            'steps': [
                {'desc': 'Entender escopo', 'type': StepType.MODEL, 'cap': 'analysis'},
                {'desc': 'Buscar informacoes', 'type': StepType.SKILL, 'skill': 'web_search'},
                {'desc': 'Sintetizar resultados', 'type': StepType.MODEL, 'cap': 'analysis'},
            ],
            'complexity': TaskComplexity.MULTI_STEP
        },
        'planning': {
            'patterns': [
                r'(?:planeje|organize|estruture).*(?:projeto|tarefa|trabalho)',
                r'(?:crie|faca).*(?:plano|roadmap|cronograma)',
            ],
            'steps': [
                {'desc': 'Definir objetivo', 'type': StepType.USER_INPUT},
                {'desc': 'Listar requisitos', 'type': StepType.MODEL, 'cap': 'analysis'},
                {'desc': 'Decompor em tarefas', 'type': StepType.MODEL, 'cap': 'chat_quality'},
                {'desc': 'Organizar sequencia', 'type': StepType.MODEL, 'cap': 'chat_quality'},
                {'desc': 'Confirmar com usuario', 'type': StepType.USER_INPUT},
            ],
            'complexity': TaskComplexity.DEPENDENT
        },
        'file_operation': {
            'patterns': [
                r'(?:leia|abra|carregue).*(?:arquivo|ficheiro)',
                r'(?:salve|escreva|grave).*(?:arquivo|ficheiro)',
            ],
            'steps': [
                {'desc': 'Executar operacao de arquivo', 'type': StepType.SKILL, 'skill': 'file_ops'},
            ],
            'complexity': TaskComplexity.SIMPLE
        },
        'calculation': {
            'patterns': [
                r'(?:calcule|compute|some|subtraia|multiplique|divida)',
                r'(?:quanto e|qual o resultado)',
            ],
            'steps': [
                {'desc': 'Executar calculo', 'type': StepType.SKILL, 'skill': 'calculator'},
            ],
            'complexity': TaskComplexity.SIMPLE
        }
    }

    # =========================================================================
    # PLANNING
    # =========================================================================

    def __init__(self):
        self._plan_counter = 0

    def create_plan(
        self,
        goal: str,
        context: Dict[str, Any] = None
    ) -> ExecutionPlan:
        """
        Cria plano de execucao para um objetivo.

        Args:
            goal: Objetivo/tarefa do usuario
            context: Contexto adicional

        Returns:
            ExecutionPlan com passos decompostos
        """
        self._plan_counter += 1
        plan_id = f"plan_{datetime.now().strftime('%H%M%S')}_{self._plan_counter}"

        goal_lower = goal.lower()
        context = context or {}

        # Encontrar regra de decomposicao
        matched_rule = None
        for rule_name, rule in self.DECOMPOSITION_RULES.items():
            for pattern in rule.get('patterns', []):
                if re.search(pattern, goal_lower, re.IGNORECASE):
                    matched_rule = rule
                    break
            if matched_rule:
                break

        # Se nao encontrou regra, usar plano generico
        if not matched_rule:
            return self._create_generic_plan(plan_id, goal, context)

        # Criar passos do plano
        steps = []
        total_complexity = 0.0

        for i, step_def in enumerate(matched_rule.get('steps', [])):
            step = PlannedStep(
                description=step_def['desc'],
                step_type=step_def.get('type', StepType.MODEL),
                skill_name=step_def.get('skill'),
                requires_model=step_def.get('type') == StepType.MODEL,
                model_capability=step_def.get('cap'),
                estimated_complexity=step_def.get('complexity', 0.5)
            )
            steps.append(step)
            total_complexity += step.estimated_complexity

        # Verificar se precisa confirmacao
        requires_confirmation = (
            matched_rule.get('complexity') in [TaskComplexity.DEPENDENT, TaskComplexity.RESUMABLE]
            or len(steps) > 3
        )

        return ExecutionPlan(
            id=plan_id,
            goal=goal,
            complexity=matched_rule.get('complexity', TaskComplexity.MULTI_STEP),
            steps=steps,
            context=context,
            estimated_total_complexity=total_complexity / len(steps) if steps else 0,
            requires_user_confirmation=requires_confirmation
        )

    def _create_generic_plan(
        self,
        plan_id: str,
        goal: str,
        context: Dict
    ) -> ExecutionPlan:
        """Cria plano generico para tarefas nao mapeadas"""
        steps = [
            PlannedStep(
                description="Analisar solicitacao",
                step_type=StepType.MODEL,
                requires_model=True,
                model_capability='analysis',
                estimated_complexity=0.3
            ),
            PlannedStep(
                description="Processar e responder",
                step_type=StepType.MODEL,
                requires_model=True,
                model_capability='chat_quality',
                estimated_complexity=0.5
            )
        ]

        return ExecutionPlan(
            id=plan_id,
            goal=goal,
            complexity=TaskComplexity.SIMPLE,
            steps=steps,
            context=context,
            estimated_total_complexity=0.4,
            requires_user_confirmation=False
        )

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def classify_task(self, user_input: str) -> TaskComplexity:
        """
        Classifica complexidade de uma tarefa.

        Returns:
            TaskComplexity
        """
        input_lower = user_input.lower()

        # Indicadores de tarefa simples
        simple_indicators = [
            r'^(?:oi|ola|hey|hi)',
            r'^(?:obrigad|valeu|brigad)',
            r'^(?:que horas|qual hora)',
            r'^(?:calcul|quanto e)',
        ]
        if any(re.search(p, input_lower) for p in simple_indicators):
            return TaskComplexity.SIMPLE

        # Indicadores de tarefa multi-step
        multi_step_indicators = [
            r'(?:crie|implemente|desenvolva).*(?:sistema|aplicacao|programa)',
            r'(?:faca|construa).*(?:completo|inteiro)',
            r'(?:primeiro|depois|em seguida)',
        ]
        if any(re.search(p, input_lower) for p in multi_step_indicators):
            return TaskComplexity.MULTI_STEP

        # Indicadores de tarefa com dependencias
        dependent_indicators = [
            r'(?:baseado em|usando o resultado)',
            r'(?:se.*entao|caso.*faca)',
            r'(?:depende de|precisa de)',
        ]
        if any(re.search(p, input_lower) for p in dependent_indicators):
            return TaskComplexity.DEPENDENT

        # Indicadores de tarefa resumivel
        resumable_indicators = [
            r'(?:continue|retome|volte)',
            r'(?:pause|para|interrompa)',
            r'(?:onde paramos|onde estava)',
        ]
        if any(re.search(p, input_lower) for p in resumable_indicators):
            return TaskComplexity.RESUMABLE

        # Default
        word_count = len(user_input.split())
        if word_count < 10:
            return TaskComplexity.SIMPLE
        elif word_count < 30:
            return TaskComplexity.MULTI_STEP
        else:
            return TaskComplexity.DEPENDENT

    def needs_planning(self, user_input: str) -> bool:
        """
        Determina se uma tarefa precisa de planejamento.

        Returns:
            True se precisa de plano explicito
        """
        complexity = self.classify_task(user_input)
        return complexity in [TaskComplexity.MULTI_STEP, TaskComplexity.DEPENDENT]

    def estimate_steps(self, user_input: str) -> int:
        """Estima numero de passos para uma tarefa"""
        plan = self.create_plan(user_input)
        return plan.step_count()

    # =========================================================================
    # FORMATTING
    # =========================================================================

    def format_plan(self, plan: ExecutionPlan) -> str:
        """Formata plano para exibicao"""
        lines = [
            f"Plano: {plan.goal}",
            f"Complexidade: {plan.complexity.value}",
            f"Passos: {plan.step_count()}",
            ""
        ]

        for i, step in enumerate(plan.steps, 1):
            step_type = step.step_type.value
            skill_info = f" [{step.skill_name}]" if step.skill_name else ""
            model_info = f" (modelo: {step.model_capability})" if step.model_capability else ""
            lines.append(f"  {i}. {step.description}{skill_info}{model_info}")

        if plan.requires_user_confirmation:
            lines.append("")
            lines.append("* Este plano requer confirmacao antes de executar.")

        return "\n".join(lines)

    def get_decomposition_rules_summary(self) -> Dict:
        """Retorna resumo das regras de decomposicao"""
        return {
            rule_name: {
                'patterns_count': len(rule.get('patterns', [])),
                'steps_count': len(rule.get('steps', [])),
                'complexity': rule.get('complexity', TaskComplexity.SIMPLE).value
            }
            for rule_name, rule in self.DECOMPOSITION_RULES.items()
        }


# =============================================================================
# INSTANCIA GLOBAL (Thread-Safe Singleton)
# =============================================================================

_planner_instance: Optional[Planner] = None
_planner_lock = threading.Lock()


def get_planner() -> Planner:
    """
    Retorna instancia global do planner (thread-safe).

    Usa double-checked locking para evitar race conditions.
    """
    global _planner_instance
    if _planner_instance is None:
        with _planner_lock:
            # Double-check dentro do lock
            if _planner_instance is None:
                _planner_instance = Planner()
    return _planner_instance


def create_plan(goal: str, context: Dict = None) -> ExecutionPlan:
    """Shortcut para create_plan"""
    return get_planner().create_plan(goal, context)


def needs_planning(user_input: str) -> bool:
    """Shortcut para needs_planning"""
    return get_planner().needs_planning(user_input)
