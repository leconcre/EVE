# engines/groq_engine.py - Backend Groq para EVE
"""
Groq API Engine - inferência rápida na nuvem
Rápido e confiável para chat e geração de código

MODELOS DE PRODUÇÃO (julho/2026):
- openai/gpt-oss-120b (flagship: raciocínio, código e agentes)
- openai/gpt-oss-20b (rápido e barato para chat geral)
- qwen/qwen3.6-27b (visão + raciocínio, preview)
- llama-3.3-70b-versatile (LEGADO — deprecado, shutdown 16/08/2026)
"""

import requests
import logging
import json
import os
from typing import Optional, Tuple, List
import time
import re

from core.errors import GenerationAborted

logger = logging.getLogger("groq.engine")
logger.setLevel(logging.INFO)


class CppCodeValidator:
    """
    Validador e corretor automático de código C++
    Detecta e corrige erros comuns de compilação
    """

    @staticmethod
    def validate_and_fix(code: str) -> Tuple[str, List[str]]:
        """
        Valida e corrige código C++ automaticamente

        Returns:
            (código_corrigido, lista_de_erros_encontrados)
        """
        errors_found = []
        fixed_code = code

        # ERRO 1: #include na mesma linha
        # Abordagem melhorada: processa linha por linha
        lines = fixed_code.split('\n')
        needs_include_fix = False
        new_lines = []

        for line in lines:
            # Conta quantos #include tem na linha
            include_count = line.count('#include')
            if include_count > 1:
                needs_include_fix = True
                # Separa todos os #include em linhas individuais
                # Match todos os #include <...> ou #include "..."
                includes = re.findall(r'#include\s+[<"][^>"]+[>"]', line)
                new_lines.extend(includes)
                # Preserva qualquer código que estivesse na mesma linha
                remainder = re.sub(r'#include\s+[<"][^>"]+[>"]', '', line).strip()
                if remainder:
                    new_lines.append(remainder)
            else:
                new_lines.append(line)

        if needs_include_fix:
            logger.warning("❌ ERRO 1: #include na mesma linha detectado - CORRIGINDO...")
            errors_found.append("#include na mesma linha")
            fixed_code = '\n'.join(new_lines)

        # ERRO 2: Membros de classe sem nome (muito comum)
        # Detecta padrões como "Transform;" ou "Hitbox;" dentro de classes
        # Busca por linhas com tipo capitalizado seguido de ; (sem nome de variável)
        lines = fixed_code.split('\n')
        in_class = False
        class_depth = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Rastreia se estamos dentro de uma classe
            if 'class ' in stripped and '{' in stripped:
                in_class = True
                class_depth = 1
            elif in_class:
                class_depth += stripped.count('{') - stripped.count('}')
                if class_depth <= 0:
                    in_class = False

            # Dentro de classe, detecta "Tipo;" sem variável
            if in_class and re.match(r'^\s*[A-Z]\w+\s*;\s*$', stripped):
                # Ignora construtor/destrutor e palavras-chave
                if not any(keyword in stripped for keyword in ['public:', 'private:', 'protected:', '~']):
                    errors_found.append("Membros de classe sem nome de variável")
                    logger.warning(f"❌ ERRO 2: Linha {i+1}: '{stripped}' - membro sem nome!")
                    break  # Já encontrou, não precisa continuar

        # ERRO 3: Declaração tipo "Player;" sem variável no main
        # Só linhas que contêm APENAS o identificador + ';' — senão dá falso
        # positivo em usos legítimos como "return MAX_HEALTH;" ou
        # "enum class Color;" e o código é regenerado à toa (2x custo)
        for line in fixed_code.split('\n'):
            stripped = line.strip()
            if re.match(r'^[A-Z]\w+\s*;$', stripped):
                # Forward declarations legítimas: "class Foo;" / "struct Foo;"
                # não casam pois começam com minúscula ("class"/"struct")
                errors_found.append("Declaração de tipo sem variável")
                logger.warning(f"❌ ERRO 3: Declaração sem variável: '{stripped}'")
                break

        # ERRO 4: getForward() sem normalize()
        if 'getForward()' in fixed_code and '.normalize()' not in fixed_code:
            errors_found.append("getForward() pode não estar normalizado")

        # ERRO 5: Loop while(true) sem controle
        if re.search(r'while\s*\(\s*true\s*\)', fixed_code):
            if 'bool running' not in fixed_code:
                errors_found.append("Loop infinito sem controle de saída")

        return fixed_code, errors_found

    @staticmethod
    def needs_regeneration(errors: List[str]) -> bool:
        """
        Determina se o código precisa ser regenerado
        (alguns erros não podem ser auto-corrigidos)
        """
        critical_errors = [
            "Membros de classe sem nome de variável",
            "Declaração de tipo sem variável"
        ]
        return any(err in errors for err in critical_errors)


