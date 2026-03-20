# core/config.py
"""
Configurações centralizadas da EVE.
Inclui políticas de execução (offline/hybrid/pro).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import os
import time


class ExecutionPolicy(Enum):
    """Política de execução do sistema"""
    OFFLINE = "offline"   # Somente modelos locais (Ollama)
    HYBRID = "hybrid"     # Local + Cloud quando necessário
    PRO = "pro"           # Prioriza cloud para tarefas críticas


@dataclass
class PolicyConfig:
    """Configuração da política de execução"""
    policy: ExecutionPolicy = ExecutionPolicy.HYBRID

    # === Thresholds para decisão ===
    cloud_threshold: float = 0.7        # Complexidade mínima para usar cloud
    fallback_enabled: bool = True       # Se cloud falhar, tenta local
    fallback_timeout_ms: int = 5000     # Timeout antes de fallback
    cloud_retry_delay_ms: int = 1000    # Delay entre retries no cloud

    # === Limites de custo (para PRO) ===
    max_cloud_calls_per_hour: int = 100
    max_cloud_calls_per_day: int = 1000
    max_tokens_per_call: int = 8000

    # === Override por capability ===
    # Capabilities que sempre usam local (mesmo em PRO)
    force_local: List[str] = field(default_factory=lambda: ['chat_fast'])
    # Capabilities que sempre usam cloud (só em PRO, se disponível)
    force_cloud: List[str] = field(default_factory=list)

    # === Timeouts por tipo de tarefa (ms) ===
    timeout_chat: int = 30000
    timeout_code: int = 180000
    timeout_analysis: int = 60000

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyConfig':
        """Cria config a partir de dicionário"""
        # Converter policy string para enum
        if 'policy' in data and isinstance(data['policy'], str):
            data['policy'] = ExecutionPolicy(data['policy'])
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k) or k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        result = {}
        for k in self.__dataclass_fields__:
            v = getattr(self, k)
            if isinstance(v, Enum):
                result[k] = v.value
            else:
                result[k] = v
        return result


@dataclass
class PolicyState:
    """Estado runtime da política (não persistido)"""
    cloud_available: bool = True
    cloud_calls_this_hour: int = 0
    cloud_calls_today: int = 0
    last_cloud_failure: Optional[float] = None
    consecutive_failures: int = 0
    last_hour_reset: float = field(default_factory=time.time)
    last_day_reset: float = field(default_factory=time.time)

    def record_cloud_call(self):
        """Registra uma chamada ao cloud"""
        now = time.time()

        # Reset contadores se necessário
        if now - self.last_hour_reset > 3600:
            self.cloud_calls_this_hour = 0
            self.last_hour_reset = now

        if now - self.last_day_reset > 86400:
            self.cloud_calls_today = 0
            self.last_day_reset = now

        self.cloud_calls_this_hour += 1
        self.cloud_calls_today += 1

    def record_cloud_failure(self):
        """Registra falha no cloud"""
        self.last_cloud_failure = time.time()
        self.consecutive_failures += 1

        # Após 3 falhas consecutivas, marca como indisponível
        if self.consecutive_failures >= 3:
            self.cloud_available = False

    def record_cloud_success(self):
        """Registra sucesso no cloud"""
        self.consecutive_failures = 0
        self.cloud_available = True

    def can_use_cloud(self, config: PolicyConfig) -> bool:
        """Verifica se pode usar cloud agora"""
        if not self.cloud_available:
            return False

        if self.cloud_calls_this_hour >= config.max_cloud_calls_per_hour:
            return False

        if self.cloud_calls_today >= config.max_cloud_calls_per_day:
            return False

        return True

    def time_until_cloud_retry(self) -> Optional[float]:
        """Retorna tempo até poder tentar cloud novamente (segundos)"""
        if self.cloud_available:
            return 0

        if self.last_cloud_failure is None:
            return 0

        # Espera 5 minutos após falhas consecutivas
        wait_time = 300 - (time.time() - self.last_cloud_failure)
        return max(0, wait_time)


@dataclass
class ModelLimits:
    """Limites e configurações de modelo"""
    context_window: int = 4096
    max_output_tokens: int = 4096
    default_temperature: float = 0.7
    code_temperature: float = 0.3


@dataclass
class MemoryConfig:
    """Configuração do sistema de memória"""
    # Limites de camadas
    short_term_size: int = 10
    long_term_max_per_category: int = 50
    long_term_max_total: int = 200

    # TTL (dias)
    default_ttl_days: int = 30
    important_ttl_days: int = 90

    # Resumo
    summary_trigger_messages: int = 5
    summary_max_tokens: int = 500

    # Limpeza
    cleanup_interval_hours: int = 24
    min_importance_to_keep: float = 0.3

    # Dedupe
    similarity_threshold: float = 0.8


@dataclass
class EveConfig:
    """Configuração principal da EVE"""
    # Sub-configurações
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    model_limits: ModelLimits = field(default_factory=ModelLimits)

    # Caminhos
    memory_file: str = "eve_memory_v2.json"
    chats_file: str = "eve_chats.json"
    features_file: str = "eve_features.json"
    personality_file: str = "core/personality.txt"

    # Comportamento geral
    enable_web_search: bool = True
    enable_spell_check: bool = True
    enable_code_artifacts: bool = True
    max_conversation_history: int = 10

    # API Keys (carregados do .env)
    groq_api_key: Optional[str] = None
    discord_token: Optional[str] = None

    @classmethod
    def load(cls, path: Optional[str] = None) -> 'EveConfig':
        """Carrega configuração de arquivo"""
        if path is None:
            project_root = Path(__file__).parent.parent
            path = project_root / 'eve_config.json'

        path = Path(path)

        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                config = cls()

                # Carregar sub-configs
                if 'policy' in data:
                    config.policy = PolicyConfig.from_dict(data['policy'])
                if 'memory' in data:
                    config.memory = MemoryConfig(**data['memory'])
                if 'model_limits' in data:
                    config.model_limits = ModelLimits(**data['model_limits'])

                # Carregar campos simples
                simple_fields = [
                    'memory_file', 'chats_file', 'features_file', 'personality_file',
                    'enable_web_search', 'enable_spell_check', 'enable_code_artifacts',
                    'max_conversation_history'
                ]
                for field_name in simple_fields:
                    if field_name in data:
                        setattr(config, field_name, data[field_name])

                return config
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Config] Erro ao carregar {path}: {e}")

        # Carregar API keys do ambiente
        config = cls()
        config.groq_api_key = os.environ.get('GROQ_API_KEY')
        config.discord_token = os.environ.get('DISCORD_BOT_TOKEN')

        return config

    def save(self, path: Optional[str] = None):
        """Salva configuração em arquivo"""
        if path is None:
            project_root = Path(__file__).parent.parent
            path = project_root / 'eve_config.json'

        path = Path(path)

        data = {
            'policy': self.policy.to_dict(),
            'memory': {k: getattr(self.memory, k) for k in self.memory.__dataclass_fields__},
            'model_limits': {k: getattr(self.model_limits, k) for k in self.model_limits.__dataclass_fields__},
            'memory_file': self.memory_file,
            'chats_file': self.chats_file,
            'features_file': self.features_file,
            'personality_file': self.personality_file,
            'enable_web_search': self.enable_web_search,
            'enable_spell_check': self.enable_spell_check,
            'enable_code_artifacts': self.enable_code_artifacts,
            'max_conversation_history': self.max_conversation_history
        }

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[Config] Erro ao salvar {path}: {e}")

    def get_timeout_for_intent(self, intent: str) -> int:
        """Retorna timeout apropriado para o tipo de intent"""
        intent_lower = intent.lower()

        if 'code' in intent_lower:
            return self.policy.timeout_code
        elif 'analysis' in intent_lower:
            return self.policy.timeout_analysis
        else:
            return self.policy.timeout_chat


# Instância global (lazy loading)
_config: Optional[EveConfig] = None


def get_config() -> EveConfig:
    """Retorna configuração global (singleton)"""
    global _config
    if _config is None:
        _config = EveConfig.load()
    return _config


def reload_config():
    """Recarrega configuração do disco"""
    global _config
    _config = EveConfig.load()
