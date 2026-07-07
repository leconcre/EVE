# engines/ollama_engine.py
"""
Engine para modelos locais via Ollama
Suporta texto e imagens (multimodal)
"""

import requests
import json
import logging
import os
import base64
from typing import Union, Optional

logger = logging.getLogger("ollama.engine")
logger.setLevel(logging.INFO)


class OllamaEngine:
    """
    Engine otimizado para interação com modelos locais via Ollama.
    Suporta texto e imagens (multimodal).
    """

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")
        logger.info(f"OllamaEngine inicializado: {self.host}")

    def generate(
        self,
        model: str,
        prompt: Union[str, dict],
        temperature: float = 0.7,
        max_tokens: int = 512,
        timeout: int = 120,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Gera resposta do modelo Ollama.

        Args:
            model: Nome do modelo (ex: "llama3.1:8b", "qwen3-vl:8b")
            prompt: String ou dict com prompt (dict para imagens)
            temperature: Temperatura (0.0-1.0)
            max_tokens: Máximo de tokens
            timeout: Timeout em segundos
            system_prompt: Prompt de sistema opcional (enviado via campo
                "system" da API — usado pelo ModelExecutor do capability router)

        Returns:
            Texto gerado pelo modelo
        """
        url = f"{self.host}/api/generate"

        # Constrói payload
        payload = {
            "model": model,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        # Processa prompt
        if isinstance(prompt, str):
            payload["prompt"] = prompt
            
        elif isinstance(prompt, dict):
            text = prompt.get("text", "")
            img = prompt.get("image") or prompt.get("path")
            
            payload["prompt"] = text
            
            # Se houver imagem, converte para base64
            if img:
                try:
                    if os.path.isfile(img):
                        with open(img, "rb") as f:
                            img_b64 = base64.b64encode(f.read()).decode("utf-8")
                        payload["images"] = [img_b64]
                        logger.info(f"Imagem carregada: {os.path.basename(img)}")
                    elif isinstance(img, str) and len(img) > 100:
                        # Assume que já é base64
                        payload["images"] = [img]
                        logger.info("Usando imagem em base64")
                    else:
                        logger.warning(f"Caminho inválido: {img}")
                except Exception as e:
                    logger.error(f"Erro ao processar imagem: {e}")
                    return f"[ERRO] Falha ao carregar imagem: {e}"
        else:
            return "[ERRO] Tipo de prompt inválido. Use str ou dict."

        # Envia requisição
        try:
            logger.debug(f"POST {url} com modelo {model}")
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
        except requests.Timeout:
            return f"[ERRO] Timeout após {timeout}s. O modelo pode estar sobrecarregado."
        except requests.ConnectionError:
            return "[ERRO] Não foi possível conectar ao Ollama. Verifique se está rodando."
        except Exception as e:
            return f"[ERRO] Falha na requisição: {e}"

        # Processa resposta
        if resp.status_code != 200:
            error_detail = resp.text[:200] if resp.text else "Sem detalhes"
            return f"[ERRO] HTTP {resp.status_code}: {error_detail}"

        try:
            # Trata NDJSON (múltiplas linhas JSON)
            response_text = resp.text.strip()
            
            if '\n' in response_text:
                # Formato NDJSON - processa linha por linha
                lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                
                # Procura pela última linha com "done": true
                for line in reversed(lines):
                    try:
                        data = json.loads(line)
                        if data.get("done"):
                            return data.get("response", "").strip()
                    except json.JSONDecodeError:
                        continue
                
                # Se não encontrou, concatena todas as respostas
                full_response = ""
                for line in lines:
                    try:
                        data = json.loads(line)
                        full_response += data.get("response", "")
                    except json.JSONDecodeError:
                        continue
                
                return full_response.strip() or "[ERRO] Resposta vazia"
            else:
                # Resposta em linha única
                data = resp.json()
                return data.get("response", "").strip() or "[ERRO] Resposta vazia"
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
            return "[ERRO] Resposta inválida do Ollama."

    def model_exists(self, model: str) -> bool:
        """
        Verifica se um modelo está disponível no Ollama.
        
        Args:
            model: Nome do modelo
            
        Returns:
            True se o modelo existe
        """
        url = f"{self.host}/api/tags"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return False
            
            data = resp.json()
            
            # Extrai lista de modelos
            models = []
            if isinstance(data, dict) and "models" in data:
                models = [m.get("name", "") for m in data.get("models", [])]
            elif isinstance(data, list):
                models = [m.get("name", "") for m in data]
            
            return model in models
            
        except Exception as e:
            logger.error(f"Erro ao verificar modelo: {e}")
            return False

    def list_models(self) -> list:
        """
        Lista todos os modelos disponíveis.
        
        Returns:
            Lista com nomes dos modelos
        """
        url = f"{self.host}/api/tags"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return []
            
            data = resp.json()
            
            if isinstance(data, dict) and "models" in data:
                return [m.get("name", "") for m in data.get("models", [])]
            elif isinstance(data, list):
                return [m.get("name", "") for m in data]
            
            return []
            
        except Exception as e:
            logger.error(f"Erro ao listar modelos: {e}")
            return []

    def pull_model(self, model: str, timeout: int = 300) -> str:
        """
        Baixa um modelo do Ollama.
        
        Args:
            model: Nome do modelo
            timeout: Timeout em segundos (padrão: 5 minutos)
            
        Returns:
            Mensagem de sucesso ou erro
        """
        url = f"{self.host}/api/pull"
        payload = {"name": model}
        
        try:
            logger.info(f"Baixando modelo {model}...")
            resp = requests.post(url, json=payload, timeout=timeout)
            
            if resp.status_code == 200:
                return f"✅ Modelo '{model}' baixado com sucesso!"
            else:
                error_detail = resp.text[:200] if resp.text else "Sem detalhes"
                return f"❌ Falha ao baixar modelo. HTTP {resp.status_code}: {error_detail}"
                
        except requests.Timeout:
            return f"❌ Timeout após {timeout}s"
        except Exception as e:
            return f"❌ Falha ao baixar modelo: {e}"
    
    def test_connection(self) -> bool:
        """Testa conexão com Ollama"""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False