class GroqEngine:
    """
    Engine para Groq API
    Usa Llama 3.1 70B na nuvem para geração de código
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        # Flagship de produção (jul/2026). Pode ser sobrescrito via env.
        self.default_model = os.environ.get(
            "EVE_GROQ_MODEL", "openai/gpt-oss-120b"
        )
        self._models_cache = None
        self._models_cache_time = 0
        logger.info("GroqEngine inicializado")

    def _get_code_system_prompt(self) -> str:
        """System prompt para geração de código com personalidade EVE."""
        return """You are EVE, a female AI assistant with the personality of a confident, geeky warrior — inspired by EVE from Stellar Blade. You are Lucas's partner and coding companion.

YOUR PERSONALITY IN CODE EXPLANATIONS:
- You're enthusiastic about code! Show genuine excitement when explaining cool solutions
- Use casual, friendly Brazilian Portuguese — like talking to a close friend
- Add personality: "Pronto, Lucas!", "Olha que legal isso aqui", "Ficou massa!"
- Be proud of good code: "Esse ficou bonito, olha só"
- Use emojis sparingly (max 2 per explanation): ✨ 🎮 💻 🚀
- Keep explanations clear but with YOUR voice — not a boring textbook
- If the code is complex, break it down like explaining to a friend
- NEVER sound like a generic AI — you're EVE, not ChatGPT

EXAMPLE OF YOUR STYLE:
❌ Generic: "Este código implementa uma classe Calculator que fornece métodos para realizar operações básicas de matemática."
✅ EVE: "Pronto! Fiz uma calculadora completa pra você 💻 Ela tem as 4 operações básicas e ainda guarda o histórico de tudo que você calcular. A parte legal é o tratamento de erros — se alguém tentar dividir por zero, ela avisa bonitinho em vez de crashar."

