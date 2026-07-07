# core/eve.py - MOTOR PRINCIPAL EVE 2.0 (ARQUITETURA MODULAR)
"""
EVE - Stellar Blade AI Assistant
Motor principal com arquitetura modular e migração incremental via feature flags

ARQUITETURA 2.0:
✅ Feature Flags para migração incremental
✅ Brain central (classificação + decisão)
✅ Memória em camadas (short-term, long-term, preferences)
✅ Sistema de Skills (pure, model_optional, model_required)
✅ Estado interno (mood computacional)
✅ Múltiplos modelos (Llama, Phi-3, Qwen)
✅ Busca web integrada (Google, DuckDuckGo, Wikipedia)
✅ Spell checker português
✅ Análise de imagens (Qwen3-VL)

VERSÃO: 2.0 - Arquitetura Modular
"""

import os
import logging
import re
import sys
import io
import json
import time
from typing import Optional, List, Union, Dict, Any
from datetime import datetime

# Carrega variáveis de ambiente do arquivo .env
from dotenv import load_dotenv
load_dotenv(override=True)  # override=True para sobrescrever variáveis de sistema

# UTF-8 encoding
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# ═══════════════════════════════════════════════════════════════════
# FEATURE FLAGS - Controla migração incremental
# ═══════════════════════════════════════════════════════════════════
from core.feature_flags import FLAGS, reload_flags
from core.cache_policy import is_cacheable_prompt

# ═══════════════════════════════════════════════════════════════════
# IMPORTAÇÕES OPCIONAIS (graceful degradation)
# ═══════════════════════════════════════════════════════════════════

# === Componentes Legados ===
try:
    from core.router import Router
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    print("⚠️ Router não disponível")

try:
    from core.memory_manager import MemoryManager
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    print("⚠️ Memory Manager não disponível")

try:
    from core.web_search_tool import WebSearchTool
    WEB_TOOLS_AVAILABLE = True
except ImportError:
    WEB_TOOLS_AVAILABLE = False
    print("⚠️ Web Search Tool não disponível")

try:
    from core.spell_checker import get_spell_checker
    SPELL_CHECKER_AVAILABLE = True
except ImportError:
    SPELL_CHECKER_AVAILABLE = False
    print("⚠️ Spell Checker não disponível")

try:
    from engines.groq_engine import GroqEngine
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq Engine não disponível")

# === Componentes EVE 2.0 (carregamento condicional) ===

# Brain
BRAIN_AVAILABLE = False
Brain = None
BrainDecision = None
IntentType = None
if FLAGS.ENABLE_BRAIN_V2:
    try:
        from core.brain import Brain, BrainDecision, IntentType
        from core.config import PolicyConfig
        BRAIN_AVAILABLE = True
        print("✅ Brain V2 carregado")
    except ImportError as e:
        print(f"⚠️ Brain V2 não disponível: {e}")

# Layered Memory
LAYERED_MEMORY_AVAILABLE = False
LayeredMemory = None
if FLAGS.ENABLE_LAYERED_MEMORY:
    try:
        from memory.layered_memory import LayeredMemory
        LAYERED_MEMORY_AVAILABLE = True
        print("✅ Layered Memory carregada")
    except ImportError as e:
        print(f"⚠️ Layered Memory não disponível: {e}")

# Skills System
SKILLS_AVAILABLE = False
SkillRegistry = None
if FLAGS.ENABLE_SKILLS:
    try:
        from skills.registry import SkillRegistry
        SKILLS_AVAILABLE = True
        print("✅ Sistema de Skills carregado")
    except ImportError as e:
        print(f"⚠️ Sistema de Skills não disponível: {e}")

# Internal State
STATE_AVAILABLE = False
InternalState = None
if FLAGS.ENABLE_INTERNAL_STATE:
    try:
        from core.state import InternalState, get_state_context_for_prompt
        STATE_AVAILABLE = True
        print("✅ Estado Interno carregado")
    except ImportError as e:
        print(f"⚠️ Estado Interno não disponível: {e}")

# === EVE 2.0 Phase 1 Components ===

# Cognitive Trace
COGNITIVE_TRACE_AVAILABLE = False
CognitiveTracer = None
if FLAGS.ENABLE_COGNITIVE_TRACE:
    try:
        from core.cognitive_trace import CognitiveTracer, get_tracer
        COGNITIVE_TRACE_AVAILABLE = True
        print("✅ Cognitive Trace carregado")
    except ImportError as e:
        print(f"⚠️ Cognitive Trace não disponível: {e}")

# Model Policy
MODEL_POLICY_AVAILABLE = False
ModelUsagePolicy = None
if FLAGS.ENABLE_MODEL_POLICY:
    try:
        from core.model_policy import ModelUsagePolicy, get_model_policy
        MODEL_POLICY_AVAILABLE = True
        print("✅ Model Policy carregado")
    except ImportError as e:
        print(f"⚠️ Model Policy não disponível: {e}")

# Session State
SESSION_STATE_AVAILABLE = False
SessionState = None
if FLAGS.ENABLE_SESSION_STATE:
    try:
        from memory.session_state import SessionState, get_session_state
        SESSION_STATE_AVAILABLE = True
        print("✅ Session State carregado")
    except ImportError as e:
        print(f"⚠️ Session State não disponível: {e}")

# Task Memory
TASK_MEMORY_AVAILABLE = False
TaskMemory = None
if FLAGS.ENABLE_TASK_MEMORY:
    try:
        from memory.task_memory import TaskMemory, get_task_memory
        TASK_MEMORY_AVAILABLE = True
        print("✅ Task Memory carregado")
    except ImportError as e:
        print(f"⚠️ Task Memory não disponível: {e}")

# Planner
PLANNER_AVAILABLE = False
Planner = None
if FLAGS.ENABLE_PLANNER:
    try:
        from core.planner import Planner, get_planner
        PLANNER_AVAILABLE = True
        print("✅ Planner carregado")
    except ImportError as e:
        print(f"⚠️ Planner não disponível: {e}")

# Task Engine
TASK_ENGINE_AVAILABLE = False
TaskEngine = None
if FLAGS.ENABLE_TASK_ENGINE:
    try:
        from core.task_engine import TaskEngine, get_task_engine
        TASK_ENGINE_AVAILABLE = True
        print("✅ Task Engine carregado")
    except ImportError as e:
        print(f"⚠️ Task Engine não disponível: {e}")


logger = logging.getLogger("eve")
logger.setLevel(logging.INFO)

