# skills/builtin/code_generator.py
"""
Skill de geração de código.
MODEL_REQUIRED - precisa de modelo para gerar código.
"""

from typing import Dict, Any, List, Optional
import re

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error, skill_needs_model
)


class CodeGeneratorSkill(Skill):
    """Gerador de código em múltiplas linguagens"""

    name = "code_generator"
    description = "Gera código em múltiplas linguagens de programação"
    version = "2.0.0"
    skill_type = SkillType.MODEL_REQUIRED
    priority = SkillPriority.HIGH
    preferred_capability = "code_strong"
    timeout_seconds = 180
    tags = ['código', 'programação', 'função', 'classe', 'script']

    # Linguagens suportadas
    LANGUAGES = {
        'python': {'ext': '.py', 'comment': '#', 'aliases': ['py', 'python3']},
        'javascript': {'ext': '.js', 'comment': '//', 'aliases': ['js', 'node']},
        'typescript': {'ext': '.ts', 'comment': '//', 'aliases': ['ts']},
        'cpp': {'ext': '.cpp', 'comment': '//', 'aliases': ['c++', 'cplusplus']},
        'c': {'ext': '.c', 'comment': '//', 'aliases': []},
        'java': {'ext': '.java', 'comment': '//', 'aliases': []},
        'rust': {'ext': '.rs', 'comment': '//', 'aliases': ['rs']},
        'go': {'ext': '.go', 'comment': '//', 'aliases': ['golang']},
        'php': {'ext': '.php', 'comment': '//', 'aliases': []},
        'ruby': {'ext': '.rb', 'comment': '#', 'aliases': ['rb']},
        'sql': {'ext': '.sql', 'comment': '--', 'aliases': ['mysql', 'postgres']},
        'html': {'ext': '.html', 'comment': '<!--', 'aliases': ['htm']},
        'css': {'ext': '.css', 'comment': '/*', 'aliases': []},
        'bash': {'ext': '.sh', 'comment': '#', 'aliases': ['sh', 'shell']},
    }

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'crie', 'escreva', 'implemente', 'código', 'função',
                'programa', 'script', 'classe', 'módulo', 'gere',
                'faça', 'desenvolva', 'programe', 'codifique'
            ],
            patterns=[
                r'\[modo código\]',
                r'\[code\]',
                r'(crie|faça|escreva)\s+(um|uma)\s+(código|função|classe|programa|script)',
                r'em\s+(python|javascript|typescript|c\+\+|java|rust|go)',
                r'implementa?r?\s+(uma?\s+)?(função|classe|método|api)',
            ],
            intents=['TASK_CODE'],
            min_confidence=0.6
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """
        Prepara prompt para geração de código.
        Retorna needs_model=True com prompt especializado.
        """
        # 1. Detectar linguagem
        language = self._detect_language(user_input, context)
        lang_info = self.LANGUAGES.get(language, self.LANGUAGES['python'])

        # 2. Extrair requisitos
        requirements = self._extract_requirements(user_input)

        # 3. Construir system prompt especializado
        system_prompt = self._build_code_prompt(language, requirements)

        # 4. Construir user prompt
        user_prompt = self._clean_user_input(user_input)

        # 5. Retornar para modelo processar
        return SkillResult(
            success=True,
            output=None,
            needs_model=True,
            model_prompt=user_prompt,
            metadata={
                'language': language,
                'language_info': lang_info,
                'requirements': requirements,
                'system_prompt': system_prompt,
                'task_type': 'code_generation'
            }
        )

    def _detect_language(
        self,
        text: str,
        context: Dict
    ) -> str:
        """Detecta linguagem de programação solicitada"""
        text_lower = text.lower()

        # Explícito na mensagem
        for lang, info in self.LANGUAGES.items():
            if lang in text_lower:
                return lang
            for alias in info.get('aliases', []):
                if alias in text_lower:
                    return lang

        # Preferência do usuário na memória
        prefs = context.get('preferences', {})
        if pref_lang := prefs.get('linguagem'):
            pref_lang = pref_lang.lower()
            if pref_lang in self.LANGUAGES:
                return pref_lang
            # Verificar aliases
            for lang, info in self.LANGUAGES.items():
                if pref_lang in info.get('aliases', []):
                    return lang

        # Detectar por contexto
        if 'react' in text_lower or 'component' in text_lower:
            return 'javascript'
        if 'api rest' in text_lower or 'flask' in text_lower or 'django' in text_lower:
            return 'python'
        if 'game' in text_lower and 'unity' not in text_lower:
            return 'cpp'

        # Default
        return 'python'

    def _extract_requirements(self, text: str) -> Dict[str, Any]:
        """Extrai requisitos do código"""
        requirements = {
            'type': 'unknown',
            'features': [],
            'constraints': []
        }

        text_lower = text.lower()

        # Tipo de código
        if 'função' in text_lower or 'function' in text_lower:
            requirements['type'] = 'function'
        elif 'classe' in text_lower or 'class' in text_lower:
            requirements['type'] = 'class'
        elif 'api' in text_lower or 'endpoint' in text_lower:
            requirements['type'] = 'api'
        elif 'script' in text_lower:
            requirements['type'] = 'script'
        elif 'teste' in text_lower or 'test' in text_lower:
            requirements['type'] = 'test'

        # Features
        features_keywords = {
            'async': ['async', 'assíncrono', 'await'],
            'typing': ['tipado', 'tipos', 'type hints'],
            'error_handling': ['tratamento de erro', 'try catch', 'exception'],
            'logging': ['log', 'logging', 'debug'],
            'documentation': ['documentado', 'docstring', 'comentado'],
            'tests': ['teste', 'test', 'unittest', 'pytest'],
        }

        for feature, keywords in features_keywords.items():
            if any(kw in text_lower for kw in keywords):
                requirements['features'].append(feature)

        # Constraints
        if 'simples' in text_lower or 'básico' in text_lower:
            requirements['constraints'].append('keep_simple')
        if 'otimizado' in text_lower or 'performático' in text_lower:
            requirements['constraints'].append('optimize')
        if 'seguro' in text_lower or 'validação' in text_lower:
            requirements['constraints'].append('validate_input')

        return requirements

    def _build_code_prompt(
        self,
        language: str,
        requirements: Dict
    ) -> str:
        """Constrói system prompt especializado para código"""
        lang_info = self.LANGUAGES.get(language, {})

        prompt_parts = [
            f"Você é um programador sênior especializado em {language}.",
            "Gere código limpo, bem estruturado e funcional.",
            "",
            "Diretrizes:",
            f"- Use boas práticas de {language}",
            "- Inclua comentários apenas onde necessário",
            "- Trate erros de forma apropriada",
            "- Use nomes descritivos para variáveis e funções",
        ]

        # Adicionar regras específicas por linguagem
        if language == 'python':
            prompt_parts.extend([
                "- Use type hints quando apropriado",
                "- Siga PEP 8",
                "- Prefira list comprehensions quando legíveis",
            ])
        elif language in ['javascript', 'typescript']:
            prompt_parts.extend([
                "- Use const/let, nunca var",
                "- Use arrow functions quando apropriado",
                "- Prefira async/await sobre callbacks",
            ])
        elif language == 'cpp':
            prompt_parts.extend([
                "- Cada #include em linha separada",
                "- Membros de classe devem ter nomes",
                "- Verificar divisão por zero",
                "- Usar smart pointers quando possível",
                "- Evitar memory leaks",
            ])

        # Adicionar features solicitadas
        if 'async' in requirements.get('features', []):
            prompt_parts.append("- Use padrões assíncronos")
        if 'error_handling' in requirements.get('features', []):
            prompt_parts.append("- Implemente tratamento de erros robusto")
        if 'documentation' in requirements.get('features', []):
            prompt_parts.append("- Inclua documentação/docstrings")

        # Constraints
        if 'keep_simple' in requirements.get('constraints', []):
            prompt_parts.append("- Mantenha o código simples e direto")
        if 'optimize' in requirements.get('constraints', []):
            prompt_parts.append("- Otimize para performance")

        prompt_parts.extend([
            "",
            "Formato de resposta:",
            "- Forneça o código em um bloco ```",
            "- Explique brevemente o que o código faz",
            "- Mencione dependências necessárias (se houver)",
        ])

        return "\n".join(prompt_parts)

    def _clean_user_input(self, text: str) -> str:
        """Limpa input do usuário"""
        # Remover prefixos comuns
        prefixes = ['[modo código]', '[code]', 'crie', 'escreva', 'implemente']
        text_clean = text

        for prefix in prefixes:
            if text_clean.lower().startswith(prefix):
                text_clean = text_clean[len(prefix):].strip()

        return text_clean