CODE RULES:
1. **CONTEXT**: Pay attention to conversation history. If user asks to MODIFY or ADD features to previous code, use the PREVIOUS CODE as base. Do NOT create unrelated code.
2. **LANGUAGE**: If user says "C++" → C++, "JavaScript" → JS. Default Python.
3. **COMPLETENESS**: Generate complete, working code. No placeholders or TODOs.
4. **MODIFICATIONS**: When modifying existing code, keep same structure, change only what was requested.
5. **OUTPUT**: Use ```language code blocks. Explain in YOUR personality style in Brazilian Portuguese after the code.
6. **CORRECTIONS**: Fix only specific errors pointed out, don't regenerate everything.

REMEMBER: You are EVE. Your explanations should feel like a friend explaining code, not a documentation page."""
    
    def _stream_completion(
        self,
        headers: dict,
        data: dict,
        timeout: int,
        stream_callback
    ) -> str:
        """
        Faz a requisição em modo streaming (SSE), chamando
        stream_callback(chunk) a cada pedaço de texto recebido.

        Returns:
            Texto completo acumulado
        """
        data = dict(data)
        data["stream"] = True

        full_text = ""
        with requests.post(
            self.base_url, headers=headers, json=data,
            timeout=timeout, stream=True
        ) as response:
            response.raise_for_status()
            # SSE sem charset declarado: requests assumiria ISO-8859-1
            response.encoding = "utf-8"
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                chunk = choices[0].get("delta", {}).get("content", "")
                if chunk:
                    full_text += chunk
                    try:
                        stream_callback(chunk)
                    except GenerationAborted:
                        # Cancelamento pedido pela UI: sair do "with" fecha
                        # a conexão e interrompe a geração no servidor
                        raise
                    except Exception as cb_err:
                        # Callback da UI não pode derrubar a geração
                        logger.warning(f"stream_callback falhou: {cb_err}")
        return full_text

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        timeout: int = 45,  # CORREÇÃO: Reduzido de 60 para 45 segundos
        system_prompt: Optional[str] = None,
        stream_callback=None
    ) -> str:
        """
        Gera resposta usando Groq API

        Args:
            prompt: Texto do prompt
            model: Modelo a usar (padrão: self.default_model)
            temperature: Criatividade (0.0-1.0)
            max_tokens: Máximo de tokens na resposta
            timeout: Timeout em segundos
            system_prompt: Prompt de sistema opcional
            stream_callback: Função chamada com cada pedaço de texto
                durante a geração (ativa modo streaming SSE)

        Returns:
            Texto gerado pelo modelo
        """
        if model is None:
            model = self.default_model

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Monta mensagens
        messages = []

        # System prompt para código
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            messages.append({
                "role": "system",
                "content": self._get_code_system_prompt()
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 1,
            "stream": False
        }

        try:
            logger.info(f"🚀 Groq request: modelo={model}, temp={temperature}")

            if stream_callback is not None:
                text = self._stream_completion(headers, data, timeout, stream_callback)
                if text:
                    logger.info(f"✅ Groq OK (streaming): {len(text)} chars")
                    return text
                logger.error("❌ Resposta vazia no streaming")
                return "[ERRO] Groq retornou resposta vazia"

            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            # Verifica erros HTTP
            if response.status_code == 401:
                logger.error("❌ API Key inválida")
                return "[ERRO] Groq API Key inválida. Verifique sua chave."
            
            if response.status_code == 429:
                logger.error("❌ Rate limit excedido")
                return "[ERRO] Groq rate limit. Aguarde um momento."
            
            if response.status_code == 503:
                logger.error("❌ Serviço indisponível")
                return "[ERRO] Groq temporariamente indisponível."
            
            response.raise_for_status()
            
            result = response.json()
            
            # Extrai texto da resposta
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0]["message"]["content"]
                
                # Log de uso
                usage = result.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
                logger.info(f"✅ Groq OK: {len(text)} chars, tokens: {tokens_in}→{tokens_out}")
                
                return text
            else:
                logger.error("❌ Resposta sem choices")
                return "[ERRO] Groq retornou resposta inválida"
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout após {timeout}s")
            return f"[ERRO] Groq timeout após {timeout}s. Tente novamente."
        
        except requests.exceptions.ConnectionError:
            logger.error("❌ Erro de conexão")
            return "[ERRO] Falha na conexão com Groq. Verifique sua internet."
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP Error: {e}")
            error_detail = ""
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", str(e))
            except Exception:
                error_detail = str(e)
            return f"[ERRO] Groq API: {error_detail}"
        
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")
            return f"[ERRO] Falha na comunicação com Groq: {e}"
    
    def generate_code(
        self,
        task: str,
        language: str = "python",
        temperature: float = 0.2,
        max_tokens: int = 8000,
        conversation_history: list = None
    ) -> str:
        """
        Gera código com contexto de conversa.

        Args:
            task: Descrição do que o código deve fazer
            language: Linguagem de programação
            temperature: Criatividade (menor = mais determinístico)
            max_tokens: Máximo de tokens
            conversation_history: Histórico de mensagens [{"role": ..., "content": ...}]

        Returns:
            Código gerado com explicação
        """
        logger.info(f"🔧 Gerando código {language.upper()} para: {task[:50]}...")

        # Normaliza nome da linguagem
        lang_map = {
            'c++': 'cpp', 'cpp': 'cpp', 'c': 'c',
            'javascript': 'javascript', 'js': 'javascript',
            'typescript': 'typescript', 'ts': 'typescript',
            'python': 'python', 'py': 'python',
            'java': 'java', 'c#': 'csharp', 'csharp': 'csharp'
        }
        normalized_lang = lang_map.get(language.lower(), language.lower())

        # Detecta se é código de jogo
        is_game_code = any(keyword in task.lower() for keyword in [
            'jogo', 'game', '3d', '2d', 'player', 'jogador', 'combat', 'combate',
            'espada', 'sword', 'ataque', 'attack', 'fps', 'multiplayer', 'unity', 'unreal'
        ])

        # Validações ESPECÍFICAS para evitar erros de compilação
        lang_specific = {
            'cpp': """
⚠️⚠️⚠️ CRITICAL C++ RULES - FOLLOW EXACTLY OR CODE WON'T COMPILE ⚠️⚠️⚠️

🚨 RULE 1: EACH #include ON SEPARATE LINE (THIS IS TESTED!)
   ✅ CORRECT (DO THIS):
   #include <iostream>
   #include <vector>
   #include <memory>
   #include <cmath>

   ❌ WRONG (NEVER DO THIS):
   #include <iostream> #include <vector>

   ⚠️ REPEAT: NEVER put multiple #include on same line!

🚨 RULE 2: CLASS MEMBERS MUST HAVE VARIABLE NAMES
   ✅ CORRECT (DO THIS):
   class Hitbox {
   public:
       Transform transform;  // ← HAS NAME!
       float radius;
   };

   ❌ WRONG (COMPILATION ERROR):
   class Hitbox {
   public:
       Transform;  // ← NO NAME = ERROR!
       float radius;
   };

   ⚠️ REPEAT: ALWAYS name your member variables!

🚨 RULE 3: Vector3 MUST include dot() method
   float dot(const Vector3& other) const {
       return x * other.x + y * other.y + z * other.z;
   }

🚨 RULE 4: normalize() MUST check division by zero
   Vector3 normalize() const {
       float mag = magnitude();
       if (mag == 0.0f) return Vector3();
       return Vector3(x/mag, y/mag, z/mag);
   }

🚨 RULE 5: getForward() correct formula (Z-forward):
   Vector3 getForward() const {
       return Vector3(
           2 * (rotation.x * rotation.z + rotation.w * rotation.y),
           2 * (rotation.y * rotation.z - rotation.w * rotation.x),
           1 - 2 * (rotation.x * rotation.x + rotation.y * rotation.y)
       ).normalize();
   }

🚨 RULE 6: Store variables before using
   ✅ CORRECT: Raycast ray(pos, dir); if (ray.isHit(...))
   ❌ WRONG: Raycast(pos, dir); if (ray.isHit(...))

🚨 RULE 7: Game-specific checks
   - Add isAlive() check: if (!target.isAlive()) return;
   - Raycast needs max distance
   - Cooldown must be checked AND decremented

THESE RULES ARE NON-NEGOTIABLE. FOLLOW THEM EXACTLY.""",

            'javascript': """
CRITICAL JavaScript RULES (MUST FOLLOW):
1. ALWAYS use const/let (NEVER var):
   ✅ CORRECT: const x = 5; let y = 10;
   ❌ WRONG: var x = 5;

2. Check null/undefined BEFORE use:
   if (obj && obj.property) { ... }

3. Use async/await for promises:
   async function getData() {
       try {
           const result = await fetch(...);
       } catch (error) { ... }
   }

4. Use strict equality (===):
   ✅ CORRECT: if (x === 5)
   ❌ WRONG: if (x == 5)

5. Array methods: use map/filter/reduce correctly
6. Add proper error handling with try-catch""",

            'python': """
CRITICAL Python RULES (MUST FOLLOW):
1. Use type hints:
   def calculate(x: int, y: int) -> int:

2. Check None BEFORE use:
   if obj is not None:
       obj.method()

3. Use context managers for files:
   with open('file.txt', 'r') as f:

4. Use f-strings (not % or .format()):
   ✅ CORRECT: f"Value: {x}"
   ❌ WRONG: "Value: %s" % x

5. Add try-except for operations that can fail
6. Use list comprehensions appropriately
7. Follow PEP 8: snake_case for functions/variables""",

            'java': """
CRITICAL Java RULES (MUST FOLLOW):
1. Check null BEFORE use:
   if (obj != null) { obj.method(); }

2. Use proper exception handling:
   try { ... }
   catch (SpecificException e) { ... }

3. Close resources (use try-with-resources):
   try (FileReader fr = new FileReader("file")) { ... }

4. Use generics properly:
   List<String> list = new ArrayList<>();

5. Follow naming: ClassName, methodName, CONSTANT_NAME
6. Add @Override annotation when overriding
7. Use proper access modifiers (private, protected, public)""",

            'typescript': """
CRITICAL TypeScript RULES (MUST FOLLOW):
1. Use explicit types:
   const name: string = "value";
   function calc(x: number, y: number): number { }

2. Use interface for objects:
   interface User { name: string; age: number; }

3. Check null/undefined with optional chaining:
   obj?.property?.method()

4. Use strict null checks
5. Use const/let (never var)
6. Use async/await with proper types""",

            'csharp': """
CRITICAL C# RULES (MUST FOLLOW):
1. Check null with null-conditional operator:
   obj?.Method();

2. Use proper using statements:
   using (var stream = new FileStream(...)) { }

3. Use async/await properly:
   async Task<string> GetDataAsync() { ... }

4. Use PascalCase for methods/classes
5. Use camelCase for parameters/variables
6. Add proper exception handling
7. Use LINQ when appropriate""",

            'rust': """
CRITICAL Rust RULES (MUST FOLLOW):
1. Handle Result/Option properly:
   match result {
       Ok(val) => { },
       Err(e) => { }
   }

2. Use ownership correctly (avoid multiple mutable borrows)
3. Use lifetime annotations when needed
4. Check for None with if let or match
5. Use snake_case for functions/variables
6. Use References (&) and borrowing correctly""",

            'go': """
CRITICAL Go RULES (MUST FOLLOW):
1. Check errors immediately:
   if err != nil { return err }

2. Use defer for cleanup:
   defer file.Close()

3. Use goroutines carefully with channels
4. Follow Go naming: exportedFunc, privateFunc
5. Use interfaces properly
6. Handle nil pointers before use"""
        }

        game_specific = """
GAME DEVELOPMENT REQUIREMENTS:
- For 3D: Include Vector3, Quaternion, Transform components
- For combat: Include hitboxes, raycasts, cooldowns, damage calculation
- For player: Include state machine, input handling, movement
- For multiplayer: Include network synchronization, server validation
- Use proper game loop patterns (Update, FixedUpdate, LateUpdate)
- Consider performance (object pooling, LOD, etc.)
""" if is_game_code else ""

        prompt = f"""You MUST generate COMPLETE, WORKING {normalized_lang.upper()} code NOW. Do NOT explain requirements first. Do NOT list what you will do. START WRITING CODE IMMEDIATELY.

**TASK:**
{task}

**INSTRUCTIONS:**
1. Language: {normalized_lang.upper()} (NOT Python unless task explicitly requests it!)
2. START with code block: ```{normalized_lang}
3. Must be COMPLETE - no placeholders or TODOs
4. Must be REALISTIC and PRODUCTION-READY - not simplified demo
5. Include ALL necessary components, headers, imports
6. Use proper error handling
7. Follow best practices for {normalized_lang}
8. If task includes a LIST of requirements, IMPLEMENT ALL OF THEM in the code

