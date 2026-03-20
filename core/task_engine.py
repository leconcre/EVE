# core/task_engine.py
"""
Motor de execucao de tarefas da EVE.
Executa planos passo a passo com suporte a pause/resume.

Principio: Execucao controlada com checkpoints explicitos.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from enum import Enum
import asyncio
import threading
import ast
import operator
import logging

from core.planner import ExecutionPlan, PlannedStep, StepType, get_planner

logger = logging.getLogger("eve.task_engine")


# =============================================================================
# SAFE EXPRESSION EVALUATOR (replaces unsafe eval())
# =============================================================================

class SafeExpressionEvaluator:
    """
    Avaliador seguro de expressoes.
    Substitui eval() para evitar injecao de codigo.

    Suporta:
    - Comparacoes: ==, !=, <, >, <=, >=
    - Operadores logicos: and, or, not
    - Operadores aritmeticos: +, -, *, /
    - Acesso a variaveis do contexto via ctx['key'] ou ctx.get('key')
    - Valores literais: numeros, strings, booleans, None
    """

    # Operadores seguros permitidos
    SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Not: operator.not_,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
    }

    def __init__(self, context: Dict[str, Any] = None):
        self.context = context or {}

    def evaluate(self, expression: str) -> Any:
        """
        Avalia expressao de forma segura.

        Args:
            expression: Expressao a avaliar

        Returns:
            Resultado da avaliacao

        Raises:
            ValueError: Se expressao for invalida ou insegura
        """
        try:
            tree = ast.parse(expression, mode='eval')
            return self._eval_node(tree.body)
        except SyntaxError as e:
            raise ValueError(f"Sintaxe invalida: {e}")
        except Exception as e:
            raise ValueError(f"Erro ao avaliar expressao: {e}")

    def _eval_node(self, node: ast.AST) -> Any:
        """Avalia um no da AST de forma segura"""

        # Constantes (numeros, strings, None, True, False)
        if isinstance(node, ast.Constant):
            return node.value

        # Compatibilidade com Python < 3.8
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Str):
            return node.s
        if isinstance(node, ast.NameConstant):
            return node.value

        # Nome de variavel (acesso ao contexto)
        if isinstance(node, ast.Name):
            name = node.id
            if name == 'ctx':
                return self.context
            if name == 'True':
                return True
            if name == 'False':
                return False
            if name == 'None':
                return None
            # Buscar no contexto
            if name in self.context:
                return self.context[name]
            raise ValueError(f"Variavel nao definida: {name}")

        # Operacao binaria
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type not in self.SAFE_OPERATORS:
                raise ValueError(f"Operador nao permitido: {op_type.__name__}")
            return self.SAFE_OPERATORS[op_type](left, right)

        # Operacao unaria
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type not in self.SAFE_OPERATORS:
                raise ValueError(f"Operador unario nao permitido: {op_type.__name__}")
            return self.SAFE_OPERATORS[op_type](operand)

        # Comparacao
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)
                op_type = type(op)
                if op_type not in self.SAFE_OPERATORS:
                    raise ValueError(f"Comparador nao permitido: {op_type.__name__}")
                if not self.SAFE_OPERATORS[op_type](left, right):
                    return False
                left = right
            return True

        # Operacao booleana (and, or)
        if isinstance(node, ast.BoolOp):
            op_type = type(node.op)
            if op_type not in self.SAFE_OPERATORS:
                raise ValueError(f"Operador booleano nao permitido: {op_type.__name__}")

            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self._eval_node(value):
                        return False
                return True
            else:  # Or
                for value in node.values:
                    if self._eval_node(value):
                        return True
                return False

        # Subscript (ctx['key'])
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value)
            # Python 3.9+ usa node.slice diretamente
            if isinstance(node.slice, ast.Index):
                key = self._eval_node(node.slice.value)
            else:
                key = self._eval_node(node.slice)
            if isinstance(value, dict):
                return value.get(key)
            raise ValueError("Subscript so permitido em dicionarios")

        # Atributo (ctx.get)
        if isinstance(node, ast.Attribute):
            value = self._eval_node(node.value)
            attr = node.attr
            # Apenas permite .get() em dicionarios
            if attr == 'get' and isinstance(value, dict):
                return value.get
            raise ValueError(f"Acesso a atributo nao permitido: {attr}")

        # Chamada de funcao (apenas ctx.get())
        if isinstance(node, ast.Call):
            func = self._eval_node(node.func)
            # Verifica se e um metodo get de dict
            if hasattr(func, '__self__') and isinstance(func.__self__, dict) and func.__name__ == 'get':
                args = [self._eval_node(arg) for arg in node.args]
                return func(*args)
            raise ValueError("Chamada de funcao nao permitida")

        # Lista
        if isinstance(node, ast.List):
            return [self._eval_node(elem) for elem in node.elts]

        # Tupla
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elem) for elem in node.elts)

        # Dict
        if isinstance(node, ast.Dict):
            return {
                self._eval_node(k): self._eval_node(v)
                for k, v in zip(node.keys, node.values)
            }

        # Expressao ternaria (a if b else c)
        if isinstance(node, ast.IfExp):
            if self._eval_node(node.test):
                return self._eval_node(node.body)
            return self._eval_node(node.orelse)

        raise ValueError(f"Tipo de expressao nao suportado: {type(node).__name__}")


def safe_eval(expression: str, context: Dict[str, Any] = None) -> Any:
    """
    Avalia expressao de forma segura.

    Substitui eval() inseguro.

    Args:
        expression: Expressao a avaliar
        context: Dicionario de contexto (acessivel via 'ctx')

    Returns:
        Resultado da avaliacao
    """
    evaluator = SafeExpressionEvaluator({'ctx': context or {}})
    return evaluator.evaluate(expression)


from memory.task_memory import (
    Task, TaskStep, TaskStatus, TaskComplexity,
    get_task_memory
)
from core.cognitive_trace import get_tracer, TraceCategory


class ExecutionState(Enum):
    """Estados de execucao"""
    IDLE = "idle"                   # Ocioso
    RUNNING = "running"             # Executando
    PAUSED = "paused"               # Pausado
    WAITING_USER = "waiting_user"   # Aguardando usuario
    COMPLETED = "completed"         # Concluido
    FAILED = "failed"               # Falhou


@dataclass
class StepResult:
    """Resultado de um passo"""
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: int = 0
    needs_user_input: bool = False
    user_prompt: Optional[str] = None


@dataclass
class ExecutionContext:
    """Contexto de execucao"""
    task_id: str
    plan: ExecutionPlan
    current_step: int = 0
    state: ExecutionState = ExecutionState.IDLE
    step_results: Dict[int, StepResult] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    variables: Dict[str, Any] = field(default_factory=dict)


class TaskEngine:
    """
    Motor de execucao de tarefas.

    Funcionalidades:
    - Executar planos passo a passo
    - Pause/resume de execucao
    - Checkpoints automaticos
    - Rollback em caso de erro
    """

    def __init__(self):
        self._active_context: Optional[ExecutionContext] = None
        self._task_memory = get_task_memory()
        self._tracer = get_tracer()
        self._step_handlers: Dict[StepType, Callable] = {}
        self._register_default_handlers()

    # =========================================================================
    # HANDLER REGISTRATION
    # =========================================================================

    def _register_default_handlers(self):
        """Registra handlers padrao para tipos de passo"""
        self._step_handlers[StepType.SKILL] = self._handle_skill_step
        self._step_handlers[StepType.MODEL] = self._handle_model_step
        self._step_handlers[StepType.USER_INPUT] = self._handle_user_input_step
        self._step_handlers[StepType.DECISION] = self._handle_decision_step
        self._step_handlers[StepType.VALIDATION] = self._handle_validation_step

    def register_handler(self, step_type: StepType, handler: Callable):
        """Registra handler customizado"""
        self._step_handlers[step_type] = handler

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def start_execution(self, plan: ExecutionPlan) -> ExecutionContext:
        """
        Inicia execucao de um plano.

        Args:
            plan: Plano a executar

        Returns:
            ExecutionContext
        """
        # Criar task na memoria
        task = plan.to_task()

        context = ExecutionContext(
            task_id=task.id,
            plan=plan,
            state=ExecutionState.RUNNING,
            started_at=datetime.now()
        )

        self._active_context = context
        self._task_memory.start_task(task.id)

        # Trace
        self._tracer.trace_planning(
            action='started',
            plan_id=plan.id,
            details={'task_id': task.id, 'steps': plan.step_count()}
        )

        return context

    def execute_next_step(
        self,
        skill_executor: Callable = None,
        model_executor: Callable = None
    ) -> Tuple[StepResult, bool]:
        """
        Executa proximo passo.

        Args:
            skill_executor: Funcao para executar skills
            model_executor: Funcao para chamar modelo

        Returns:
            (StepResult, is_complete)
        """
        if not self._active_context:
            return StepResult(success=False, output=None, error="Nenhuma execucao ativa"), True

        context = self._active_context

        if context.state != ExecutionState.RUNNING:
            return StepResult(
                success=False,
                output=None,
                error=f"Execucao nao esta rodando (estado: {context.state.value})"
            ), True

        # Verificar se acabou
        if context.current_step >= len(context.plan.steps):
            context.state = ExecutionState.COMPLETED
            self._complete_execution()
            return StepResult(success=True, output="Plano concluido"), True

        # Obter passo atual
        step = context.plan.steps[context.current_step]
        start_time = datetime.now()

        # Executar handler
        handler = self._step_handlers.get(step.step_type)
        if not handler:
            result = StepResult(
                success=False,
                output=None,
                error=f"Handler nao encontrado para {step.step_type.value}"
            )
        else:
            try:
                result = handler(
                    step,
                    context,
                    skill_executor=skill_executor,
                    model_executor=model_executor
                )
            except Exception as e:
                result = StepResult(
                    success=False,
                    output=None,
                    error=str(e)
                )

        # Calcular duracao
        result.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # Armazenar resultado
        context.step_results[context.current_step] = result

        # Atualizar task memory
        task = self._task_memory.get_task(context.task_id)
        if task:
            if result.success:
                self._task_memory.complete_step(
                    context.task_id,
                    result=str(result.output)[:200] if result.output else None
                )
            else:
                self._task_memory.fail_step(
                    context.task_id,
                    error=result.error
                )
                context.state = ExecutionState.FAILED
                return result, True

        # Aguardar usuario se necessario
        if result.needs_user_input:
            context.state = ExecutionState.WAITING_USER
            return result, False

        # Avancar para proximo passo
        context.current_step += 1

        # Verificar se acabou
        is_complete = context.current_step >= len(context.plan.steps)
        if is_complete:
            context.state = ExecutionState.COMPLETED
            self._complete_execution()

        return result, is_complete

    def provide_user_input(self, user_input: str) -> bool:
        """
        Fornece input do usuario para continuar execucao.

        Returns:
            True se pode continuar
        """
        if not self._active_context:
            return False

        context = self._active_context

        if context.state != ExecutionState.WAITING_USER:
            return False

        # Armazenar input
        context.variables['last_user_input'] = user_input

        # Retomar execucao
        context.state = ExecutionState.RUNNING
        context.current_step += 1

        return True

    def pause_execution(self) -> bool:
        """Pausa execucao atual"""
        if not self._active_context:
            return False

        context = self._active_context

        if context.state != ExecutionState.RUNNING:
            return False

        context.state = ExecutionState.PAUSED
        context.paused_at = datetime.now()

        self._task_memory.pause_task(context.task_id)

        self._tracer.trace_planning(
            action='paused',
            plan_id=context.plan.id,
            details={'at_step': context.current_step}
        )

        return True

    def resume_execution(self) -> bool:
        """Retoma execucao pausada"""
        if not self._active_context:
            return False

        context = self._active_context

        if context.state != ExecutionState.PAUSED:
            return False

        context.state = ExecutionState.RUNNING
        context.paused_at = None

        self._task_memory.resume_task(context.task_id)

        self._tracer.trace_planning(
            action='resumed',
            plan_id=context.plan.id,
            details={'from_step': context.current_step}
        )

        return True

    def cancel_execution(self) -> bool:
        """Cancela execucao atual"""
        if not self._active_context:
            return False

        context = self._active_context
        context.state = ExecutionState.FAILED

        self._task_memory.cancel_task(context.task_id)

        self._tracer.trace_planning(
            action='cancelled',
            plan_id=context.plan.id,
            details={'at_step': context.current_step}
        )

        self._active_context = None
        return True

    def _complete_execution(self):
        """Finaliza execucao"""
        if not self._active_context:
            return

        context = self._active_context

        self._task_memory.complete_task(
            context.task_id,
            result="Plano executado com sucesso"
        )

        self._tracer.trace_planning(
            action='completed',
            plan_id=context.plan.id,
            details={
                'steps_executed': context.current_step,
                'total_steps': len(context.plan.steps)
            }
        )

        self._active_context = None

    # =========================================================================
    # STEP HANDLERS
    # =========================================================================

    def _handle_skill_step(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        skill_executor: Callable = None,
        **kwargs
    ) -> StepResult:
        """Handler para passos de skill"""
        if not skill_executor:
            return StepResult(
                success=False,
                output=None,
                error="Executor de skill nao fornecido"
            )

        if not step.skill_name:
            return StepResult(
                success=False,
                output=None,
                error="Nome da skill nao especificado"
            )

        try:
            result = skill_executor(step.skill_name, context.variables)
            return StepResult(
                success=True,
                output=result
            )
        except Exception as e:
            return StepResult(
                success=False,
                output=None,
                error=str(e)
            )

    def _handle_model_step(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        model_executor: Callable = None,
        **kwargs
    ) -> StepResult:
        """Handler para passos de modelo"""
        if not model_executor:
            return StepResult(
                success=False,
                output=None,
                error="Executor de modelo nao fornecido"
            )

        try:
            # Construir prompt
            prompt = self._build_step_prompt(step, context)

            result = model_executor(
                prompt,
                capability=step.model_capability
            )

            # Armazenar resultado em variaveis
            context.variables[f'step_{context.current_step}_result'] = result

            return StepResult(
                success=True,
                output=result
            )
        except Exception as e:
            return StepResult(
                success=False,
                output=None,
                error=str(e)
            )

    def _handle_user_input_step(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        **kwargs
    ) -> StepResult:
        """Handler para passos que requerem input do usuario"""
        return StepResult(
            success=True,
            output=None,
            needs_user_input=True,
            user_prompt=step.description
        )

    def _handle_decision_step(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        **kwargs
    ) -> StepResult:
        """Handler para passos de decisao"""
        # Verificar condicao se especificada
        if step.validation_rule:
            # Avaliar regra de forma SEGURA (sem eval())
            try:
                result = safe_eval(step.validation_rule, context.variables)
                return StepResult(
                    success=True,
                    output=result
                )
            except ValueError as e:
                logger.warning(f"Regra de validacao invalida: {e}")
                return StepResult(
                    success=False,
                    output=None,
                    error=f"Erro ao avaliar regra: {e}"
                )
            except Exception as e:
                logger.error(f"Erro inesperado ao avaliar regra: {e}")
                return StepResult(
                    success=False,
                    output=None,
                    error=f"Erro ao avaliar regra: {e}"
                )

        return StepResult(success=True, output="Decisao automatica")

    def _handle_validation_step(
        self,
        step: PlannedStep,
        context: ExecutionContext,
        **kwargs
    ) -> StepResult:
        """Handler para passos de validacao"""
        # Verificar resultado do passo anterior
        prev_step = context.current_step - 1
        if prev_step < 0:
            return StepResult(success=True, output="Nada a validar")

        prev_result = context.step_results.get(prev_step)
        if not prev_result:
            return StepResult(
                success=False,
                output=None,
                error="Resultado anterior nao encontrado"
            )

        if not prev_result.success:
            return StepResult(
                success=False,
                output=None,
                error=f"Passo anterior falhou: {prev_result.error}"
            )

        return StepResult(
            success=True,
            output=f"Validado: {str(prev_result.output)[:100]}"
        )

    def _build_step_prompt(
        self,
        step: PlannedStep,
        context: ExecutionContext
    ) -> str:
        """Constroi prompt para passo de modelo"""
        parts = [
            f"Tarefa: {context.plan.goal}",
            f"Passo atual: {step.description}",
        ]

        # Adicionar resultados anteriores relevantes
        if context.step_results:
            parts.append("\nResultados anteriores:")
            for i, result in context.step_results.items():
                if result.success and result.output:
                    output_preview = str(result.output)[:200]
                    parts.append(f"  Passo {i+1}: {output_preview}")

        # Adicionar contexto do usuario
        if 'last_user_input' in context.variables:
            parts.append(f"\nInput do usuario: {context.variables['last_user_input']}")

        return "\n".join(parts)

    # =========================================================================
    # STATUS & QUERIES
    # =========================================================================

    def get_status(self) -> Dict:
        """Retorna status atual"""
        if not self._active_context:
            return {
                'state': ExecutionState.IDLE.value,
                'active': False
            }

        context = self._active_context

        return {
            'state': context.state.value,
            'active': True,
            'task_id': context.task_id,
            'plan_id': context.plan.id,
            'goal': context.plan.goal,
            'current_step': context.current_step,
            'total_steps': len(context.plan.steps),
            'progress': (context.current_step / len(context.plan.steps) * 100)
                        if context.plan.steps else 0,
            'started_at': context.started_at.isoformat() if context.started_at else None,
            'paused_at': context.paused_at.isoformat() if context.paused_at else None
        }

    def get_current_step_info(self) -> Optional[Dict]:
        """Retorna info do passo atual"""
        if not self._active_context:
            return None

        context = self._active_context

        if context.current_step >= len(context.plan.steps):
            return None

        step = context.plan.steps[context.current_step]

        return {
            'index': context.current_step,
            'description': step.description,
            'type': step.step_type.value,
            'skill': step.skill_name,
            'capability': step.model_capability,
            'requires_model': step.requires_model
        }

    def get_progress_summary(self) -> str:
        """Retorna resumo do progresso"""
        if not self._active_context:
            return "Nenhuma execucao ativa"

        context = self._active_context
        status = self.get_status()

        return (
            f"Tarefa: {context.plan.goal}\n"
            f"Estado: {status['state']}\n"
            f"Progresso: {status['progress']:.0f}% "
            f"({context.current_step}/{len(context.plan.steps)} passos)"
        )

    def is_active(self) -> bool:
        """Verifica se ha execucao ativa"""
        return (
            self._active_context is not None
            and self._active_context.state in [
                ExecutionState.RUNNING,
                ExecutionState.PAUSED,
                ExecutionState.WAITING_USER
            ]
        )


# =============================================================================
# INSTANCIA GLOBAL (Thread-Safe Singleton)
# =============================================================================

_engine_instance: Optional[TaskEngine] = None
_engine_lock = threading.Lock()


def get_task_engine() -> TaskEngine:
    """
    Retorna instancia global do task engine (thread-safe).

    Usa double-checked locking para evitar race conditions.
    """
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            # Double-check dentro do lock
            if _engine_instance is None:
                _engine_instance = TaskEngine()
    return _engine_instance
