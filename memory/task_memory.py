# memory/task_memory.py
"""
Memoria de tarefas da EVE.
Gerencia tarefas ativas, pausadas e historico.

Principio: Tarefas explicitas com estado claro.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json
import uuid
import logging
import threading

logger = logging.getLogger("eve.task_memory")


class TaskStatus(Enum):
    """Status de uma tarefa"""
    PENDING = "pending"             # Aguardando inicio
    ACTIVE = "active"               # Em execucao
    PAUSED = "paused"               # Pausada pelo usuario/sistema
    BLOCKED = "blocked"             # Bloqueada por dependencia
    COMPLETED = "completed"         # Concluida com sucesso
    FAILED = "failed"               # Falhou
    CANCELLED = "cancelled"         # Cancelada


class TaskComplexity(Enum):
    """Complexidade de uma tarefa"""
    SIMPLE = "simple"               # Uma acao, sem decomposicao
    MULTI_STEP = "multi_step"       # Multiplos passos sequenciais
    DEPENDENT = "dependent"         # Depende de outras tarefas
    RESUMABLE = "resumable"         # Pode ser pausada e retomada


@dataclass
class TaskStep:
    """Um passo de uma tarefa"""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def duration_seconds(self) -> Optional[float]:
        """Duracao em segundos"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class Task:
    """Uma tarefa completa"""
    id: str
    description: str
    complexity: TaskComplexity
    status: TaskStatus = TaskStatus.PENDING
    steps: List[TaskStep] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # IDs de tarefas
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    priority: int = 1               # 1=baixa, 2=media, 3=alta

    def current_step_index(self) -> int:
        """Indice do passo atual"""
        for i, step in enumerate(self.steps):
            if step.status in [TaskStatus.PENDING, TaskStatus.ACTIVE]:
                return i
        return len(self.steps)

    def current_step(self) -> Optional[TaskStep]:
        """Retorna passo atual"""
        idx = self.current_step_index()
        if idx < len(self.steps):
            return self.steps[idx]
        return None

    def progress_percent(self) -> float:
        """Progresso em porcentagem"""
        if not self.steps:
            return 100.0 if self.status == TaskStatus.COMPLETED else 0.0
        completed = sum(1 for s in self.steps if s.status == TaskStatus.COMPLETED)
        return (completed / len(self.steps)) * 100

    def to_dict(self) -> Dict:
        """Converte para dicionario"""
        return {
            'id': self.id,
            'description': self.description,
            'complexity': self.complexity.value,
            'status': self.status.value,
            'steps': [
                {
                    'id': s.id,
                    'description': s.description,
                    'status': s.status.value,
                    'result': s.result
                }
                for s in self.steps
            ],
            'progress': self.progress_percent(),
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class TaskMemory:
    """
    Gerenciador de memoria de tarefas.

    Funcionalidades:
    - Criar e rastrear tarefas
    - Gerenciar status e progresso
    - Persistir entre sessoes
    - Historico de tarefas
    """

    def __init__(self, storage_path: str = "eve_tasks.json"):
        self._tasks: Dict[str, Task] = {}
        self._storage_path = storage_path
        self._task_counter = 0
        self._lock = threading.RLock()  # Thread-safe access
        self._load()

    # =========================================================================
    # TASK CREATION
    # =========================================================================

    def create_task(
        self,
        description: str,
        complexity: TaskComplexity = TaskComplexity.SIMPLE,
        steps: List[str] = None,
        dependencies: List[str] = None,
        priority: int = 1,
        context: Dict = None
    ) -> Task:
        """
        Cria nova tarefa.

        Args:
            description: Descricao da tarefa
            complexity: Complexidade
            steps: Lista de descricoes de passos (opcional)
            dependencies: IDs de tarefas que devem completar primeiro
            priority: 1=baixa, 2=media, 3=alta
            context: Dados de contexto

        Returns:
            Task criada
        """
        self._task_counter += 1
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._task_counter}"

        # Criar passos
        task_steps = []
        if steps:
            for i, step_desc in enumerate(steps):
                step = TaskStep(
                    id=f"{task_id}_step_{i+1}",
                    description=step_desc
                )
                task_steps.append(step)

        task = Task(
            id=task_id,
            description=description,
            complexity=complexity,
            steps=task_steps,
            dependencies=dependencies or [],
            priority=priority,
            context=context or {}
        )

        self._tasks[task_id] = task
        self._save()

        return task

    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================

    def start_task(self, task_id: str) -> bool:
        """Inicia uma tarefa"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        # Verificar dependencias
        if not self._dependencies_met(task):
            task.status = TaskStatus.BLOCKED
            return False

        task.status = TaskStatus.ACTIVE
        task.started_at = datetime.now()

        # Iniciar primeiro passo
        if task.steps:
            task.steps[0].status = TaskStatus.ACTIVE
            task.steps[0].started_at = datetime.now()

        self._save()
        return True

    def complete_step(
        self,
        task_id: str,
        step_id: str = None,
        result: str = None
    ) -> bool:
        """Completa um passo da tarefa"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        # Encontrar passo
        step = None
        if step_id:
            for s in task.steps:
                if s.id == step_id:
                    step = s
                    break
        else:
            step = task.current_step()

        if not step:
            return False

        # Completar
        step.status = TaskStatus.COMPLETED
        step.completed_at = datetime.now()
        step.result = result

        # Iniciar proximo passo ou completar tarefa
        next_idx = task.current_step_index()
        if next_idx < len(task.steps):
            task.steps[next_idx].status = TaskStatus.ACTIVE
            task.steps[next_idx].started_at = datetime.now()
        else:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

        self._save()
        return True

    def fail_step(
        self,
        task_id: str,
        step_id: str = None,
        error: str = None
    ) -> bool:
        """Marca passo como falho"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        # Encontrar passo
        step = task.current_step() if not step_id else None
        if step_id:
            for s in task.steps:
                if s.id == step_id:
                    step = s
                    break

        if step:
            step.status = TaskStatus.FAILED
            step.error = error
            step.completed_at = datetime.now()

        task.status = TaskStatus.FAILED
        task.error = error
        self._save()
        return True

    def complete_task(self, task_id: str, result: str = None) -> bool:
        """Completa uma tarefa (para tarefas simples)"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result

        # Completar todos os passos pendentes
        for step in task.steps:
            if step.status == TaskStatus.PENDING:
                step.status = TaskStatus.COMPLETED
                step.completed_at = datetime.now()

        self._save()
        return True

    def pause_task(self, task_id: str) -> bool:
        """Pausa uma tarefa"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.ACTIVE:
            return False

        task.status = TaskStatus.PAUSED
        task.paused_at = datetime.now()
        self._save()
        return True

    def resume_task(self, task_id: str) -> bool:
        """Retoma uma tarefa pausada"""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False

        # Verificar dependencias novamente
        if not self._dependencies_met(task):
            task.status = TaskStatus.BLOCKED
            return False

        task.status = TaskStatus.ACTIVE
        task.paused_at = None
        self._save()
        return True

    def cancel_task(self, task_id: str) -> bool:
        """Cancela uma tarefa"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        self._save()
        return True

    # =========================================================================
    # QUERIES
    # =========================================================================

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retorna tarefa por ID"""
        return self._tasks.get(task_id)

    def get_active_tasks(self) -> List[Task]:
        """Retorna tarefas ativas"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.ACTIVE]

    def get_pending_tasks(self) -> List[Task]:
        """Retorna tarefas pendentes"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_paused_tasks(self) -> List[Task]:
        """Retorna tarefas pausadas"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PAUSED]

    def get_blocked_tasks(self) -> List[Task]:
        """Retorna tarefas bloqueadas"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.BLOCKED]

    def get_recent_completed(self, limit: int = 10) -> List[Task]:
        """Retorna tarefas recentes completadas"""
        completed = [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
        completed.sort(key=lambda t: t.completed_at or datetime.min, reverse=True)
        return completed[:limit]

    def get_all_actionable(self) -> List[Task]:
        """Retorna todas as tarefas que precisam de acao"""
        actionable = []
        for task in self._tasks.values():
            if task.status in [TaskStatus.ACTIVE, TaskStatus.PENDING, TaskStatus.PAUSED]:
                actionable.append(task)
        # Ordenar por prioridade
        actionable.sort(key=lambda t: (-t.priority, t.created_at))
        return actionable

    def has_active_task(self) -> bool:
        """Verifica se ha tarefa ativa"""
        return any(t.status == TaskStatus.ACTIVE for t in self._tasks.values())

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _dependencies_met(self, task: Task) -> bool:
        """Verifica se todas as dependencias estao completas"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def check_blocked_tasks(self):
        """Verifica tarefas bloqueadas que podem ser desbloqueadas"""
        for task in self._tasks.values():
            if task.status == TaskStatus.BLOCKED:
                if self._dependencies_met(task):
                    task.status = TaskStatus.PENDING

    # =========================================================================
    # SUMMARY
    # =========================================================================

    def get_summary(self) -> str:
        """Gera resumo das tarefas"""
        active = self.get_active_tasks()
        pending = self.get_pending_tasks()
        paused = self.get_paused_tasks()

        parts = []

        if active:
            for t in active:
                progress = t.progress_percent()
                step_info = ""
                current = t.current_step()
                if current:
                    step_info = f" - Passo atual: {current.description}"
                parts.append(f"[ATIVA] {t.description} ({progress:.0f}%){step_info}")

        if paused:
            for t in paused:
                parts.append(f"[PAUSADA] {t.description}")

        if pending:
            count = len(pending)
            if count > 3:
                parts.append(f"[PENDENTES] {count} tarefas aguardando")
            else:
                for t in pending:
                    parts.append(f"[PENDENTE] {t.description}")

        if not parts:
            return "Nenhuma tarefa ativa."

        return "\n".join(parts)

    def get_stats(self) -> Dict:
        """Retorna estatisticas"""
        statuses = {}
        for task in self._tasks.values():
            status = task.status.value
            statuses[status] = statuses.get(status, 0) + 1

        return {
            'total': len(self._tasks),
            'by_status': statuses,
            'active_count': len(self.get_active_tasks()),
            'pending_count': len(self.get_pending_tasks()),
            'has_high_priority': any(t.priority == 3 for t in self.get_all_actionable())
        }

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _save(self):
        """Salva tarefas em arquivo (thread-safe)"""
        with self._lock:
            try:
                data = {
                    'task_counter': self._task_counter,
                    'tasks': {
                        tid: self._task_to_dict(task)
                        for tid, task in self._tasks.items()
                    }
                }
                with open(self._storage_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except IOError as e:
                logger.error(f"Erro ao salvar tarefas: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado ao salvar tarefas: {e}")

    def _load(self):
        """Carrega tarefas de arquivo (thread-safe)"""
        with self._lock:
            try:
                with open(self._storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._task_counter = data.get('task_counter', 0)
                    for tid, task_data in data.get('tasks', {}).items():
                        self._tasks[tid] = self._dict_to_task(task_data)
                logger.debug(f"Carregadas {len(self._tasks)} tarefas de {self._storage_path}")
            except FileNotFoundError:
                logger.debug(f"Arquivo de tarefas não encontrado: {self._storage_path}")
            except json.JSONDecodeError as e:
                logger.warning(f"Arquivo de tarefas corrompido, iniciando vazio: {e}")
            except IOError as e:
                logger.error(f"Erro ao carregar tarefas: {e}")

    def _task_to_dict(self, task: Task) -> Dict:
        """Converte Task para dict serializavel"""
        return {
            'id': task.id,
            'description': task.description,
            'complexity': task.complexity.value,
            'status': task.status.value,
            'steps': [
                {
                    'id': s.id,
                    'description': s.description,
                    'status': s.status.value,
                    'result': s.result,
                    'error': s.error,
                    'started_at': s.started_at.isoformat() if s.started_at else None,
                    'completed_at': s.completed_at.isoformat() if s.completed_at else None
                }
                for s in task.steps
            ],
            'dependencies': task.dependencies,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'paused_at': task.paused_at.isoformat() if task.paused_at else None,
            'context': task.context,
            'result': task.result,
            'error': task.error,
            'priority': task.priority
        }

    def _dict_to_task(self, data: Dict) -> Task:
        """Converte dict para Task"""
        steps = [
            TaskStep(
                id=s['id'],
                description=s['description'],
                status=TaskStatus(s['status']),
                result=s.get('result'),
                error=s.get('error'),
                started_at=datetime.fromisoformat(s['started_at']) if s.get('started_at') else None,
                completed_at=datetime.fromisoformat(s['completed_at']) if s.get('completed_at') else None
            )
            for s in data.get('steps', [])
        ]

        return Task(
            id=data['id'],
            description=data['description'],
            complexity=TaskComplexity(data.get('complexity', 'simple')),
            status=TaskStatus(data['status']),
            steps=steps,
            dependencies=data.get('dependencies', []),
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            paused_at=datetime.fromisoformat(data['paused_at']) if data.get('paused_at') else None,
            context=data.get('context', {}),
            result=data.get('result'),
            error=data.get('error'),
            priority=data.get('priority', 1)
        )

    def clear_completed(self, older_than_days: int = 7):
        """Remove tarefas completadas antigas"""
        now = datetime.now()
        to_remove = []

        for tid, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]:
                if task.completed_at:
                    age_days = (now - task.completed_at).days
                    if age_days > older_than_days:
                        to_remove.append(tid)

        for tid in to_remove:
            del self._tasks[tid]

        if to_remove:
            self._save()


# =============================================================================
# INSTANCIA GLOBAL
# =============================================================================

_task_memory: Optional[TaskMemory] = None


def get_task_memory() -> TaskMemory:
    """Retorna instancia global da memoria de tarefas"""
    global _task_memory
    if _task_memory is None:
        _task_memory = TaskMemory()
    return _task_memory
