# core/model_policy.py
"""
Politica de uso de modelos da EVE.
Define regras explicitas de quando usar cada modelo.

Principio: Groq 70B e poderoso mas limitado. Use com sabedoria.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta
import re
import threading

from core.feature_flags import FLAGS


class ModelTier(Enum):
    """Niveis de modelo"""
    PREMIUM = "premium"      # Groq 70B - poderoso, rate limited
    STANDARD = "standard"    # Ollama local - rapido, sem limite
    FAST = "fast"            # Ollama 8B - mais rapido, menos capaz
    CACHE = "cache"          # Resposta cacheada
    SKILL = "skill"          # Skill pura, sem modelo


@dataclass
class ModelChoice:
    """Resultado da escolha de modelo"""
    model_id: str
    tier: ModelTier
    reason: str
    rule_matched: str
    alternatives: List[str]


class ModelUsagePolicy:
    """
    Politica explicita de quando usar cada modelo.

    Principios:
    - Groq 70B: tarefas de codigo, raciocinio complexo
    - Ollama local: conversas, tarefas simples
    - Skills puras: calculos, data/hora, operacoes deterministicas
    """

    # =========================================================================
    # REGRAS DE USO DO GROQ
    # =========================================================================

    USE_GROQ_RULES = {
        'code_generation': {
            'description': 'Geracao de codigo',
            'triggers': [
                r'\[modo codigo\]',
                r'(?:crie|escreva|implemente|gere).*(?:codigo|funcao|classe|programa)',
                r'(?:em|usando)\s+(?:python|javascript|typescript|c\+\+|java|rust|go)',
            ],
            'reason': 'Qualidade de codigo e critica, requer modelo forte',
            'min_confidence': 0.7
        },
        'code_review': {
            'description': 'Revisao de codigo',
            'triggers': [
                r'(?:revise|analise|verifique).*(?:codigo|funcao|classe)',
                r'(?:o que esta|tem algo).*(?:errado|bug|problema)',
                r'(?:melhore|otimize|refatore)',
            ],
            'reason': 'Deteccao de bugs requer raciocinio forte',
            'min_confidence': 0.6
        },
        'complex_reasoning': {
            'description': 'Raciocinio complexo',
            'triggers': [
                r'explique.*passo a passo',
                r'por que.*(?:acontece|funciona|nao funciona)',
                r'qual.*(?:diferenca|melhor|vantagem).*entre',
                r'como.*(?:resolve|implementa|faz).*(?:problema|desafio)',
            ],
            'reason': 'Chain-of-thought beneficia modelo maior',
            'min_confidence': 0.5
        },
        'planning': {
            'description': 'Planejamento de tarefas',
            'triggers': [
                r'(?:organize|planeje|estruture)',
                r'crie.*(?:plano|roadmap|cronograma)',
                r'quais.*(?:passos|etapas).*para',
            ],
            'reason': 'Decomposicao de tarefas precisa de entendimento forte',
            'min_confidence': 0.5
        },
        'long_context': {
            'description': 'Analise de contexto longo',
            'triggers': [],  # Baseado em tamanho, nao patterns
            'reason': 'Contexto longo precisa de atencao melhor',
            'min_tokens': 1000,
            'min_confidence': 0.6
        }
    }

    # =========================================================================
    # REGRAS PARA NAO USAR GROQ
    # =========================================================================

    AVOID_GROQ_RULES = {
        'simple_greeting': {
            'description': 'Saudacao simples',
            'triggers': [
                r'^(?:oi|ola|hey|hi|bom dia|boa tarde|boa noite)[\s!.]*$',
                r'^(?:tudo bem|como vai|e ai)[\s?!.]*$',
                r'^(?:obrigad[oa]|valeu|brigad[oa])[\s!.]*$',
            ],
            'use_instead': 'ollama:qwen3.5:9b',
            'reason': 'Desperdicio de recursos para interacao simples'
        },
        'factual_simple': {
            'description': 'Pergunta factual simples',
            'triggers': [
                r'^(?:que horas|qual.*hora)',
                r'^(?:quanto e|calcule)',
                r'^(?:qual.*data|que dia)',
            ],
            'use_instead': 'skill',
            'reason': 'Skills sao mais rapidas e deterministicas'
        },
        'short_question': {
            'description': 'Pergunta muito curta',
            'triggers': [],  # Baseado em tamanho
            'use_instead': 'ollama:qwen3.5:9b',
            'reason': 'Pergunta simples nao precisa de modelo forte',
            'max_tokens': 20
        },
        'rate_limited': {
            'description': 'Proximo do limite de rate',
            'triggers': [],  # Baseado em estado
            'use_instead': 'ollama:qwen3.5:9b',
            'reason': 'Preservar quota para tarefas importantes'
        }
    }

    # =========================================================================
    # MAPEAMENTO DE CAPABILITIES
    # =========================================================================

    CAPABILITY_MODELS = {
        'code_strong': 'groq:openai/gpt-oss-120b',
        'code_fast': 'ollama:qwen2.5-coder:7b',
        'chat_quality': 'ollama:qwen3.5:9b',
        'chat_fast': 'ollama:qwen3.5:9b',
        'analysis': 'ollama:qwen2.5-coder:7b',
        'vision': 'ollama:qwen3-vl:8b',
        'default': 'ollama:qwen3.5:9b'
    }

    def __init__(self):
        self._groq_calls_today = 0
        self._last_reset = datetime.now().date()
        self._daily_limit = 100  # Limite diario estimado

    # =========================================================================
    # SELECAO DE MODELO
    # =========================================================================

    def select_model(
        self,
        user_input: str,
        capability: str = None,
        intent: str = None,
        has_skill: bool = False,
        force_groq: bool = False,
        context_tokens: int = 0
    ) -> ModelChoice:
        """
        Seleciona modelo com justificativa.

        Args:
            user_input: Entrada do usuario
            capability: Capacidade requerida pelo Brain
            intent: Intent detectada
            has_skill: Se uma skill foi selecionada
            force_groq: Se deve forcar uso do Groq
            context_tokens: Quantidade de tokens no contexto

        Returns:
            ModelChoice com modelo, razao e alternativas
        """
        # Reset diario
        self._check_daily_reset()

        input_lower = user_input.lower().strip()
        input_tokens = len(user_input.split())

        # 1. Skill pura resolve
        if has_skill and self._skill_can_handle(input_lower):
            return ModelChoice(
                model_id=None,
                tier=ModelTier.SKILL,
                reason="Skill pura pode resolver sem modelo",
                rule_matched='skill_resolution',
                alternatives=['ollama:qwen3.5:9b']
            )

        # 2. Forca Groq (botao de codigo)
        if force_groq:
            self._groq_calls_today += 1
            return ModelChoice(
                model_id='groq:openai/gpt-oss-120b',
                tier=ModelTier.PREMIUM,
                reason="Modo codigo forcado pelo usuario",
                rule_matched='force_groq',
                alternatives=['ollama:qwen2.5-coder:7b']
            )

        # 3. Verificar regras AVOID_GROQ
        for rule_name, rule in self.AVOID_GROQ_RULES.items():
            if self._matches_avoid_rule(rule, input_lower, input_tokens):
                model = rule['use_instead']
                if model == 'skill':
                    return ModelChoice(
                        model_id=None,
                        tier=ModelTier.SKILL,
                        reason=rule['reason'],
                        rule_matched=rule_name,
                        alternatives=['ollama:qwen3.5:9b']
                    )
                return ModelChoice(
                    model_id=model,
                    tier=ModelTier.STANDARD,
                    reason=rule['reason'],
                    rule_matched=rule_name,
                    alternatives=['groq:openai/gpt-oss-120b']
                )

        # 4. Verificar rate limit
        if self._is_rate_limited():
            return ModelChoice(
                model_id='ollama:qwen3.5:9b',
                tier=ModelTier.STANDARD,
                reason="Proximo do limite diario de Groq",
                rule_matched='rate_limited',
                alternatives=['ollama:qwen2.5-coder:7b']
            )

        # 5. Verificar regras USE_GROQ
        for rule_name, rule in self.USE_GROQ_RULES.items():
            confidence = self._matches_use_rule(rule, input_lower, context_tokens)
            if confidence >= rule.get('min_confidence', 0.5):
                self._groq_calls_today += 1
                return ModelChoice(
                    model_id='groq:openai/gpt-oss-120b',
                    tier=ModelTier.PREMIUM,
                    reason=rule['reason'],
                    rule_matched=rule_name,
                    alternatives=['ollama:qwen2.5-coder:7b', 'ollama:qwen3.5:9b']
                )

        # 6. Baseado em capability
        if capability and capability in self.CAPABILITY_MODELS:
            model = self.CAPABILITY_MODELS[capability]
            tier = ModelTier.PREMIUM if 'groq' in model else ModelTier.STANDARD
            if 'groq' in model:
                self._groq_calls_today += 1
            return ModelChoice(
                model_id=model,
                tier=tier,
                reason=f"Capability: {capability}",
                rule_matched='capability_mapping',
                alternatives=list(set(self.CAPABILITY_MODELS.values()) - {model})[:3]
            )

        # 7. Default
        return ModelChoice(
            model_id='ollama:qwen3.5:9b',
            tier=ModelTier.STANDARD,
            reason="Modelo padrao para tarefas gerais",
            rule_matched='default',
            alternatives=['groq:openai/gpt-oss-120b', 'ollama:qwen2.5-coder:7b']
        )

    # =========================================================================
    # MATCHING
    # =========================================================================

    def _matches_avoid_rule(
        self,
        rule: Dict,
        input_lower: str,
        input_tokens: int
    ) -> bool:
        """Verifica se input corresponde a regra de evitar"""
        # Verificar tamanho maximo
        if 'max_tokens' in rule and input_tokens <= rule['max_tokens']:
            return True

        # Verificar triggers
        for pattern in rule.get('triggers', []):
            if re.search(pattern, input_lower, re.IGNORECASE):
                return True

        return False

    def _matches_use_rule(
        self,
        rule: Dict,
        input_lower: str,
        context_tokens: int
    ) -> float:
        """
        Verifica se input corresponde a regra de uso.
        Retorna confianca (0.0 a 1.0)
        """
        confidence = 0.0

        # Verificar tokens minimos
        if 'min_tokens' in rule and context_tokens >= rule['min_tokens']:
            confidence = max(confidence, 0.6)

        # Verificar triggers
        for pattern in rule.get('triggers', []):
            if re.search(pattern, input_lower, re.IGNORECASE):
                confidence = max(confidence, 0.8)
                break

        return confidence

    def _skill_can_handle(self, input_lower: str) -> bool:
        """Verifica se uma skill pode resolver sem modelo"""
        skill_patterns = [
            r'^(?:quanto e|calcul|some|subtrai|multiplic|divid)',
            r'^(?:que horas|hora atual)',
            r'^(?:que dia|data de hoje|data atual)',
        ]
        return any(re.search(p, input_lower) for p in skill_patterns)

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    def _check_daily_reset(self):
        """Reseta contador diario se necessario"""
        today = datetime.now().date()
        if today > self._last_reset:
            self._groq_calls_today = 0
            self._last_reset = today

    def _is_rate_limited(self) -> bool:
        """Verifica se esta proximo do limite"""
        return self._groq_calls_today >= (self._daily_limit * 0.9)

    def get_groq_usage(self) -> Dict:
        """Retorna estatisticas de uso do Groq"""
        return {
            'calls_today': self._groq_calls_today,
            'daily_limit': self._daily_limit,
            'percentage_used': self._groq_calls_today / self._daily_limit * 100,
            'is_limited': self._is_rate_limited()
        }

    # =========================================================================
    # UTILS
    # =========================================================================

    def get_rules_summary(self) -> Dict:
        """Retorna resumo das regras"""
        return {
            'use_groq_rules': list(self.USE_GROQ_RULES.keys()),
            'avoid_groq_rules': list(self.AVOID_GROQ_RULES.keys()),
            'capabilities': list(self.CAPABILITY_MODELS.keys())
        }

    def explain_choice(self, choice: ModelChoice) -> str:
        """Explica escolha de modelo em linguagem natural"""
        tier_names = {
            ModelTier.PREMIUM: "modelo premium (Groq)",
            ModelTier.STANDARD: "modelo local padrao",
            ModelTier.FAST: "modelo rapido",
            ModelTier.CACHE: "cache",
            ModelTier.SKILL: "skill deterministica"
        }

        return (
            f"Escolhi {tier_names.get(choice.tier, 'modelo')} "
            f"({choice.model_id or 'skill pura'}).\n"
            f"Motivo: {choice.reason}\n"
            f"Regra aplicada: {choice.rule_matched}\n"
            f"Alternativas: {', '.join(choice.alternatives[:3])}"
        )


# =============================================================================
# INSTANCIA GLOBAL (Thread-Safe Singleton)
# =============================================================================

_policy_instance: Optional[ModelUsagePolicy] = None
_policy_lock = threading.Lock()


def get_model_policy() -> ModelUsagePolicy:
    """
    Retorna instancia global da politica (thread-safe).

    Usa double-checked locking para evitar race conditions.
    """
    global _policy_instance
    if _policy_instance is None:
        with _policy_lock:
            # Double-check dentro do lock
            if _policy_instance is None:
                _policy_instance = ModelUsagePolicy()
    return _policy_instance


def select_model(*args, **kwargs) -> ModelChoice:
    """Shortcut para select_model"""
    return get_model_policy().select_model(*args, **kwargs)
