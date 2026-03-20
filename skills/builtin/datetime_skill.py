# skills/builtin/datetime_skill.py
"""
Skill de data e hora.
PURE - não precisa de modelo.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import re

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error
)


class DateTimeSkill(Skill):
    """Informações de data e hora sem usar modelo"""

    name = "datetime"
    description = "Fornece data, hora e cálculos temporais"
    version = "1.0.0"
    skill_type = SkillType.PURE
    priority = SkillPriority.HIGH
    tags = ['data', 'hora', 'tempo', 'dia', 'calendário']

    # Dias da semana em português
    WEEKDAYS_PT = [
        'Segunda-feira', 'Terça-feira', 'Quarta-feira',
        'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'
    ]

    # Meses em português
    MONTHS_PT = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril',
        'Maio', 'Junho', 'Julho', 'Agosto',
        'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'que horas', 'hora atual', 'que dia', 'data de hoje',
                'hoje é', 'dia da semana', 'que mês', 'que ano',
                'quanto tempo', 'dias até', 'semanas até'
            ],
            patterns=[
                r'que\s+(?:horas?|dia|data)',
                r'(?:qual|que)\s+(?:é\s+)?(?:a\s+)?data',
                r'hoje\s+é\s+(?:que|qual)',
                r'(?:quantos?\s+)?dias?\s+(?:até|falta)',
            ],
            intents=['COMMAND', 'QUESTION_FACTUAL'],
            min_confidence=0.6
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Executa consulta de data/hora"""
        text_lower = user_input.lower()
        now = datetime.now()

        # Hora atual
        if 'hora' in text_lower or 'horas' in text_lower:
            return self._current_time(now)

        # Data atual
        if any(kw in text_lower for kw in ['que dia', 'data', 'hoje']):
            return self._current_date(now)

        # Dia da semana
        if 'dia da semana' in text_lower or 'que dia é' in text_lower:
            return self._weekday_info(now)

        # Cálculo de dias até uma data
        if 'dias até' in text_lower or 'falta' in text_lower:
            return self._days_until(text_lower, now)

        # Default: data e hora completa
        return self._full_datetime(now)

    def _current_time(self, now: datetime) -> SkillResult:
        """Retorna hora atual"""
        time_str = now.strftime('%H:%M:%S')
        period = 'da manhã' if now.hour < 12 else ('da tarde' if now.hour < 18 else 'da noite')

        output = f"🕐 **Hora atual:** {time_str} ({now.strftime('%H:%M')} {period})"

        return skill_success(
            output,
            time=time_str,
            hour=now.hour,
            minute=now.minute
        )

    def _current_date(self, now: datetime) -> SkillResult:
        """Retorna data atual"""
        weekday = self.WEEKDAYS_PT[now.weekday()]
        month = self.MONTHS_PT[now.month - 1]

        date_str = f"{now.day} de {month} de {now.year}"
        iso_date = now.strftime('%Y-%m-%d')

        output = f"📅 **Hoje:** {weekday}, {date_str}"

        return skill_success(
            output,
            date=iso_date,
            day=now.day,
            month=now.month,
            year=now.year,
            weekday=weekday
        )

    def _weekday_info(self, now: datetime) -> SkillResult:
        """Retorna informação sobre dia da semana"""
        weekday = self.WEEKDAYS_PT[now.weekday()]
        weekday_num = now.weekday() + 1  # 1=Segunda, 7=Domingo

        # Informação sobre fim de semana
        is_weekend = now.weekday() >= 5
        if is_weekend:
            info = "É fim de semana! 🎉"
        else:
            days_to_weekend = 5 - now.weekday()
            info = f"Faltam {days_to_weekend} dia(s) para o fim de semana."

        output = f"📆 **Dia da semana:** {weekday}\n{info}"

        return skill_success(
            output,
            weekday=weekday,
            weekday_number=weekday_num,
            is_weekend=is_weekend
        )

    def _days_until(self, text: str, now: datetime) -> SkillResult:
        """Calcula dias até uma data"""
        # Tentar extrair data
        target_date = self._parse_date(text, now)

        if not target_date:
            return skill_error(
                "Não consegui identificar a data. "
                "Exemplos: 'dias até 25/12', 'dias até natal', 'dias até ano novo'"
            )

        diff = target_date - now.replace(hour=0, minute=0, second=0, microsecond=0)
        days = diff.days

        if days < 0:
            return skill_success(
                f"⏰ Essa data já passou ({abs(days)} dia(s) atrás).",
                days=days,
                target_date=target_date.strftime('%Y-%m-%d')
            )
        elif days == 0:
            return skill_success(
                "🎯 **É hoje!**",
                days=0,
                target_date=target_date.strftime('%Y-%m-%d')
            )
        else:
            weeks = days // 7
            remaining_days = days % 7

            if weeks > 0:
                time_str = f"{weeks} semana(s) e {remaining_days} dia(s)"
            else:
                time_str = f"{days} dia(s)"

            output = f"📆 **Faltam {time_str}** até {target_date.strftime('%d/%m/%Y')}"

            return skill_success(
                output,
                days=days,
                weeks=weeks,
                target_date=target_date.strftime('%Y-%m-%d')
            )

    def _full_datetime(self, now: datetime) -> SkillResult:
        """Retorna data e hora completa"""
        weekday = self.WEEKDAYS_PT[now.weekday()]
        month = self.MONTHS_PT[now.month - 1]

        output = [
            f"📅 **{weekday}**, {now.day} de {month} de {now.year}",
            f"🕐 **{now.strftime('%H:%M:%S')}**"
        ]

        return skill_success(
            "\n".join(output),
            datetime=now.isoformat(),
            weekday=weekday
        )

    def _parse_date(self, text: str, reference: datetime) -> Optional[datetime]:
        """Tenta parsear uma data do texto"""
        text_lower = text.lower()

        # Datas especiais
        special_dates = {
            'natal': (12, 25),
            'ano novo': (1, 1),
            'reveillon': (12, 31),
            'dia das mães': (5, 12),  # Segundo domingo de maio (aproximado)
            'dia dos pais': (8, 11),  # Segundo domingo de agosto (aproximado)
            'dia das crianças': (10, 12),
            'independência': (9, 7),
            'proclamação': (11, 15),
        }

        for name, (month, day) in special_dates.items():
            if name in text_lower:
                year = reference.year
                target = datetime(year, month, day)
                if target < reference:
                    target = datetime(year + 1, month, day)
                return target

        # Tentar formato DD/MM ou DD/MM/YYYY
        date_match = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', text)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year = date_match.group(3)

            if year:
                year = int(year)
                if year < 100:
                    year += 2000
            else:
                year = reference.year

            try:
                target = datetime(year, month, day)
                if target < reference and not date_match.group(3):
                    target = datetime(year + 1, month, day)
                return target
            except ValueError:
                return None

        return None
