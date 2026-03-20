# skills/builtin/log_analyzer.py
"""
Skill de análise de logs.
MODEL_OPTIONAL - faz análise básica sem modelo, pede modelo para análise profunda.
"""

from typing import Dict, Any, List, Optional
import re
from collections import Counter
from datetime import datetime

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error, skill_needs_model
)


class LogAnalyzerSkill(Skill):
    """Analisador de logs com parsing heurístico"""

    name = "log_analyzer"
    description = "Analisa logs, detecta erros e padrões problemáticos"
    version = "1.0.0"
    skill_type = SkillType.MODEL_OPTIONAL  # Pode usar modelo para análise profunda
    priority = SkillPriority.HIGH
    preferred_capability = "analysis_strong"
    tags = ['log', 'erro', 'debug', 'análise', 'traceback']

    # Padrões de erro conhecidos
    ERROR_PATTERNS = {
        'python_exception': r'(\w+Error|\w+Exception):\s*(.+)',
        'traceback': r'Traceback \(most recent call last\)',
        'generic_error': r'(?:ERROR|ERRO|FATAL|CRITICAL)[:\s]+(.+)',
        'warning': r'(?:WARNING|WARN|AVISO)[:\s]+(.+)',
        'null_reference': r'(?:null|None|undefined|nil)\s+(?:pointer|reference|object)',
        'timeout': r'(?:timeout|timed out|connection refused)',
        'permission': r'(?:permission denied|access denied|unauthorized)',
        'file_not_found': r'(?:file not found|no such file|FileNotFoundError)',
        'connection': r'(?:connection (?:error|failed|refused|reset))',
        'memory': r'(?:out of memory|memory error|heap)',
        'syntax': r'(?:syntax error|unexpected token|parse error)',
    }

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'analise', 'analisar', 'log', 'erro', 'error',
                'traceback', 'exception', 'debug', 'problema',
                'o que significa', 'stack trace'
            ],
            patterns=[
                r'(?:analise|veja)\s+(?:esse?|este?)\s+(?:log|erro)',
                r'(?:o que|qual)\s+(?:é|significa)\s+(?:esse?|este?)\s+erro',
                r'Traceback',
                r'\w+Error:',
            ],
            intents=['TASK_ANALYSIS', 'QUESTION_TECHNICAL'],
            min_confidence=0.5
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Executa análise de log"""
        # Extrair conteúdo do log
        log_content = self._extract_log_content(user_input, context)

        if not log_content:
            return skill_error(
                "Não encontrei log para analisar. "
                "Cole o log diretamente ou indique o arquivo."
            )

        # 1. Análise básica (sem modelo)
        analysis = self._basic_analysis(log_content)

        # 2. Se complexo ou muitos erros, pedir modelo
        if analysis['needs_deep_analysis']:
            prompt = self._build_model_prompt(log_content, analysis)
            return skill_needs_model(
                prompt=prompt,
                partial_output=analysis
            )

        # 3. Retornar análise básica
        return skill_success(
            self._format_analysis(analysis),
            **analysis
        )

    def _extract_log_content(
        self,
        user_input: str,
        context: Dict
    ) -> Optional[str]:
        """Extrai conteúdo do log da entrada ou contexto"""
        # Se tem código/log no input
        if '```' in user_input:
            # Extrair bloco de código
            match = re.search(r'```(?:\w+)?\n?(.*?)```', user_input, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Se parece um log/erro
        if any(p in user_input.lower() for p in ['error', 'traceback', 'exception']):
            return user_input

        # Se tem muitas linhas, provavelmente é um log
        if user_input.count('\n') > 3:
            return user_input

        # Verificar contexto
        if context.get('file_content'):
            return context['file_content']

        return None

    def _basic_analysis(self, log: str) -> Dict[str, Any]:
        """Análise básica de log com regex"""
        lines = log.split('\n')
        total_lines = len(lines)

        # Detectar erros
        errors = []
        warnings = []
        error_types = Counter()

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Erros
            if any(e in line_lower for e in ['error', 'erro', 'exception', 'fatal', 'critical']):
                errors.append({
                    'line': i + 1,
                    'content': line[:200],
                    'type': self._classify_error(line)
                })
                error_types[self._classify_error(line)] += 1

            # Warnings
            elif any(w in line_lower for w in ['warning', 'warn', 'aviso']):
                warnings.append({
                    'line': i + 1,
                    'content': line[:200]
                })

        # Detectar padrões específicos
        patterns_found = self._detect_patterns(log)

        # Extrair stack trace (Python)
        stack_trace = self._extract_stack_trace(log)

        # Calcular complexidade
        complexity = self._calculate_complexity(errors, warnings, patterns_found)

        # Decidir se precisa análise profunda
        needs_deep = (
            len(errors) > 5 or
            complexity > 0.7 or
            len(patterns_found) > 3 or
            stack_trace is not None
        )

        return {
            'total_lines': total_lines,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'errors': errors[:10],  # Limitar
            'warnings': warnings[:5],
            'error_types': dict(error_types.most_common(5)),
            'patterns_found': patterns_found,
            'stack_trace': stack_trace,
            'complexity': complexity,
            'needs_deep_analysis': needs_deep,
            'summary': f"{len(errors)} erros, {len(warnings)} warnings em {total_lines} linhas"
        }

    def _classify_error(self, line: str) -> str:
        """Classifica tipo de erro"""
        line_lower = line.lower()

        if 'timeout' in line_lower:
            return 'timeout'
        if 'connection' in line_lower:
            return 'connection'
        if 'permission' in line_lower or 'denied' in line_lower:
            return 'permission'
        if 'memory' in line_lower or 'heap' in line_lower:
            return 'memory'
        if 'null' in line_lower or 'none' in line_lower or 'undefined' in line_lower:
            return 'null_reference'
        if 'syntax' in line_lower or 'parse' in line_lower:
            return 'syntax'
        if 'not found' in line_lower:
            return 'not_found'

        # Tentar extrair tipo de exceção Python
        match = re.search(r'(\w+Error|\w+Exception)', line)
        if match:
            return match.group(1)

        return 'unknown'

    def _detect_patterns(self, log: str) -> List[Dict]:
        """Detecta padrões problemáticos conhecidos"""
        patterns = []

        for name, pattern in self.ERROR_PATTERNS.items():
            matches = re.findall(pattern, log, re.IGNORECASE | re.MULTILINE)
            if matches:
                patterns.append({
                    'pattern': name,
                    'count': len(matches),
                    'examples': [str(m)[:100] for m in matches[:3]]
                })

        return patterns

    def _extract_stack_trace(self, log: str) -> Optional[Dict]:
        """Extrai e analisa stack trace Python"""
        # Encontrar traceback
        match = re.search(
            r'Traceback \(most recent call last\):(.*?)(\w+Error|\w+Exception):\s*(.+)',
            log,
            re.DOTALL
        )

        if not match:
            return None

        trace_body = match.group(1)
        error_type = match.group(2)
        error_message = match.group(3).strip()

        # Extrair frames
        frames = re.findall(
            r'File "([^"]+)", line (\d+), in (\w+)',
            trace_body
        )

        return {
            'error_type': error_type,
            'error_message': error_message,
            'frames': [
                {'file': f[0], 'line': int(f[1]), 'function': f[2]}
                for f in frames
            ],
            'origin': frames[-1] if frames else None
        }

    def _calculate_complexity(
        self,
        errors: List,
        warnings: List,
        patterns: List
    ) -> float:
        """Calcula complexidade do log (0-1)"""
        score = 0.0

        # Quantidade de erros
        if len(errors) > 10:
            score += 0.3
        elif len(errors) > 5:
            score += 0.2
        elif len(errors) > 0:
            score += 0.1

        # Variedade de tipos
        error_types = set(e.get('type', '') for e in errors)
        score += min(len(error_types) * 0.1, 0.3)

        # Padrões críticos
        critical_patterns = ['memory', 'timeout', 'connection']
        for p in patterns:
            if p['pattern'] in critical_patterns:
                score += 0.15

        return min(score, 1.0)

    def _format_analysis(self, analysis: Dict) -> str:
        """Formata análise para output"""
        lines = ["📋 **Análise de Log**\n"]

        # Resumo
        lines.append(f"📊 {analysis['summary']}")
        lines.append(f"🔍 Complexidade: {analysis['complexity']:.0%}")
        lines.append("")

        # Tipos de erro
        if analysis['error_types']:
            lines.append("**Tipos de erro:**")
            for err_type, count in analysis['error_types'].items():
                lines.append(f"  • {err_type}: {count}x")
            lines.append("")

        # Stack trace
        if analysis['stack_trace']:
            st = analysis['stack_trace']
            lines.append(f"**🔴 {st['error_type']}:** {st['error_message']}")
            if st['origin']:
                origin = st['origin']
                lines.append(f"  📍 Origem: {origin['file']}:{origin['line']} em {origin['function']}")
            lines.append("")

        # Padrões
        if analysis['patterns_found']:
            lines.append("**Padrões detectados:**")
            for p in analysis['patterns_found'][:5]:
                lines.append(f"  ⚠️ {p['pattern']}: {p['count']}x")
            lines.append("")

        # Primeiros erros
        if analysis['errors']:
            lines.append("**Primeiros erros:**")
            for err in analysis['errors'][:3]:
                lines.append(f"  L{err['line']}: {err['content'][:80]}...")

        return "\n".join(lines)

    def _build_model_prompt(self, log: str, analysis: Dict) -> str:
        """Constrói prompt para análise profunda com modelo"""
        prompt = f"""Analise este log em detalhes e forneça:

1. **Causa raiz** mais provável
2. **Padrões problemáticos** identificados
3. **Sugestões de correção** ordenadas por prioridade
4. **Próximos passos** de investigação

Análise preliminar:
- {analysis['error_count']} erros encontrados
- Tipos: {', '.join(analysis['error_types'].keys())}
- Complexidade: {analysis['complexity']:.0%}
{f"- Stack trace de {analysis['stack_trace']['error_type']}" if analysis['stack_trace'] else ""}

Log (últimas linhas relevantes):
```
{log[-3000:]}
```

Forneça análise concisa e acionável."""

        return prompt
