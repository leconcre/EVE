# core/brain.py
"""
Cérebro Central da EVE.
Classifica intenções, decide fluxo e orquestra sem executar.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Tuple
import re
import time

from .config import PolicyConfig, ExecutionPolicy, PolicyState
from .context import ContextRequirement, ContextSource, ToolType, build_context
from .models.spec import ModelCapability
from .feature_flags import FLAGS


class IntentType(Enum):
    """Tipos de intenção classificados pelo Brain"""
    CONVERSATION = auto()        # Conversa casual, saudações
    QUESTION_TECHNICAL = auto()  # Perguntas sobre código, sistemas
    QUESTION_FACTUAL = auto()    # Perguntas que precisam de busca
    QUESTION_CONCEPTUAL = auto() # Perguntas conceituais/explicativas
    TASK_CODE = auto()           # Gerar/modificar código
    TASK_ANALYSIS = auto()       # Analisar logs, código, texto
    TASK_FILE = auto()           # Operações com arquivos
    TASK_SUMMARIZE = auto()      # Resumir texto
    COMMAND = auto()             # Comandos diretos (limpar, sair)
    CLARIFICATION = auto()       # Usuário pedindo esclarecimento
    FOLLOWUP = auto()            # Continuação de conversa anterior


@dataclass
class BrainDecision:
    """
    Decisão do Brain - o que fazer, não como fazer.
    O Brain DECIDE, o orquestrador EXECUTA.
    """
    # Classificação
    intent: IntentType
    confidence: float                    # 0.0 a 1.0

    # Capability e skill
    selected_capability: Optional[str]   # ModelCapability.value ou None
    selected_skill: Optional[str]        # Nome da skill ou None

    # Contexto
    context_requirement: ContextRequirement

    # Pré/pós processamento
    preprocessing: List[str] = field(default_factory=list)
    postprocessing: List[str] = field(default_factory=list)

    # Metadados
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Debug
    reasoning: str = ""                  # Explicação da decisão

    def needs_model(self) -> bool:
        """Verifica se precisa chamar modelo"""
        return self.selected_capability is not None

    def needs_skill(self) -> bool:
        """Verifica se precisa executar skill"""
        return self.selected_skill is not None

    def to_dict(self) -> Dict:
        """Converte para dicionário (debug/logging)"""
        return {
            'intent': self.intent.name,
            'confidence': self.confidence,
            'capability': self.selected_capability,
            'skill': self.selected_skill,
            'context_sources': [s.name for s in self.context_requirement.sources],
            'context_tools': [t.tool_type.name for t in self.context_requirement.tools],
            'preprocessing': self.preprocessing,
            'postprocessing': self.postprocessing,
            'metadata': self.metadata,
            'reasoning': self.reasoning
        }


class Brain:
    """
    Cérebro central da EVE.

    Princípio: DECIDE, não EXECUTA.
    O Brain analisa, classifica e retorna um plano de ação.
    A execução fica com o orquestrador (eve.py).
    """

    def __init__(
        self,
        policy_config: PolicyConfig = None,
        skill_registry=None,
        state=None
    ):
        self.policy = policy_config or PolicyConfig()
        self.policy_state = PolicyState()
        self.skills = skill_registry
        self.state = state

        # Padrões de classificação
        self._intent_patterns = self._build_intent_patterns()
        self._capability_map = self._build_capability_map()
        self._compile_regex_patterns()

    def analyze(
        self,
        user_input: str,
        conversation_context: List[Dict] = None,
        attached_files: List[str] = None
    ) -> BrainDecision:
        """
        Análise principal. Retorna decisão completa.

        Fluxo:
        1. Classificar intenção
        2. Calcular complexidade
        3. Determinar contexto necessário
        4. Selecionar skill (se aplicável)
        5. Selecionar capability (se precisar de modelo)
        6. Definir pré/pós-processamento
        """
        start_time = time.time()
        conversation_context = conversation_context or []
        attached_files = attached_files or []

        # 1. Classificar intenção
        intent, confidence = self._classify_intent(user_input, attached_files)

        # 2. Calcular complexidade
        complexity = self._calculate_complexity(user_input, intent)

        # 3. Determinar contexto necessário
        context_req = self._determine_context_requirements(
            intent, user_input, conversation_context
        )

        # 4. Selecionar skill
        skill = self._select_skill(intent, user_input)

        # 5. Selecionar capability (se precisar de modelo)
        capability = None
        if not self._skill_resolves_without_model(skill):
            capability = self._select_capability(intent, complexity)

        # 6. Pré/pós processamento
        preprocessing, postprocessing = self._determine_processing(
            intent, skill, capability
        )

        # 7. Metadados extras
        metadata = self._extract_metadata(user_input, intent, attached_files)

        # Construir decisão
        decision = BrainDecision(
            intent=intent,
            confidence=confidence,
            selected_capability=capability,
            selected_skill=skill,
            context_requirement=context_req,
            preprocessing=preprocessing,
            postprocessing=postprocessing,
            metadata=metadata,
            reasoning=self._build_reasoning(intent, skill, capability, complexity)
        )

        # Ajustar baseado no estado (se disponível)
        if self.state:
            decision = self._adjust_for_state(decision)

        analysis_time = int((time.time() - start_time) * 1000)
        decision.metadata['analysis_time_ms'] = analysis_time

        if FLAGS.DEBUG_BRAIN_DECISIONS:
            print(f"[Brain] Intent: {intent.name} (conf: {confidence:.2f})")
            print(f"[Brain] Capability: {capability}")
            print(f"[Brain] Skill: {skill}")
            print(f"[Brain] Reasoning: {decision.reasoning}")

        return decision

    # =========================================================================
    # CLASSIFICAÇÃO DE INTENÇÃO
    # =========================================================================

    def _classify_intent(
        self,
        text: str,
        files: List[str]
    ) -> Tuple[IntentType, float]:
        """
        Classificação por camadas:
        1. Regras explícitas (alta confiança)
        2. Padrões de palavras-chave
        3. Análise estrutural
        4. Fallback
        """
        text_lower = text.lower().strip()

        # === Camada 1: Regras explícitas ===

        # Modo código explícito
        if text_lower.startswith('[modo código]') or text_lower.startswith('[code]'):
            return IntentType.TASK_CODE, 1.0

        # Arquivos de imagem anexos
        if files and any(self._is_image_file(f) for f in files):
            return IntentType.TASK_ANALYSIS, 0.95

        # Comandos
        if text_lower in ['sair', 'exit', 'quit', 'limpar', 'clear', '/clear', '/exit']:
            return IntentType.COMMAND, 1.0

        # === Camada 2: Padrões por intenção ===

        best_intent = IntentType.CONVERSATION
        best_score = 0.0

        for intent, patterns in self._intent_patterns.items():
            score = self._pattern_match_score(text_lower, patterns)
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score > 0.6:
            return best_intent, min(best_score, 1.0)

        # === Camada 3: Análise estrutural ===

        # Pergunta longa com termos técnicos
        if '?' in text and len(text.split()) > 5:
            if self._has_technical_terms(text_lower):
                return IntentType.QUESTION_TECHNICAL, 0.6
            if self._has_factual_indicators(text_lower):
                return IntentType.QUESTION_FACTUAL, 0.55
            return IntentType.QUESTION_CONCEPTUAL, 0.5

        # Código detectado no texto
        if self._has_code_patterns(text):
            return IntentType.TASK_CODE, 0.7

        # Referência a conversa anterior
        if self._references_past(text_lower):
            return IntentType.FOLLOWUP, 0.6

        # === Camada 4: Fallback ===
        return IntentType.CONVERSATION, 0.4

    def _build_intent_patterns(self) -> Dict[IntentType, Dict]:
        """Constrói padrões de classificação por intenção"""
        return {
            IntentType.TASK_CODE: {
                'triggers': [
                    'crie', 'escreva', 'implemente', 'código', 'função',
                    'programa', 'script', 'classe', 'módulo', 'gere',
                    'faça um', 'desenvolva', 'programe'
                ],
                'strong': [
                    'def ', 'class ', 'import ', 'function ',
                    '```', 'return ', 'for ', 'while ', 'if '
                ],
                'context': [
                    'python', 'javascript', 'typescript', 'c++', 'java',
                    'rust', 'go', 'html', 'css', 'sql', 'api'
                ]
            },
            IntentType.QUESTION_TECHNICAL: {
                'triggers': [
                    'como funciona', 'por que', 'explique o código',
                    'o que faz', 'qual a diferença', 'quando usar'
                ],
                'strong': [
                    'erro', 'bug', 'problema', 'não funciona', 'falha',
                    'exception', 'traceback', 'debug'
                ],
                'context': [
                    'código', 'sistema', 'api', 'banco', 'função',
                    'classe', 'método', 'biblioteca'
                ]
            },
            IntentType.QUESTION_FACTUAL: {
                'triggers': [
                    'o que é', 'quem é', 'quando', 'onde', 'quantos',
                    'qual é', 'quais são', 'defina'
                ],
                'strong': [
                    'história', 'significado', 'origem', 'data',
                    'nome', 'país', 'cidade'
                ],
                'context': []
            },
            IntentType.TASK_ANALYSIS: {
                'triggers': [
                    'analise', 'revise', 'verifique', 'encontre',
                    'examine', 'avalie', 'veja isso'
                ],
                'strong': [
                    'log', 'erro', 'warning', 'stack trace',
                    'performance', 'otimize'
                ],
                'context': ['arquivo', 'código', 'saída', 'resultado']
            },
            IntentType.TASK_FILE: {
                'triggers': [
                    'liste', 'mostre', 'mova', 'copie', 'renomeie',
                    'delete', 'apague', 'crie pasta', 'organize'
                ],
                'strong': ['arquivo', 'pasta', 'diretório', 'folder'],
                'context': []
            },
            IntentType.TASK_SUMMARIZE: {
                'triggers': [
                    'resuma', 'resumo', 'sintetize', 'condense',
                    'principais pontos', 'em poucas palavras'
                ],
                'strong': ['texto', 'artigo', 'documento'],
                'context': []
            },
            IntentType.CONVERSATION: {
                'triggers': [
                    'oi', 'olá', 'opa', 'eai', 'tudo bem',
                    'obrigado', 'valeu', 'legal', 'bom dia',
                    'boa tarde', 'boa noite', 'fala'
                ],
                'strong': [
                    'como você está', 'quem é você', 'seu nome',
                    'tchau', 'até mais', 'flw'
                ],
                'context': []
            },
            IntentType.CLARIFICATION: {
                'triggers': [
                    'não entendi', 'pode explicar', 'como assim',
                    'o que você quer dizer', 'repita', 'mais detalhes'
                ],
                'strong': ['confuso', 'perdido', 'não ficou claro'],
                'context': []
            }
        }

    def _pattern_match_score(
        self,
        text: str,
        patterns: Dict[str, List[str]]
    ) -> float:
        """Calcula score de match com padrões"""
        score = 0.0

        # Triggers (peso 0.2 cada, max 0.6)
        trigger_matches = sum(
            1 for t in patterns.get('triggers', [])
            if t in text
        )
        score += min(trigger_matches * 0.2, 0.6)

        # Strong (peso 0.3 cada, max 0.6)
        strong_matches = sum(
            1 for s in patterns.get('strong', [])
            if s in text
        )
        score += min(strong_matches * 0.3, 0.6)

        # Context (peso 0.1 cada, max 0.3)
        context_matches = sum(
            1 for c in patterns.get('context', [])
            if c in text
        )
        score += min(context_matches * 0.1, 0.3)

        return min(score, 1.0)

    def _has_technical_terms(self, text: str) -> bool:
        """Verifica presença de termos técnicos"""
        technical = [
            'api', 'função', 'classe', 'método', 'variável',
            'banco', 'database', 'servidor', 'cliente', 'http',
            'json', 'array', 'objeto', 'loop', 'recursão',
            'compilar', 'runtime', 'memory', 'thread', 'async'
        ]
        return any(term in text for term in technical)

    def _has_factual_indicators(self, text: str) -> bool:
        """Verifica indicadores de pergunta factual"""
        factual = [
            'o que é', 'quem é', 'quando foi', 'onde fica',
            'qual é o', 'quantos', 'história de'
        ]
        return any(ind in text for ind in factual)

    def _compile_regex_patterns(self):
        """Compila regexes usados frequentemente para performance"""
        patterns = [
            r'def \w+\(',           # Python function
            r'class \w+',           # Class definition
            r'function \w+\(',      # JS function
            r'const \w+ =',         # JS const
            r'import .+ from',      # JS/TS import
            r'#include <',          # C/C++ include
            r'public class',        # Java
            r'fn \w+\(',            # Rust
            r'```\w*\n',            # Code block
        ]
        self._compiled_code_patterns = [re.compile(p) for p in patterns]

    def _has_code_patterns(self, text: str) -> bool:
        """Detecta padrões de código no texto"""
        return any(p.search(text) for p in self._compiled_code_patterns)

    def _references_past(self, text: str) -> bool:
        """Detecta referência a conversa anterior"""
        past_indicators = [
            'você disse', 'você falou', 'mencionei', 'falei',
            'lembra', 'como eu disse', 'sobre aquilo',
            'o que a gente', 'continue', 'e sobre'
        ]
        return any(ind in text for ind in past_indicators)

    def _is_image_file(self, path: str) -> bool:
        """Verifica se é arquivo de imagem"""
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
        return any(path.lower().endswith(ext) for ext in image_extensions)

    # =========================================================================
    # SELEÇÃO DE CAPABILITY E SKILL
    # =========================================================================

    def _build_capability_map(self) -> Dict[IntentType, str]:
        """Mapeamento de intenção para capability padrão"""
        return {
            IntentType.CONVERSATION: ModelCapability.CHAT_FAST.value,
            IntentType.QUESTION_TECHNICAL: ModelCapability.CODE_STRONG.value,
            IntentType.QUESTION_FACTUAL: ModelCapability.CHAT_FAST.value,
            IntentType.QUESTION_CONCEPTUAL: ModelCapability.CHAT_STRONG.value,
            IntentType.TASK_CODE: ModelCapability.CODE_STRONG.value,
            IntentType.TASK_ANALYSIS: ModelCapability.ANALYSIS_STRONG.value,
            IntentType.TASK_FILE: None,  # Skill resolve sem modelo
            IntentType.TASK_SUMMARIZE: ModelCapability.SUMMARIZATION.value,
            IntentType.COMMAND: None,
            IntentType.CLARIFICATION: ModelCapability.CHAT_FAST.value,
            IntentType.FOLLOWUP: ModelCapability.CHAT_FAST.value,
        }

    def _select_capability(
        self,
        intent: IntentType,
        complexity: float
    ) -> Optional[str]:
        """
        Seleciona capability baseada em intenção e complexidade.
        Aplica restrições de policy.
        """
        # Capability base
        capability = self._capability_map.get(intent)

        if not capability:
            return None

        # Upgrade baseado em complexidade
        if complexity > 0.8:
            if capability == ModelCapability.CHAT_FAST.value:
                capability = ModelCapability.CHAT_STRONG.value

        # Aplicar policy
        capability = self._apply_policy_to_capability(capability, complexity)

        return capability

    def _apply_policy_to_capability(
        self,
        capability: str,
        complexity: float
    ) -> str:
        """Ajusta capability baseado na policy"""
        policy = self.policy.policy

        if policy == ExecutionPolicy.OFFLINE:
            # Em modo offline, preferir capabilities que modelos locais suportam bem
            if capability == ModelCapability.CODE_STRONG.value and complexity < 0.7:
                return ModelCapability.CHAT_STRONG.value

        elif policy == ExecutionPolicy.PRO:
            # Em modo PRO, pode usar capabilities mais fortes
            if capability == ModelCapability.CHAT_FAST.value and complexity > 0.5:
                return ModelCapability.CHAT_STRONG.value

        return capability

    def _select_skill(
        self,
        intent: IntentType,
        user_input: str
    ) -> Optional[str]:
        """Seleciona skill apropriada (se houver)"""
        if not self.skills:
            return None

        # Primeiro, verificar skills puras (sem modelo)
        pure_skill = self.skills.find_pure_skill(user_input, intent.name)
        if pure_skill:
            if FLAGS.DEBUG_SKILL_SELECTION:
                print(f"[Brain] Skill pura encontrada: {pure_skill}")
            return pure_skill

        # Depois, skills opcionais
        optional_skill = self.skills.find_optional_skill(user_input, intent.name)
        if optional_skill:
            if FLAGS.DEBUG_SKILL_SELECTION:
                print(f"[Brain] Skill opcional encontrada: {optional_skill}")
            return optional_skill

        # Por último, skills que requerem modelo
        model_skill = self.skills.find_model_skill(user_input, intent.name)
        if model_skill:
            if FLAGS.DEBUG_SKILL_SELECTION:
                print(f"[Brain] Skill com modelo encontrada: {model_skill}")
            return model_skill

        return None

    def _skill_resolves_without_model(self, skill_name: Optional[str]) -> bool:
        """Verifica se skill resolve sem precisar de modelo"""
        if not skill_name or not self.skills:
            return False

        skill = self.skills.get(skill_name)
        if not skill:
            return False

        # Skills do tipo PURE nunca precisam de modelo
        from skills.base import SkillType
        return skill.skill_type == SkillType.PURE

    # =========================================================================
    # CONTEXTO E PROCESSAMENTO
    # =========================================================================

    def _determine_context_requirements(
        self,
        intent: IntentType,
        user_input: str,
        conversation_context: List[Dict]
    ) -> ContextRequirement:
        """Determina contexto e ferramentas necessárias"""
        builder = build_context()
        text_lower = user_input.lower()

        # === SOURCES (contexto passivo) ===

        # Sempre incluir short-term para continuidade
        builder.with_short_term()

        # Long-term se referencia passado ou precisa de preferências
        if self._references_past(text_lower) or intent == IntentType.FOLLOWUP:
            builder.with_long_term(user_input)

        # Preferências para tarefas de código ou conversa
        if intent in [IntentType.TASK_CODE, IntentType.CONVERSATION]:
            builder.with_preferences()

        # Resumo se conversa longa
        if len(conversation_context) > 5:
            builder.with_summary()

        # === TOOLS (ações ativas) ===

        # Web search para perguntas factuais
        if intent == IntentType.QUESTION_FACTUAL:
            query = self._extract_search_query(user_input)
            builder.with_web_search(query, max_results=3)

        # File read se menciona arquivo
        file_path = self._extract_file_path(user_input)
        if file_path:
            builder.with_file_read(file_path, required=True)

        return builder.build()

    def _determine_processing(
        self,
        intent: IntentType,
        skill: Optional[str],
        capability: Optional[str]
    ) -> Tuple[List[str], List[str]]:
        """Determina etapas de pré e pós processamento"""
        preprocessing = []
        postprocessing = []

        # Pré-processamento
        if intent == IntentType.TASK_CODE:
            preprocessing.append('detect_language')

        if intent == IntentType.TASK_ANALYSIS:
            preprocessing.append('extract_error_context')

        # Pós-processamento
        if intent == IntentType.TASK_CODE:
            postprocessing.extend([
                'validate_code',
                'extract_artifacts',
                'spell_check'
            ])
        elif intent in [IntentType.CONVERSATION, IntentType.QUESTION_CONCEPTUAL]:
            postprocessing.extend([
                'spell_check',
                'format_response'
            ])
        else:
            postprocessing.append('spell_check')

        # Sempre sanitizar
        postprocessing.append('sanitize_output')

        return preprocessing, postprocessing

    def _calculate_complexity(
        self,
        text: str,
        intent: IntentType
    ) -> float:
        """Calcula complexidade da tarefa (0.0 a 1.0)"""
        complexity = 0.3  # Base

        # Tamanho do texto
        words = len(text.split())
        if words > 50:
            complexity += 0.2
        elif words > 20:
            complexity += 0.1

        # Intent naturalmente complexa
        complex_intents = [
            IntentType.TASK_CODE,
            IntentType.TASK_ANALYSIS,
            IntentType.QUESTION_TECHNICAL
        ]
        if intent in complex_intents:
            complexity += 0.2

        # Múltiplos requisitos (detectar "e", "também", listas)
        if ' e ' in text.lower() and len(text) > 50:
            complexity += 0.15
        if any(text.count(c) > 2 for c in [',', ';', '\n']):
            complexity += 0.1

        # Código no texto
        if self._has_code_patterns(text):
            complexity += 0.15

        return min(complexity, 1.0)

    def _extract_metadata(
        self,
        user_input: str,
        intent: IntentType,
        files: List[str]
    ) -> Dict[str, Any]:
        """Extrai metadados relevantes"""
        metadata = {
            'input_length': len(user_input),
            'has_files': len(files) > 0,
            'file_types': [f.split('.')[-1] for f in files if '.' in f]
        }

        # Detectar linguagem de programação
        if intent == IntentType.TASK_CODE:
            metadata['language'] = self._detect_programming_language(user_input)

        # Detectar se é pergunta
        metadata['is_question'] = '?' in user_input

        return metadata

    def _detect_programming_language(self, text: str) -> str:
        """Detecta linguagem de programação mencionada"""
        text_lower = text.lower()

        languages = {
            'python': ['python', 'py', 'pip', 'django', 'flask'],
            'javascript': ['javascript', 'js', 'node', 'npm', 'react', 'vue'],
            'typescript': ['typescript', 'ts', 'angular'],
            'cpp': ['c++', 'cpp', 'cmake'],
            'c': ['linguagem c', ' c ', 'gcc'],
            'java': ['java', 'jvm', 'spring', 'maven'],
            'rust': ['rust', 'cargo', 'rustc'],
            'go': ['golang', ' go ', 'goroutine'],
            'php': ['php', 'laravel', 'composer'],
            'sql': ['sql', 'mysql', 'postgres', 'sqlite']
        }

        for lang, keywords in languages.items():
            if any(kw in text_lower for kw in keywords):
                return lang

        return 'python'  # Default

    def _extract_search_query(self, text: str) -> str:
        """Extrai query de busca do texto"""
        # Remover prefixos comuns
        prefixes = [
            'o que é', 'quem é', 'quando foi', 'onde fica',
            'me explique', 'pesquise sobre', 'busque'
        ]

        query = text.lower()
        for prefix in prefixes:
            if query.startswith(prefix):
                query = query[len(prefix):].strip()
                break

        # Limitar tamanho
        words = query.split()[:8]
        return ' '.join(words)

    def _extract_file_path(self, text: str) -> Optional[str]:
        """Extrai caminho de arquivo do texto"""
        # Padrões de caminho
        patterns = [
            r'[A-Za-z]:\\[^\s]+',           # Windows absolute
            r'/[^\s]+\.[a-zA-Z]+',           # Unix absolute
            r'\.\/[^\s]+',                   # Relative ./
            r'\.\.[^\s]+',                   # Relative ../
            r'[\w\-]+\.[a-zA-Z]{2,4}\b'      # filename.ext
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    # =========================================================================
    # AJUSTES E HELPERS
    # =========================================================================

    def _adjust_for_state(self, decision: BrainDecision) -> BrainDecision:
        """Ajusta decisão baseado no estado interno"""
        if not self.state:
            return decision

        modifiers = self.state.get_response_modifiers()

        # Ajustar metadados com modifiers
        decision.metadata['response_modifiers'] = modifiers.to_dict()

        # Se em modo FOCUSED, preferir respostas concisas
        if self.state.current_mood.mood.value == 'focused':
            if 'format_verbose' in decision.postprocessing:
                decision.postprocessing.remove('format_verbose')

        return decision

    def _build_reasoning(
        self,
        intent: IntentType,
        skill: Optional[str],
        capability: Optional[str],
        complexity: float
    ) -> str:
        """Constrói explicação da decisão (para debug)"""
        parts = [f"Intent={intent.name}"]

        if skill:
            parts.append(f"Skill={skill}")
        if capability:
            parts.append(f"Capability={capability}")

        parts.append(f"Complexity={complexity:.2f}")
        parts.append(f"Policy={self.policy.policy.value}")

        return ", ".join(parts)
