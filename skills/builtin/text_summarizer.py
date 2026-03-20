# skills/builtin/text_summarizer.py
"""
Skill de resumo de texto.
MODEL_OPTIONAL - pode fazer resumo básico sem modelo.
"""

from typing import Dict, Any, List, Optional
import re
from collections import Counter

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error, skill_needs_model
)


class TextSummarizerSkill(Skill):
    """Resumidor de texto com extração heurística"""

    name = "text_summarizer"
    description = "Resume textos, artigos e documentos"
    version = "1.0.0"
    skill_type = SkillType.MODEL_OPTIONAL
    priority = SkillPriority.NORMAL
    preferred_capability = "summarization"
    tags = ['resumo', 'resumir', 'sintetizar', 'texto']

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'resuma', 'resumir', 'resumo', 'sintetize', 'sintetizar',
                'condense', 'principais pontos', 'em poucas palavras',
                'tldr', 'tl;dr'
            ],
            patterns=[
                r'(?:resuma|sintetize)\s+(?:esse?|este?|o)\s+(?:texto|artigo|documento)',
                r'(?:quais|qual)\s+(?:são|é)\s+(?:os\s+)?principais?\s+pontos?',
                r'(?:faça|faz)\s+um\s+resumo',
            ],
            intents=['TASK_SUMMARIZE'],
            min_confidence=0.5
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Executa resumo de texto"""
        # Extrair texto para resumir
        text = self._extract_text(user_input, context)

        if not text:
            return skill_error(
                "Não encontrei texto para resumir. "
                "Cole o texto diretamente ou indique a fonte."
            )

        # Analisar tamanho e complexidade
        word_count = len(text.split())
        sentence_count = len(re.split(r'[.!?]+', text))

        # Para textos curtos, resumo heurístico
        if word_count < 300:
            summary = self._heuristic_summary(text)
            return skill_success(
                summary,
                method='heuristic',
                original_words=word_count,
                summary_words=len(summary.split())
            )

        # Para textos longos, usar modelo
        prompt = self._build_summary_prompt(text, word_count)
        return skill_needs_model(
            prompt=prompt,
            partial_output={
                'original_words': word_count,
                'sentence_count': sentence_count
            }
        )

    def _extract_text(
        self,
        user_input: str,
        context: Dict
    ) -> Optional[str]:
        """Extrai texto para resumir"""
        # Verificar contexto de arquivo
        if context.get('file_content'):
            return context['file_content']

        # Remover comando de resumo
        text = re.sub(
            r'^(?:resuma|sintetize|resumo de|faça um resumo de)\s*:?\s*',
            '',
            user_input,
            flags=re.IGNORECASE
        )

        # Se sobrou texto significativo
        if len(text.split()) > 20:
            return text

        return None

    def _heuristic_summary(self, text: str) -> str:
        """Resumo heurístico para textos curtos"""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if len(sentences) <= 3:
            return text

        # Pontuar sentenças
        scored_sentences = []

        for i, sent in enumerate(sentences):
            score = 0

            # Posição (início e fim são importantes)
            if i == 0:
                score += 2
            elif i == len(sentences) - 1:
                score += 1
            elif i < len(sentences) * 0.3:
                score += 1

            # Tamanho (preferir médias)
            words = len(sent.split())
            if 10 <= words <= 25:
                score += 1

            # Palavras importantes
            important_words = [
                'importante', 'principal', 'essencial', 'fundamental',
                'portanto', 'assim', 'conclusão', 'resultado',
                'porque', 'motivo', 'razão', 'objetivo'
            ]
            if any(w in sent.lower() for w in important_words):
                score += 2

            # Números (indicam dados concretos)
            if re.search(r'\d+', sent):
                score += 0.5

            scored_sentences.append((score, sent))

        # Selecionar top sentenças
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        n_sentences = min(3, len(sentences) // 2 + 1)
        selected = scored_sentences[:n_sentences]

        # Ordenar por posição original
        selected_sents = [s for _, s in selected]
        ordered = [s for s in sentences if s in selected_sents]

        summary = ' '.join(ordered)

        # Adicionar indicador de resumo
        word_count = len(summary.split())
        original_count = len(text.split())

        header = f"📝 **Resumo** ({word_count} palavras de {original_count}):\n\n"
        return header + summary

    def _build_summary_prompt(self, text: str, word_count: int) -> str:
        """Constrói prompt para resumo com modelo"""
        # Determinar tamanho do resumo
        if word_count > 1000:
            target = "200-300 palavras"
        elif word_count > 500:
            target = "100-150 palavras"
        else:
            target = "50-100 palavras"

        prompt = f"""Resuma o texto abaixo em {target}.

