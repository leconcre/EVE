# core/feature_flags.py
"""
Sistema de Feature Flags para migração incremental da EVE.
Permite habilitar/desabilitar features sem quebrar o sistema.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os
import json
from pathlib import Path


@dataclass
class FeatureFlags:
    """
    Feature flags para migração incremental.
    Permite habilitar/desabilitar features sem quebrar o sistema.
    """
    # === Sistema Core ===
    ENABLE_BRAIN_V2: bool = False         # Novo Brain com capabilities
    ENABLE_LAYERED_MEMORY: bool = False   # Nova memória em camadas
    ENABLE_SKILLS: bool = False           # Sistema de skills
    ENABLE_INTERNAL_STATE: bool = False   # Estado interno

    # === Sub-features ===
    ENABLE_EXECUTION_POLICY: bool = False # offline/hybrid/pro
    ENABLE_HEURISTIC_SUMMARY: bool = False # Resumo sem LLM
    ENABLE_MEMORY_CLEANER: bool = False   # Anti-lixo + dedupe
    ENABLE_CONTEXT_TOOLS: bool = False    # Separação context/tools
    ENABLE_CAPABILITY_ROUTING: bool = False  # Router por capability

    # === EVE 2.0 Phase 1 ===
    ENABLE_COGNITIVE_TRACE: bool = False  # Sistema de trace cognitivo
    ENABLE_MODEL_POLICY: bool = False     # Politica de uso de modelos
    ENABLE_SESSION_STATE: bool = False    # Estado de sessao
    ENABLE_TASK_MEMORY: bool = False      # Memoria de tarefas
    ENABLE_PLANNER: bool = False          # Sistema de planejamento
    ENABLE_TASK_ENGINE: bool = False      # Motor de execucao

    # === Debug ===
    DEBUG_BRAIN_DECISIONS: bool = False   # Log decisões do brain
    DEBUG_SKILL_SELECTION: bool = False   # Log seleção de skills
    DEBUG_MODEL_ROUTING: bool = False     # Log routing de modelos
    DEBUG_MEMORY_OPS: bool = False        # Log operações de memória
    DEBUG_CONTEXT_COLLECTION: bool = False  # Log coleta de contexto
    DEBUG_COGNITIVE_TRACE: bool = False   # Log do cognitive trace
    DEBUG_PLANNER: bool = False           # Log do planner
    DEBUG_TASK_ENGINE: bool = False       # Log do task engine

    # === Experimental ===
    EXPERIMENTAL_PARALLEL_TOOLS: bool = False  # Execução paralela de tools
    EXPERIMENTAL_LLM_SUMMARY: bool = False     # Resumo com LLM (opcional)

    @classmethod
    def load(cls, path: Optional[str] = None) -> 'FeatureFlags':
        """Carrega flags de arquivo JSON"""
        if path is None:
            # Preferir o data/ do diretório de trabalho (padrão do runtime:
            # eve_web/GUI fazem chdir para a raiz; no exe PyInstaller o
            # __file__ aponta para dentro do bundle e não serve de base)
            cwd_path = Path('data') / 'eve_features.json'
            if cwd_path.exists():
                path = cwd_path
            else:
                project_root = Path(__file__).parent.parent
                path = project_root / 'data' / 'eve_features.json'

        path = Path(path)

        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Filtrar apenas campos válidos
                valid_fields = {k for k in cls.__dataclass_fields__}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                return cls(**filtered_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[FeatureFlags] Erro ao carregar {path}: {e}")

        return cls()

    def save(self, path: Optional[str] = None):
        """Salva flags em arquivo JSON"""
        if path is None:
            # Espelha a lógica do load(): CWD primeiro (ver comentário lá)
            if (Path('data')).is_dir():
                path = Path('data') / 'eve_features.json'
            else:
                project_root = Path(__file__).parent.parent
                path = project_root / 'data' / 'eve_features.json'

        path = Path(path)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[FeatureFlags] Erro ao salvar {path}: {e}")

    @classmethod
    def from_env(cls) -> 'FeatureFlags':
        """Carrega flags de variáveis de ambiente"""
        flags = cls()
        for field_name in flags.__dataclass_fields__:
            env_key = f'EVE_{field_name}'
            env_val = os.environ.get(env_key)
            if env_val is not None:
                setattr(flags, field_name, env_val.lower() in ('true', '1', 'yes'))
        return flags

    @classmethod
    def from_env_with_file_fallback(cls, path: Optional[str] = None) -> 'FeatureFlags':
        """
        Carrega flags com prioridade:
        1. Variáveis de ambiente (maior prioridade)
        2. Arquivo JSON (fallback)
        3. Defaults (último recurso)
        """
        # Carregar do arquivo primeiro
        flags = cls.load(path)

        # Sobrescrever com variáveis de ambiente
        for field_name in flags.__dataclass_fields__:
            env_key = f'EVE_{field_name}'
            env_val = os.environ.get(env_key)
            if env_val is not None:
                setattr(flags, field_name, env_val.lower() in ('true', '1', 'yes'))

        return flags

    def to_dict(self) -> Dict[str, bool]:
        """Converte para dicionário"""
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def is_enabled(self, feature: str) -> bool:
        """Verifica se uma feature está habilitada"""
        return getattr(self, feature, False)

    def enable(self, feature: str):
        """Habilita uma feature"""
        if hasattr(self, feature):
            setattr(self, feature, True)

    def disable(self, feature: str):
        """Desabilita uma feature"""
        if hasattr(self, feature):
            setattr(self, feature, False)

    def get_enabled_features(self) -> list:
        """Retorna lista de features habilitadas"""
        return [k for k, v in self.to_dict().items() if v]

    def get_disabled_features(self) -> list:
        """Retorna lista de features desabilitadas"""
        return [k for k, v in self.to_dict().items() if not v]

    def __repr__(self) -> str:
        enabled = self.get_enabled_features()
        return f"FeatureFlags(enabled={enabled})"


# Instância global - carregada automaticamente
FLAGS = FeatureFlags.from_env_with_file_fallback()


def reload_flags():
    """Recarrega as flags do arquivo/ambiente"""
    global FLAGS
    FLAGS = FeatureFlags.from_env_with_file_fallback()


def get_flag(name: str) -> bool:
    """Getter conveniente para flags"""
    return FLAGS.is_enabled(name)


# Funções de conveniência para verificação rápida
def brain_v2_enabled() -> bool:
    return FLAGS.ENABLE_BRAIN_V2


def layered_memory_enabled() -> bool:
    return FLAGS.ENABLE_LAYERED_MEMORY


def skills_enabled() -> bool:
    return FLAGS.ENABLE_SKILLS


def internal_state_enabled() -> bool:
    return FLAGS.ENABLE_INTERNAL_STATE


def debug_enabled(component: str = None) -> bool:
    """Verifica se debug está habilitado para um componente"""
    if component is None:
        return any([
            FLAGS.DEBUG_BRAIN_DECISIONS,
            FLAGS.DEBUG_SKILL_SELECTION,
            FLAGS.DEBUG_MODEL_ROUTING,
            FLAGS.DEBUG_MEMORY_OPS,
            FLAGS.DEBUG_CONTEXT_COLLECTION,
            FLAGS.DEBUG_COGNITIVE_TRACE,
            FLAGS.DEBUG_PLANNER,
            FLAGS.DEBUG_TASK_ENGINE
        ])

    debug_map = {
        'brain': FLAGS.DEBUG_BRAIN_DECISIONS,
        'skills': FLAGS.DEBUG_SKILL_SELECTION,
        'routing': FLAGS.DEBUG_MODEL_ROUTING,
        'memory': FLAGS.DEBUG_MEMORY_OPS,
        'context': FLAGS.DEBUG_CONTEXT_COLLECTION,
        'trace': FLAGS.DEBUG_COGNITIVE_TRACE,
        'planner': FLAGS.DEBUG_PLANNER,
        'task_engine': FLAGS.DEBUG_TASK_ENGINE
    }
    return debug_map.get(component, False)


# === Convenience functions for new components ===

def cognitive_trace_enabled() -> bool:
    return FLAGS.ENABLE_COGNITIVE_TRACE


def model_policy_enabled() -> bool:
    return FLAGS.ENABLE_MODEL_POLICY


def session_state_enabled() -> bool:
    return FLAGS.ENABLE_SESSION_STATE


def task_memory_enabled() -> bool:
    return FLAGS.ENABLE_TASK_MEMORY


def planner_enabled() -> bool:
    return FLAGS.ENABLE_PLANNER


def task_engine_enabled() -> bool:
    return FLAGS.ENABLE_TASK_ENGINE
