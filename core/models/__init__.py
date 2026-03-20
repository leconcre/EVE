# core/models/__init__.py
"""
Sistema de modelos da EVE.
Gerencia especificações, capabilities e roteamento.
"""

from .spec import (
    ModelCapability,
    ModelSpec,
    MODEL_REGISTRY,
    get_models_by_capability,
    get_model_by_id,
    get_available_capabilities
)

from .router import (
    ModelRouter,
    NoModelForCapability,
    NoAvailableModel
)

__all__ = [
    'ModelCapability',
    'ModelSpec',
    'MODEL_REGISTRY',
    'ModelRouter',
    'NoModelForCapability',
    'NoAvailableModel',
    'get_models_by_capability',
    'get_model_by_id',
    'get_available_capabilities'
]
