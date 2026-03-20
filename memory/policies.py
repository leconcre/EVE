# memory/policies.py
"""
Politicas de memoria da EVE.
Regras explicitas de quando salvar, esquecer e resumir.

Principio: DECISOES EXPLICITAS, nao heuristicas opacas.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import re


class MemoryAction(Enum):
    """Acoes de memoria"""
    SAVE = "save"
    FORGET = "forget"
    UPDATE = "update"
    ARCHIVE = "archive"
    SUMMARIZE = "summarize"
    DEDUPE = "dedupe"
    SKIP = "skip"


@dataclass
class PolicyDecision:
    """Resultado de uma decisao de politica"""
    action: MemoryAction
    reason: str
    rule_matched: str
    confidence: float
    metadata: Dict = None


class MemoryPolicy:
    """
    Regras explicitas de quando salvar, esquecer e resumir.

    Todas as decisoes sao baseadas em regras claras,
    nao em heuristicas magicas.
    """

    # =========================================================================
    # REGRAS DE SALVAMENTO (LONG-TERM)
    # =========================================================================

    SAVE_RULES = {
        'user_name': {
            'category': 'user_info',
            'patterns': [
                r'(?:meu nome e|me chamo|sou o|sou a)\s+(\w+)',
                r'(?:pode me chamar de)\s+(\w+)',
            ],
            'importance': 0.95,
            'ttl_days': None,  # Permanente
            'reason': 'Informacao pessoal explicita do usuario'
        },
        'user_profession': {
            'category': 'user_info',
            'patterns': [
                r'(?:trabalho como|sou)\s+(desenvolvedor|programador|engenheiro|designer|analista|estudante)',
                r'(?:minha profissao e)\s+(\w+)',
            ],
            'importance': 0.85,
            'ttl_days': None,
            'reason': 'Profissao do usuario'
        },
        'user_location': {
            'category': 'user_info',
            'patterns': [
                r'(?:moro em|sou de|estou em)\s+(.+?)(?:\.|,|$)',
            ],
            'importance': 0.7,
            'ttl_days': None,
            'reason': 'Localizacao do usuario'
        },
        'preference_explicit': {
            'category': 'preferences',
            'patterns': [
                r'(?:prefiro|gosto de|adoro|amo)\s+(.+?)(?:\.|,|$)',
                r'(?:minha linguagem favorita e)\s+(\w+)',
                r'(?:uso mais|trabalho principalmente com)\s+(\w+)',
            ],
            'importance': 0.85,
            'ttl_days': None,
            'reason': 'Preferencia explicita do usuario'
        },
        'preference_negative': {
            'category': 'preferences',
            'patterns': [
                r'(?:nao gosto de|odeio|detesto)\s+(.+?)(?:\.|,|$)',
            ],
            'importance': 0.8,
            'ttl_days': None,
            'reason': 'Preferencia negativa explicita'
        },
        'project_mention': {
            'category': 'projects',
            'patterns': [
                r'(?:meu projeto|trabalhando em|desenvolvendo)\s+(.+?)(?:\.|,|$)',
                r'(?:o projeto se chama|nome do projeto e)\s+(.+?)(?:\.|,|$)',
            ],
            'importance': 0.7,
            'ttl_days': 30,
            'reason': 'Projeto mencionado pelo usuario'
        },
        'problem_reported': {
            'category': 'problems',
            'patterns': [
                r'(?:tenho um problema|erro|bug)(?:\s+(?:com|no|na))?\s+(.+?)(?:\.|$)',
                r'(?:nao consigo|nao funciona)\s+(.+?)(?:\.|$)',
            ],
            'importance': 0.6,
            'ttl_days': 7,
            'reason': 'Problema relatado (nao resolvido)'
        },
        'achievement': {
            'category': 'achievements',
            'patterns': [
                r'(?:consegui|finalizei|terminei|completei)\s+(.+?)(?:\.|,|!|$)',
            ],
            'importance': 0.7,
            'ttl_days': 14,
            'reason': 'Conquista do usuario'
        },
        'technical_skill': {
            'category': 'technical',
            'patterns': [
                r'(?:sei|conheco|domino)\s+(python|javascript|react|vue|angular|sql)',
                r'(?:tenho experiencia com)\s+(.+?)(?:\.|,|$)',
            ],
            'importance': 0.65,
            'ttl_days': 60,
            'reason': 'Habilidade tecnica mencionada'
        }
    }

    # =========================================================================
    # REGRAS DE ESQUECIMENTO
    # =========================================================================

    FORGET_RULES = {
        'expired_ttl': {
            'condition': 'entry.age_days > entry.ttl_days',
            'action': MemoryAction.FORGET,
            'reason': 'TTL expirado'
        },
        'low_importance_old': {
            'condition': 'importance < 0.3 AND age_days > 7',
            'action': MemoryAction.FORGET,
            'reason': 'Baixa importancia e antigo'
        },
        'never_accessed': {
            'condition': 'access_count == 0 AND age_days > 30',
            'action': MemoryAction.FORGET,
            'reason': 'Nunca acessado e antigo'
        },
        'problem_resolved': {
            'condition': 'category == "problems" AND marked_resolved',
            'action': MemoryAction.ARCHIVE,
            'delay_days': 14,
            'reason': 'Problema resolvido'
        },
        'superseded': {
            'condition': 'newer_entry_same_key_exists',
            'action': MemoryAction.FORGET,
            'reason': 'Substituido por informacao mais recente'
        }
    }

    # =========================================================================
    # REGRAS DE RESUMO
    # =========================================================================

    SUMMARIZE_RULES = {
        'message_threshold': {
            'condition': 'messages_since_summary >= 5',
            'action': MemoryAction.SUMMARIZE,
            'reason': 'Limite de mensagens atingido'
        },
        'topic_change': {
            'condition': 'detected_topic != previous_topic',
            'action': MemoryAction.SUMMARIZE,
            'reason': 'Mudanca de topico detectada'
        },
        'session_end': {
            'condition': 'session_ending',
            'action': MemoryAction.SUMMARIZE,
            'reason': 'Fim de sessao'
        },
        'long_conversation': {
            'condition': 'total_tokens > 2000',
            'action': MemoryAction.SUMMARIZE,
            'reason': 'Conversa longa, comprimir contexto'
        },
        'time_gap': {
            'condition': 'time_since_last_message > 30 minutes',
            'action': MemoryAction.SUMMARIZE,
            'reason': 'Gap de tempo grande'
        }
    }

    # =========================================================================
    # DECISOES DE SALVAMENTO
    # =========================================================================

    def should_save(
        self,
        text: str,
        category: str = None
    ) -> PolicyDecision:
        """
        Decide se deve salvar na memoria longa.

        Returns:
            PolicyDecision com acao e justificativa
        """
        text_lower = text.lower()

        for rule_name, rule in self.SAVE_RULES.items():
            # Filtrar por categoria se especificada
            if category and rule.get('category') != category:
                continue

            # Verificar patterns
            for pattern in rule.get('patterns', []):
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    return PolicyDecision(
                        action=MemoryAction.SAVE,
                        reason=rule['reason'],
                        rule_matched=rule_name,
                        confidence=rule.get('importance', 0.5),
                        metadata={
                            'category': rule.get('category'),
                            'importance': rule.get('importance', 0.5),
                            'ttl_days': rule.get('ttl_days'),
                            'extracted': match.group(1) if match.groups() else match.group(0)
                        }
                    )

        return PolicyDecision(
            action=MemoryAction.SKIP,
            reason='Nenhuma regra de salvamento correspondeu',
            rule_matched='none',
            confidence=0.0
        )

    def should_forget(
        self,
        entry: Dict,
        current_time: datetime = None
    ) -> PolicyDecision:
        """
        Decide se deve esquecer uma entrada.

        Args:
            entry: Dicionario com campos da entrada
                - timestamp: datetime de criacao
                - importance: float 0-1
                - access_count: int
                - category: str
                - ttl_days: int ou None
                - marked_resolved: bool (opcional)

        Returns:
            PolicyDecision com acao e justificativa
        """
        current_time = current_time or datetime.now()

        # Calcular idade
        timestamp = entry.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        age_days = (current_time - timestamp).days if timestamp else 0

        importance = entry.get('importance', 0.5)
        access_count = entry.get('access_count', 0)
        category = entry.get('category', '')
        ttl_days = entry.get('ttl_days')
        marked_resolved = entry.get('marked_resolved', False)

        # Regra: TTL expirado
        if ttl_days is not None and age_days > ttl_days:
            return PolicyDecision(
                action=MemoryAction.FORGET,
                reason='TTL expirado',
                rule_matched='expired_ttl',
                confidence=1.0
            )

        # Regra: Baixa importancia e antigo
        if importance < 0.3 and age_days > 7:
            return PolicyDecision(
                action=MemoryAction.FORGET,
                reason='Baixa importancia e mais de 7 dias',
                rule_matched='low_importance_old',
                confidence=0.8
            )

        # Regra: Nunca acessado e antigo
        if access_count == 0 and age_days > 30:
            return PolicyDecision(
                action=MemoryAction.FORGET,
                reason='Nunca acessado em 30 dias',
                rule_matched='never_accessed',
                confidence=0.7
            )

        # Regra: Problema resolvido
        if category == 'problems' and marked_resolved and age_days > 14:
            return PolicyDecision(
                action=MemoryAction.ARCHIVE,
                reason='Problema resolvido ha mais de 14 dias',
                rule_matched='problem_resolved',
                confidence=0.9
            )

        return PolicyDecision(
            action=MemoryAction.SKIP,
            reason='Entrada deve ser mantida',
            rule_matched='keep',
            confidence=1.0
        )

    def should_summarize(
        self,
        messages_since_summary: int,
        total_tokens: int,
        topic_changed: bool,
        session_ending: bool,
        minutes_since_last: int
    ) -> PolicyDecision:
        """
        Decide se deve resumir o contexto.

        Returns:
            PolicyDecision com acao e justificativa
        """
        # Limite de mensagens
        if messages_since_summary >= 5:
            return PolicyDecision(
                action=MemoryAction.SUMMARIZE,
                reason='5+ mensagens desde ultimo resumo',
                rule_matched='message_threshold',
                confidence=0.9
            )

        # Mudanca de topico
        if topic_changed:
            return PolicyDecision(
                action=MemoryAction.SUMMARIZE,
                reason='Topico mudou',
                rule_matched='topic_change',
                confidence=0.8
            )

        # Fim de sessao
        if session_ending:
            return PolicyDecision(
                action=MemoryAction.SUMMARIZE,
                reason='Sessao encerrando',
                rule_matched='session_end',
                confidence=1.0
            )

        # Conversa longa
        if total_tokens > 2000:
            return PolicyDecision(
                action=MemoryAction.SUMMARIZE,
                reason='Contexto muito longo (>2000 tokens)',
                rule_matched='long_conversation',
                confidence=0.85
            )

        # Gap de tempo
        if minutes_since_last > 30:
            return PolicyDecision(
                action=MemoryAction.SUMMARIZE,
                reason='Gap de 30+ minutos',
                rule_matched='time_gap',
                confidence=0.7
            )

        return PolicyDecision(
            action=MemoryAction.SKIP,
            reason='Resumo nao necessario',
            rule_matched='none',
            confidence=0.0
        )

    # =========================================================================
    # DEDUPLICACAO
    # =========================================================================

    def is_duplicate(
        self,
        new_content: str,
        existing_contents: List[str],
        threshold: float = 0.8
    ) -> Tuple[bool, Optional[str]]:
        """
        Detecta duplicatas SEM embeddings.

        Estrategias:
        1. Normalizacao + exact match
        2. Jaccard similarity de tokens
        3. Substring containment

        Returns:
            (is_duplicate, matching_content)
        """
        normalized_new = self._normalize(new_content)

        for existing in existing_contents:
            normalized_existing = self._normalize(existing)

            # Exact match apos normalizacao
            if normalized_new == normalized_existing:
                return True, existing

            # Jaccard similarity
            tokens_new = set(normalized_new.split())
            tokens_existing = set(normalized_existing.split())

            if not tokens_new or not tokens_existing:
                continue

            intersection = len(tokens_new & tokens_existing)
            union = len(tokens_new | tokens_existing)

            if union > 0 and intersection / union > threshold:
                return True, existing

            # Um contem o outro (substring)
            if len(normalized_new) > 10 and len(normalized_existing) > 10:
                if normalized_new in normalized_existing:
                    return True, existing
                if normalized_existing in normalized_new:
                    return True, existing

        return False, None

    def _normalize(self, text: str) -> str:
        """Normaliza texto para comparacao"""
        # Lowercase
        text = text.lower()

        # Remove pontuacao
        text = re.sub(r'[^\w\s]', '', text)

        # Remove espacos extras
        text = ' '.join(text.split())

        return text

    # =========================================================================
    # EXTRACAO
    # =========================================================================

    def extract_facts(self, text: str) -> List[Dict]:
        """
        Extrai fatos do texto usando as regras de salvamento.

        Returns:
            Lista de fatos extraidos com metadados
        """
        facts = []
        text_lower = text.lower()

        for rule_name, rule in self.SAVE_RULES.items():
            for pattern in rule.get('patterns', []):
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    content = match.group(1) if match.groups() else match.group(0)
                    content = content.strip()

                    if len(content) < 2 or len(content) > 200:
                        continue

                    facts.append({
                        'content': content,
                        'category': rule.get('category', 'general'),
                        'importance': rule.get('importance', 0.5),
                        'ttl_days': rule.get('ttl_days'),
                        'rule': rule_name,
                        'reason': rule.get('reason', '')
                    })

        return facts

    # =========================================================================
    # STATS
    # =========================================================================

    def get_rules_summary(self) -> Dict:
        """Retorna resumo das regras"""
        return {
            'save_rules': len(self.SAVE_RULES),
            'forget_rules': len(self.FORGET_RULES),
            'summarize_rules': len(self.SUMMARIZE_RULES),
            'categories': list(set(
                r.get('category') for r in self.SAVE_RULES.values()
                if r.get('category')
            ))
        }


# =============================================================================
# INSTANCIA GLOBAL
# =============================================================================

_policy_instance: Optional[MemoryPolicy] = None


def get_memory_policy() -> MemoryPolicy:
    """Retorna instancia global da politica"""
    global _policy_instance
    if _policy_instance is None:
        _policy_instance = MemoryPolicy()
    return _policy_instance
