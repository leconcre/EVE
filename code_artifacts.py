# code_artifacts.py - Sistema de Artefatos de Código v2.0
"""
Sistema de detecção e extração de código das respostas da EVE
Cria artefatos baixáveis automaticamente quando EVE gera código

MELHORIAS v2.0:
- Detecção mais robusta de blocos de código
- Suporte a mais linguagens
- Extração de código mesmo sem markdown
- Limpeza de texto explicativo
"""

import re
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime


def extract_filename_from_code(code: str) -> Optional[str]:
    """
    Tenta extrair um nome de arquivo da primeira linha do código.
    Ex: # filename: main.py
    """
    first_line = code.strip().split('\n')[0]
    # Padrões comuns para nomes de arquivo em comentários
    patterns = [
        r'#\s*filename\s*:\s*([\w\._-]+)',
        r'//\s*filename\s*:\s*([\w\._-]+)',
        r'--\s*filename\s*:\s*([\w\._-]+)',
        r'"""\s*filename\s*:\s*([\w\._-]+)\s*"""',
    ]
    for pattern in patterns:
        match = re.search(pattern, first_line, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

class CodeArtifact:
    """Representa um artefato de código"""
    
    def __init__(self, code: str, language: str, description: str = ""):
        self.code = code.strip()
        self.language = language.lower()
        self.description = description
        self.timestamp = datetime.now()
        self.filename = self._generate_filename()
    
    def _generate_filename(self) -> str:
        """Gera nome de arquivo inteligente"""
        # 1. Tenta extrair do código
        extracted_name = extract_filename_from_code(self.code)
        if extracted_name:
            return extracted_name

        # 2. Usa a descrição (se houver)
        if self.description and len(self.description) > 5:
            # Limpa descrição para nome de arquivo
            clean_desc = re.sub(r'[^\w\s-]', '', self.description.lower())
            clean_desc = re.sub(r'\s+', '_', clean_desc)[:30]
            base_name = clean_desc
        else:
            # 3. Fallback para nome genérico
            base_name = f"code_{self.timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Adiciona extensão
        extensions = {
            'python': '.py', 'javascript': '.js', 'typescript': '.ts', 'java': '.java',
            'cpp': '.cpp', 'c': '.c', 'csharp': '.cs', 'html': '.html', 'css': '.css',
            'sql': '.sql', 'bash': '.sh', 'json': '.json', 'xml': '.xml', 'yaml': '.yaml',
            'markdown': '.md', 'rust': '.rs', 'go': '.go', 'ruby': '.rb', 'php': '.php',
            'swift': '.swift', 'kotlin': '.kt', 'text': '.txt'
        }
        # Mapeia apelidos
        lang_map = {
            'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'c++': 'cpp',
            'c#': 'csharp', 'cs': 'csharp', 'sh': 'bash', 'yml': 'yaml',
            'md': 'markdown', 'rs': 'rust', 'golang': 'go', 'rb': 'ruby', 'kt': 'kotlin'
        }
        normalized_lang = lang_map.get(self.language, self.language)
        ext = extensions.get(normalized_lang, '.txt')
        
        return f"{base_name}{ext}"
    
    def save(self, directory: str = "code_artifacts") -> str:
        """
        Salva o artefato em arquivo
        
        Returns:
            Caminho completo do arquivo salvo
        """
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, self.filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.code)
        
        return filepath
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'code': self.code,
            'language': self.language,
            'description': self.description,
            'filename': self.filename,
            'lines': self.code.count('\n') + 1,
            'size': len(self.code)
        }