class CodeExplainerSkill(Skill):
    """Explica código existente"""

    name = "code_explainer"
    description = "Explica código, identifica problemas e sugere melhorias"
    version = "1.0.0"
    skill_type = SkillType.MODEL_REQUIRED
    priority = SkillPriority.NORMAL
    preferred_capability = "code_strong"
    tags = ['explicar', 'código', 'entender', 'review']

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'explique', 'explicar', 'o que faz', 'como funciona',
                'review', 'analise', 'esse código', 'este código'
            ],
            patterns=[
                r'(?:explique|analise)\s+(?:esse?|este?)\s+código',
                r'o que\s+(?:esse?|este?)\s+código\s+faz',
                r'como\s+(?:esse?|este?)\s+(?:código|função)\s+funciona',
            ],
            intents=['QUESTION_TECHNICAL'],
            min_confidence=0.5
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Prepara explicação de código"""
        # Extrair código
        code = self._extract_code(user_input)

        if not code:
            return skill_error(
                "Não encontrei código para explicar. "
                "Cole o código diretamente ou use blocos ```."
            )

        # Detectar linguagem
        language = self._detect_language(code)

        # Construir prompt
        prompt = f"""Explique este código {language} de forma clara e didática:

```{language}
{code}
```

Inclua:
1. O que o código faz (visão geral)
2. Explicação linha a linha das partes importantes
3. Possíveis melhorias ou problemas
4. Complexidade (se relevante)

