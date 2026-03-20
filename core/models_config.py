# core/models_config.py
"""
Configuração de modelos disponíveis para EVE
"""

MODELS = {
    "llama_chat": {
        "name": "Llama 3.1 8B",
        "backend": "ollama",
        "model_id": "llama3.1:8b",
        "max_tokens": 4096,
        "temperature": 0.7,
        "tags": ["conversação", "personalidade", "raciocínio-geral", "explicações-longas"],
    },
    "phi_code": {
        "name": "Phi-3 3.8B",
        "backend": "ollama",
        "model_id": "phi3:3.8b",
        "max_tokens": 4096,
        "temperature": 0.4,
        "tags": ["programação", "código", "técnico", "matemática", "lógica"],
    },
    "qwen_reason": {
        "name": "Qwen 2.5",
        "backend": "ollama",
        "model_id": "qwen2.5",
        "max_tokens": 4096,
        "temperature": 0.6,
        "tags": ["multilingue", "pesquisas", "resumos", "produtividade"],
    },
    "qwen_vl": {
        "name": "Qwen 3 VL 8B",
        "backend": "ollama",
        "model_id": "qwen3-vl:8b",
        "max_tokens": 4096,
        "temperature": 0.6,
        "tags": ["multimodal", "imagem", "análise de imagens", "visão e linguagem", "screenshots", "UI", "OCR"],
        "vram_required": "5-6 GB",
        "recommended_for": "RTX 4060, RTX 3060, RTX 2060",
        "features": ["análise detalhada", "reconhecimento de texto", "interface de jogos"]
    },
}

INTENT_TO_MODEL = {
    "chat": "llama_chat",
    "code": "phi_code",
    "reasoning": "qwen_reason",
    "debug": "phi_code",
    "image": "qwen_vl",
}

# Mapa reverso: model_id -> configuração
MODEL_BY_ID = {
    config["model_id"]: config
    for config in MODELS.values()
}

def get_model_config(model_id: str) -> dict:
    """
    Retorna configuração de um modelo pelo ID.
    
    Args:
        model_id: ID do modelo (ex: "llama3.1:8b")
        
    Returns:
        Dicionário com configuração do modelo
    """
    return MODEL_BY_ID.get(model_id, {
        "name": "Unknown",
        "backend": "ollama",
        "model_id": model_id,
        "max_tokens": 2048,
        "temperature": 0.7,
        "tags": []
    })

def list_available_models() -> list:
    """
    Lista todos os modelos disponíveis.
    
    Returns:
        Lista com IDs dos modelos
    """
    return list(MODEL_BY_ID.keys())