# core/models/spec.py
"""
Especificações de modelos e capabilities.
Define ModelSpec e o registro de modelos disponíveis.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ModelCapability(Enum):
    """Capabilities que um modelo pode ter"""
    CHAT_FAST = "chat_fast"               # Respostas rápidas, simples
    CHAT_STRONG = "chat_strong"           # Conversas complexas
    CODE_STRONG = "code_strong"           # Geração de código
    CODE_REVIEW = "code_review"           # Análise/revisão de código
    ANALYSIS_STRONG = "analysis_strong"   # Análise de texto/logs
    VISION = "vision"                     # Análise de imagens
    REASONING = "reasoning"               # Raciocínio lógico/matemático
    MULTILINGUAL = "multilingual"         # Múltiplos idiomas
    SUMMARIZATION = "summarization"       # Resumo de texto

    @classmethod
    def from_string(cls, s: str) -> 'ModelCapability':
        """Converte string para capability"""
        s = s.lower().replace('-', '_')
        for cap in cls:
            if cap.value == s:
                return cap
        raise ValueError(f"Capability desconhecida: {s}")


@dataclass
class ModelSpec:
    """
    Especificação completa de um modelo.
    Descreve capabilities, limites e scores.
    """
    # === Identificação ===
    provider: str                     # 'ollama', 'groq', 'openai'
    model_id: str                     # 'llama3.1:8b', 'llama-3.3-70b-versatile'
    display_name: str                 # Nome amigável para exibição

    # === Capabilities ===
    capabilities: List[ModelCapability] = field(default_factory=list)
    primary_capability: Optional[ModelCapability] = None

    # === Limites ===
    context_window: int = 4096        # Tokens de contexto
    max_output_tokens: int = 4096     # Máximo de tokens na resposta

    # === Scores (0.0 a 1.0) ===
    speed_score: float = 0.5          # Latência (1.0 = muito rápido)
    quality_score: float = 0.5        # Qualidade de output
    reliability_score: float = 0.8    # Uptime/estabilidade
    cost_score: float = 1.0           # Custo (1.0 = gratuito)

    # === Metadados ===
    requires_api_key: bool = False
    is_local: bool = True
    vram_required_gb: Optional[float] = None
    supports_streaming: bool = True
    supports_json_mode: bool = False
    default_temperature: float = 0.7

    # === Tags para busca ===
    tags: List[str] = field(default_factory=list)

    def capability_score(self, capability: ModelCapability) -> float:
        """
        Retorna score para uma capability específica.
        1.0 se for a capability primária, 0.7 se for secundária, 0.0 se não tiver.
        """
        if capability not in self.capabilities:
            return 0.0
        if capability == self.primary_capability:
            return 1.0
        return 0.7

    def has_capability(self, capability: ModelCapability) -> bool:
        """Verifica se modelo tem uma capability"""
        return capability in self.capabilities

    def matches_tags(self, tags: List[str]) -> bool:
        """Verifica se modelo tem alguma das tags"""
        return any(tag in self.tags for tag in tags)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'provider': self.provider,
            'model_id': self.model_id,
            'display_name': self.display_name,
            'capabilities': [c.value for c in self.capabilities],
            'primary_capability': self.primary_capability.value if self.primary_capability else None,
            'context_window': self.context_window,
            'max_output_tokens': self.max_output_tokens,
            'speed_score': self.speed_score,
            'quality_score': self.quality_score,
            'reliability_score': self.reliability_score,
            'cost_score': self.cost_score,
            'is_local': self.is_local,
            'requires_api_key': self.requires_api_key
        }

    def __repr__(self) -> str:
        return f"ModelSpec({self.provider}:{self.model_id})"


# =============================================================================
# REGISTRO DE MODELOS DISPONÍVEIS
# =============================================================================

MODEL_REGISTRY: List[ModelSpec] = [
    # =========================================================================
    # LOCAL (Ollama)
    # =========================================================================

    ModelSpec(
        provider='ollama',
        model_id='llama3.1:8b',
        display_name='Llama 3.1 8B',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.CHAT_STRONG,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_FAST,
        context_window=8192,
        max_output_tokens=4096,
        speed_score=0.8,
        quality_score=0.6,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        tags=['chat', 'conversação', 'geral', 'rápido']
    ),

    ModelSpec(
        provider='ollama',
        model_id='llama3.2:3b',
        display_name='Llama 3.2 3B',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_FAST,
        context_window=8192,
        max_output_tokens=4096,
        speed_score=0.95,
        quality_score=0.4,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=2.5,
        tags=['chat', 'rápido', 'leve']
    ),

    ModelSpec(
        provider='ollama',
        model_id='qwen2.5:7b',
        display_name='Qwen 2.5 7B',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.CHAT_STRONG,
            ModelCapability.REASONING,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.REASONING,
        context_window=32768,
        max_output_tokens=8192,
        speed_score=0.7,
        quality_score=0.65,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        tags=['raciocínio', 'matemática', 'lógica', 'multilingue']
    ),

    ModelSpec(
        provider='ollama',
        model_id='qwen2.5:14b',
        display_name='Qwen 2.5 14B',
        capabilities=[
            ModelCapability.CHAT_STRONG,
            ModelCapability.REASONING,
            ModelCapability.CODE_STRONG,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_STRONG,
        context_window=32768,
        max_output_tokens=8192,
        speed_score=0.5,
        quality_score=0.75,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=9.0,
        tags=['avançado', 'raciocínio', 'código']
    ),

    ModelSpec(
        provider='ollama',
        model_id='qwen2.5-coder:7b',
        display_name='Qwen 2.5 Coder 7B',
        capabilities=[
            ModelCapability.CODE_STRONG,
            ModelCapability.CODE_REVIEW
        ],
        primary_capability=ModelCapability.CODE_STRONG,
        context_window=32768,
        max_output_tokens=8192,
        speed_score=0.7,
        quality_score=0.7,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        default_temperature=0.3,
        tags=['código', 'programação', 'debug']
    ),

    ModelSpec(
        provider='ollama',
        model_id='codellama:7b',
        display_name='Code Llama 7B',
        capabilities=[
            ModelCapability.CODE_STRONG,
            ModelCapability.CODE_REVIEW
        ],
        primary_capability=ModelCapability.CODE_STRONG,
        context_window=16384,
        max_output_tokens=4096,
        speed_score=0.75,
        quality_score=0.65,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        default_temperature=0.3,
        tags=['código', 'programação']
    ),

    ModelSpec(
        provider='ollama',
        model_id='deepseek-coder:6.7b',
        display_name='DeepSeek Coder 6.7B',
        capabilities=[
            ModelCapability.CODE_STRONG,
            ModelCapability.CODE_REVIEW
        ],
        primary_capability=ModelCapability.CODE_STRONG,
        context_window=16384,
        max_output_tokens=4096,
        speed_score=0.7,
        quality_score=0.72,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        default_temperature=0.3,
        tags=['código', 'programação', 'deepseek']
    ),

    ModelSpec(
        provider='ollama',
        model_id='qwen2-vl:7b',
        display_name='Qwen2 VL 7B (Vision)',
        capabilities=[
            ModelCapability.VISION,
            ModelCapability.CHAT_FAST,
            ModelCapability.ANALYSIS_STRONG
        ],
        primary_capability=ModelCapability.VISION,
        context_window=8192,
        max_output_tokens=4096,
        speed_score=0.5,
        quality_score=0.7,
        reliability_score=0.9,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=6.0,
        tags=['visão', 'imagem', 'OCR', 'análise visual']
    ),

    ModelSpec(
        provider='ollama',
        model_id='llava:7b',
        display_name='LLaVA 7B (Vision)',
        capabilities=[
            ModelCapability.VISION,
            ModelCapability.CHAT_FAST
        ],
        primary_capability=ModelCapability.VISION,
        context_window=4096,
        max_output_tokens=2048,
        speed_score=0.6,
        quality_score=0.6,
        reliability_score=0.9,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.5,
        tags=['visão', 'imagem']
    ),

    ModelSpec(
        provider='ollama',
        model_id='phi3:3.8b',
        display_name='Phi-3 3.8B',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.REASONING
        ],
        primary_capability=ModelCapability.CHAT_FAST,
        context_window=4096,
        max_output_tokens=2048,
        speed_score=0.9,
        quality_score=0.55,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=2.5,
        tags=['rápido', 'leve', 'microsoft']
    ),

    ModelSpec(
        provider='ollama',
        model_id='mistral:7b',
        display_name='Mistral 7B',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.CHAT_STRONG,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_STRONG,
        context_window=8192,
        max_output_tokens=4096,
        speed_score=0.75,
        quality_score=0.65,
        reliability_score=0.95,
        cost_score=1.0,
        is_local=True,
        vram_required_gb=5.0,
        tags=['chat', 'geral', 'mistral']
    ),

    # =========================================================================
    # CLOUD (Groq)
    # =========================================================================

    ModelSpec(
        provider='groq',
        model_id='llama-3.3-70b-versatile',
        display_name='Llama 3.3 70B (Groq)',
        capabilities=[
            ModelCapability.CHAT_STRONG,
            ModelCapability.CODE_STRONG,
            ModelCapability.CODE_REVIEW,
            ModelCapability.ANALYSIS_STRONG,
            ModelCapability.REASONING,
            ModelCapability.SUMMARIZATION,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CODE_STRONG,
        context_window=128000,
        max_output_tokens=8000,
        speed_score=0.9,      # Groq é muito rápido
        quality_score=0.95,
        reliability_score=0.85,  # Depende de internet
        cost_score=0.7,       # API gratuita com limites
        requires_api_key=True,
        is_local=False,
        default_temperature=0.7,
        tags=['avançado', 'código', 'análise', 'groq', '70b']
    ),

    ModelSpec(
        provider='groq',
        model_id='llama-3.1-70b-versatile',
        display_name='Llama 3.1 70B (Groq)',
        capabilities=[
            ModelCapability.CHAT_STRONG,
            ModelCapability.CODE_STRONG,
            ModelCapability.CODE_REVIEW,
            ModelCapability.ANALYSIS_STRONG,
            ModelCapability.REASONING,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_STRONG,
        context_window=128000,
        max_output_tokens=8000,
        speed_score=0.88,
        quality_score=0.9,
        reliability_score=0.85,
        cost_score=0.7,
        requires_api_key=True,
        is_local=False,
        tags=['avançado', 'chat', 'groq', '70b']
    ),

    ModelSpec(
        provider='groq',
        model_id='llama-3.1-8b-instant',
        display_name='Llama 3.1 8B Instant (Groq)',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_FAST,
        context_window=128000,
        max_output_tokens=8000,
        speed_score=0.95,
        quality_score=0.6,
        reliability_score=0.85,
        cost_score=0.8,
        requires_api_key=True,
        is_local=False,
        tags=['rápido', 'chat', 'groq']
    ),

    ModelSpec(
        provider='groq',
        model_id='mixtral-8x7b-32768',
        display_name='Mixtral 8x7B (Groq)',
        capabilities=[
            ModelCapability.CHAT_STRONG,
            ModelCapability.CODE_STRONG,
            ModelCapability.REASONING,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_STRONG,
        context_window=32768,
        max_output_tokens=4096,
        speed_score=0.85,
        quality_score=0.75,
        reliability_score=0.85,
        cost_score=0.75,
        requires_api_key=True,
        is_local=False,
        tags=['mixtral', 'moe', 'groq']
    ),

    ModelSpec(
        provider='groq',
        model_id='gemma2-9b-it',
        display_name='Gemma 2 9B (Groq)',
        capabilities=[
            ModelCapability.CHAT_FAST,
            ModelCapability.CHAT_STRONG,
            ModelCapability.MULTILINGUAL
        ],
        primary_capability=ModelCapability.CHAT_FAST,
        context_window=8192,
        max_output_tokens=4096,
        speed_score=0.9,
        quality_score=0.65,
        reliability_score=0.85,
        cost_score=0.8,
        requires_api_key=True,
        is_local=False,
        tags=['gemma', 'google', 'groq']
    ),
]


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_models_by_capability(
    capability: ModelCapability,
    local_only: bool = False,
    cloud_only: bool = False
) -> List[ModelSpec]:
    """Retorna modelos que têm uma capability específica"""
    result = []
    for model in MODEL_REGISTRY:
        if capability not in model.capabilities:
            continue
        if local_only and not model.is_local:
            continue
        if cloud_only and model.is_local:
            continue
        result.append(model)
    return result


def get_model_by_id(provider: str, model_id: str) -> Optional[ModelSpec]:
    """Busca modelo por provider e ID"""
    for model in MODEL_REGISTRY:
        if model.provider == provider and model.model_id == model_id:
            return model
    return None


def get_model_by_full_id(full_id: str) -> Optional[ModelSpec]:
    """
    Busca modelo por ID completo (provider:model_id).
    Ex: 'groq:llama-3.3-70b-versatile'
    """
    if ':' in full_id:
        provider, model_id = full_id.split(':', 1)
        return get_model_by_id(provider, model_id)
    return None


def get_available_capabilities() -> List[ModelCapability]:
    """Retorna todas as capabilities disponíveis nos modelos registrados"""
    caps = set()
    for model in MODEL_REGISTRY:
        caps.update(model.capabilities)
    return list(caps)


def get_local_models() -> List[ModelSpec]:
    """Retorna apenas modelos locais"""
    return [m for m in MODEL_REGISTRY if m.is_local]


def get_cloud_models() -> List[ModelSpec]:
    """Retorna apenas modelos cloud"""
    return [m for m in MODEL_REGISTRY if not m.is_local]


def find_best_model_for_capability(
    capability: ModelCapability,
    prefer_local: bool = True,
    min_quality: float = 0.0
) -> Optional[ModelSpec]:
    """
    Encontra o melhor modelo para uma capability.
    Útil para seleção rápida sem usar o router completo.
    """
    candidates = get_models_by_capability(capability)

    if not candidates:
        return None

    # Filtrar por qualidade mínima
    candidates = [m for m in candidates if m.quality_score >= min_quality]

    if not candidates:
        return None

    # Ordenar por preferência
    def sort_key(m: ModelSpec):
        local_bonus = 0.1 if (prefer_local and m.is_local) else 0
        cap_score = m.capability_score(capability)
        return cap_score + m.quality_score + local_bonus

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]