# ═══════════════════════════════════════════════════════════════════
# CLASSE EVE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class Eve:
    """
    Motor principal da EVE 2.0 com arquitetura modular.

    Features Legadas:
    - Roteamento inteligente de modelos
    - Busca web automática
    - Sistema de memória
    - Correção ortográfica
    - Personalidade completa
    - Análise de imagens

    Features 2.0 (via Feature Flags):
    - Brain central (classificação + orquestração)
    - Memória em camadas (short/long-term + preferences)
    - Sistema de Skills (pure, optional, required)
    - Estado interno (mood computacional)
    """

    def __init__(
        self,
        personality_file: str = "core/personality.txt",
        memory_file: str = "data/eve_memory.json",
        enable_web_search: bool = True,
    ):
        """
        Inicializa EVE com todos os componentes.

        Args:
            personality_file: Caminho do arquivo de personalidade
            memory_file: Caminho do arquivo de memória
            enable_web_search: Se deve habilitar busca web
        """
        logger.info("Inicializando EVE 2.0...")
        logger.info(f"Feature Flags: {FLAGS.get_enabled_features()}")

        # ═══════════════════════════════════════════════════════════════
        # COMPONENTES LEGADOS
        # ═══════════════════════════════════════════════════════════════

        # Router (roteamento de modelos)
        if ROUTER_AVAILABLE:
            self.router = Router()
            logger.info("✅ Router carregado")
        else:
            self.router = None
            logger.warning("❌ Router não disponível")

        # Groq Engine
        self.groq_engine = None
        if GROQ_AVAILABLE:
            try:
                groq_api_key = os.getenv("GROQ_API_KEY")
                if groq_api_key:
                    self.groq_engine = GroqEngine(api_key=groq_api_key)
                    logger.info("✅ Groq Engine carregado")
                else:
                    logger.warning("GROQ_API_KEY não encontrada. Groq Engine desabilitado.")
            except Exception as e:
                logger.error(f"Erro ao inicializar Groq Engine: {e}")

        # Memória LEGADA (contexto persistente)
        # Usado quando ENABLE_LAYERED_MEMORY=False
        self.memory = None
        self.layered_memory = None

        if FLAGS.ENABLE_LAYERED_MEMORY and LAYERED_MEMORY_AVAILABLE:
            # === MEMÓRIA V2 (Layered) ===
            self.layered_memory = LayeredMemory(
                persistence_path="data/eve_memory_v2.json"
            )
            logger.info(f"✅ Layered Memory carregada")
        elif MEMORY_AVAILABLE:
            # === MEMÓRIA LEGADA ===
            self.memory = MemoryManager(
                persistence_file=memory_file
            )
            logger.info(f"✅ Memória legada carregada ({len(self.memory)} entradas)")
        else:
            logger.warning("❌ Nenhum sistema de memória disponível")

        # Personalidade
        self.personality_file = personality_file
        self.personality = self._load_personality(personality_file)
        logger.info("✅ Personalidade carregada")

        # Histórico de conversa (sessão atual)
        self.conversation_history = []
        self.chats_file = "data/eve_chats.json"
        self.max_history = 10

        # Spell checker
        if SPELL_CHECKER_AVAILABLE:
            self.spell_checker = get_spell_checker()
            logger.info("✅ Spell checker habilitado")
        else:
            self.spell_checker = None
            logger.warning("❌ Spell checker não disponível")

        # Ferramentas web
        self.web_search_enabled = enable_web_search and WEB_TOOLS_AVAILABLE
        if self.web_search_enabled:
            self.web_search = WebSearchTool()
            logger.info("✅ Busca web habilitada")
        else:
            self.web_search = None
            logger.info("ℹ️ Modo offline (sem busca web)")

        # ═══════════════════════════════════════════════════════════════
        # COMPONENTES EVE 2.0 (Feature Flags)
        # ═══════════════════════════════════════════════════════════════

        # Estado Interno
        self.internal_state = None
        if FLAGS.ENABLE_INTERNAL_STATE and STATE_AVAILABLE:
            self.internal_state = InternalState(
                persistence_path="data/eve_state.json"
            )
            logger.info("✅ Estado Interno inicializado")

        # Sistema de Skills
        self.skill_registry = None
        if FLAGS.ENABLE_SKILLS and SKILLS_AVAILABLE:
            self.skill_registry = SkillRegistry()
            self.skill_registry.load_all()
            stats = self.skill_registry.get_stats()
            logger.info(f"✅ Skills carregadas: {stats['total']} total ({stats['pure']} pure, {stats['model_optional']} optional)")

        # Brain V2
        self.brain = None
        if FLAGS.ENABLE_BRAIN_V2 and BRAIN_AVAILABLE:
            self.brain = Brain(
                policy_config=PolicyConfig(),
                skill_registry=self.skill_registry,
                state=self.internal_state
            )
            logger.info("✅ Brain V2 inicializado")

        # ═══════════════════════════════════════════════════════════════
        # COMPONENTES EVE 2.0 PHASE 1
        # ═══════════════════════════════════════════════════════════════

        # Cognitive Trace (explainability)
        self.cognitive_tracer = None
        if FLAGS.ENABLE_COGNITIVE_TRACE and COGNITIVE_TRACE_AVAILABLE:
            self.cognitive_tracer = get_tracer()
            logger.info("✅ Cognitive Tracer inicializado")

        # Model Policy (Groq vs Ollama decisions)
        self.model_policy = None
        if FLAGS.ENABLE_MODEL_POLICY and MODEL_POLICY_AVAILABLE:
            self.model_policy = get_model_policy()
            logger.info("✅ Model Policy inicializado")

        # Session State (current cognitive state)
        self.session_state = None
        if FLAGS.ENABLE_SESSION_STATE and SESSION_STATE_AVAILABLE:
            self.session_state = get_session_state()
            logger.info("✅ Session State inicializado")

        # Task Memory (active/pending tasks)
        self.task_memory = None
        if FLAGS.ENABLE_TASK_MEMORY and TASK_MEMORY_AVAILABLE:
            self.task_memory = get_task_memory()
            stats = self.task_memory.get_stats()
            logger.info(f"✅ Task Memory inicializado ({stats['total']} tarefas)")

        # Planner (task decomposition)
        self.planner = None
        if FLAGS.ENABLE_PLANNER and PLANNER_AVAILABLE:
            self.planner = get_planner()
            logger.info("✅ Planner inicializado")

        # Task Engine (step execution)
        self.task_engine = None
        if FLAGS.ENABLE_TASK_ENGINE and TASK_ENGINE_AVAILABLE:
            self.task_engine = get_task_engine()
            logger.info("✅ Task Engine inicializado")

        # Capability Router (experimental — ENABLE_CAPABILITY_ROUTING)
        # Conecta o core.models.router.ModelRouter ao fluxo V2
        self.model_executor = None
        if FLAGS.ENABLE_CAPABILITY_ROUTING:
            try:
                from core.models.router import ModelRouter, ModelExecutor
                from engines.ollama_engine import OllamaEngine

                capability_router = ModelRouter()
                self.model_executor = ModelExecutor(
                    router=capability_router,
                    ollama_engine=OllamaEngine(),
                    groq_engine=self.groq_engine
                )
                logger.info("✅ Capability Router conectado (experimental)")
            except Exception as e:
                logger.warning(f"⚠️ Capability Router não disponível: {e}")

        logger.info("🎉 EVE 2.0 inicializado com sucesso!")
    
    # ═══════════════════════════════════════════════════════════════
    # PERSONALIDADE
    # ═══════════════════════════════════════════════════════════════
    
    def _load_personality(self, file_path: str) -> str:
        """
        Carrega arquivo de personalidade.
        
        Args:
            file_path: Caminho do arquivo personality.txt
            
        Returns:
            String com conteúdo da personalidade
        """
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"Personalidade carregada de {file_path}")
                return content
            except Exception as e:
                logger.error(f"Erro ao carregar personalidade: {e}")
        
        # Personalidade padrão (fallback)
        logger.warning("Usando personalidade padrão")
        return """Você é EVE, uma assistente inteligente.
Seja útil, precisa e amigável.
Use português brasileiro."""
    
    # ═══════════════════════════════════════════════════════════════
    # FORMATAÇÃO DE RESPOSTAS
    # ═══════════════════════════════════════════════════════════════
    
    def _format_response(self, response: str) -> str:
        """
        Formata resposta para melhor legibilidade.
        Apenas limpeza leve — respeita a formatação do modelo.
        """
        if not response or len(response) < 20:
            return response

        # Remove espaços em branco excessivos no início/fim
        response = response.strip()

        # Normaliza múltiplas linhas em branco (máximo 2)
        response = re.sub(r'\n{3,}', '\n\n', response)

        # Remove espaços trailing em cada linha
        lines = [line.rstrip() for line in response.split('\n')]
        response = '\n'.join(lines)

        return response
    
    # ═══════════════════════════════════════════════════════════════
    # BUSCA WEB
    # ═══════════════════════════════════════════════════════════════
    
    def _should_search_web(self, prompt: str) -> bool:
        """
        Detecta se deve fazer busca web baseado no prompt.
        Busca apenas quando realmente necessário para evitar respostas poluídas.
        """
        if not self.web_search_enabled:
            return False

        prompt_lower = prompt.lower().strip()

        # Ignora prompts curtos e saudações
        if len(prompt_lower) < 10:
            return False

        casual = [
            "oi", "olá", "ola", "hi", "hello", "tudo bem", "como vai",
            "obrigado", "valeu", "ok", "blz", "entendi", "sim", "não",
            "legal", "massa", "show", "beleza", "tchau", "até mais"
        ]
        if prompt_lower in casual:
            return False

        # Busca EXPLÍCITA - sempre busca (prioridade máxima)
        explicit = ["pesquise", "pesquisar", "busque", "buscar", "procure", "procurar"]
        if any(t in prompt_lower for t in explicit):
            return True

        # Não buscar para perguntas sobre programação/código
        code_signals = [
            "código", "codigo", "função", "funcao", "script",
            "debug", "erro no código", "compilar", "rodar", "executar",
            "variável", "variavel", "class ", "def ", "import ", "print(",
            "[modo código]"
        ]
        if any(s in prompt_lower for s in code_signals):
            return False

        # Não buscar para conversas sobre o próprio bot/EVE
        eve_signals = ["você", "voce", "eve", "seu nome", "sua", "me ajuda", "me ajude"]
        if any(s in prompt_lower for s in eve_signals) and len(prompt_lower) < 40:
            return False

        # Perguntas factuais que realmente precisam de dados externos
        factual_questions = [
            "o que é", "o que foi", "o que são",
            "quem foi", "quem é", "quem eram",
            "quando foi", "quando aconteceu",
            "onde fica", "onde é",
            "me fale sobre", "fale sobre",
            "qual a história", "qual a população",
            "notícias sobre", "últimas notícias"
        ]
        if any(q in prompt_lower for q in factual_questions):
            return True

        return False

    def _detect_uncertainty(self, response: str) -> bool:
        """
        Detecta se a resposta indica incerteza ou falta de conhecimento.

        Args:
            response: Resposta gerada pela EVE

        Returns:
            True se detectar incerteza
        """
        uncertainty_phrases = [
            "não sei", "não tenho certeza", "não consigo", "não conheço",
            "desconheço", "não tenho informações", "não posso responder",
            "preciso de mais informações", "não disponível", "não encontrado"
        ]

        response_lower = response.lower()
        return any(phrase in response_lower for phrase in uncertainty_phrases)
    
    def _extract_search_query(self, prompt: str) -> str:
        """
        Extrai query de busca do prompt do usuário via extração local de palavras-chave.

        Args:
            prompt: Prompt do usuário

        Returns:
            Query otimizada para busca
        """
        query = prompt.lower().strip()

        # Abreviações comuns (principalmente jogos)
        abbr = {
            'hoi4': 'hearts of iron 4',
            'vic3': 'victoria 3',
            'ck3': 'crusader kings 3',
            'eu4': 'europa universalis 4',
            'stellaris': 'stellaris game',
            'tor': 'tor browser network'
        }

        # Substitui abreviações
        for a, full in abbr.items():
            if a in query:
                query = query.replace(a, full)
                logger.info(f"Expandiu abreviação: {a} → {full}")

        # Remove pontuação
        query = re.sub(r'[?!.,;:]+', ' ', query)
        words = query.split()

        # CORREÇÃO: Lista reduzida de stop words (remove menos palavras importantes)
        stop_words = ['pode', 'você', 'voce', 'quero', 'pesquise', 'busque']
        keywords = [w for w in words if len(w) >= 3 and w not in stop_words]  # Reduzido de 4 para 3

        # CORREÇÃO: Pega até 8 palavras-chave (aumentado de 6 para 8)
        result = ' '.join(keywords[:8])

        return result if result else prompt[:50]
    
    # ═══════════════════════════════════════════════════════════════
    # VALIDAÇÃO DE RESPOSTAS
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_response(self, response: str) -> str:
        """
        Valida e limpa resposta do modelo.
        Protege blocos de código da limpeza.
        """
        if not response or len(response) < 5:
            return "Desculpa, tive um problema."

        # Detecta vazamento de sistema (crítico!)
        if "PERSONALIDADE CORE:" in response or "REGRAS CRÍTICAS:" in response:
            logger.error("Vazamento de sistema detectado!")
            return "Ops, tive um bug!"

        # === Protege blocos de código antes de processar ===
        code_blocks = []
        def _save_code(match):
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

        # Extrai blocos ```...``` para não serem processados
        response = re.sub(r'```[\s\S]*?```', _save_code, response)

        # Remove apenas caracteres de controle (mantém emojis, acentos, etc)
        response = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', response)

        # Remove placeholders de links inventados
        response = re.sub(
            r'\{link que (?:direciona|redireciona) para (?:uma )?fonte (?:confiável|segura)\}',
            '',
            response,
            flags=re.IGNORECASE
        )

        # Spell checker (apenas no texto, não no código)
        if self.spell_checker:
            response = self.spell_checker.correct_text(response, aggressive=False, use_online=False)

        # Remove repetições de palavras consecutivas (fora de código)
        # Só palavras com 4+ letras para não afetar duplicações legítimas
        # do português ("dia a dia", "que que" coloquial etc.)
        response = re.sub(r'\b([A-Za-zÀ-ÿ]{4,})\s+\1\b', r'\1', response, flags=re.IGNORECASE)

        # Normaliza múltiplas linhas em branco
        response = re.sub(r'\n{3,}', '\n\n', response)

        # === Restaura blocos de código intactos ===
        for i, block in enumerate(code_blocks):
            response = response.replace(f"__CODE_BLOCK_{i}__", block)

        return response.strip()
    
    # ═══════════════════════════════════════════════════════════════
    # GERAÇÃO DE RESPOSTAS (PRINCIPAL)
    # ═══════════════════════════════════════════════════════════════

    def generate_response(
        self,
        prompt: str,
        model_choice: Optional[str] = None,
        files: Optional[List[str]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        Gera resposta com todas as funcionalidades integradas.

        Esta é a função principal do EVE Engine.
        Com ENABLE_BRAIN_V2=True, usa o novo fluxo Brain-based.
        Caso contrário, usa o fluxo legado.

        Args:
            prompt: Pergunta/comando do usuário
            model_choice: Modelo específico (opcional)
            files: Lista de arquivos anexados (imagens)
            max_tokens: Máximo de tokens na resposta
            temperature: Temperatura (0.0-1.0)
            stream_callback: Função chamada com cada pedaço de texto durante
                a geração (só no modelo local/Ollama). O texto final retornado
                passa por pós-processamento e pode diferir levemente do
                streamado — a UI deve substituir o preview pelo final.

        Returns:
            Dicionário com 'text', 'artifacts', 'model_used', etc.
        """
        start_time = time.time()

        # Validação de entrada
        if not prompt or (isinstance(prompt, str) and len(prompt.strip()) == 0):
            return {
                "text": "Desculpe, não recebi nenhuma pergunta.",
                "artifacts": None,
                "model_used": "none",
                "web_search_used": False
            }

        # ═══════════════════════════════════════════════════════════
        # FLUXO BRAIN V2 (quando habilitado)
        # ═══════════════════════════════════════════════════════════
        if FLAGS.ENABLE_BRAIN_V2 and self.brain and isinstance(prompt, str):
            return self._generate_response_v2(
                prompt=prompt,
                model_choice=model_choice,
                files=files,
                max_tokens=max_tokens,
                temperature=temperature,
                start_time=start_time,
                stream_callback=stream_callback
            )

        # ═══════════════════════════════════════════════════════════
        # FLUXO LEGADO (backward compatibility)
        # ═══════════════════════════════════════════════════════════
        return self._generate_response_legacy(
            prompt=prompt,
            model_choice=model_choice,
            files=files,
            max_tokens=max_tokens,
            temperature=temperature
        )

    def _generate_response_v2(
        self,
        prompt: str,
        model_choice: Optional[str],
        files: Optional[List[str]],
        max_tokens: int,
        temperature: float,
        start_time: float,
        stream_callback=None
    ) -> Dict[str, Any]:
        """
        Fluxo de geração usando Brain V2.
        Brain decide → Contexto → Skills → Modelo → Pós-processamento
        """
        logger.info("🧠 [Brain V2] Iniciando análise...")

        # Limita tamanho
        if len(prompt) > 5000:
            prompt = prompt[:5000]
            logger.warning("⚠️ Prompt truncado para 5000 caracteres")

        # 1. Brain analisa e decide
        decision = self.brain.analyze(
            user_input=prompt,
            conversation_context=self.conversation_history,
            attached_files=files or []
        )

        if FLAGS.DEBUG_BRAIN_DECISIONS:
            logger.info(f"[Brain] Decision: {decision.to_dict()}")

        # Override: Se model_choice="groq", forçar modo código
        if model_choice == "groq":
            decision.metadata['force_code'] = True
            logger.info("🚀 Modo CÓDIGO forçado via model_choice")

        # 2. Verificar cache (só para prompts independentes de contexto,
        #    sem código, skill ou imagem anexada)
        if (not files and not decision.needs_skill()
                and not decision.metadata.get('force_code')
                and is_cacheable_prompt(prompt)):
            cached = self._get_cached_response(prompt)
            if cached:
                return cached

        # Adicionar ao histórico
        self._add_to_history("user", prompt)

        # 3. Executar skill se selecionada
        # (com imagem anexada, skill é pulada — skills só processam texto
        #  e poderiam interceptar a mensagem antes do modelo de visão)
        skill_output = None
        if decision.selected_skill and self.skill_registry and not files:
            skill_result = self._execute_skill(decision, prompt)
            if skill_result and skill_result.get('handled'):
                return skill_result
            if skill_result:
                skill_output = skill_result.get('output')

        # 4. Coletar contexto (memória, estado e tools como busca web)
        context = self._collect_context(decision, prompt)
        if skill_output:
            context['skill_output'] = skill_output

        # 5. Gerar resposta com modelo
        response = self._generate_with_model(
            prompt=prompt,
            decision=decision,
            context=context,
            model_choice=model_choice,
            max_tokens=max_tokens,
            temperature=temperature,
            files=files,
            stream_callback=stream_callback
        )

        # 6. Pós-processamento
        response_text = self._postprocess_response(
            response['text'],
            decision.postprocessing
        )

        # 7. Atualizar estado interno
        response_time_ms = int((time.time() - start_time) * 1000)
        self._update_state(prompt, response_text, response_time_ms, response.get('model_used'))

        # 8. Salvar na memória
        self._save_to_memory(prompt, response_text)

        self._add_to_history("assistant", response_text, response.get('artifacts'))

        return {
            "text": response_text,
            "artifacts": response.get('artifacts'),
            "model_used": response.get('model_used', 'unknown'),
            "web_search_used": bool(context.get('web_search')) or response.get('web_search_used', False),
            "brain_decision": decision.to_dict() if FLAGS.DEBUG_BRAIN_DECISIONS else None,
            "response_time_ms": response_time_ms
        }

    def _execute_skill(
        self,
        decision,  # BrainDecision
        prompt: str
    ) -> Optional[Dict[str, Any]]:
        """Executa skill selecionada pelo Brain"""
        if not decision.selected_skill or not self.skill_registry:
            return None

        skill = self.skill_registry.get(decision.selected_skill)
        if not skill:
            return None

        logger.info(f"🔧 Executando skill: {decision.selected_skill}")

        # Preparar contexto para skill
        skill_context = {
            'conversation_history': self.conversation_history[-5:],
            'metadata': decision.metadata,
            'preferences': self.layered_memory.get_preferences() if self.layered_memory else {}
        }

        # Executar
        result = self.skill_registry.execute_skill(
            decision.selected_skill,
            prompt,
            skill_context
        )

        if result and result.success:
            # Skill pura resolve sem modelo
            if not skill.requires_model:
                return {
                    'handled': True,
                    'text': result.output,
                    'artifacts': result.artifacts,
                    'model_used': f'skill:{decision.selected_skill}',
                    'web_search_used': False
                }
            # Skill que precisa de modelo: devolve a saída para entrar
            # no contexto do prompt em vez de ser descartada
            return {'handled': False, 'output': result.output}

        return None

    def _collect_context(
        self,
        decision,  # BrainDecision
        prompt: str
    ) -> Dict[str, Any]:
        """Coleta contexto baseado na decisão do Brain"""
        context = {
            'personality': self.personality,
            'conversation': self._build_conversation_context()
        }

        # Contexto da memória em camadas
        if self.layered_memory:
            layers = []
            ctx_req = decision.context_requirement

            # Determinar quais camadas usar baseado no ContextRequirement
            from core.context import ContextSource
            for src in ctx_req.sources:
                if src == ContextSource.SHORT_TERM:
                    layers.append('short')
                elif src == ContextSource.LONG_TERM:
                    layers.append('long')
                elif src == ContextSource.PREFERENCES:
                    layers.append('preferences')
                elif src == ContextSource.SUMMARY:
                    layers.append('summary')

            if not layers:
                layers = ['short', 'preferences']

            memory_context = self.layered_memory.get_context(
                query=prompt if 'long' in layers else None,
                layers=layers
            )
            context['memory'] = memory_context

        # Estado interno
        if self.internal_state:
            context['state_instruction'] = get_state_context_for_prompt(self.internal_state)

        # Ferramentas decididas pelo Brain (busca web etc.)
        context['web_search'] = self._run_web_search_tool(decision, prompt)

        return context

    def _run_web_search_tool(self, decision, prompt: str) -> Optional[str]:
        """
        Executa a busca web decidida pelo Brain (fluxo V2).
        Retorna o texto formatado da busca ou None.
        """
        if not self.web_search_enabled or not self.web_search:
            return None
        if decision.metadata.get('force_code'):
            return None

        from core.context import ToolType
        ctx_req = decision.context_requirement
        if not ctx_req.has_tool(ToolType.WEB_SEARCH):
            return None

        params = ctx_req.get_tool_params(ToolType.WEB_SEARCH) or {}
        query = params.get('query') or self._extract_search_query(prompt)
        if not query or len(query) <= 3:
            return None

        logger.info(f"🔍 [Brain V2] Buscando na web: {query}")
        try:
            result = self.web_search.search_formatted(query)
        except Exception as e:
            logger.warning(f"⚠️ Busca web falhou: {e}")
            return None

        if (result and len(result) > 100
                and not result.startswith(("[OFFLINE]", "[ERRO]", "[SEM RESULTADOS]"))):
            logger.info(f"✅ Resultado da web válido ({len(result)} caracteres)")
            return result

        logger.info("⚠️ Busca web sem resultado útil")
        return None

    def _generate_with_model(
        self,
        prompt: str,
        decision,  # BrainDecision
        context: Dict[str, Any],
        model_choice: Optional[str],
        max_tokens: int,
        temperature: float,
        files: Optional[List[str]] = None,
        stream_callback=None
    ) -> Dict[str, Any]:
        """Gera resposta usando modelo apropriado"""

        # Imagens anexadas: rotear direto para o modelo de visão
        if files:
            return self._generate_image_response(prompt, files, max_tokens, temperature)

        # Construir prompt completo
        full_prompt = self._build_full_prompt(prompt, context, decision)

        # Modo código forçado
        if decision.metadata.get('force_code') or model_choice == "groq":
            if self.groq_engine:
                return self._generate_code_response(prompt, decision)

        # Usar Groq para tarefas de código
        if decision.selected_capability == 'code_strong' and self.groq_engine:
            return self._generate_code_response(prompt, decision)

        # Router por capability (experimental, atrás de flag)
        if self.model_executor and decision.selected_capability:
            result = self._generate_via_capability_router(
                decision, full_prompt, max_tokens, temperature
            )
            if result is not None:
                return result
            # Falhou — segue para o fluxo padrão abaixo

        # Chat: tenta Groq primeiro (rápido, nuvem) com fallback local.
        # Resultados de busca web são sempre processados pelo modelo local
        # (mesma regra do fluxo legado).
        if (self.groq_engine and not context.get('web_search')
                and not model_choice):
            groq_response = self._generate_groq_chat(
                full_prompt, max_tokens, temperature
            )
            if groq_response is not None:
                return groq_response
            logger.warning("⚠️ Groq indisponível - usando modelo local")

        # Modelo local (Ollama)
        return self._generate_local_response(
            full_prompt, model_choice, max_tokens, temperature,
            stream_callback=stream_callback
        )

    def _generate_groq_chat(
        self,
        full_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Optional[Dict[str, Any]]:
        """
        Tenta gerar resposta de chat via Groq (nuvem).
        Retorna None se falhar, para o chamador cair no modelo local.
        """
        logger.info("☁️ Tentando gerar com Groq (nuvem)...")
        try:
            response_text = self.groq_engine.generate(
                prompt=full_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=self.personality
            )
        except Exception as e:
            logger.warning(f"⚠️ Erro ao usar Groq: {e}")
            return None

        if not response_text or response_text.startswith("[ERRO]"):
            return None

        logger.info("✅ Resposta gerada com Groq (nuvem)")
        return {
            'text': response_text,
            'artifacts': True if "```" in response_text else None,
            'model_used': 'groq',
            'web_search_used': False
        }

    def _generate_via_capability_router(
        self,
        decision,  # BrainDecision
        full_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Optional[Dict[str, Any]]:
        """
        Gera resposta usando o ModelRouter por capabilities
        (ENABLE_CAPABILITY_ROUTING). Retorna None em caso de falha,
        para o chamador usar o fluxo padrão.
        """
        try:
            response_text, model = self.model_executor.execute(
                capability=decision.selected_capability,
                prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.warning(f"⚠️ Capability router falhou ({e}) - usando fluxo padrão")
            return None

        if not response_text or response_text.startswith("[ERRO]"):
            return None

        logger.info(f"✅ [Capability Router] Resposta via {model.provider}:{model.model_id}")
        return {
            'text': response_text,
            'artifacts': True if "```" in response_text else None,
            'model_used': f'{model.provider}_{model.model_id}',
            'web_search_used': False
        }

    def _build_full_prompt(
        self,
        prompt: str,
        context: Dict[str, Any],
        decision  # BrainDecision (unused but kept for API consistency)
    ) -> str:
        """Constrói prompt completo com todos os contextos"""
        parts = [context.get('personality', '')]

        # Adicionar instrução de estado
        if context.get('state_instruction'):
            parts.append(f"\n{context['state_instruction']}\n")

        # Adicionar contexto de memória
        if context.get('memory'):
            mem = context['memory']
            if mem.get('summary'):
                parts.append(f"\n[Resumo da conversa]: {mem['summary']}\n")
            if mem.get('relevant_facts'):
                facts = [f['content'] for f in mem['relevant_facts'][:3]]
                parts.append(f"\n[Lembranças relevantes]: {', '.join(facts)}\n")
            if mem.get('preferences'):
                prefs = mem['preferences']
                if prefs:
                    parts.append(f"\n[Preferências do usuário]: {prefs}\n")

        # Adicionar resultado de skill (quando a skill não resolve sozinha)
        if context.get('skill_output'):
            parts.append(f"\n[Resultado de ferramenta interna]:\n{context['skill_output']}\n")

        # Adicionar informações da web (com regras contra alucinação)
        if context.get('web_search'):
            parts.append(f"""
REGRAS ESTRITAS:
1. Use APENAS as informações fornecidas abaixo
2. NÃO invente, deduza ou adicione detalhes que não estão explicitamente escritos
3. Se não tem certeza ou a informação não está disponível, diga: "Não tenho informação específica sobre isso"

===== INFORMAÇÃO DA WEB =====
{context['web_search']}
=============================
""")

        # Adicionar histórico
        parts.append(context.get('conversation', ''))

        # Adicionar prompt atual
        parts.append(f"\nUsuário (AGORA): {prompt}")

        return '\n'.join(parts)

    def _generate_code_response(
        self,
        prompt: str,
        decision  # BrainDecision
    ) -> Dict[str, Any]:
        """Gera resposta de código usando Groq"""
        if not self.groq_engine:
            return self._generate_local_response(prompt, None, 400, 0.6)

        task = prompt.replace("[MODO CÓDIGO]", "").strip()
        language = decision.metadata.get('language', 'python')

        logger.info(f"🚀 Gerando código ({language}) com Groq...")

        response_text = self.groq_engine.generate_code(
            task=task,
            language=language,
            conversation_history=self.conversation_history
        )

        if response_text.startswith("[ERRO]"):
            logger.warning("❌ Groq falhou - fallback para modelo local")
            return self._generate_local_response(prompt, None, 400, 0.3)

        artifacts = True if "```" in response_text else None

        return {
            'text': response_text,
            'artifacts': artifacts,
            'model_used': 'groq',
            'web_search_used': False
        }

    def _generate_image_response(
        self,
        prompt: str,
        files: List[str],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Gera resposta para imagem anexada usando o modelo de visão (fluxo V2)"""
        if not self.router:
            return {
                'text': "[ERRO] Router não disponível",
                'artifacts': None,
                'model_used': 'error',
                'web_search_used': False
            }

        prompt_dict = {
            "type": "image",
            "path": files[0],
            "text": prompt if isinstance(prompt, str) else "Descreva esta imagem"
        }

        backend, model_id = self.router.resolve_model(prompt_dict, None)
        logger.info(f"🖼️ [Brain V2] Analisando imagem com {model_id}")

        response = self.router.generate(
            prompt_dict,
            explicit_model=model_id,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return {
            'text': response.get('text', ''),
            'artifacts': response.get('artifacts'),
            'model_used': f'ollama_{model_id}',
            'web_search_used': False
        }

    def _generate_local_response(
        self,
        prompt: str,
        model_choice: Optional[str],
        max_tokens: int,
        temperature: float,
        stream_callback=None
    ) -> Dict[str, Any]:
        """Gera resposta usando modelo local (Ollama)"""
        if not self.router:
            return {
                'text': "[ERRO] Router não disponível",
                'model_used': 'error',
                'web_search_used': False
            }

        # "groq" não é um modelo do router local — usa roteamento automático
        explicit = None if model_choice == "groq" else model_choice
        backend, model_id = self.router.resolve_model(prompt, explicit)
        logger.info(f"💻 Gerando com Ollama: {model_id}")

        response = self.router.generate(
            prompt,
            explicit_model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            stream_callback=stream_callback
        )

        return {
            'text': response.get('text', ''),
            'artifacts': response.get('artifacts'),
            'model_used': f'ollama_{model_id}',
            'web_search_used': False
        }

    def _postprocess_response(
        self,
        response: str,
        steps: List[str]
    ) -> str:
        """Aplica pós-processamento à resposta"""
        if not response:
            return "Desculpa, tive um problema."

        # Validação base
        response = self._validate_response(response)

        # Formatação
        if 'format_response' in steps:
            response = self._format_response(response)

        return response

    def _update_state(
        self,
        prompt: str,
        response: str,
        response_time_ms: int,
        model_used: str
    ):
        """Atualiza estado interno após interação"""
        if self.internal_state:
            self.internal_state.update(
                user_input=prompt,
                response=response,
                success=True,
                response_time_ms=response_time_ms,
                model_used=model_used
            )

    def _save_to_memory(self, prompt: str, response: str):
        """Salva interação na memória"""
        cacheable = is_cacheable_prompt(prompt)
        if self.layered_memory:
            self.layered_memory.add_exchange(
                user_input=prompt,
                assistant_response=response,
                cacheable=cacheable
            )
        elif self.memory:
            self.memory.add_memory(prompt, metadata={"response": response})
            if cacheable and len(prompt) < 200:
                self.memory.cache_response(prompt, response)

    def _get_cached_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Verifica cache de respostas"""
        cached = None

        if self.layered_memory:
            cached = self.layered_memory.get_cached_response(prompt)
        elif self.memory:
            cached = self.memory.get_cached_response(prompt)

        if cached:
            logger.info("✨ Resposta do cache (instantânea)")
            return {
                "text": cached,
                "artifacts": None,
                "model_used": "cache",
                "web_search_used": False
            }
        return None

    def _generate_response_legacy(
        self,
        prompt: str,
        model_choice: Optional[str],
        files: Optional[List[str]],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Fluxo de geração LEGADO (backward compatibility).
        Usado quando ENABLE_BRAIN_V2=False.
        """
        # Limita tamanho para evitar sobrecarga
        if isinstance(prompt, str):
            if len(prompt) > 5000:
                prompt = prompt[:5000]
                logger.warning("⚠️ Prompt truncado para 5000 caracteres")

            logger.info(f"Gerando resposta para: {prompt[:50]}...")

            # Verifica cache para perguntas frequentes
            # (só para prompts independentes de contexto)
            if self.memory and not files and is_cacheable_prompt(prompt):
                cached_response = self.memory.get_cached_response(prompt)
                if cached_response:
                    logger.info("✨ Resposta do cache (instantânea)")
                    return {
                        "text": cached_response,
                        "artifacts": None,
                        "model_used": "cache",
                        "web_search_used": False
                    }

            self._add_to_history("user", prompt)
        else:
            logger.info("Gerando resposta para imagem...")
        
        # ═══════════════════════════════════════════════════════════
        # DETECÇÃO DE INTENT (movido para ANTES da busca web)
        # ═══════════════════════════════════════════════════════════

        intent = "chat"  # default

        # CORREÇÃO CRÍTICA: Se model_choice for "groq", FORÇA modo código
        # Isso acontece quando o usuário ativa o botão de código na GUI
        logger.info(f"[DEBUG] model_choice = {model_choice}")

        if model_choice == "groq":
            intent = "code"
            logger.info("🚀 Modo CÓDIGO forçado (botão ativado na GUI)")
        elif self.router and isinstance(prompt, str):
            intent = self.router.detect_intent(prompt)
            logger.info(f"🧠 Intenção detectada: {intent}")

        logger.info(f"[DEBUG] Intent final = {intent}")

        # ═══════════════════════════════════════════════════════════
        # BUSCA WEB (se necessário e SE NÃO FOR MODO CÓDIGO)
        # ═══════════════════════════════════════════════════════════

        web_context = ""
        used_web_search = False

        # CORREÇÃO CRÍTICA: NUNCA busca web se a intent for 'code' OU model_choice for "groq"
        if intent == 'code' or model_choice == "groq":
            logger.info("⏭️ PULANDO busca web - Modo código ativo")
        elif isinstance(prompt, str) and self._should_search_web(prompt):
            query = self._extract_search_query(prompt)

            if query and len(query) > 3:
                logger.info(f"🔍 Buscando na web: {query}")

                # Tenta buscar com múltiplas variações da query
                search_result = None
                queries_to_try = []

                # Detecta jogos e adiciona "game" ou "video game" para melhor contexto
                games_keywords = {
                    "victoria": "Victoria 3 video game",
                    "hearts": "Hearts of Iron 4 game",
                    "hoi4": "Hearts of Iron 4 game",
                    "hoi": "Hearts of Iron 4 game",
                    "crusader": "Crusader Kings 3 game",
                    "ck3": "Crusader Kings 3 game",
                    "europa": "Europa Universalis 4 game",
                    "eu4": "Europa Universalis 4 game",
                    "stellaris": "Stellaris game"
                }

                # Verifica se é um jogo conhecido
                is_game = False
                for keyword, game_name in games_keywords.items():
                    if keyword in query.lower():
                        queries_to_try.insert(0, f"{game_name} {query}")
                        queries_to_try.insert(0, game_name)
                        is_game = True
                        break

                # Se não for jogo específico, tenta query original
                queries_to_try.append(query)

                # Se menciona "jogo" ou "game", adiciona às tentativas
                if "jogo" in prompt.lower() or "game" in prompt.lower():
                    queries_to_try.insert(0, f"{query} video game")

                # Para jogos, tenta Wikipedia DIRETAMENTE em inglês primeiro
                if is_game:
                    logger.info("🎮 Jogo detectado! Tentando Wikipedia EN diretamente...")
                    for wiki_query in queries_to_try:
                        wiki_result = self.web_search._search_wikipedia(wiki_query, lang="en")
                        if wiki_result.get("success") and wiki_result.get("abstract"):
                            abstract = wiki_result.get("abstract", "")
                            if len(abstract) > 100:
                                search_result = f"INFORMAÇÃO ENCONTRADA:\n{abstract}"
                                logger.info(f"   ✅ Wikipedia EN sucesso com: {wiki_query}")
                                break

                    # Se não achou em inglês, tenta em português
                    if not search_result:
                        logger.info("   Tentando Wikipedia PT...")
                        for wiki_query in queries_to_try:
                            wiki_result = self.web_search._search_wikipedia(wiki_query, lang="pt")
                            if wiki_result.get("success") and wiki_result.get("abstract"):
                                abstract = wiki_result.get("abstract", "")
                                if len(abstract) > 100:
                                    search_result = f"INFORMAÇÃO ENCONTRADA:\n{abstract}"
                                    logger.info(f"   ✅ Wikipedia PT sucesso com: {wiki_query}")
                                    break

                # Se Wikipedia não funcionou, tenta Google/DuckDuckGo
                if not search_result or search_result.startswith("[OFFLINE]") or search_result.startswith("[ERRO]"):
                    for q in queries_to_try:
                        logger.info(f"   Tentando busca geral: {q}")
                        search_result = self.web_search.search_formatted(q)
                        if not search_result.startswith("[OFFLINE]") and not search_result.startswith("[ERRO]") and len(search_result) > 100:
                            logger.info(f"   ✅ Sucesso com query: {q}")
                            break
                        else:
                            logger.warning(f"   ❌ Falhou: {q}")

                # Valida se o resultado tem conteúdo substancial (mínimo 100 caracteres)
                if not search_result.startswith("[OFFLINE]") and not search_result.startswith("[ERRO]") and len(search_result) > 100:
                    used_web_search = True
                    logger.info(f"✅ Resultado da web válido ({len(search_result)} caracteres)")

                    # Usa modelo LOCAL (Ollama) para processar resultados da web
                    # Adiciona contexto web que será processado pelo Ollama
                    web_context = f"\n\n===== INFORMAÇÃO DA WEB =====\n{search_result}\n=============================\n"
                    logger.info("💻 Busca web bem-sucedida - será processada pelo modelo local (Ollama)")
                else:
                    # Resultado inválido - limpa e registra motivo
                    if search_result and len(search_result) <= 100:
                        logger.warning(f"⚠️ Resultado muito curto ({len(search_result)} chars), ignorando busca web")
                    search_result = None

        # ═══════════════════════════════════════════════════════════
        # CONTEXTO DE CONVERSA
        # ═══════════════════════════════════════════════════════════
        
        conversation_context = self._build_conversation_context()
        
        # ═══════════════════════════════════════════════════════════
        # MONTA PROMPT FINAL
        # ═══════════════════════════════════════════════════════════
        
        if isinstance(prompt, str) and not files:
            # Texto normal
            if web_context:
                # Quando há informações da web, instrui a usar APENAS essas informações
                full_prompt = f"""{self.personality}

REGRAS ESTRITAS:
1. Use APENAS as informações fornecidas abaixo
2. NÃO invente, deduza ou adicione detalhes que não estão explicitamente escritos
3. Se não tem certeza ou a informação não está disponível, diga: "Não tenho informação específica sobre isso"
4. Seja preciso e baseado apenas nos fatos fornecidos

{web_context}

{conversation_context}

Usuário (AGORA): {prompt}"""
            else:
                # Sem busca web, prompt normal
                full_prompt = f"""{self.personality}

{conversation_context}

Usuário (AGORA): {prompt}"""
        else:
            # Imagem ou outro formato
            full_prompt = prompt
        
        # ═══════════════════════════════════════════════════════════
        # GERA RESPOSTA
        # ═══════════════════════════════════════════════════════════

        response_text = ""
        response_artifacts = None
        model_used = "unknown"  # Rastreia qual modelo foi usado

        # NOTA: Intent já foi detectada acima (antes da busca web)
        # para evitar busca web desnecessária em modo código

        if self.router:
            # Se houve busca web, SEMPRE usa modelo local (Ollama) para processar
            if used_web_search and web_context:
                logger.info("🔍 Busca web detectada - forçando uso do modelo LOCAL (Ollama)")
                groq_failed = True  # Força uso do Ollama
            else:
                # Sistema híbrido: Tenta Groq primeiro, fallback para Ollama
                groq_failed = False

            # MODO CÓDIGO: Sempre usa Groq se disponível (EXCETO se houver busca web)
            # CORREÇÃO: Também entra neste bloco se model_choice for "groq"
            logger.info(f"[DEBUG] Verificando condições para gerar código:")
            logger.info(f"[DEBUG]   intent == 'code': {intent == 'code'}")
            logger.info(f"[DEBUG]   model_choice == 'groq': {model_choice == 'groq'}")
            logger.info(f"[DEBUG]   self.groq_engine: {self.groq_engine is not None}")
            logger.info(f"[DEBUG]   isinstance(prompt, str): {isinstance(prompt, str)}")
            logger.info(f"[DEBUG]   not used_web_search: {not used_web_search}")

            if (intent == 'code' or model_choice == "groq") and self.groq_engine and isinstance(prompt, str) and not used_web_search:
                logger.info("🚀 ✅ Gerando código com Groq...")
                task = prompt.replace("[MODO CÓDIGO]", "").strip()
                task_lower = task.lower()

                # NOVO: Detecta se usuário está pedindo correção
                correction_keywords = [
                    'corrig', 'fix', 'erro', 'error', 'bug', 'problema', 'consert',
                    'ajust', 'melhore', 'improve', 'não compila', 'não funciona',
                    'está errado', 'está com erro', 'tem um erro'
                ]
                is_correction = any(keyword in task_lower for keyword in correction_keywords)

                if is_correction:
                    logger.info("🔧 Correção detectada - incluindo código anterior do histórico")
                    # Busca último código no histórico
                    last_code = None
                    for msg in reversed(self.conversation_history):
                        if msg.get("role") == "assistant":
                            content = msg.get("content", "")
                            if "```" in content:
                                last_code = content
                                break

                    if last_code:
                        task = f"""CONTEXTO: Você gerou este código anteriormente:
{last_code}

TAREFA: {task}

IMPORTANTE: NÃO gere código completamente novo. CORRIJA apenas os erros específicos mencionados no código acima."""
                        logger.info("📝 Contexto de código anterior incluído no prompt")

                # Detecta linguagem do pedido
                detected_language = "python"  # default

                # Detecta linguagem mencionada explicitamente
                if any(x in task_lower for x in ['c++', 'cpp', 'em c++']):
                    detected_language = "cpp"
                elif any(x in task_lower for x in ['javascript', 'js', 'em js', 'em javascript']):
                    detected_language = "javascript"
                elif any(x in task_lower for x in ['typescript', 'ts', 'em ts']):
                    detected_language = "typescript"
                elif any(x in task_lower for x in ['java', 'em java']) and 'javascript' not in task_lower:
                    detected_language = "java"
                elif any(x in task_lower for x in ['c#', 'csharp', 'em c#']):
                    detected_language = "csharp"
                elif any(x in task_lower for x in ['python', 'em python', 'py']):
                    detected_language = "python"

                logger.info(f"🔍 Linguagem detectada: {detected_language.upper()}")

                response_text = self.groq_engine.generate_code(
                    task=task,
                    language=detected_language,
                    conversation_history=self.conversation_history
                )
                model_used = "groq"

                # Detecta se há blocos de código na resposta
                if "```" in response_text:
                    logger.info("✨ Código detectado na resposta Groq - marcando como artefato")
                    response_artifacts = True  # Marca que há artefatos (GUI vai extrair)

                # CORREÇÃO: Se Groq falhar, faz fallback para Ollama local
                if response_text.startswith("[ERRO]"):
                    logger.warning("❌ Groq falhou - fazendo FALLBACK para Ollama local...")
                    model_used = "groq_failed"
                    groq_failed = True  # Força uso do Ollama
                    response_text = ""  # Limpa para tentar Ollama
                else:
                    groq_failed = False  # Groq funcionou, não precisa de fallback

            # MODO CHAT: Tenta Groq primeiro, fallback para Ollama (EXCETO se houver busca web)
            elif intent == 'chat' and self.groq_engine and isinstance(prompt, str) and not files and not used_web_search:
                logger.info("☁️ Tentando gerar com Groq (nuvem)...")
                try:
                    response_text = self.groq_engine.generate(
                        prompt=full_prompt,
                        model="llama-3.3-70b-versatile",
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                    # Verifica se Groq falhou
                    if response_text.startswith("[ERRO]"):
                        logger.warning("⚠️ Groq indisponível, usando Ollama local...")
                        groq_failed = True
                    else:
                        logger.info("✅ Resposta gerada com Groq (nuvem)")
                        model_used = "groq"
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao usar Groq: {e}")
                    groq_failed = True
            else:
                groq_failed = True  # Força uso do Ollama para imagens e outros casos

            # FALLBACK: Usa Ollama local se Groq falhou ou não está disponível
            if groq_failed or (intent != 'code' and not response_text):
                # "groq" não é um modelo do router local — roteamento automático
                explicit = None if model_choice == "groq" else model_choice

                if files:
                    # Modo imagem: resolve o modelo a partir do payload de imagem
                    prompt_dict = {
                        "type": "image",
                        "path": files[0],
                        "text": prompt if isinstance(prompt, str) else prompt.get("text", "")
                    }
                    backend, model_id = self.router.resolve_model(prompt_dict, explicit)
                    logger.info(f"💻 Gerando com Ollama local: {model_id}")
                    model_used = f"ollama_{model_id}"
                    response = self.router.generate(
                        prompt_dict,
                        explicit_model=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                else:
                    # Modo texto
                    backend, model_id = self.router.resolve_model(full_prompt, explicit)
                    logger.info(f"💻 Gerando com Ollama local: {model_id}")
                    model_used = f"ollama_{model_id}"
                    response = self.router.generate(
                        full_prompt,
                        explicit_model=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )

                response_text = response.get("text", "")
                response_artifacts = response.get("artifacts")
        else:
            response_text = "[ERRO] Router não disponível"
            model_used = "error"
        
        # ═══════════════════════════════════════════════════════════
        # PÓS-PROCESSAMENTO
        # ═══════════════════════════════════════════════════════════
        
        if isinstance(response_text, str):
            self._add_to_history("assistant", response_text, artifacts=response_artifacts)
        
        response_text = self._validate_response(response_text)
        
        # Salva na memória DEPOIS de ter a resposta final
        if self.memory and isinstance(prompt, str):
            self.memory.add_memory(prompt, metadata={"response": response_text})

            # Cacheia apenas prompts independentes de contexto
            if model_used != "cache" and len(prompt) < 200 and is_cacheable_prompt(prompt):
                self.memory.cache_response(prompt, response_text)

        response_text = self._format_response(response_text)

        logger.info(f"✅ Resposta gerada ({len(response_text)} chars)")

        return {
            "text": response_text,
            "artifacts": response_artifacts,
            "model_used": model_used,
            "web_search_used": used_web_search
        }
    
    # ═══════════════════════════════════════════════════════════════
    # HISTÓRICO DE CONVERSA
    # ═══════════════════════════════════════════════════════════════
    
    def _build_conversation_context(self) -> str:
        """
        Constrói contexto das últimas mensagens da conversa.
        
        Returns:
            String formatada com histórico
        """
        if not self.conversation_history:
            return ""
        
        context_parts = ["=== HISTÓRICO DA CONVERSA ==="]

        # Pega últimas 8 mensagens com contexto suficiente
        for entry in self.conversation_history[-8:]:
            role = "Você" if entry["role"] == "user" else "EVE"
            content = entry['content'][:800]
            context_parts.append(f"{role}: {content}")

        context_parts.append("=============================\n")
        return "\n".join(context_parts)
    
    def _add_to_history(self, role: str, content: str, artifacts: Optional[List[str]] = None):
        """
        Adiciona mensagem ao histórico da sessão.
        
        Args:
            role: "user" ou "assistant"
            content: Conteúdo da mensagem
            artifacts: Lista de artefatos (opcional)
        """
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if artifacts:
            entry["artifacts"] = artifacts
        
        self.conversation_history.append(entry)
        
        # Mantém apenas últimas max_history mensagens
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def clear_conversation_history(self):
        """Limpa histórico da conversa atual"""
        self.conversation_history = []
        logger.info("Histórico de conversa limpo")

    def _save_chat_history(self):
        """Salva a conversa atual no arquivo eve_chats.json"""
        if not self.conversation_history:
            return

        try:
            # Carrega chats existentes
            all_chats = {}
            if os.path.isfile(self.chats_file):
                with open(self.chats_file, "r", encoding="utf-8") as f:
                    all_chats = json.load(f)

            # Cria um ID único para a sessão
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            first_user_message = self.conversation_history[0]['content']
            
            all_chats[session_id] = {
                "title": first_user_message[:50] + "...",
                "messages": self.conversation_history,
                "timestamp": datetime.now().isoformat()
            }

            # Salva o arquivo
            with open(self.chats_file, "w", encoding="utf-8") as f:
                json.dump(all_chats, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Histórico de chat salvo com ID: {session_id}")
        except Exception as e:
            logger.error(f"Erro ao salvar histórico de chat: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # MÉTODOS UTILITÁRIOS E SHUTDOWN
    # ═══════════════════════════════════════════════════════════════
    
    def shutdown(self):
        """
        Executa o desligamento seguro, salvando todos os dados pendentes.
        Deve ser chamado antes de fechar o programa.
        """
        logger.info("Iniciando desligamento seguro da EVE 2.0...")

        # Salvar histórico de chats
        self._save_chat_history()

        # Salvar memória legada
        if self.memory:
            self.memory.force_save()
            logger.info("✅ Memória legada salva.")

        # Salvar memória em camadas (EVE 2.0)
        if self.layered_memory:
            self.layered_memory._save()
            logger.info("✅ Layered Memory salva.")

        # Salvar estado interno (EVE 2.0)
        if self.internal_state:
            self.internal_state._save()
            logger.info("✅ Estado interno salvo.")
            logger.info(f"📊 Resumo da sessão: {self.internal_state.get_session_summary()}")

        logger.info("👋 EVE 2.0 desligada.")

    def get_stats(self) -> Dict:
        """
        Retorna estatísticas do sistema EVE.

        Returns:
            Dict com estatísticas (legadas + EVE 2.0)
        """
        stats = {
            # === Componentes Legados ===
            "router_available": ROUTER_AVAILABLE,
            "memory_available": MEMORY_AVAILABLE,
            "web_search_available": WEB_TOOLS_AVAILABLE,
            "spell_checker_available": SPELL_CHECKER_AVAILABLE,
            "groq_available": GROQ_AVAILABLE and self.groq_engine is not None,
            "conversation_messages": len(self.conversation_history),

            # === Feature Flags ===
            "feature_flags": FLAGS.to_dict(),
            "enabled_features": FLAGS.get_enabled_features(),
        }

        # Memória legada
        if self.memory:
            stats["memory_entries"] = len(self.memory)

        # === EVE 2.0 Stats ===

        # Brain V2
        stats["brain_v2_available"] = BRAIN_AVAILABLE and self.brain is not None
        if self.brain:
            stats["brain_policy"] = self.brain.policy.policy.value

        # Layered Memory
        stats["layered_memory_available"] = LAYERED_MEMORY_AVAILABLE and self.layered_memory is not None
        if self.layered_memory:
            stats["layered_memory_stats"] = self.layered_memory.get_stats()

        # Skills
        stats["skills_available"] = SKILLS_AVAILABLE and self.skill_registry is not None
        if self.skill_registry:
            stats["skills_stats"] = self.skill_registry.get_stats()

        # Internal State
        stats["internal_state_available"] = STATE_AVAILABLE and self.internal_state is not None
        if self.internal_state:
            stats["internal_state_stats"] = self.internal_state.get_stats()

        # === EVE 2.0 Phase 1 Stats ===

        # Cognitive Trace
        stats["cognitive_trace_available"] = COGNITIVE_TRACE_AVAILABLE and self.cognitive_tracer is not None
        if self.cognitive_tracer:
            stats["cognitive_trace_stats"] = self.cognitive_tracer.get_session_summary()

        # Model Policy
        stats["model_policy_available"] = MODEL_POLICY_AVAILABLE and self.model_policy is not None
        if self.model_policy:
            stats["groq_usage"] = self.model_policy.get_groq_usage()

        # Session State
        stats["session_state_available"] = SESSION_STATE_AVAILABLE and self.session_state is not None
        if self.session_state:
            stats["session_state"] = self.session_state.get_state_dict()

        # Task Memory
        stats["task_memory_available"] = TASK_MEMORY_AVAILABLE and self.task_memory is not None
        if self.task_memory:
            stats["task_memory_stats"] = self.task_memory.get_stats()

        # Planner
        stats["planner_available"] = PLANNER_AVAILABLE and self.planner is not None

        # Task Engine
        stats["task_engine_available"] = TASK_ENGINE_AVAILABLE and self.task_engine is not None
        if self.task_engine:
            stats["task_engine_status"] = self.task_engine.get_status()

        return stats
    
    def reload_personality(self):
        """Recarrega arquivo de personalidade"""
        self.personality = self._load_personality(self.personality_file)
        logger.info("Personalidade recarregada")
    
    def __repr__(self):
        features = []
        if self.brain:
            features.append("brain_v2")
        if self.layered_memory:
            features.append("layered_memory")
        if self.skill_registry:
            features.append("skills")
        if self.internal_state:
            features.append("internal_state")
        if self.cognitive_tracer:
            features.append("cognitive_trace")
        if self.model_policy:
            features.append("model_policy")
        if self.session_state:
            features.append("session_state")
        if self.task_memory:
            features.append("task_memory")
        if self.planner:
            features.append("planner")
        if self.task_engine:
            features.append("task_engine")

        return (
            f"Eve(router={ROUTER_AVAILABLE}, "
            f"memory={MEMORY_AVAILABLE or LAYERED_MEMORY_AVAILABLE}, "
            f"web={WEB_TOOLS_AVAILABLE}, "
            f"v2_features={features})"
        )


# ═══════════════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("🧪 Testando EVE 2.0 Engine")
    print("=" * 60)

    # Mostrar feature flags ativos
    print("\n📋 Feature Flags:")
    print(f"   Enabled: {FLAGS.get_enabled_features() or '(nenhum)'}")

    # Inicializar EVE
    print("\n🚀 Inicializando EVE...")
    eve = Eve()

    # Mostrar stats
    print("\n📊 Estatísticas:")
    stats = eve.get_stats()
    pprint.pprint(stats, indent=2)

    # Teste de representação
    print(f"\n🔍 Representação: {eve}")

    # Teste simples de geração (se desejar)
    # response = eve.generate_response("Oi, tudo bem?")
    # print(f"\n💬 Teste de resposta: {response['text'][:100]}...")

    print("\n✅ EVE 2.0 pronta!")

    # Teste de desligamento
    eve.shutdown()