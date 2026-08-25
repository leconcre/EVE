# tests/test_web_features.py
"""
Testes das funcionalidades novas da interface web (jul/2026):
- Cancelamento de geração (GenerationAborted não pode ser engolida)
- Regeneração (forget_last_exchange / forget_cached_response)
- Renomear e buscar conversas (endpoints do eve_web)
- Convenção "groq:<id>" no roteamento local
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.errors import GenerationAborted
from memory.layered_memory import LayeredMemory


class TestForgetLastExchange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = LayeredMemory(
            persistence_path=str(Path(self.tmp.name) / "mem.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_forget_remove_curto_prazo_e_cache(self):
        self.mem.add_exchange("qual a capital do brasil?", "Brasília.")
        self.assertEqual(len(self.mem.short_term), 1)

        # garante uma entrada de cache para o prompt (independente da
        # política de cacheabilidade do add_exchange)
        key = self.mem._normalize_for_cache("qual a capital do brasil?")
        self.mem.response_cache[key] = ("Brasília.", datetime.now())

        self.mem.forget_last_exchange("qual a capital do brasil?")
        self.assertEqual(len(self.mem.short_term), 0)
        self.assertNotIn(key, self.mem.response_cache)

    def test_forget_com_memoria_vazia_nao_quebra(self):
        self.mem.forget_last_exchange("nada")  # não deve lançar
        self.assertEqual(len(self.mem.short_term), 0)

    def test_forget_cached_response_nao_toca_curto_prazo(self):
        self.mem.add_exchange("oi", "olá!")
        key = self.mem._normalize_for_cache("oi")
        self.mem.response_cache[key] = ("olá!", datetime.now())

        self.mem.forget_cached_response("oi")
        self.assertNotIn(key, self.mem.response_cache)
        self.assertEqual(len(self.mem.short_term), 1)


class TestGenerationAbortedNoStream(unittest.TestCase):
    """O callback lançando GenerationAborted deve INTERROMPER o stream
    do Ollama (a exceção não pode ser engolida como erro comum)."""

    def _mock_response(self, lines):
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status = MagicMock()
        resp.iter_lines = MagicMock(return_value=iter(lines))
        return resp

    def test_aborto_interrompe_stream(self):
        from core import router

        lines = [
            json.dumps({"response": "olá ", "done": False}),
            json.dumps({"response": "mundo", "done": False}),
            json.dumps({"response": "!", "done": True}),
        ]
        chunks = []

        def cb(chunk):
            chunks.append(chunk)
            if len(chunks) >= 2:
                raise GenerationAborted()

        with patch.object(router.requests, "post",
                          return_value=self._mock_response(lines)):
            with self.assertRaises(GenerationAborted):
                router._ollama_stream("http://x/api/generate", {"model": "m"},
                                      {}, 10, cb)
        self.assertEqual(chunks, ["olá ", "mundo"])

    def test_erro_comum_do_callback_nao_derruba(self):
        from core import router

        lines = [
            json.dumps({"response": "abc", "done": False}),
            json.dumps({"response": "def", "done": True}),
        ]

        def cb(chunk):
            raise ValueError("bug da UI")

        with patch.object(router.requests, "post",
                          return_value=self._mock_response(lines)):
            out = router._ollama_stream("http://x/api/generate", {"model": "m"},
                                        {}, 10, cb)
        self.assertEqual(out["response"], "abcdef")


class TestGroqPrefixNoRouterLocal(unittest.TestCase):
    """'groq' e 'groq:<id>' nunca podem chegar como modelo explícito
    do router local (viraria chamada Ollama para um modelo inexistente)."""

    def test_resolve_model_rejeita_groq_puro(self):
        from core.router import resolve_model
        backend, model_id = resolve_model("escreva um poema", "groq")
        self.assertNotEqual(model_id, "groq")


class TestEndpointsDeChats(unittest.TestCase):
    def setUp(self):
        import eve_web
        self.eve_web = eve_web
        self.tmp = tempfile.TemporaryDirectory()
        self.chats_file = Path(self.tmp.name) / "chats.json"
        self.chats_file.write_text(json.dumps({
            "c1": {"title": "Receita de bolo",
                   "timestamp": "2026-07-10 10:00:00",
                   "messages": [
                       {"role": "user", "content": "como faço bolo de fubá?"},
                       {"role": "assistant", "content": "Misture fubá..."}]},
            "c2": {"title": "Python",
                   "timestamp": "2026-07-09 09:00:00",
                   "messages": [
                       {"role": "user", "content": "loop assíncrono"},
                       {"role": "assistant", "content": "Use asyncio..."}]},
        }, ensure_ascii=False), encoding="utf-8")
        self._orig = eve_web.CHATS_FILE
        eve_web.CHATS_FILE = self.chats_file

    def tearDown(self):
        self.eve_web.CHATS_FILE = self._orig
        self.tmp.cleanup()

    def test_busca_por_titulo_e_conteudo(self):
        r = self.eve_web.list_chats(q="fubá")
        self.assertEqual([c["id"] for c in r["chats"]], ["c1"])
        r = self.eve_web.list_chats(q="asyncio")
        self.assertEqual([c["id"] for c in r["chats"]], ["c2"])
        r = self.eve_web.list_chats(q=None)
        self.assertEqual(len(r["chats"]), 2)

    def test_preview_presente(self):
        r = self.eve_web.list_chats()
        self.assertTrue(all("preview" in c for c in r["chats"]))
        self.assertIn("Misture", r["chats"][0]["preview"])

    def test_renomear(self):
        req = self.eve_web.RenameRequest(title="  Bolo de fubá da vovó  ")
        out = self.eve_web.rename_chat("c1", req)
        self.assertEqual(out["title"], "Bolo de fubá da vovó")
        data = json.loads(self.chats_file.read_text(encoding="utf-8"))
        self.assertEqual(data["c1"]["title"], "Bolo de fubá da vovó")

    def test_renomear_vazio_da_400(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            self.eve_web.rename_chat("c1", self.eve_web.RenameRequest(title="  "))

    def test_renomear_chat_inexistente_da_404(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            self.eve_web.rename_chat("nao-existe",
                                     self.eve_web.RenameRequest(title="x"))


class TestValidacaoDeModelo(unittest.TestCase):
    def setUp(self):
        import eve_web
        self.eve_web = eve_web

    def test_auto_groq_e_none_passam_sem_consultar_ollama(self):
        # nenhum destes deve levantar (nem chamar a rede)
        with patch.object(self.eve_web, "_ollama_tags") as tags:
            self.eve_web._validate_model_choice(None)
            self.eve_web._validate_model_choice("auto")
            self.eve_web._validate_model_choice("groq:openai/gpt-oss-120b")
            tags.assert_not_called()

    def test_modelo_local_inexistente_da_400(self):
        from fastapi import HTTPException
        with patch.object(self.eve_web, "_ollama_tags",
                          return_value=[{"name": "qwen3.5:9b"}]):
            with self.assertRaises(HTTPException):
                self.eve_web._validate_model_choice("modelo-fantasma:1b")

    def test_modelo_local_instalado_passa(self):
        with patch.object(self.eve_web, "_ollama_tags",
                          return_value=[{"name": "qwen3.5:9b"}]):
            self.eve_web._validate_model_choice("qwen3.5:9b")

    def test_ollama_fora_e_permissivo(self):
        with patch.object(self.eve_web, "_ollama_tags", return_value=None):
            self.eve_web._validate_model_choice("qualquer:1b")


if __name__ == "__main__":
    unittest.main()
