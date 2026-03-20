# skills/builtin/file_operations.py
"""
Skill de operações de arquivo.
PURE - não precisa de modelo.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import os
import shutil
import re

from ..base import (
    Skill, SkillType, SkillTrigger, SkillResult, SkillPriority,
    skill_success, skill_error
)


class FileOperationsSkill(Skill):
    """Operações de arquivo sem usar modelo"""

    name = "file_operations"
    description = "Operações de arquivo: listar, mover, copiar, renomear, info"
    version = "1.0.0"
    skill_type = SkillType.PURE  # Nunca precisa de modelo
    priority = SkillPriority.HIGH
    tags = ['arquivo', 'pasta', 'diretório', 'file', 'folder']

    def _build_trigger(self) -> SkillTrigger:
        return SkillTrigger(
            keywords=[
                'listar', 'liste', 'mostrar', 'mostre', 'ver',
                'mover', 'mova', 'copiar', 'copie',
                'renomear', 'renomeie', 'deletar', 'delete', 'apagar',
                'criar pasta', 'nova pasta', 'mkdir',
                'tamanho', 'info', 'informação',
                'arquivos', 'pastas', 'diretório'
            ],
            patterns=[
                r'(liste|mostre|veja)\s+(os\s+)?(arquivos|pastas)',
                r'(mova|copie|renomeie|delete)\s+',
                r'crie\s+(uma\s+)?pasta',
                r'(tamanho|info)\s+(do|da|de)\s+',
                r'quantos\s+arquivos',
            ],
            intents=['TASK_FILE', 'COMMAND'],
            min_confidence=0.5
        )

    def execute(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> SkillResult:
        """Executa operação de arquivo"""
        text_lower = user_input.lower()

        # Detectar operação
        if any(kw in text_lower for kw in ['listar', 'liste', 'mostrar', 'mostre', 'arquivos', 'pastas']):
            return self._list_files(user_input, context)

        elif any(kw in text_lower for kw in ['mover', 'mova']):
            return self._move_file(user_input, context)

        elif any(kw in text_lower for kw in ['copiar', 'copie']):
            return self._copy_file(user_input, context)

        elif any(kw in text_lower for kw in ['renomear', 'renomeie']):
            return self._rename_file(user_input, context)

        elif any(kw in text_lower for kw in ['criar pasta', 'nova pasta', 'mkdir']):
            return self._create_folder(user_input, context)

        elif any(kw in text_lower for kw in ['tamanho', 'info', 'informação']):
            return self._file_info(user_input, context)

        elif any(kw in text_lower for kw in ['deletar', 'delete', 'apagar']):
            return skill_error("Operação de delete desabilitada por segurança. Use o sistema operacional.")

        return skill_error("Não entendi a operação de arquivo solicitada.")

    def _list_files(self, user_input: str, context: Dict) -> SkillResult:
        """Lista arquivos em um diretório"""
        path = self._extract_path(user_input) or '.'

        try:
            p = Path(path).resolve()

            if not p.exists():
                return skill_error(f"Caminho não encontrado: {path}")

            if not p.is_dir():
                return skill_error(f"Não é um diretório: {path}")

            items = []
            total_size = 0
            file_count = 0
            dir_count = 0

            for item in sorted(p.iterdir()):
                try:
                    if item.is_dir():
                        icon = "📁"
                        size_str = ""
                        dir_count += 1
                    else:
                        icon = self._get_file_icon(item.suffix)
                        size = item.stat().st_size
                        size_str = f" ({self._format_size(size)})"
                        total_size += size
                        file_count += 1

                    items.append(f"{icon} {item.name}{size_str}")
                except (PermissionError, OSError):
                    items.append(f"⚠️ {item.name} (sem acesso)")

            # Limitar output
            if len(items) > 50:
                items = items[:50]
                items.append(f"... e mais {len(list(p.iterdir())) - 50} itens")

            header = f"📂 {p}\n"
            header += f"📊 {file_count} arquivos, {dir_count} pastas"
            if total_size > 0:
                header += f", {self._format_size(total_size)} total"

            output = header + "\n\n" + "\n".join(items)

            return skill_success(
                output,
                path=str(p),
                file_count=file_count,
                dir_count=dir_count,
                total_size=total_size
            )

        except PermissionError:
            return skill_error(f"Sem permissão para acessar: {path}")
        except Exception as e:
            return skill_error(f"Erro ao listar: {str(e)}")

    def _move_file(self, user_input: str, context: Dict) -> SkillResult:
        """Move arquivo ou pasta"""
        paths = self._extract_two_paths(user_input)
        if not paths:
            return skill_error("Não consegui identificar origem e destino. Use: mova [origem] para [destino]")

        source, dest = paths

        try:
            source_path = Path(source).resolve()
            dest_path = Path(dest).resolve()

            if not source_path.exists():
                return skill_error(f"Origem não encontrada: {source}")

            shutil.move(str(source_path), str(dest_path))

            return skill_success(
                f"✅ Movido:\n  {source_path}\n  → {dest_path}",
                source=str(source_path),
                destination=str(dest_path)
            )

        except Exception as e:
            return skill_error(f"Erro ao mover: {str(e)}")

    def _copy_file(self, user_input: str, context: Dict) -> SkillResult:
        """Copia arquivo ou pasta"""
        paths = self._extract_two_paths(user_input)
        if not paths:
            return skill_error("Não consegui identificar origem e destino. Use: copie [origem] para [destino]")

        source, dest = paths

        try:
            source_path = Path(source).resolve()
            dest_path = Path(dest).resolve()

            if not source_path.exists():
                return skill_error(f"Origem não encontrada: {source}")

            if source_path.is_dir():
                shutil.copytree(str(source_path), str(dest_path))
            else:
                shutil.copy2(str(source_path), str(dest_path))

            return skill_success(
                f"✅ Copiado:\n  {source_path}\n  → {dest_path}",
                source=str(source_path),
                destination=str(dest_path)
            )

        except Exception as e:
            return skill_error(f"Erro ao copiar: {str(e)}")

    def _rename_file(self, user_input: str, context: Dict) -> SkillResult:
        """Renomeia arquivo ou pasta"""
        paths = self._extract_two_paths(user_input)
        if not paths:
            return skill_error("Não consegui identificar nome atual e novo nome. Use: renomeie [atual] para [novo]")

        old_name, new_name = paths

        try:
            old_path = Path(old_name).resolve()

            if not old_path.exists():
                return skill_error(f"Arquivo não encontrado: {old_name}")

            # Novo caminho no mesmo diretório
            new_path = old_path.parent / new_name

            old_path.rename(new_path)

            return skill_success(
                f"✅ Renomeado:\n  {old_path.name}\n  → {new_path.name}",
                old_name=str(old_path),
                new_name=str(new_path)
            )

        except Exception as e:
            return skill_error(f"Erro ao renomear: {str(e)}")

    def _create_folder(self, user_input: str, context: Dict) -> SkillResult:
        """Cria uma nova pasta"""
        path = self._extract_path(user_input)
        if not path:
            return skill_error("Especifique o nome ou caminho da pasta.")

        try:
            folder_path = Path(path).resolve()

            if folder_path.exists():
                return skill_error(f"Já existe: {folder_path}")

            folder_path.mkdir(parents=True, exist_ok=True)

            return skill_success(
                f"✅ Pasta criada: {folder_path}",
                path=str(folder_path)
            )

        except Exception as e:
            return skill_error(f"Erro ao criar pasta: {str(e)}")

    def _file_info(self, user_input: str, context: Dict) -> SkillResult:
        """Mostra informações de arquivo/pasta"""
        path = self._extract_path(user_input)
        if not path:
            return skill_error("Especifique o arquivo ou pasta.")

        try:
            p = Path(path).resolve()

            if not p.exists():
                return skill_error(f"Não encontrado: {path}")

            stat = p.stat()

            info_lines = [
                f"📄 **{p.name}**",
                f"📍 Caminho: {p}",
                f"📦 Tipo: {'Diretório' if p.is_dir() else 'Arquivo'}",
            ]

            if p.is_file():
                info_lines.append(f"📊 Tamanho: {self._format_size(stat.st_size)}")
                info_lines.append(f"📝 Extensão: {p.suffix or 'nenhuma'}")

            from datetime import datetime
            modified = datetime.fromtimestamp(stat.st_mtime)
            info_lines.append(f"🕐 Modificado: {modified.strftime('%d/%m/%Y %H:%M')}")

            if p.is_dir():
                # Contar itens
                items = list(p.iterdir())
                files = sum(1 for i in items if i.is_file())
                dirs = sum(1 for i in items if i.is_dir())
                info_lines.append(f"📁 Conteúdo: {files} arquivos, {dirs} pastas")

            return skill_success(
                "\n".join(info_lines),
                path=str(p),
                size=stat.st_size if p.is_file() else None,
                is_dir=p.is_dir()
            )

        except Exception as e:
            return skill_error(f"Erro ao obter info: {str(e)}")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _extract_path(self, text: str) -> Optional[str]:
        """Extrai caminho do texto"""
        # Padrões de caminho
        patterns = [
            r'"([^"]+)"',                    # Entre aspas
            r"'([^']+)'",                    # Entre aspas simples
            r'`([^`]+)`',                    # Entre crases
            r'[A-Za-z]:\\[^\s]+',            # Windows absolute
            r'/[^\s]+',                      # Unix absolute
            r'\./[^\s]+',                    # Relative ./
            r'\.\.\/[^\s]+',                 # Relative ../
            r'[\w\-\.]+/[\w\-\./]+',         # path/to/something
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return None

    def _extract_two_paths(self, text: str) -> Optional[tuple]:
        """Extrai dois caminhos (origem e destino)"""
        # Tentar padrão "X para Y"
        match = re.search(
            r'(?:mova|copie|renomeie)\s+(.+?)\s+(?:para|pra|->|=>)\s+(.+?)(?:\s|$)',
            text.lower()
        )

        if match:
            source = match.group(1).strip().strip('"\'`')
            dest = match.group(2).strip().strip('"\'`')
            return (source, dest)

        # Tentar extrair dois caminhos quaisquer
        paths = []
        patterns = [r'"([^"]+)"', r"'([^']+)'", r'`([^`]+)`']

        for pattern in patterns:
            matches = re.findall(pattern, text)
            paths.extend(matches)

        if len(paths) >= 2:
            return (paths[0], paths[1])

        return None

    def _format_size(self, size: int) -> str:
        """Formata tamanho em bytes para human-readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def _get_file_icon(self, extension: str) -> str:
        """Retorna emoji baseado na extensão"""
        icons = {
            '.py': '🐍',
            '.js': '📜',
            '.ts': '📘',
            '.html': '🌐',
            '.css': '🎨',
            '.json': '📋',
            '.md': '📝',
            '.txt': '📄',
            '.pdf': '📕',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.png': '🖼️',
            '.gif': '🖼️',
            '.mp3': '🎵',
            '.mp4': '🎬',
            '.zip': '📦',
            '.rar': '📦',
            '.exe': '⚙️',
            '.dll': '⚙️',
        }
        return icons.get(extension.lower(), '📄')
