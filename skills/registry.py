# skills/registry.py
"""
Registry central de Skills.
Gerencia carregamento, busca e execução de skills.
"""

from typing import Dict, List, Optional, Type
from pathlib import Path
import importlib
import importlib.util
import sys

from .base import Skill, SkillType, SkillResult, SkillPriority
from core.feature_flags import FLAGS


class SkillRegistry:
    """
    Registro central de skills.
    Gerencia carregamento, busca e execução.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._loaded = False
        self._load_errors: List[str] = []

    # =========================================================================
    # CARREGAMENTO
    # =========================================================================

    def load_builtin(self):
        """Carrega skills built-in"""
        try:
            from .builtin import get_builtin_skills

            for skill_class in get_builtin_skills():
                try:
                    skill = skill_class()
                    self.register(skill)
                except Exception as e:
                    self._load_errors.append(f"Erro ao instanciar {skill_class}: {e}")

        except ImportError as e:
            self._load_errors.append(f"Erro ao importar builtin skills: {e}")

        self._loaded = True

    def load_custom(self, custom_path: str = 'skills/custom'):
        """
        Carrega skills customizadas de um diretório.
        Cada arquivo .py pode conter uma ou mais classes Skill.
        """
        custom_dir = Path(custom_path)
        if not custom_dir.exists():
            return

        for py_file in custom_dir.glob('*.py'):
            if py_file.name.startswith('_'):
                continue

            try:
                # Carregar módulo dinamicamente
                spec = importlib.util.spec_from_file_location(
                    f"skills.custom.{py_file.stem}",
                    py_file
                )
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                # Procurar classes que herdam de Skill
                for name in dir(module):
                    obj = getattr(module, name)
                    if (isinstance(obj, type) and
                        issubclass(obj, Skill) and
                        obj is not Skill and
                        not name.startswith('_')):
                        try:
                            skill = obj()
                            self.register(skill)
                            if FLAGS.DEBUG_SKILL_SELECTION:
                                print(f"[SkillRegistry] Carregada custom skill: {skill.name}")
                        except Exception as e:
                            self._load_errors.append(f"Erro ao instanciar {name}: {e}")

            except Exception as e:
                self._load_errors.append(f"Erro ao carregar {py_file}: {e}")

    def load_all(self):
        """Carrega todas as skills (builtin + custom)"""
        self.load_builtin()
        self.load_custom()

    # =========================================================================
    # REGISTRO
    # =========================================================================

    def register(self, skill: Skill) -> bool:
        """
        Registra uma skill.
        Retorna True se registrada com sucesso.
        """
        if skill.name in self._skills:
            if FLAGS.DEBUG_SKILL_SELECTION:
                print(f"[SkillRegistry] Skill já registrada: {skill.name}")
            return False

        self._skills[skill.name] = skill
        skill.on_load()

        if FLAGS.DEBUG_SKILL_SELECTION:
            print(f"[SkillRegistry] Registrada: {skill.name} ({skill.skill_type.value})")

        return True

    def unregister(self, name: str) -> bool:
        """Remove uma skill do registro"""
        if name not in self._skills:
            return False

        skill = self._skills[name]
        skill.on_unload()
        del self._skills[name]
        return True

    # =========================================================================
    # BUSCA
    # =========================================================================

    def get(self, name: str) -> Optional[Skill]:
        """Obtém skill por nome"""
        return self._skills.get(name)

    def get_by_type(self, skill_type: SkillType) -> List[Skill]:
        """Retorna skills de um tipo específico"""
        return [
            s for s in self._skills.values()
            if s.skill_type == skill_type
        ]

    def find_pure_skill(
        self,
        user_input: str,
        intent: str = None
    ) -> Optional[str]:
        """
        Encontra skill PURA (sem modelo) que pode lidar com a entrada.
        Prioriza skills puras para economizar chamadas de modelo.
        """
        return self._find_skill_by_type(
            user_input, intent, SkillType.PURE
        )

    def find_optional_skill(
        self,
        user_input: str,
        intent: str = None
    ) -> Optional[str]:
        """
        Encontra skill MODEL_OPTIONAL que pode lidar com a entrada.
        """
        return self._find_skill_by_type(
            user_input, intent, SkillType.MODEL_OPTIONAL
        )

    def find_model_skill(
        self,
        user_input: str,
        intent: str = None
    ) -> Optional[str]:
        """
        Encontra skill MODEL_REQUIRED que pode lidar com a entrada.
        """
        return self._find_skill_by_type(
            user_input, intent, SkillType.MODEL_REQUIRED
        )

    def _find_skill_by_type(
        self,
        user_input: str,
        intent: str,
        skill_type: SkillType
    ) -> Optional[str]:
        """Encontra skill de um tipo específico"""
        best_skill = None
        best_score = 0.0

        for skill in self._skills.values():
            if skill.skill_type != skill_type:
                continue

            score = skill.matches(user_input, intent)

            # Ajustar por prioridade
            priority_boost = {
                SkillPriority.CRITICAL: 0.2,
                SkillPriority.HIGH: 0.1,
                SkillPriority.NORMAL: 0.0,
                SkillPriority.LOW: -0.1
            }
            score += priority_boost.get(skill.priority, 0)

            if score > best_score and score >= skill.trigger.min_confidence:
                best_score = score
                best_skill = skill

        return best_skill.name if best_skill else None

    def find_best_match(
        self,
        user_input: str,
        intent: str = None
    ) -> Optional[Skill]:
        """
        Encontra a skill mais adequada para a entrada.
        Prioriza: PURE > MODEL_OPTIONAL > MODEL_REQUIRED
        """
        # 1. Tentar skill pura
        pure_name = self.find_pure_skill(user_input, intent)
        if pure_name:
            return self._skills[pure_name]

        # 2. Tentar skill opcional
        optional_name = self.find_optional_skill(user_input, intent)
        if optional_name:
            return self._skills[optional_name]

        # 3. Tentar skill que requer modelo
        model_name = self.find_model_skill(user_input, intent)
        if model_name:
            return self._skills[model_name]

        return None

    def find_by_tags(self, tags: List[str]) -> List[Skill]:
        """Encontra skills por tags"""
        result = []
        for skill in self._skills.values():
            if any(tag in skill.tags for tag in tags):
                result.append(skill)
        return result

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def execute_skill(
        self,
        name: str,
        user_input: str,
        context: Dict
    ) -> Optional[SkillResult]:
        """
        Executa uma skill pelo nome.
        Retorna None se skill não encontrada.
        """
        skill = self.get(name)
        if not skill:
            return None

        try:
            # Hook antes
            skill.on_before_execute(user_input, context)

            # Executar
            result = skill.execute(user_input, context)

            # Hook depois
            skill.on_after_execute(result)

            return result

        except Exception as e:
            return SkillResult(
                success=False,
                output=None,
                error=f"Erro ao executar skill {name}: {str(e)}"
            )

    # =========================================================================
    # LISTAGEM E INFO
    # =========================================================================

    def list_skills(self) -> List[Dict]:
        """Lista todas as skills registradas"""
        return [skill.get_info() for skill in self._skills.values()]

    def list_by_type(self) -> Dict[str, List[str]]:
        """Agrupa skills por tipo"""
        result = {
            'pure': [],
            'model_optional': [],
            'model_required': []
        }

        for skill in self._skills.values():
            type_key = skill.skill_type.value
            result[type_key].append(skill.name)

        return result

    def get_stats(self) -> Dict:
        """Retorna estatísticas do registry"""
        by_type = self.list_by_type()
        return {
            'total': len(self._skills),
            'pure': len(by_type['pure']),
            'model_optional': len(by_type['model_optional']),
            'model_required': len(by_type['model_required']),
            'load_errors': len(self._load_errors),
            'loaded': self._loaded
        }

    def get_load_errors(self) -> List[str]:
        """Retorna erros de carregamento"""
        return self._load_errors.copy()

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __iter__(self):
        return iter(self._skills.values())
