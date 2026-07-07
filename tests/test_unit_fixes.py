# tests/test_unit_fixes.py
"""
Testes unitários das correções de bugs (julho/2026).

Rodar da raiz do projeto:
    python -m unittest tests.test_unit_fixes -v

Não precisa de rede, Ollama nem chave de API.
"""

import os
import sys
import tempfile
import unittest

# Garante que a raiz do projeto está no path quando rodado direto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache_policy import is_cacheable_prompt


class TestCachePolicy(unittest.TestCase):
    """Respostas contextuais não podem ser cacheadas nem replayadas."""

    def test_saudacoes_sao_cacheaveis(self):
        for prompt in ["oi", "Olá", "bom dia", "tudo bem?", "quem é você?"]:
            self.assertTrue(is_cacheable_prompt(prompt), prompt)

    def test_continuacoes_nao_sao_cacheaveis(self):
        for prompt in ["sim", "não", "ok", "continue", "e depois?",
                       "por que?", "valeu", "entendi", "mais"]:
            self.assertFalse(is_cacheable_prompt(prompt), prompt)

    def test_referencias_ao_contexto_nao_sao_cacheaveis(self):
        for prompt in ["explica isso melhor por favor",
                       "você disse que era rápido, confirma?",
                       "corrige o código que tem um erro"]:
            self.assertFalse(is_cacheable_prompt(prompt), prompt)

    def test_pergunta_independente_e_cacheavel(self):
        self.assertTrue(is_cacheable_prompt("o que é fotossíntese?"))
        self.assertTrue(is_cacheable_prompt("qual a capital da França?"))

    def test_prompt_vazio_nao_e_cacheavel(self):
        self.assertFalse(is_cacheable_prompt(""))
        self.assertFalse(is_cacheable_prompt(None))


class TestSpellChecker(unittest.TestCase):
    """O corretor não pode corromper palavras válidas do português."""

    @classmethod
    def setUpClass(cls):
        from core.spell_checker import EVESpellChecker
        cls.checker = EVESpellChecker()

    def test_esta_pronome_preservado(self):
        # 'esta' (pronome) NÃO pode virar 'está'
        resultado = self.checker.correct_text("esta imagem mostra um mapa")
        self.assertIn("esta imagem", resultado)

    def test_pais_plural_preservado(self):
        # 'pais' (plural de pai) NÃO pode virar 'país'
        resultado = self.checker.correct_text("meus pais moram no interior")
        self.assertIn("meus pais", resultado)

    def test_correcoes_seguras_continuam_funcionando(self):
        # 'nao' e 'voce' não são palavras válidas — corrigir é seguro
        resultado = self.checker.correct_text("nao entendi voce")
        self.assertIn("não", resultado)
        self.assertIn("você", resultado)


class TestCppValidator(unittest.TestCase):
    """Validador C++ sem falsos positivos que regeneram código à toa."""

    @classmethod
    def setUpClass(cls):
        from engines.groq_engine import CppCodeValidator
        cls.validator = CppCodeValidator

    def test_uso_de_constante_nao_e_erro(self):
        code = "int f() {\n    return MAX_HEALTH;\n}\n"
        _, errors = self.validator.validate_and_fix(code)
        self.assertNotIn("Declaração de tipo sem variável", errors)

    def test_declaracao_sem_variavel_e_detectada(self):
        code = "int main() {\nPlayer;\nreturn 0;\n}\n"
        _, errors = self.validator.validate_and_fix(code)
        self.assertIn("Declaração de tipo sem variável", errors)

    def test_includes_na_mesma_linha_preserva_resto(self):
        code = '#include <iostream> #include <vector> int x = 1;\n'
        fixed, errors = self.validator.validate_and_fix(code)
        self.assertIn("#include na mesma linha", errors)
        self.assertIn("#include <iostream>", fixed)
        self.assertIn("#include <vector>", fixed)
        # O código que estava na mesma linha não pode ser descartado
        self.assertIn("int x = 1;", fixed)

    def test_membro_de_classe_sem_nome_e_detectado(self):
        code = "class Hitbox {\npublic:\n    Transform;\n    float radius;\n};\n"
        _, errors = self.validator.validate_and_fix(code)
        self.assertIn("Membros de classe sem nome de variável", errors)