Seja conciso mas completo."""

        return SkillResult(
            success=True,
            output=None,
            needs_model=True,
            model_prompt=prompt,
            metadata={
                'language': language,
                'code_length': len(code),
                'task_type': 'code_explanation'
            }
        )

    def _extract_code(self, text: str) -> Optional[str]:
        """Extrai código do texto"""
        # Bloco de código markdown
        match = re.search(r'```(?:\w+)?\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Se tem indentação típica de código
        lines = text.split('\n')
        code_lines = [l for l in lines if l.startswith('    ') or l.startswith('\t')]
        if len(code_lines) > 2:
            return '\n'.join(code_lines)

        # Se parece código (tem keywords)
        code_indicators = ['def ', 'class ', 'function ', 'const ', 'import ', 'from ']
        if any(ind in text for ind in code_indicators):
            return text

        return None

    def _detect_language(self, code: str) -> str:
        """Detecta linguagem do código"""
        patterns = {
            'python': [r'\bdef\s+\w+\s*\(', r'\bimport\s+\w+', r':\s*$'],
            'javascript': [r'\bfunction\s+\w+', r'\bconst\s+\w+\s*=', r'=>'],
            'typescript': [r':\s*\w+\s*[=\)]', r'\binterface\s+\w+'],
            'java': [r'\bpublic\s+class', r'\bprivate\s+\w+', r'\bvoid\s+\w+'],
            'cpp': [r'#include\s*<', r'::\w+', r'\bstd::'],
            'rust': [r'\bfn\s+\w+', r'\blet\s+mut', r'\bimpl\s+\w+'],
            'go': [r'\bfunc\s+\w+', r'\bpackage\s+\w+', r':='],
        }

        for lang, patterns_list in patterns.items():
            matches = sum(1 for p in patterns_list if re.search(p, code))
            if matches >= 2:
                return lang

        return 'unknown'
