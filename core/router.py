# core/router.py - ROTEAMENTO COMPLETO DE MODELOS (REESCRITO)
# LEGACY: Será substituído por core.models.router.ModelRouter na migração v2
"""
Router inteligente que escolhe o modelo certo automaticamente:
- Llama 3.1 8B: conversação geral, personalidade EVE
- Phi-3 3.8B: código e programação (DESABILITADO - usa Groq)
- Qwen 2.5: raciocínio complexo e pesquisa
- Qwen3-VL 8B: análise de imagens
- Groq Llama 70B: código (via API externa)

VERSÃO: Completa com suporte a Groq API
"""

import os
import time
import json
import logging
import requests
import base64
import re
from typing import Optional, Tuple, Union

from core.errors import GenerationAborted

logger = logging.getLogger("eve.router")
logger.setLevel(logging.INFO)

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
REQUEST_TIMEOUT = float(os.getenv("EVE_REQUEST_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("EVE_MAX_RETRIES", "2"))
RETRY_BACKOFF = float(os.getenv("EVE_RETRY_BACKOFF", "3.0"))

# Modelos padrão por papel (linha 2026) — sobrescreva via variáveis de
# ambiente para usar outros modelos já baixados no Ollama.
CHAT_MODEL = os.getenv("EVE_CHAT_MODEL", "qwen3.5:9b")
CODE_MODEL = os.getenv("EVE_CODE_MODEL", "qwen2.5-coder:7b")
REASON_MODEL = os.getenv("EVE_REASON_MODEL", "deepseek-r1:8b")
VISION_MODEL = os.getenv("EVE_VISION_MODEL", "qwen3-vl:8b")

# Mapa de modelos disponíveis
MODEL_MAP = {
    CHAT_MODEL: "ollama",         # Chat geral
    CODE_MODEL: "ollama",         # Código (backup, Groq preferido)
    REASON_MODEL: "ollama",       # Raciocínio
    VISION_MODEL: "ollama",       # Imagens
    "groq": "groq",               # API externa Groq
}

# Palavras-chave para detecção de intenção
INTENT_KEYWORDS = {
    "code": [
        "[MODO CÓDIGO]", "[modo código]", "[modo codigo]",
        "pode fazer um codigo", "pode fazer um código", "pode criar um codigo", "pode criar um código",
        "pode escrever um codigo", "pode escrever um código",
        "codigo de", "código de", "codigo para", "código para",
        "crie uma função", "crie um código", "crie um codigo",
        "escreva um código", "escreva um codigo",
        "faça um script", "faça um código", "faça um codigo",
        "desenvolva um programa", "desenvolva um código",
        "gere código", "gere codigo",
        "criar código", "criar codigo", "fazer código", "fazer codigo",
        "hello world", "calculadora",
        "def ", "class ", "function ", "import ", "const ", "let ", "var "
    ],
    "chat": ["olá", "oi", "como vai", "hello", "hi", "tudo bem", "e aí", "obrigado", "valeu", "legal", "massa"],
    "reason": ["matemática", "calcule", "resolva", "explain", "explique", "por que", "como funciona"],
    "image": ["imagem", "image", "foto", "picture", "analise", "veja", "olhe"],
}

# Mapeamento de intenção para modelo
INTENT_TO_MODEL = {
    "code": CODE_MODEL,         # Código (Groq preferido se disponível)
    "chat": CHAT_MODEL,         # Chat normal
    "reason": REASON_MODEL,     # Raciocínio
    "image": VISION_MODEL,      # Imagens
}

# Modelos de visão (aceitam imagens)
VISION_MODELS = [VISION_MODEL]

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE DETECÇÃO E ROTEAMENTO
# ═══════════════════════════════════════════════════════════════════

def detect_intent(prompt: Union[str, dict]) -> str:
    """
    Detecta a intenção do usuário baseado no prompt.
    
    Args:
        prompt: String ou dict com o prompt
        
    Returns:
        Intent detectado: "code", "chat", "reason", ou "image"
    """
    # Se é dict com type="image", retorna image
    if isinstance(prompt, dict) and prompt.get("type") == "image":
        return "image"
    
    # Converte para texto
    text = prompt.lower() if isinstance(prompt, str) else prompt.get("text", "").lower()
    
    # Conta ocorrências de keywords para cada intent
    scores = {intent: 0 for intent in INTENT_KEYWORDS}
    
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[intent] += 1
    
    # Retorna intent com maior score
    best_intent = max(scores.items(), key=lambda x: x[1])[0]
    result = best_intent if scores[best_intent] > 0 else "chat"
    
    logger.debug(f"Intent detectado: {result} (scores: {scores})")
    return result


def resolve_model(prompt: Union[str, dict], explicit_model: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolve qual modelo usar baseado no prompt ou modelo explícito.
    
    Args:
        prompt: Prompt do usuário
        explicit_model: Modelo explicitamente solicitado (opcional)
        
    Returns:
        Tupla (backend, model_id)
    """
    # Se modelo explícito foi fornecido, usa ele
    # ("groq" não é servido pelo router local — cai no roteamento automático,
    #  senão generate() levantaria NotImplementedError e o fallback quebraria)
    if explicit_model and explicit_model != "groq":
        model_id = explicit_model
        backend = MODEL_MAP.get(model_id, "ollama")
        logger.info(f"Modelo explícito: {model_id} (backend: {backend})")
        return backend, model_id

    if explicit_model == "groq":
        logger.warning("Modelo 'groq' não é suportado pelo router local - usando roteamento automático")

    # Detecta intenção
    intent = detect_intent(prompt)

    # Só roteia para o modelo de visão quando há imagem de verdade;
    # texto que apenas menciona "imagem/foto" vai para o modelo de chat
    is_real_image = isinstance(prompt, dict) and prompt.get("type") == "image"
    if intent == "image" and not is_real_image:
        intent = "chat"

    # Escolhe modelo baseado na intenção
    if intent == "image":
        model_id = VISION_MODELS[0]  # Sempre Qwen3-VL para imagens
    else:
        model_id = INTENT_TO_MODEL.get(intent, CHAT_MODEL)
    
    backend = MODEL_MAP.get(model_id, "ollama")
    
    logger.info(f"Roteamento automático: {intent} → {model_id} (backend: {backend})")
    return backend, model_id


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE LIMPEZA E PÓS-PROCESSAMENTO
# ═══════════════════════════════════════════════════════════════════

def _clean_thinking_text(text: str) -> str:
    """
    Remove texto de 'pensamento' em inglês do Qwen3-VL.
    
    Qwen3-VL às vezes gera texto em inglês antes da resposta em português.
    Esta função detecta e remove esse texto.
    """
    if not text:
        return text
    
    text = text.lstrip('\n')
    lines = text.split('\n')
    
    # Indicadores de português
    pt_indicators = [
        'é um', 'está ', 'são ', 'uma tela', 'um jogo', 'esta imagem',
        'vejo', 'mostra', 'tela de', 'interface', 'mapa', 'painel',
        'á', 'é', 'í', 'ó', 'ú', 'ã', 'õ', 'ç'
    ]
    
    # Procura primeira linha em português
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(ind in line_lower for ind in pt_indicators):
            text = '\n'.join(lines[i:])
            break
    
    # Remove padrões em inglês no início
    english_patterns = [
        r'^(Okay|Let me|First|Wait|I need|I can|Looking|The user|The image|This is|So|Now|Next)[,\s].*?\n',
    ]
    
    for pattern in english_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove linhas em branco excessivas
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def _strip_inline_thinking(text: str) -> str:
    """
    Remove blocos <think>...</think> que alguns modelos (ex.: deepseek-r1)
    embutem na resposta mesmo com think=false. Bloco não fechado (resposta
    cortada pelo num_predict) também é removido.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*\Z", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _extract_response_from_ollama(data: dict, model: str) -> str:
    """
    Extrai resposta do formato JSON do Ollama.
    Suporta campo 'thinking' do Qwen3-VL.

    Args:
        data: Dicionário JSON retornado pelo Ollama
        model: Nome do modelo usado

    Returns:
        Texto da resposta extraído
    """
    # Tenta campo 'response' padrão
    text = data.get("response", "").strip()
    if text:
        text = _strip_inline_thinking(text)
    if text:
        return text
    
    # Qwen3-VL usa 'thinking'
    if "thinking" in data:
        text = data.get("thinking", "").strip()
        if text:
            logger.info("Resposta extraída de 'thinking' (Qwen3-VL)")
            text = _clean_thinking_text(text)
            if text:
                return text
    
    # Tenta outros campos
    if "message" in data:
        if isinstance(data["message"], dict):
            text = data["message"].get("content", "").strip()
        else:
            text = str(data["message"]).strip()
        if text:
            return text
    
    if "content" in data:
        text = data.get("content", "").strip()
        if text:
            return text
    
    logger.error("Nenhum campo de resposta válido encontrado")
    return ""


# ═══════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL DE GERAÇÃO (OLLAMA)
# ═══════════════════════════════════════════════════════════════════

def _ollama_stream(
    url: str,
    payload: dict,
    headers: dict,
    timeout: float,
    stream_callback
) -> dict:
    """
    Faz a requisição ao Ollama em modo streaming, chamando
    stream_callback(chunk) a cada pedaço de texto recebido.

    Returns:
        Dict no mesmo formato da resposta não-streaming
    """
    payload = dict(payload)
    payload["stream"] = True

    full_response = ""
    with requests.post(url, json=payload, headers=headers,
                       timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        # NDJSON sem charset declarado: garante decodificação UTF-8
        resp.encoding = "utf-8"
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            chunk = data.get("response", "")
            if chunk:
                full_response += chunk
                try:
                    stream_callback(chunk)
                except GenerationAborted:
                    # Cancelamento pedido pela UI: sair do "with" fecha o
                    # socket e o Ollama interrompe a geração no servidor
                    raise
                except Exception as cb_err:
                    # Callback da UI não pode derrubar a geração
                    logger.warning(f"stream_callback falhou: {cb_err}")

            if data.get("done"):
                break

    return {
        "model": payload.get("model", ""),
        "response": full_response,
        "done": True
    }


def _ollama_generate(
    model: str,
    prompt: Union[str, dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
    timeout: int = None,
    stream_callback=None
) -> dict:
    """
    Gera resposta usando Ollama local.
    Suporta texto e imagens (multimodal).
    Com stream_callback, envia o texto progressivamente enquanto gera.
    
    Args:
        model: Nome do modelo Ollama
        prompt: String ou dict com prompt (dict para imagens)
        max_tokens: Número máximo de tokens
        temperature: Temperatura (0.0-1.0)
        timeout: Timeout em segundos (None = usa REQUEST_TIMEOUT)
        
    Returns:
        Dict com resposta do Ollama
    """
    url = f"{OLLAMA_BASE}/api/generate"
    headers = {"Content-Type": "application/json"}
    
    # Timeout padrão
    if timeout is None:
        timeout = REQUEST_TIMEOUT

    # Monta payload
    if isinstance(prompt, dict) and prompt.get("type") == "image":
        # Modo imagem
        image_path = prompt.get("path", "")
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        
        logger.info(f"Carregando imagem: {os.path.basename(image_path)}")
        
        # Converte imagem para base64
        with open(image_path, "rb") as f:
            image_data = f.read()
            image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        # Timeout maior para imagens
        timeout = 300
        
        payload = {
            "model": model,
            "prompt": prompt.get("text", "Descreva esta imagem"),
            "images": [image_b64],
            "stream": False,
            "think": False,  # visão: resposta direta, sem gastar tokens em thinking
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_gpu": 99,  # Força uso máximo da GPU
                "num_thread": 8,  # Threads para CPU
            }
        }
    else:
        # Modo texto
        payload = {
            "model": model,
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "stream": False,
            # Desliga o modo thinking (qwen3.5 etc.): sem isso o modelo gasta
            # o num_predict raciocinando no campo "thinking" e o "response"
            # volta vazio. Modelos sem thinking ignoram o campo (Ollama 0.31).
            "think": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "num_gpu": 99,  # Força uso máximo da GPU
                "num_thread": 8,  # Threads para CPU
            }
        }

    # Faz requisição com retry
    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        
        try:
            logger.info(f"Requisição {attempt}/{MAX_RETRIES} para {model}...")

            # Modo streaming: envia chunks para o callback enquanto gera
            if stream_callback is not None:
                data = _ollama_stream(url, payload, headers, timeout, stream_callback)
                logger.info("✅ Resposta recebida (streaming)")
                return data

            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            
            response_text = resp.text.strip()
            
            # Processa resposta NDJSON (múltiplas linhas JSON)
            if '\n' in response_text:
                lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                
                # Procura pela última linha com "done": true
                for line in reversed(lines):
                    try:
                        data = json.loads(line)
                        if data.get("done"):
                            logger.info("✅ Resposta recebida (NDJSON)")
                            return data
                    except json.JSONDecodeError:
                        continue
                
                # Se não encontrou "done", concatena todas as respostas
                full_response = ""
                for line in lines:
                    try:
                        data = json.loads(line)
                        full_response += data.get("response", "")
                    except json.JSONDecodeError:
                        continue
                
                logger.info("✅ Resposta concatenada (NDJSON sem done)")
                return {
                    "model": model,
                    "response": full_response,
                    "done": True
                }
            else:
                # Resposta em linha única
                data = resp.json()
                logger.info("✅ Resposta recebida (single JSON)")
                return data
                
        except GenerationAborted:
            # Cancelamento não é falha: nunca faz retry
            raise

        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout (tentativa {attempt}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES:
                raise Exception(f"Timeout após {attempt} tentativas ({timeout}s cada)")
            time.sleep(RETRY_BACKOFF * attempt)
            
        except requests.exceptions.ConnectionError:
            logger.error(f"🔌 Erro de conexão (tentativa {attempt}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES:
                raise Exception("Ollama offline. Execute: ollama serve")
            time.sleep(RETRY_BACKOFF * attempt)
            
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF * attempt)

    # Só chega aqui se MAX_RETRIES < 1 (ex.: EVE_MAX_RETRIES=0 no ambiente)
    raise Exception(f"Nenhuma tentativa executada (EVE_MAX_RETRIES={MAX_RETRIES})")


# ═══════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL DE GERAÇÃO (INTERFACE PÚBLICA)
# ═══════════════════════════════════════════════════════════════════

def generate(
    prompt: Union[str, dict],
    *,
    explicit_model: Optional[str] = None,
    max_tokens: int = 512,
    temperature: float = 0.7,
    return_raw: bool = False,
    stream_callback=None
) -> dict:
    """
    Gera resposta do modelo apropriado.
    Esta é a função principal do router.
    
    Args:
        prompt: Prompt do usuário (string ou dict para imagens)
        explicit_model: Modelo específico a usar (opcional)
        max_tokens: Número máximo de tokens
        temperature: Temperatura (0.0-1.0)
        return_raw: Se True, retorna resposta bruta do modelo
        
    Returns:
        Dict com:
            - text: Texto da resposta
            - meta: Metadados (backend, model, raw response)
    
    Raises:
        NotImplementedError: Se backend não for Ollama
        Exception: Se geração falhar
    """
    # Resolve qual modelo usar
    backend, model_id = resolve_model(prompt, explicit_model)
    
    # Atualmente só suportamos Ollama
    if backend != "ollama":
        raise NotImplementedError(f"Backend {backend} não implementado")

    # Gera resposta via Ollama
    logger.info(f"Gerando com {model_id}...")
    resp = _ollama_generate(
        model=model_id,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stream_callback=stream_callback
    )
    
    # Extrai texto da resposta (suporta thinking do Qwen3-VL)
    text = _extract_response_from_ollama(resp, model_id)
    
    if not text:
        logger.error("⚠️ Resposta vazia do modelo")
        text = "[ERRO] Modelo não retornou resposta."
    
    # Monta resultado
    result = {
        "text": text,
        "meta": {
            "backend": backend,
            "model": model_id,
            "raw": resp
        }
    }
    
    return result if not return_raw else resp


# ═══════════════════════════════════════════════════════════════════
# CLASSE ROUTER (COMPATIBILIDADE)
# ═══════════════════════════════════════════════════════════════════

class Router:
    """
    Classe Router para compatibilidade com código antigo.
    Encapsula as funções do módulo.
    """
    
    def __init__(self):
        logger.info("Router inicializado")
    
    def generate(
        self,
        prompt: Union[str, dict],
        explicit_model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        return_raw: bool = False,
        stream_callback=None
    ) -> dict:
        """Gera resposta (wrapper para função generate)"""
        return generate(
            prompt,
            explicit_model=explicit_model,
            max_tokens=max_tokens,
            temperature=temperature,
            return_raw=return_raw,
            stream_callback=stream_callback
        )
    
    def resolve_model(
        self,
        prompt: Union[str, dict],
        explicit_model: Optional[str] = None
    ) -> Tuple[str, str]:
        """Resolve modelo (wrapper para função resolve_model)"""
        return resolve_model(prompt, explicit_model)

    def detect_intent(self, prompt: Union[str, dict]) -> str:
        """Detecta intenção (wrapper para função detect_intent)"""
        return detect_intent(prompt)


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Testa detecção de intent
    print("Testando detecção de intent:")
    print(f"  'oi' → {detect_intent('oi')}")
    print(f"  'crie uma função' → {detect_intent('crie uma função')}")
    print(f"  'analise esta imagem' → {detect_intent('analise esta imagem')}")
    print(f"  'calcule 2+2' → {detect_intent('calcule 2+2')}")
    
    print("\nTestando resolução de modelo:")
    print(f"  'olá' → {resolve_model('olá')}")
    print(f"  'def hello()' → {resolve_model('def hello()')}")