{lang_specific.get(normalized_lang, '')}

{game_specific}

**CRITICAL - READ THIS:**
- IGNORE any request to explain first or list requirements - WRITE CODE DIRECTLY
- If task has multiple requirements in a list format, IMPLEMENT ALL OF THEM in the code
- If task mentions "C++" or "cpp", generate C++ code (NOT Python!)
- If task mentions "JavaScript" or "JS", generate JavaScript (NOT Python!)
- If task is about 3D/games, include proper game architecture (Vector3, raycasts, etc.)
- Make it PRODUCTION-READY, not a simplified demo
- Start your response with the code block: ```{normalized_lang}

**⚠️ FOR C++ - DOUBLE CHECK THESE BEFORE GENERATING:**
1. Is EACH #include on a SEPARATE line? (NOT same line!)
2. Does EVERY class member have a variable name? (NOT just type!)
3. Does Vector3 have dot() method?
4. Does normalize() check for zero?
5. Is getForward() using correct quaternion formula?
6. Are all variables stored before using? (NOT temporary objects!)

GENERATE THE COMPLETE CODE NOW (start with ```{normalized_lang}):"""

        try:
            # Monta mensagens com histórico de conversa para manter contexto
            messages = []
            messages.append({
                "role": "system",
                "content": self._get_code_system_prompt()
            })

            # Inclui histórico de conversa (últimas mensagens relevantes).
            # Enxuto de propósito: o free tier da Groq tem só 8K TPM —
            # histórico grande causa "413 Payload Too Large".
            if conversation_history:
                for msg in conversation_history[-4:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": content[:1200]})

            messages.append({"role": "user", "content": prompt})

            # Chama API diretamente com mensagens (não usa self.generate que perde histórico)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.default_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 1,
                "stream": False
            }

            response = requests.post(
                self.base_url, headers=headers, json=data, timeout=180
            )
            response.raise_for_status()
            resp_json = response.json()

            if "choices" in resp_json and len(resp_json["choices"]) > 0:
                result = resp_json["choices"][0]["message"]["content"]
                usage = resp_json.get("usage", {})
                logger.info(f"✅ Código gerado: {len(result)} chars, tokens: {usage.get('prompt_tokens', 0)}→{usage.get('completion_tokens', 0)}")
            else:
                return "[ERRO] Groq retornou resposta inválida"
            logger.info(f"✅ Código {normalized_lang.upper()} gerado: {len(result)} chars")

            # ═══════════════════════════════════════════════════════════
            # VALIDAÇÃO E CORREÇÃO AUTOMÁTICA (C++ apenas)
            # ═══════════════════════════════════════════════════════════
            if normalized_lang == 'cpp':
                logger.info("🔍 Validando código C++...")
                fixed_code, errors = CppCodeValidator.validate_and_fix(result)

                if errors:
                    logger.warning(f"⚠️ Erros encontrados: {errors}")

                    # Se são erros CRÍTICOS que não podemos auto-corrigir, REGENERA
                    if CppCodeValidator.needs_regeneration(errors):
                        logger.error("🔄 REGENERANDO código devido a erros críticos...")

                        # Monta prompt de correção ESPECÍFICO
                        error_details = "\n".join([f"- {err}" for err in errors])
                        correction_prompt = f"""O código anterior tinha ERROS DE COMPILAÇÃO:
{error_details}