class TestRouter(unittest.TestCase):
    """Roteamento de modelos: groq explícito e visão sem imagem."""

    @classmethod
    def setUpClass(cls):
        from core import router
        cls.router = router

    def test_groq_explicito_nao_quebra(self):
        # "groq" não é servido pelo router local — deve cair no
        # roteamento automático em vez de retornar backend inexistente
        backend, model_id = self.router.resolve_model("olá, tudo bem?", "groq")
        self.assertEqual(backend, "ollama")
        self.assertNotEqual(model_id, "groq")

    def test_texto_sobre_imagem_nao_vai_para_modelo_de_visao(self):
        # Mencionar "imagem" sem anexar imagem não deve rotear para o Qwen-VL
        backend, model_id = self.router.resolve_model(
            "analise esta imagem que descrevi acima"
        )
        self.assertNotIn(model_id, self.router.VISION_MODELS)

    def test_imagem_real_vai_para_modelo_de_visao(self):
        prompt_dict = {"type": "image", "path": "foto.png", "text": "descreva"}
        backend, model_id = self.router.resolve_model(prompt_dict)
        self.assertIn(model_id, self.router.VISION_MODELS)

    def test_modelo_explicito_normal_e_respeitado(self):
        backend, model_id = self.router.resolve_model("oi", "qwen2.5")
        self.assertEqual(model_id, "qwen2.5")


class TestLayeredMemoryCache(unittest.TestCase):
    """Cache da memória em camadas só guarda o que for marcado cacheable."""

    def setUp(self):
        from memory.layered_memory import LayeredMemory
        self.tmpdir = tempfile.mkdtemp()
        self.memory = LayeredMemory(
            persistence_path=os.path.join(self.tmpdir, "mem_test.json")
        )

    def test_resposta_contextual_nao_e_cacheada(self):
        self.memory.add_exchange("sim", "Beleza, vou fazer isso então!",
                                 cacheable=False)
        self.assertIsNone(self.memory.get_cached_response("sim"))

    def test_resposta_independente_e_cacheada(self):
        self.memory.add_exchange("o que é fotossíntese?",
                                 "É o processo de conversão de luz em energia.",
                                 cacheable=True)
        self.assertEqual(
            self.memory.get_cached_response("o que é fotossíntese?"),
            "É o processo de conversão de luz em energia."
        )

    def test_padrao_e_nao_cachear(self):
        self.memory.add_exchange("continue", "Continuando de onde paramos...")
        self.assertIsNone(self.memory.get_cached_response("continue"))


class TestValidateResponse(unittest.TestCase):
    """_validate_response não pode corromper emojis, código ou formatação."""

    @classmethod
    def setUpClass(cls):
        from core.eve import Eve
        # Instância mínima sem inicializar engines (init é pesado/faz rede)
        cls.eve = Eve.__new__(Eve)
        cls.eve.spell_checker = None

    def test_emojis_preservados(self):
        resposta = self.eve._validate_response("Consegui resolver! 🎮✨ Ficou ótimo.")
        self.assertIn("🎮", resposta)
        self.assertIn("✨", resposta)

    def test_bloco_de_codigo_preservado(self):
        code = "Aqui está:\n```python\ndef soma(a, b):\n    return a + b\n```\nPronto!"
        resposta = self.eve._validate_response(code)
        self.assertIn("def soma(a, b):", resposta)
        self.assertIn("    return a + b", resposta)

    def test_quebras_de_linha_preservadas(self):
        texto = "Primeiro parágrafo.\n\nSegundo parágrafo."
        resposta = self.eve._validate_response(texto)
        self.assertIn("\n\n", resposta)

    def test_repeticao_curta_legitima_preservada(self):
        # "dia a dia" não é repetição adjacente; "que que" coloquial tem
        # menos de 4 letras — nada disso pode ser colapsado
        resposta = self.eve._validate_response("No dia a dia isso é que que importa mesmo.")
        self.assertIn("dia a dia", resposta)
        self.assertIn("que que", resposta)

    def test_repeticao_real_removida(self):
        resposta = self.eve._validate_response("Isso ficou muito muito legal de verdade.")
        self.assertNotIn("muito muito", resposta)

    def test_vazamento_de_sistema_bloqueado(self):
        resposta = self.eve._validate_response("PERSONALIDADE CORE: blá blá blá")
        self.assertNotIn("PERSONALIDADE CORE", resposta)


if __name__ == "__main__":
    unittest.main(verbosity=2)
