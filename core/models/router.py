# core/models/router.py
"""
Router de modelos por capability.
Seleciona o melhor modelo disponível baseado em capabilities e policy.
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

from .spec import (
    ModelSpec,
    ModelCapability,
    MODEL_REGISTRY,
    get_models_by_capability,
    get_model_by_id
)
from ..config import PolicyConfig, PolicyState, ExecutionPolicy
from ..feature_flags import FLAGS


class NoModelForCapability(Exception):
    """Nenhum modelo registrado tem a capability solicitada"""
    pass


class NoAvailableModel(Exception):
    """Nenhum modelo disponível pode atender a requisição"""
    pass


class ModelExecutionError(Exception):
    """Erro durante execução do modelo"""
    pass


@dataclass
class RoutingHints:
    """Hints para roteamento de modelo"""
    preferred_provider: Optional[str] = None
    allow_cloud: bool = True
    allow_local: bool = True
    fallback_enabled: bool = True
    prefer_speed: bool = False
    prefer_quality: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    @classmethod
    def from_policy(cls, policy: PolicyConfig, policy_state: PolicyState) -> 'RoutingHints':
        """Cria hints baseado na policy atual"""
        hints = cls()
        hints.fallback_enabled = policy.fallback_enabled

        if policy.policy == ExecutionPolicy.OFFLINE:
            hints.allow_cloud = False
            hints.preferred_provider = 'ollama'
        elif policy.policy == ExecutionPolicy.PRO:
            hints.preferred_provider = 'groq'
            hints.prefer_quality = True

        # Verificar estado do cloud
        if not policy_state.can_use_cloud(policy):
            hints.allow_cloud = False

        return hints


@dataclass
class RoutingResult:
    """Resultado do roteamento"""
    model: ModelSpec
    hints_applied: Dict[str, Any]
    fallback_available: Optional[ModelSpec] = None
    routing_time_ms: int = 0


class ModelRouter:
    """
    Router de modelos por capability.

    Responsabilidades:
    - Resolver melhor modelo para uma capability
    - Aplicar restrições de policy
    - Verificar disponibilidade
    - Gerenciar fallback
    - Cache de disponibilidade
    """

    def __init__(
        self,
        registry: List[ModelSpec] = None,
        policy_config: PolicyConfig = None
    ):
        self.registry = registry or MODEL_REGISTRY
        self.policy = policy_config or PolicyConfig()
        self.policy_state = PolicyState()

        # Cache de disponibilidade (model_id -> (available, timestamp))
        self._availability_cache: Dict[str, Tuple[bool, float]] = {}
        self._cache_ttl_seconds = 60

        # Lock para operações thread-safe
        self._lock = threading.Lock()

        # Executor para verificações paralelas
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Callbacks para engines
        self._ollama_check_fn: Optional[Callable] = None
        self._groq_check_fn: Optional[Callable] = None

    def set_availability_checkers(
        self,
        ollama_fn: Callable[[str], bool] = None,
        groq_fn: Callable[[], bool] = None
    ):
        """Define funções para verificar disponibilidade dos providers"""
        self._ollama_check_fn = ollama_fn
        self._groq_check_fn = groq_fn

    def resolve(
        self,
        capability: str | ModelCapability,
        hints: RoutingHints = None
    ) -> RoutingResult:
        """
        Resolve o melhor modelo para uma capability.

        Args:
            capability: Capability necessária (string ou enum)
            hints: Hints opcionais para roteamento

        Returns:
            RoutingResult com modelo selecionado

        Raises:
            NoModelForCapability: Se nenhum modelo tem a capability
            NoAvailableModel: Se nenhum modelo disponível
        """
        start_time = time.time()

        # Normalizar capability
        if isinstance(capability, str):
            capability = ModelCapability.from_string(capability)

        hints = hints or RoutingHints()

        if FLAGS.DEBUG_MODEL_ROUTING:
            print(f"[Router] Resolvendo capability: {capability.value}")
            print(f"[Router] Hints: cloud={hints.allow_cloud}, local={hints.allow_local}")

        # 1. Filtrar por capability
        candidates = [
            m for m in self.registry
            if capability in m.capabilities
        ]

        if not candidates:
            raise NoModelForCapability(f"Nenhum modelo com capability: {capability.value}")

        # 2. Aplicar constraints de hints
        candidates = self._apply_hints_filter(candidates, hints)

        if not candidates:
            raise NoAvailableModel(f"Hints muito restritivos para: {capability.value}")

        # 3. Filtrar por disponibilidade
        available_candidates = [
            m for m in candidates
            if self._is_available(m)
        ]

        if not available_candidates:
            # Tentar fallback se permitido
            if hints.fallback_enabled:
                fallback = self._find_fallback(capability, candidates)
                if fallback and self._is_available(fallback):
                    available_candidates = [fallback]

        if not available_candidates:
            raise NoAvailableModel(f"Nenhum modelo disponível para: {capability.value}")

        # 4. Ordenar por score
        scored = [
            (self._compute_score(m, capability, hints), m)
            for m in available_candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = scored[0][1]

        # 5. Encontrar fallback
        fallback = None
        if len(scored) > 1:
            fallback = scored[1][1]
        elif hints.fallback_enabled:
            fallback = self._find_fallback(capability, [selected])

        routing_time = int((time.time() - start_time) * 1000)

        if FLAGS.DEBUG_MODEL_ROUTING:
            print(f"[Router] Selecionado: {selected.provider}:{selected.model_id}")
            print(f"[Router] Fallback: {fallback.model_id if fallback else 'None'}")
            print(f"[Router] Tempo: {routing_time}ms")

        return RoutingResult(
            model=selected,
            hints_applied={
                'allow_cloud': hints.allow_cloud,
                'allow_local': hints.allow_local,
                'preferred_provider': hints.preferred_provider
            },
            fallback_available=fallback,
            routing_time_ms=routing_time
        )

    def _apply_hints_filter(
        self,
        candidates: List[ModelSpec],
        hints: RoutingHints
    ) -> List[ModelSpec]:
        """Aplica filtros baseados nos hints"""
        result = candidates

        # Filtrar por cloud/local
        if not hints.allow_cloud:
            result = [m for m in result if m.is_local]
        if not hints.allow_local:
            result = [m for m in result if not m.is_local]

        # Provider preferido (não remove outros, apenas prioriza depois)
        if hints.preferred_provider:
            preferred = [m for m in result if m.provider == hints.preferred_provider]
            if preferred:
                result = preferred

        return result

    def _compute_score(
        self,
        model: ModelSpec,
        capability: ModelCapability,
        hints: RoutingHints
    ) -> float:
        """
        Calcula score composto para seleção.

        Pesos:
        - Capability match: 30%
        - Quality: 25%
        - Speed: 20%
        - Reliability: 15%
        - Cost: 10%
        """
        cap_score = model.capability_score(capability)

        # Ajustar pesos baseado em hints
        if hints.prefer_speed:
            weights = (0.2, 0.15, 0.35, 0.2, 0.1)
        elif hints.prefer_quality:
            weights = (0.25, 0.4, 0.1, 0.15, 0.1)
        else:
            weights = (0.3, 0.25, 0.2, 0.15, 0.1)

        score = (
            cap_score * weights[0] +
            model.quality_score * weights[1] +
            model.speed_score * weights[2] +
            model.reliability_score * weights[3] +
            model.cost_score * weights[4]
        )

        # Bonus para provider preferido
        if hints.preferred_provider and model.provider == hints.preferred_provider:
            score += 0.1

        return score

    def _is_available(self, model: ModelSpec) -> bool:
        """Verifica se modelo está disponível"""
        cache_key = f"{model.provider}:{model.model_id}"

        with self._lock:
            # Verificar cache
            if cache_key in self._availability_cache:
                available, timestamp = self._availability_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl_seconds:
                    return available

        # Verificar disponibilidade real
        available = self._check_availability(model)

        with self._lock:
            self._availability_cache[cache_key] = (available, time.time())

        return available

    def _check_availability(self, model: ModelSpec) -> bool:
        """Verifica disponibilidade real do modelo"""
        try:
            if model.provider == 'ollama':
                if self._ollama_check_fn:
                    return self._ollama_check_fn(model.model_id)
                return self._default_ollama_check(model.model_id)

            elif model.provider == 'groq':
                if self._groq_check_fn:
                    return self._groq_check_fn()
                return self._default_groq_check()

            else:
                return False

        except Exception as e:
            if FLAGS.DEBUG_MODEL_ROUTING:
                print(f"[Router] Erro ao verificar {model.model_id}: {e}")
            return False

    def _default_ollama_check(self, model_id: str) -> bool:
        """Verificação default do Ollama"""
        try:
            response = requests.get(
                'http://localhost:11434/api/tags',
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                models = [m.get('name', '') for m in data.get('models', [])]
                # Verificar se modelo está na lista (com ou sem tag)
                return any(
                    model_id in m or m.startswith(model_id.split(':')[0])
                    for m in models
                )
            return False
        except Exception:
            return False

    def _default_groq_check(self) -> bool:
        """Verificação default do Groq"""
        import os
        # Apenas verifica se tem API key
        return bool(os.environ.get('GROQ_API_KEY'))

    def _find_fallback(
        self,
        capability: ModelCapability,
        exclude: List[ModelSpec]
    ) -> Optional[ModelSpec]:
        """Encontra modelo de fallback"""
        exclude_ids = {m.model_id for m in exclude}

        # Priorizar modelos locais para fallback (mais confiáveis)
        candidates = [
            m for m in self.registry
            if capability in m.capabilities
            and m.model_id not in exclude_ids
            and m.is_local
        ]

        if not candidates:
            # Se não há locais, tentar cloud
            candidates = [
                m for m in self.registry
                if capability in m.capabilities
                and m.model_id not in exclude_ids
            ]

        if not candidates:
            return None

        # Ordenar por reliability
        candidates.sort(key=lambda m: m.reliability_score, reverse=True)
        return candidates[0]

    def invalidate_cache(self, model_id: str = None):
        """Invalida cache de disponibilidade"""
        with self._lock:
            if model_id:
                keys_to_remove = [
                    k for k in self._availability_cache
                    if model_id in k
                ]
                for k in keys_to_remove:
                    del self._availability_cache[k]
            else:
                self._availability_cache.clear()

    def mark_cloud_failure(self):
        """Marca falha no cloud"""
        self.policy_state.record_cloud_failure()
        self.invalidate_cache()

    def mark_cloud_success(self):
        """Marca sucesso no cloud"""
        self.policy_state.record_cloud_success()

    def get_hints_for_policy(self) -> RoutingHints:
        """Retorna hints baseados na policy atual"""
        return RoutingHints.from_policy(self.policy, self.policy_state)

    def list_available_models(self) -> List[Dict]:
        """Lista modelos disponíveis com status"""
        result = []
        for model in self.registry:
            available = self._is_available(model)
            result.append({
                'provider': model.provider,
                'model_id': model.model_id,
                'display_name': model.display_name,
                'available': available,
                'capabilities': [c.value for c in model.capabilities],
                'is_local': model.is_local
            })
        return result


# =============================================================================
# EXECUTOR DE MODELOS
# =============================================================================

class ModelExecutor:
    """
    Executor de modelos com fallback automático.
    Integra com router para execução end-to-end.
    """

    def __init__(
        self,
        router: ModelRouter,
        ollama_engine=None,
        groq_engine=None
    ):
        self.router = router
        self.ollama_engine = ollama_engine
        self.groq_engine = groq_engine

    def execute(
        self,
        capability: str | ModelCapability,
        prompt: str,
        hints: RoutingHints = None,
        system_prompt: str = None,
        **kwargs
    ) -> Tuple[str, ModelSpec]:
        """
        Executa prompt no modelo apropriado.

        Returns:
            Tupla (resposta, modelo_usado)
        """
        # Resolver modelo
        result = self.router.resolve(capability, hints)
        model = result.model

        try:
            response = self._call_model(
                model, prompt, system_prompt, **kwargs
            )
            if not model.is_local:
                self.router.mark_cloud_success()
            return response, model

        except Exception as e:
            if FLAGS.DEBUG_MODEL_ROUTING:
                print(f"[Executor] Erro no modelo {model.model_id}: {e}")

            if not model.is_local:
                self.router.mark_cloud_failure()

            # Tentar fallback
            if result.fallback_available and (hints is None or hints.fallback_enabled):
                try:
                    response = self._call_model(
                        result.fallback_available, prompt, system_prompt, **kwargs
                    )
                    return response, result.fallback_available
                except Exception as e2:
                    raise ModelExecutionError(f"Falha no modelo e fallback: {e}, {e2}")

            raise ModelExecutionError(f"Falha no modelo: {e}")

    def _call_model(
        self,
        model: ModelSpec,
        prompt: str,
        system_prompt: str = None,
        **kwargs
    ) -> str:
        """Chama o modelo específico"""
        # Aplicar defaults do modelo
        if 'temperature' not in kwargs:
            kwargs['temperature'] = model.default_temperature
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = model.max_output_tokens

        if model.provider == 'ollama':
            if not self.ollama_engine:
                raise ModelExecutionError("Ollama engine não configurado")
            return self.ollama_engine.generate(
                prompt=prompt,
                model=model.model_id,
                system_prompt=system_prompt,
                **kwargs
            )

        elif model.provider == 'groq':
            if not self.groq_engine:
                raise ModelExecutionError("Groq engine não configurado")
            return self.groq_engine.generate(
                prompt=prompt,
                model=model.model_id,
                system_prompt=system_prompt,
                **kwargs
            )

        else:
            raise ModelExecutionError(f"Provider não suportado: {model.provider}")