class CodeArtifactDetector:
    """Detecta e extrai artefatos de código de texto"""
    
    def __init__(self):
        # Palavras-chave que indicam código por linguagem
        self.language_indicators = {
            'python': ['def ', 'import ', 'from ', 'class ', 'print(', '__init__', 'self.', 'elif ', 'lambda ', 'async def'],
            'javascript': ['function ', 'const ', 'let ', 'var ', '=>', 'console.log', 'document.', 'window.', 'export ', 'import '],
            'typescript': ['interface ', 'type ', ': string', ': number', ': boolean', 'implements ', 'extends '],
            'java': ['public class', 'private ', 'protected ', 'void ', 'System.out', 'public static', '@Override'],
            'cpp': ['#include', 'std::', 'cout', 'cin', 'namespace ', 'template<', '::'],
            'c': ['#include', 'printf(', 'scanf(', 'int main(', 'void ', 'malloc('],
            'html': ['<!DOCTYPE', '<html', '<head', '<body', '<div', '<script', '<style'],
            'css': ['{', '}', ':', ';', 'color:', 'margin:', 'padding:', 'display:', 'flex'],
            'sql': ['SELECT ', 'FROM ', 'WHERE ', 'INSERT ', 'UPDATE ', 'DELETE ', 'CREATE TABLE', 'JOIN '],
            'bash': ['#!/bin/', 'echo ', 'if [', 'then', 'fi', 'done', 'for ', 'while '],
            'json': ['{"', '"}', '":', '[]', 'null', 'true', 'false'],
            'rust': ['fn ', 'let mut', 'impl ', 'pub fn', 'match ', '->'],
            'go': ['func ', 'package ', 'import (', 'type ', 'struct {', 'interface {'],
        }
    
    def detect_code_blocks(self, text: str) -> List[CodeArtifact]:
        """
        Detecta todos os blocos de código no texto

        Returns:
            Lista de CodeArtifacts encontrados
        """
        artifacts = []
        matched_positions = set()  # Rastreia posições já encontradas

        # PADRÃO 1: Blocos markdown com linguagem ```python ... ```
        # Mais flexível: permite ```python\ncode``` ou ```python code```
        pattern_with_lang = r'```(\w+)\s*(.*?)```'
        for match in re.finditer(pattern_with_lang, text, re.DOTALL | re.IGNORECASE):
            language = match.group(1).lower()
            code = match.group(2).strip()

            # Ignora se linguagem é apenas formatação (como bash, sh para comandos)
            if language in ['bash', 'sh', 'shell'] and len(code.split('\n')) <= 2:
                continue

            if self._is_valid_code(code):
                description = self._extract_description(text, match.start())
                artifact = CodeArtifact(code, language, description)
                artifacts.append(artifact)
                matched_positions.add((match.start(), match.end()))

        # PADRÃO 2: Blocos markdown sem linguagem ``` ... ```
        # Procura TODOS os blocos, não só quando não há artefatos
        pattern_no_lang = r'```\s*(.*?)```'
        for match in re.finditer(pattern_no_lang, text, re.DOTALL):
            # Pula se já foi encontrado no padrão 1
            if (match.start(), match.end()) in matched_positions:
                continue

            code = match.group(1).strip()

            if self._is_valid_code(code):
                language = self._detect_language(code)
                description = self._extract_description(text, match.start())
                artifact = CodeArtifact(code, language, description)
                artifacts.append(artifact)
                matched_positions.add((match.start(), match.end()))

        # PADRÃO 3: Código inline com def/class/function (sem markdown)
        # Só executa se nenhum bloco markdown foi encontrado
        if not artifacts:
            # Procura por funções/classes Python
            func_pattern = r'((?:def|class)\s+\w+.*?(?:\n(?:    |\t).*)+)'
            for match in re.finditer(func_pattern, text, re.MULTILINE):
                code = match.group(1).strip()
                if len(code) > 50:
                    artifact = CodeArtifact(code, 'python', 'Código detectado')
                    artifacts.append(artifact)

        return artifacts
    
    def _detect_language(self, code: str) -> str:
        """Detecta linguagem do código por análise heurística"""
        code_sample = code[:1000]  # Analisa primeiros 1000 chars
        
        scores = {}
        for lang, indicators in self.language_indicators.items():
            score = sum(1 for ind in indicators if ind in code_sample)
            if score > 0:
                scores[lang] = score
        
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        # Fallback: verifica estrutura
        if re.search(r'def \w+\(', code):
            return 'python'
        if re.search(r'function \w+\(', code):
            return 'javascript'
        if '{' in code and '}' in code:
            return 'javascript'
        
        return 'text'
    
    def _is_valid_code(self, code: str) -> bool:
        """Verifica se o texto é realmente código (menos restritivo)"""
        if not code or len(code.strip()) < 10:  # Reduzido de 15 para 10
            return False

        # Rejeita textos que são claramente apenas prosa
        # Se mais de 80% das linhas começam com letra maiúscula e terminam com ponto, é prosa
        lines = [l.strip() for l in code.split('\n') if l.strip()]
        if len(lines) > 3:
            prose_lines = sum(1 for l in lines if l and l[0].isupper() and l.endswith('.'))
            if prose_lines / len(lines) > 0.8:
                return False

        # Conta indicadores de código
        indicators = 0

        # Tem indentação consistente?
        if re.search(r'^\s{2,}', code, re.MULTILINE):
            indicators += 1

        # Tem símbolos de programação?
        code_symbols = ['(', ')', '{', '}', '[', ']', '=>', '->', '::', '==', '!=', '+=', '-=', '//', '/*']
        symbol_count = sum(1 for sym in code_symbols if sym in code)
        if symbol_count >= 2:
            indicators += 2

        # Tem palavras-chave de programação?
        keywords = ['def ', 'function ', 'class ', 'import ', 'from ', 'return ', 'if ', 'else', 'for ', 'while ',
                   'const ', 'let ', 'var ', 'async ', 'await ', 'try ', 'catch ', 'throw ', 'new ', 'this.']
        keyword_count = sum(1 for kw in keywords if kw in code)
        if keyword_count >= 1:
            indicators += 2

        # Tem estrutura de bloco (múltiplas linhas)?
        if code.count('\n') >= 1:  # Reduzido de 2 para 1
            indicators += 1

        # Tem imports/includes?
        if re.search(r'(import |from |#include|require\()', code):
            indicators += 2

        # É muito curto mas tem código claro? (como print("Hello"))
        if len(code) < 50:
            # Aceita se tem pelo menos 1 palavra-chave E 1 símbolo
            if keyword_count >= 1 and symbol_count >= 1:
                return True

        # Precisa de menos indicadores agora (2 ao invés de 2)
        return indicators >= 2
    
    def _extract_description(self, full_text: str, code_start_pos: int) -> str:
        """Extrai descrição antes do código"""
        before_text = full_text[max(0, code_start_pos - 200):code_start_pos]
        
        # Remove blocos de código anteriores
        before_text = re.sub(r'```.*?```', '', before_text, flags=re.DOTALL)
        
        # Pega última frase/linha significativa
        lines = [l.strip() for l in before_text.split('\n') if l.strip()]
        
        for line in reversed(lines):
            # Ignora linhas muito curtas ou só pontuação
            if len(line) > 10 and not line.startswith('```'):
                # Limita tamanho e remove acentos para nome de arquivo
                desc = line[:60] + ('...' if len(line) > 60 else '')
                # Normaliza: remove acentos
                import unicodedata
                desc = unicodedata.normalize('NFKD', desc).encode('ASCII', 'ignore').decode('ASCII')
                return desc

        return "code"  # Sem acento


# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════

def extract_and_save_artifacts(response_text: str) -> List[Dict]:
    """
    Extrai artefatos de código e salva em arquivos

    Returns:
        Lista de dicts com informações dos artefatos salvos
    """
    print(f"[ARTIFACTS] Iniciando extração... (texto: {len(response_text)} chars)")
    print(f"[ARTIFACTS] Tem blocos de código? {'```' in response_text}")

    detector = CodeArtifactDetector()
    artifacts = detector.detect_code_blocks(response_text)

    print(f"[ARTIFACTS] Blocos detectados: {len(artifacts)}")

    saved_artifacts = []
    for i, artifact in enumerate(artifacts):
        try:
            print(f"[ARTIFACTS] Salvando artefato {i+1}/{len(artifacts)}")
            print(f"[ARTIFACTS]   Tipo: {type(artifact)}")
            print(f"[ARTIFACTS]   Filename: {artifact.filename}")
            print(f"[ARTIFACTS]   Language: {artifact.language}")

            filepath = artifact.save()
            artifact_dict = {
                'filename': artifact.filename,
                'path': filepath,
                'language': artifact.language,
                'description': artifact.description,
                'lines': artifact.code.count('\n') + 1,
                'size': len(artifact.code),
                'code': artifact.code  # Inclui código para modal
            }

            # VALIDAÇÃO: Confirma que criou um dict válido
            print(f"[ARTIFACTS]   Dict criado com chaves: {artifact_dict.keys()}")
            print(f"[ARTIFACTS]   Tipo do dict: {type(artifact_dict)}")

            saved_artifacts.append(artifact_dict)
            print(f"[OK] Artefato salvo: {filepath}")
        except Exception as e:
            print(f"[ERRO] Erro ao salvar artefato {i}: {e}")
            import traceback
            traceback.print_exc()

    print(f"[ARTIFACTS] Total salvos: {len(saved_artifacts)}")

    # VALIDAÇÃO FINAL antes de retornar
    print(f"[ARTIFACTS] Tipo do retorno: {type(saved_artifacts)}")
    if saved_artifacts:
        print(f"[ARTIFACTS] Tipo do primeiro item: {type(saved_artifacts[0])}")
        if isinstance(saved_artifacts[0], dict):
            print(f"[ARTIFACTS] Chaves do primeiro item: {saved_artifacts[0].keys()}")
        else:
            print(f"[ARTIFACTS] ⚠️ ALERTA: Primeiro item NÃO é dict!")

    return saved_artifacts


