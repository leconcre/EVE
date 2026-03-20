# skills/builtin/calculator.py
"""
Skill de calculadora.
PURE - não precisa de modelo.
"""

from typing import Dict, Any, Optional
import re
import math
import operator

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error
)


class CalculatorSkill(Skill):
    """Calculadora matemática sem usar modelo"""

    name = "calculator"
    description = "Calcula expressões matemáticas"
    version = "1.0.0"
    skill_type = SkillType.PURE
    priority = SkillPriority.HIGH
    tags = ['calcular', 'matemática', 'conta', 'expressão']

    # Operadores seguros
    SAFE_OPERATORS = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '//': operator.floordiv,
        '%': operator.mod,
        '**': operator.pow,
        '^': operator.pow,
    }

    # Funções matemáticas seguras
    SAFE_FUNCTIONS = {
        'sqrt': math.sqrt,
        'raiz': math.sqrt,
        'abs': abs,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log10,
        'ln': math.log,
        'exp': math.exp,
        'floor': math.floor,
        'ceil': math.ceil,
        'round': round,
        'pow': pow,
        'factorial': math.factorial,
        'fatorial': math.factorial,
    }

    # Constantes
    CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
        'tau': math.tau,
    }

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'calcule', 'calcular', 'quanto é', 'quanto da',
                'resultado de', 'soma', 'subtrai', 'multiplica',
                'divide', 'raiz', 'potência', 'porcentagem'
            ],
            patterns=[
                r'(?:calcule|quanto é|quanto da)\s+',
                r'\d+\s*[\+\-\*\/\^]\s*\d+',
                r'(?:soma|subtrai|multiplica|divide)\s+\d+',
                r'(?:raiz|sqrt)\s*(?:de\s*)?\d+',
                r'\d+\s*%\s*(?:de\s*)?\d+',
            ],
            intents=['COMMAND'],
            min_confidence=0.6
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Executa cálculo"""
        # Extrair expressão
        expression = self._extract_expression(user_input)

        if not expression:
            return skill_error(
                "Não consegui identificar a expressão matemática. "
                "Exemplos: 'calcule 2 + 2', 'quanto é 10 * 5', 'raiz de 16'"
            )

        # Normalizar expressão
        normalized = self._normalize_expression(expression)

        if not normalized:
            return skill_error(f"Expressão inválida: {expression}")

        # Calcular
        try:
            result = self._safe_eval(normalized)

            if result is None:
                return skill_error("Não foi possível calcular a expressão.")

            # Formatar resultado
            formatted = self._format_result(result, expression)

            return skill_success(
                formatted,
                expression=expression,
                normalized=normalized,
                result=result
            )

        except ZeroDivisionError:
            return skill_error("Erro: Divisão por zero!")
        except ValueError as e:
            return skill_error(f"Erro matemático: {str(e)}")
        except Exception as e:
            return skill_error(f"Erro ao calcular: {str(e)}")

    def _extract_expression(self, text: str) -> Optional[str]:
        """Extrai expressão matemática do texto"""
        # Remover prefixos comuns
        prefixes = [
            'calcule', 'calcular', 'quanto é', 'quanto da', 'quanto dá',
            'resultado de', 'me diga', 'qual é', 'compute'
        ]

        text_clean = text.lower().strip()
        for prefix in prefixes:
            if text_clean.startswith(prefix):
                text_clean = text_clean[len(prefix):].strip()

        # Limpar pontuação final
        text_clean = text_clean.rstrip('?!.')

        # Se tem números e operadores, provavelmente é expressão
        if re.search(r'\d', text_clean) and re.search(r'[\+\-\*\/\^%]|raiz|sqrt|soma|subtrai', text_clean):
            return text_clean

        # Tentar extrair expressão numérica pura
        match = re.search(r'[\d\.\s\+\-\*\/\^\(\)%]+', text_clean)
        if match and len(match.group().replace(' ', '')) > 2:
            return match.group().strip()

        return text_clean if text_clean else None

    def _normalize_expression(self, expr: str) -> Optional[str]:
        """Normaliza expressão para avaliação"""
        expr = expr.lower().strip()

        # Substituições de palavras
        replacements = [
            # Operações em português
            (r'(\d+)\s*mais\s*(\d+)', r'\1+\2'),
            (r'(\d+)\s*menos\s*(\d+)', r'\1-\2'),
            (r'(\d+)\s*vezes\s*(\d+)', r'\1*\2'),
            (r'(\d+)\s*dividido\s*(?:por\s*)?(\d+)', r'\1/\2'),
            (r'(\d+)\s*elevado\s*(?:a\s*)?(\d+)', r'\1**\2'),

            # Soma/subtração
            (r'soma\s*(?:de\s*)?(\d+)\s*(?:e|com)\s*(\d+)', r'\1+\2'),
            (r'subtrai\s*(\d+)\s*(?:de|menos)\s*(\d+)', r'\2-\1'),

            # Raiz
            (r'raiz\s*(?:quadrada\s*)?(?:de\s*)?(\d+)', r'sqrt(\1)'),
            (r'sqrt\s*(?:de\s*)?(\d+)', r'sqrt(\1)'),

            # Potência
            (r'(\d+)\s*ao\s*quadrado', r'\1**2'),
            (r'(\d+)\s*ao\s*cubo', r'\1**3'),

            # Porcentagem
            (r'(\d+)\s*%\s*de\s*(\d+)', r'(\1/100)*\2'),
            (r'(\d+)\s*por\s*cento\s*de\s*(\d+)', r'(\1/100)*\2'),

            # Fatorial
            (r'fatorial\s*(?:de\s*)?(\d+)', r'factorial(\1)'),
            (r'(\d+)!', r'factorial(\1)'),

            # Símbolos
            (r'\^', '**'),
            (r'×', '*'),
            (r'÷', '/'),
            (r'x(?=\d)', '*'),  # 2x3 -> 2*3
        ]

        result = expr
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Substituir constantes
        for const, value in self.CONSTANTS.items():
            result = re.sub(rf'\b{const}\b', str(value), result, flags=re.IGNORECASE)

        # Limpar espaços
        result = re.sub(r'\s+', '', result)

        # Validar caracteres permitidos
        allowed = set('0123456789.+-*/()%,')
        func_pattern = r'(' + '|'.join(self.SAFE_FUNCTIONS.keys()) + r')'

        # Remover funções válidas para validação
        check_str = re.sub(func_pattern, '', result, flags=re.IGNORECASE)

        if not all(c in allowed for c in check_str):
            return None

        return result

    def _safe_eval(self, expr: str) -> Optional[float]:
        """Avalia expressão de forma segura"""
        # Não usar eval - parse manual

        # Substituir funções
        for func_name, func in self.SAFE_FUNCTIONS.items():
            pattern = rf'{func_name}\(([^)]+)\)'
            while re.search(pattern, expr, re.IGNORECASE):
                match = re.search(pattern, expr, re.IGNORECASE)
                if match:
                    arg = match.group(1)
                    # Avaliar argumento recursivamente
                    arg_val = self._safe_eval(arg)
                    if arg_val is None:
                        return None
                    try:
                        result = func(arg_val)
                        expr = expr[:match.start()] + str(result) + expr[match.end():]
                    except Exception:
                        return None

        # Avaliar expressão numérica simples
        try:
            # Usar compile para validação adicional
            code = compile(expr, '<string>', 'eval')

            # Verificar bytecode (só números e operações)
            for name in code.co_names:
                if name not in self.SAFE_FUNCTIONS and name not in self.CONSTANTS:
                    return None

            # Avaliar com namespace restrito
            result = eval(code, {"__builtins__": {}}, self.SAFE_FUNCTIONS)
            return float(result)

        except Exception:
            return None

    def _format_result(self, result: float, expression: str) -> str:
        """Formata resultado para exibição"""
        # Verificar se é inteiro
        if result == int(result):
            result_str = str(int(result))
        else:
            # Limitar casas decimais
            result_str = f"{result:.10g}"

        # Formatar número grande
        if abs(result) >= 1e6:
            result_str = f"{result:.4e}"
        elif abs(result) >= 1000:
            result_str = f"{result:,.2f}".replace(',', '.')

        return f"🧮 **Resultado:**\n\n`{expression}` = **{result_str}**"
