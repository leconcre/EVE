# tests/test_new_features.py
"""
Testes das novas funcionalidades (julho/2026):
- Chat V2 via Groq com fallback local
- Streaming do Ollama (parse NDJSON com callback)
- system_prompt no OllamaEngine
- Política de cache com prefixo de falante do Discord

Rodar da raiz do projeto:
    python -m unittest tests.test_new_features -v
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache_policy import is_cacheable_prompt


# ─── Fakes ────────────────────────────────────────────────────────────

class FakeGroq:
    """Groq engine falso que devolve resposta fixa e conta chamadas."""
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        return self.response


class FakeRouter:
    """Router local falso."""
    def __init__(self):
        self.calls = 0

    def resolve_model(self, prompt, explicit=None):
        return ("ollama", "llama3.1:8b")

    def generate(self, prompt, explicit_model=None, max_tokens=512,
                 temperature=0.7, return_raw=False, stream_callback=None):
        self.calls += 1
        if stream_callback:
            stream_callback("resposta ")
            stream_callback("local")
        return {"text": "resposta local", "artifacts": None}


class FakeDecision:
    """BrainDecision mínimo para _generate_with_model."""
    def __init__(self, capability='chat_fast'):
        self.metadata = {}
        self.selected_capability = capability


def make_eve(groq_response=None):
    """Eve mínima sem rodar o __init__ pesado."""
    from core.eve import Eve
    e = Eve.__new__(Eve)
    e.spell_checker = None
    e.groq_engine = FakeGroq(groq_response) if groq_response is not None else None
    e.router = FakeRouter()
    e.model_executor = None
    e.personality = "PERSONA"
    return e


# ─── Testes ───────────────────────────────────────────────────────────

class TestV2GroqChatFallback(unittest.TestCase):
    """Chat no fluxo V2: Groq primeiro, fallback para o modelo local."""

    def test_groq_ok_e_usado_para_chat(self):
        eve = make_eve(groq_response="Oi! Tudo ótimo por aqui ✨")
        result = eve._generate_with_model(
            prompt="oi", decision=FakeDecision(), context={},
            model_choice=None, max_tokens=100, temperature=0.7
        )
        self.assertEqual(result["model_used"], "groq")
        self.assertEqual(eve.groq_engine.calls, 1)
        self.assertEqual(eve.router.calls, 0)

    def test_groq_com_erro_cai_no_local(self):
        eve = make_eve(groq_response="[ERRO] Groq rate limit")
        result = eve._generate_with_model(
            prompt="oi", decision=FakeDecision(), context={},
            model_choice=None, max_tokens=100, temperature=0.7
        )
        self.assertTrue(result["model_used"].startswith("ollama"))
        self.assertEqual(result["text"], "resposta local")

    def test_sem_groq_vai_direto_para_local(self):
        eve = make_eve(groq_response=None)  # groq_engine = None
        result = eve._generate_with_model(
            prompt="oi", decision=FakeDecision(), context={},
            model_choice=None, max_tokens=100, temperature=0.7
        )
        self.assertTrue(result["model_used"].startswith("ollama"))

    def test_busca_web_forca_modelo_local(self):
        # Resultados da web são processados pelo modelo local (regra do legado)
        eve = make_eve(groq_response="não deveria ser chamado")
        result = eve._generate_with_model(
            prompt="o que é X?", decision=FakeDecision(),
            context={"web_search": "INFORMAÇÃO ENCONTRADA: ..."},
            model_choice=None, max_tokens=100, temperature=0.7
        )
        self.assertEqual(eve.groq_engine.calls, 0)
        self.assertTrue(result["model_used"].startswith("ollama"))

    def test_modelo_explicito_pula_groq(self):
        eve = make_eve(groq_response="não deveria ser chamado")
        result = eve._generate_with_model(
            prompt="oi", decision=FakeDecision(), context={},
            model_choice="qwen2.5", max_tokens=100, temperature=0.7
        )
        self.assertEqual(eve.groq_engine.calls, 0)
        self.assertTrue(result["model_used"].startswith("ollama"))

    def test_stream_callback_chega_ao_router(self):
        eve = make_eve(groq_response=None)
        chunks = []
        eve._generate_with_model(
            prompt="oi", decision=FakeDecision(), context={},
            model_choice=None, max_tokens=100, temperature=0.7,
            stream_callback=chunks.append
        )
        self.assertEqual("".join(chunks), "resposta local")


class TestOllamaStreaming(unittest.TestCase):
    """Parse do streaming NDJSON do Ollama."""

    def test_stream_acumula_chunks_e_chama_callback(self):
        from core import router as legacy_router

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                yield '{"response": "Olá ", "done": false}'
                yield ''  # linha vazia deve ser ignorada
                yield 'linha-invalida-nao-json'
                yield '{"response": "mundo!", "done": true}'

        chunks = []
        with patch.object(legacy_router.requests, "post",
                          lambda *a, **k: FakeResp()):
            data = legacy_router._ollama_stream(
                "http://fake/api/generate", {"model": "m"}, {}, 10,
                chunks.append
            )

        self.assertEqual(data["response"], "Olá mundo!")
        self.assertTrue(data["done"])
        self.assertEqual(chunks, ["Olá ", "mundo!"])

    def test_callback_com_erro_nao_derruba_geracao(self):
        from core import router as legacy_router

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                yield '{"response": "abc", "done": true}'

        def bad_callback(chunk):
            raise RuntimeError("UI quebrou")

        with patch.object(legacy_router.requests, "post",
                          lambda *a, **k: FakeResp()):
            data = legacy_router._ollama_stream(
                "http://fake/api/generate", {"model": "m"}, {}, 10,
                bad_callback
            )

        self.assertEqual(data["response"], "abc")


class TestOllamaEngineSystemPrompt(unittest.TestCase):
    """OllamaEngine aceita system_prompt (compat com ModelExecutor)."""

    def test_system_prompt_entra_no_payload(self):
        from engines import ollama_engine as mod

        captured = {}

        class FakeResp:
            status_code = 200
            text = '{"response": "ok", "done": true}'

            def raise_for_status(self):
                pass

            def json(self):
                return {"response": "ok", "done": True}

        def fake_post(url, json=None, timeout=None):
            captured["payload"] = json
            return FakeResp()

        engine = mod.OllamaEngine()
        with patch.object(mod.requests, "post", fake_post):
            result = engine.generate(
                model="llama3.1:8b", prompt="oi",
                system_prompt="Você é a EVE."
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["payload"]["system"], "Você é a EVE.")
        self.assertEqual(captured["payload"]["prompt"], "oi")


class TestCachePolicySpeakerPrefix(unittest.TestCase):
    """Prefixo de falante do Discord não pode enganar a política de cache."""

    def test_continuacao_com_prefixo_nao_e_cacheavel(self):
        self.assertFalse(is_cacheable_prompt("[Lucas diz]: sim"))
        self.assertFalse(is_cacheable_prompt("[João diz]: continue"))

    def test_saudacao_com_prefixo_e_cacheavel(self):
        self.assertTrue(is_cacheable_prompt("[Lucas diz]: oi"))

    def test_pergunta_com_prefixo_e_cacheavel(self):
        self.assertTrue(is_cacheable_prompt("[Lucas diz]: o que é fotossíntese?"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