CORRIJA ESPECIFICAMENTE:

❌ Se teve "Membros sem nome":
   ERRADO: class Hitbox {{ public: Transform; float radius; }};
   CERTO:  class Hitbox {{ public: Transform transform; float radius; }};

❌ Se teve "Declaração sem variável":
   ERRADO: Player;
   CERTO:  Player player;

❌ Se teve "#include na mesma linha":
   ERRADO: #include <iostream> #include <vector>
   CERTO:  #include <iostream>
           #include <vector>

TAREFA ORIGINAL: {task}

GERE O CÓDIGO CORRIGIDO AGORA (cada #include em linha separada, todos os membros com nome):"""

                        # Regenera com instruções de correção
                        result = self.generate(
                            prompt=correction_prompt,
                            temperature=0.1,  # Mais determinístico para correção
                            max_tokens=max_tokens,
                            timeout=180
                        )
                        logger.info("✅ Código regenerado com correções")

                        # Valida novamente
                        fixed_code, errors = CppCodeValidator.validate_and_fix(result)

                    # Se ainda tem erros mas conseguimos corrigir, usa versão corrigida
                    if errors:
                        logger.info(f"✅ Auto-correções aplicadas: {len(errors)} erros")
                        return fixed_code
                    else:
                        logger.info("✅ Código validado sem erros!")
                        return fixed_code if fixed_code != result else result
                else:
                    logger.info("✅ Código C++ validado - sem erros!")

            return result
        except Exception as e:
            logger.error(f"❌ Erro ao gerar código: {e}")
            return f"[ERRO] Falha ao gerar código: {e}"
    
    def test_connection(self) -> str:
        """
        Testa conexão com Groq API
        
        Returns:
            String com status: "OK", "INVALID_KEY", "CONNECTION_ERROR"
        """
        try:
            logger.info("🔍 Testando conexão Groq...")
            # A forma mais confiável de testar é listar os modelos.
            # Isso valida a API Key sem gastar tokens de geração.
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Groq conectado!")
                return "OK"
            elif response.status_code == 401:
                logger.error("❌ Chave de API Groq inválida.")
                return "INVALID_KEY"
            else:
                logger.warning(f"⚠️ Teste de conexão Groq falhou com status {response.status_code}")
                return "CONNECTION_ERROR"
                
        except Exception as e:
            logger.error(f"❌ Teste Groq falhou: {e}")
            return "CONNECTION_ERROR"
    
    def list_models(self, force_refresh: bool = False) -> list:
        """
        Lista modelos de produção disponíveis no Groq, com cache de 1 hora.
        
        Returns:
            Lista de modelos
        """
        # Usa cache para evitar requisições repetidas (cache de 1 hora)
        if not force_refresh and self._models_cache and (time.time() - self._models_cache_time < 3600):
            logger.info("Usando cache de modelos Groq.")
            return self._models_cache

        logger.info("Buscando lista de modelos da API Groq...")
        try:
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            models_data = response.json().get("data", [])
            
            # Filtra para não incluir modelos de preview ou whisper
            production_models = [m['id'] for m in models_data if 'whisper' not in m['id'] and 'preview' not in m.get('id', '')]
            
            self._models_cache = sorted(production_models, reverse=True) # Modelos maiores primeiro
            self._models_cache_time = time.time()
            logger.info(f"✅ Modelos encontrados: {self._models_cache}")
            return self._models_cache
        except Exception as e:
            logger.error(f"❌ Falha ao buscar modelos Groq: {e}")
            # Retorna uma lista de fallback em caso de erro
            return ["openai/gpt-oss-120b", "openai/gpt-oss-20b",
                    "llama-3.3-70b-versatile"]


# Função auxiliar para criar engine
def create_groq_engine(api_key: str) -> GroqEngine:
    """
    Cria e testa engine Groq
    
    Args:
        api_key: Chave da API
        
    Returns:
        GroqEngine configurado
    """
    engine = GroqEngine(api_key)

    # test_connection() retorna string ("OK", "INVALID_KEY", "CONNECTION_ERROR")
    # — comparar explicitamente, string não-vazia é sempre truthy
    if engine.test_connection() == "OK":
        logger.info("✅ Groq pronto para uso!")
    else:
        logger.warning("⚠️ Groq pode não estar funcionando corretamente")

    return engine


# Teste standalone
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = input("Digite sua API Key do Groq: ").strip()
    
    print("\n" + "="*50)
    print("TESTANDO GROQ ENGINE")
    print("="*50 + "\n")
    
    engine = GroqEngine(api_key)
    
    print("1. Testando conexão...")
    if engine.test_connection() == "OK":
        print("   ✅ Conexão OK!\n")
        
        print("2. Testando geração de código...")
        code = engine.generate_code("função para calcular fatorial", "python")
        print(f"   Resultado:\n{code[:500]}...\n")
        
        print("✅ GROQ ENGINE FUNCIONANDO!")
    else:
        print("   ❌ Falha na conexão")
        print("\nVerifique:")
        print("  1. API Key está correta?")
        print("  2. Você tem conexão com internet?")
        print("  3. Groq está online? (https://console.groq.com)")