def clean_response_from_code(response_text: str) -> str:
    """
    Remove blocos de código do texto de resposta
    Mantém apenas explicação
    
    Returns:
        Texto sem blocos de código
    """
    # Remove blocos ```linguagem ... ```
    cleaned = re.sub(r'```\w*\s*\n.*?```', '', response_text, flags=re.DOTALL)
    
    # Remove blocos ``` ... ```
    cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
    
    # Limpa linhas vazias múltiplas
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # Remove espaços extras
    cleaned = cleaned.strip()
    
    # Se ficou muito curto, retorna mensagem padrão
    if len(cleaned) < 10:
        return "Código gerado com sucesso! Clique no botão abaixo para ver:"
    
    return cleaned


def get_code_icon(language: str) -> str:
    """Retorna emoji apropriado para a linguagem"""
    icons = {
        'python': '🐍',
        'py': '🐍',
        'javascript': '📜',
        'js': '📜',
        'typescript': '📘',
        'ts': '📘',
        'java': '☕',
        'cpp': '⚙️',
        'c++': '⚙️',
        'c': '🔧',
        'csharp': '🎯',
        'cs': '🎯',
        'c#': '🎯',
        'html': '🌐',
        'css': '🎨',
        'sql': '🗄️',
        'bash': '💻',
        'shell': '💻',
        'sh': '💻',
        'json': '📋',
        'rust': '🦀',
        'go': '🐹',
        'ruby': '💎',
        'php': '🐘',
        'swift': '🍎',
        'kotlin': '🎯',
    }
    return icons.get(language.lower(), '📄')


def format_code_info(artifact: Dict) -> str:
    """Formata informações do artefato para exibição"""
    icon = get_code_icon(artifact['language'])
    return f"{icon} {artifact['filename']} • {artifact['language'].upper()} • {artifact['lines']} linhas"


# ═══════════════════════════════════════════════════════════════════
# TESTE
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Teste com código Python
    test_text = """
    Aqui está uma calculadora simples em Python:
    
    ```python
    def calculadora():
        '''Calculadora básica'''
        print("=== CALCULADORA ===")
        
        num1 = float(input("Primeiro número: "))
        num2 = float(input("Segundo número: "))
        op = input("Operação (+, -, *, /): ")
        
        if op == '+':
            resultado = num1 + num2
        elif op == '-':
            resultado = num1 - num2
        elif op == '*':
            resultado = num1 * num2
        elif op == '/':
            resultado = num1 / num2 if num2 != 0 else "Erro: divisão por zero"
        else:
            resultado = "Operação inválida"
        
        print(f"Resultado: {resultado}")
    
    if __name__ == "__main__":
        calculadora()
    ```
    
    Este código cria uma calculadora que aceita dois números e uma operação básica.
    Execute com: python calculadora.py
    """
    
    print("="*60)
    print("TESTE DO SISTEMA DE ARTEFATOS")
    print("="*60 + "\n")
    
    artifacts = extract_and_save_artifacts(test_text)
    
    print(f"\n📦 Artefatos encontrados: {len(artifacts)}")
    for art in artifacts:
        print(f"   - {format_code_info(art)}")
    
    print("\n📝 Texto limpo:")
    clean = clean_response_from_code(test_text)
    print(clean[:200] + "..." if len(clean) > 200 else clean)
    
    print("\n✅ Teste concluído!")