Diretrizes:
- Capture os pontos principais
- Mantenha a essência do conteúdo
- Use linguagem clara e direta
- Preserve informações importantes (números, nomes, datas)

Texto ({word_count} palavras):
---
{text[:4000]}
---

Resumo:"""

        return prompt


class KeyPointsExtractorSkill(Skill):
    """Extrai pontos-chave de um texto"""

    name = "key_points_extractor"
    description = "Extrai os pontos principais de um texto"
    version = "1.0.0"
    skill_type = SkillType.MODEL_OPTIONAL
    priority = SkillPriority.NORMAL
    tags = ['pontos', 'principais', 'extrair', 'bullets']

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'pontos principais', 'pontos chave', 'key points',
                'bullets', 'itens principais', 'extraia os pontos'
            ],
            patterns=[
                r'(?:quais|liste)\s+(?:são\s+)?(?:os\s+)?pontos\s+(?:principais|chave)',
                r'extraia?\s+(?:os\s+)?pontos',
            ],
            intents=['TASK_SUMMARIZE'],
            min_confidence=0.5
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Extrai pontos-chave"""
        text = self._extract_text(user_input, context)

        if not text:
            return skill_error("Não encontrei texto para extrair pontos.")

        word_count = len(text.split())

        # Extração heurística para textos curtos
        if word_count < 500:
            points = self._extract_heuristic(text)
            return skill_success(
                self._format_points(points),
                points=points,
                method='heuristic'
            )

        # Modelo para textos longos
        prompt = f"""Extraia os 5-7 pontos principais deste texto em formato de lista:

Texto:
{text[:3500]}

Liste cada ponto em uma linha, começando com "•" """

        return skill_needs_model(prompt=prompt)

    def _extract_text(self, user_input: str, context: Dict) -> Optional[str]:
        """Extrai texto"""
        if context.get('file_content'):
            return context['file_content']

        # Remover comando
        text = re.sub(
            r'^(?:extraia?|liste|quais são)\s+(?:os\s+)?pontos.*?:\s*',
            '',
            user_input,
            flags=re.IGNORECASE
        )

        if len(text.split()) > 20:
            return text
        return None

    def _extract_heuristic(self, text: str) -> List[str]:
        """Extração heurística de pontos"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        points = []

        # Indicadores de pontos importantes
        indicators = [
            'importante', 'principal', 'essencial', 'fundamental',
            'primeiro', 'segundo', 'terceiro',
            'além disso', 'também', 'por fim',
            'destaque', 'nota', 'atenção'
        ]

        for sent in sentences:
            sent_lower = sent.lower()

            # Verificar indicadores
            if any(ind in sent_lower for ind in indicators):
                points.append(sent.strip())
                continue

            # Sentenças com estrutura de afirmação
            if re.match(r'^[A-Z].*(?:é|são|foi|foram|tem|têm)\s', sent):
                if 10 <= len(sent.split()) <= 30:
                    points.append(sent.strip())

        # Limitar e remover duplicatas
        seen = set()
        unique_points = []
        for p in points:
            p_norm = p.lower()[:50]
            if p_norm not in seen:
                seen.add(p_norm)
                unique_points.append(p)

        return unique_points[:7]

    def _format_points(self, points: List[str]) -> str:
        """Formata pontos para output"""
        if not points:
            return "Não foi possível extrair pontos-chave claros."

        lines = ["📌 **Pontos Principais:**\n"]
        for i, point in enumerate(points, 1):
            lines.append(f"  {i}. {point}")

        return "\n".join(lines)
