# eve_web.py - Interface web moderna da EVE
"""
Servidor web local da EVE (FastAPI + SSE).

Uso:
    python eve_web.py            # http://127.0.0.1:8765

A interface fica em web/ (HTML/CSS/JS puro, sem CDN — funciona offline).
O motor é o mesmo core.eve.Eve usado pela GUI e pelo terminal:
- Streaming de tokens via Server-Sent Events (Groq e Ollama)
- Gestão de chats persistidos em data/eve_chats.json
- Upload de imagens para o modelo de visão
- Status ao vivo das engines (nuvem/local)
"""

import json
import logging
import os
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

# ─── Preparação do ambiente ANTES de importar o core ─────────────────
# Os caminhos do core (data/, core/personality.txt) são relativos ao CWD.
# No executável (PyInstaller): recursos somente-leitura (web/, personality,
# avatar, ícone) vêm do bundle (_MEIPASS); dados graváveis (data/, logs/)
# e o .env ficam ao lado do EVE.exe.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BUNDLE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    PROJECT_ROOT = Path(sys.executable).parent.resolve()
else:
    BUNDLE_DIR = PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(PROJECT_ROOT)

# Garante que o .env ao lado do exe/projeto seja lido antes do core
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CHATS_FILE = DATA_DIR / "eve_chats.json"
FEATURES_FILE = DATA_DIR / "eve_features.json"
WEB_DIR = BUNDLE_DIR / "web"
PERSONALITY_FILE = BUNDLE_DIR / "core" / "personality.txt"

DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
os.makedirs(PROJECT_ROOT / "logs", exist_ok=True)

# Instalação nova: liga os recursos modernos (Brain V2 = streaming +
# skills + memória em camadas). Configuração existente é respeitada.
if not FEATURES_FILE.exists():
    FEATURES_FILE.write_text(json.dumps({
        "ENABLE_BRAIN_V2": True,
        "ENABLE_LAYERED_MEMORY": True,
        "ENABLE_SKILLS": True,
        "ENABLE_INTERNAL_STATE": True,
        "ENABLE_HEURISTIC_SUMMARY": True,
        "ENABLE_MEMORY_CLEANER": True,
        "ENABLE_CONTEXT_TOOLS": True,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

logging.basicConfig(
    filename="logs/eve_web.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eve.web")

from contextlib import asynccontextmanager

import anyio
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.eve import Eve
from core.errors import GenerationAborted
from core.feature_flags import FLAGS

# ─── Motor ────────────────────────────────────────────────────────────
# Eve NÃO é thread-safe: todo acesso à geração é serializado por este lock.
eve: Eve = None
eve_lock = threading.Lock()

# Chat ativo no servidor (espelha o padrão da GUI: o front gerencia o
# transcript completo; a Eve mantém só a janela de contexto interna).
active_chat_id: str = None

# Gerações em andamento: request_id -> Event de cancelamento.
# Vive FORA do eve_lock: o endpoint de stop não pode esperar a geração.
active_generations: dict = {}
_gen_lock = threading.Lock()

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

# Modelos da nuvem oferecidos no seletor (lineup Groq de produção, jul/2026)
GROQ_MODEL_CHOICES = [
    {"id": "groq:openai/gpt-oss-120b", "label": "GPT-OSS 120B",
     "desc": "Nuvem · chat forte, código e raciocínio", "badge": "nuvem"},
    {"id": "groq:openai/gpt-oss-20b", "label": "GPT-OSS 20B",
     "desc": "Nuvem · o mais rápido", "badge": "nuvem"},
    {"id": "groq:qwen/qwen3.6-27b", "label": "Qwen3.6 27B",
     "desc": "Nuvem · visão e thinking", "badge": "preview"},
]


def _ollama_tags():
    """Modelos instalados no Ollama, ou None se o daemon estiver fora."""
    try:
        base = os.getenv("OLLAMA_BASE", "http://localhost:11434")
        r = requests.get(f"{base}/api/tags", timeout=3)
        if r.status_code == 200:
            return r.json().get("models", [])
    except Exception:
        pass
    return None


def _validate_model_choice(model):
    """Valida o override de modelo do request (HTTP 400 se inválido)."""
    if not model or model == "auto" or model.startswith("groq:"):
        return
    tags = _ollama_tags()
    if tags is None:
        return  # Ollama fora: deixa o erro amigável acontecer na geração
    names = {m.get("name", "") for m in tags}
    if model not in names and f"{model}:latest" not in names:
        raise HTTPException(
            400, f"Modelo local '{model}' não está instalado no Ollama. "
                 f"Instale com: ollama pull {model}")


def _load_chats() -> dict:
    if CHATS_FILE.exists():
        try:
            return json.loads(CHATS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Erro ao ler {CHATS_FILE}: {e}")
    return {}


def _save_chats(chats: dict):
    try:
        CHATS_FILE.write_text(
            json.dumps(chats, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        logger.error(f"Erro ao salvar {CHATS_FILE}: {e}")


def _sync_eve_context(messages: list):
    """Repopula a janela de contexto interna da Eve com um chat carregado."""
    eve.conversation_history = [
        {
            "role": m["role"],
            "content": m["content"],
            "timestamp": m.get("timestamp", ""),
        }
        for m in messages[-10:]
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global eve
    logger.info("Inicializando motor EVE...")
    eve = Eve(personality_file=str(PERSONALITY_FILE),
              memory_file="data/eve_memory.json",
              enable_web_search=True)
    logger.info(f"EVE pronta. Flags ativas: {FLAGS.get_enabled_features()}")
    if not FLAGS.ENABLE_BRAIN_V2:
        logger.warning(
            "ENABLE_BRAIN_V2 desligado em data/eve_features.json — "
            "o streaming de tokens fica indisponível (respostas chegam inteiras)."
        )
    yield
    logger.info("Encerrando: salvando memória e estado...")
    with eve_lock:
        eve.shutdown()


app = FastAPI(title="EVE Web", lifespan=lifespan)


# ─── Modelos de request ───────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = ""
    chat_id: Optional[str] = None
    code_mode: bool = False
    images: list[str] = []
    # None/"auto" = roteamento automático; "groq:<id>" = modelo Groq
    # específico; qualquer outra string = modelo Ollama explícito.
    model: Optional[str] = None
    # Id gerado pelo cliente para permitir cancelar via /api/chat/stop
    request_id: Optional[str] = None


class StopRequest(BaseModel):
    request_id: str


class RegenerateRequest(BaseModel):
    chat_id: str
    request_id: Optional[str] = None
    model: Optional[str] = None


class EditRequest(BaseModel):
    chat_id: str
    message: str
    request_id: Optional[str] = None
    model: Optional[str] = None


class RenameRequest(BaseModel):
    title: str


# ─── Páginas e assets ────────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/avatar")
def avatar():
    for name in ("eve_avatar.webp", "eve_avatar.png"):
        p = BUNDLE_DIR / name
        if p.exists():
            return FileResponse(p)
        p = BUNDLE_DIR / "assets" / name
        if p.exists():
            return FileResponse(p)
    raise HTTPException(404)


@app.get("/eve_icon.ico")
def favicon():
    p = BUNDLE_DIR / "eve_icon.ico"
    if p.exists():
        return FileResponse(p)
    raise HTTPException(404)


@app.get("/api/uploads/{name}")
def get_upload(name: str):
    """Serve imagens enviadas (para exibir no histórico do chat)."""
    p = (UPLOADS_DIR / name).resolve()
    if not str(p).startswith(str(UPLOADS_DIR.resolve())) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


# ─── Status e modelos ────────────────────────────────────────────────
@app.get("/api/status")
def api_status():
    """Saúde das engines + stats dos subsistemas (roda no threadpool)."""
    groq_ok = False
    ollama_ok = False
    ollama_models = []
    try:
        if eve.groq_engine:
            groq_ok = eve.groq_engine.test_connection() == "OK"
    except Exception:
        pass
    try:
        import requests as _rq
        base = os.getenv("OLLAMA_BASE", "http://localhost:11434")
        r = _rq.get(f"{base}/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_ok = True
            ollama_models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass

    stats = {}
    try:
        stats = eve.get_stats()
    except Exception as e:
        logger.error(f"get_stats falhou: {e}")

    return {
        "groq": {"online": groq_ok,
                 "model": eve.groq_engine.default_model if eve.groq_engine else None},
        "ollama": {"online": ollama_ok, "models": ollama_models},
        "streaming": FLAGS.ENABLE_BRAIN_V2,
        "stats": stats,
    }


@app.get("/api/models")
def api_models():
    """Lista curada para o seletor de modelo do front."""
    cloud = list(GROQ_MODEL_CHOICES) if (eve and eve.groq_engine) else []
    local = []
    for m in sorted(_ollama_tags() or [], key=lambda x: x.get("name", "")):
        name = m.get("name", "")
        size_gb = (m.get("size") or 0) / 1e9
        local.append({
            "id": name,
            "label": name,
            "desc": f"Local · {size_gb:.1f} GB",
            "badge": "local",
        })
    return {
        "auto": {"id": "auto", "label": "Automático",
                 "desc": "EVE escolhe: nuvem rápida com fallback local"},
        "cloud": cloud,
        "local": local,
    }


# ─── Gestão de chats ─────────────────────────────────────────────────
@app.get("/api/chats")
def list_chats(q: Optional[str] = None):
    chats = _load_chats()
    ql = (q or "").strip().lower()
    items = []
    for cid, c in chats.items():
        msgs = c.get("messages", [])
        if ql:
            in_title = ql in c.get("title", "").lower()
            in_content = any(
                ql in str(m.get("content", "")).lower() for m in msgs)
            if not (in_title or in_content):
                continue
        preview = ""
        if msgs:
            last = msgs[-1]
            prefix = "Você: " if last.get("role") == "user" else ""
            preview = (prefix + str(last.get("content", ""))
                       .replace("\n", " ").strip())[:60]
        items.append({
            "id": cid,
            "title": c.get("title", "Sem título"),
            "timestamp": c.get("timestamp", ""),
            "messages": len(msgs),
            "preview": preview,
        })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"chats": items, "active": active_chat_id}


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, req: RenameRequest):
    title = req.title.strip()[:80]
    if not title:
        raise HTTPException(400, "Título vazio")
    chats = _load_chats()
    if chat_id not in chats:
        raise HTTPException(404, "Chat não encontrado")
    chats[chat_id]["title"] = title
    _save_chats(chats)
    return {"ok": True, "title": title}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    global active_chat_id
    chats = _load_chats()
    if chat_id not in chats:
        raise HTTPException(404, "Chat não encontrado")
    active_chat_id = chat_id
    with eve_lock:
        _sync_eve_context(chats[chat_id].get("messages", []))
    return {"id": chat_id, **chats[chat_id]}


@app.post("/api/chats/new")
def new_chat():
    global active_chat_id
    active_chat_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    with eve_lock:
        eve.clear_conversation_history()
    return {"id": active_chat_id}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    global active_chat_id
    chats = _load_chats()
    if chat_id in chats:
        del chats[chat_id]
        _save_chats(chats)
    if active_chat_id == chat_id:
        active_chat_id = None
        with eve_lock:
            eve.clear_conversation_history()
    return {"ok": True}


# ─── Upload de imagens ───────────────────────────────────────────────
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "img.png").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(400, f"Formato não suportado: {ext}")
    dest = UPLOADS_DIR / f"{uuid.uuid4().hex}{ext}"
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Imagem maior que 20MB")
    dest.write_bytes(content)
    return {"path": str(dest), "name": file.filename}


# ─── Chat com streaming (SSE) ────────────────────────────────────────
def _persist_message(chat_id: str, message: dict):
    chats = _load_chats()
    if chat_id not in chats:
        chats[chat_id] = {
            "title": message.get("content", "Novo chat")[:45] or "Novo chat",
            "messages": [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    chats[chat_id]["messages"].append(message)
    chats[chat_id]["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_chats(chats)


def _generate_worker(req: ChatRequest, q: queue.Queue,
                     cancel_ev: threading.Event, persist_user: bool = True):
    """Roda a geração (bloqueante) numa thread, empurrando eventos na fila."""
    acc = []  # texto já streamado (vira a resposta parcial num aborto local)
    try:
        def on_chunk(chunk: str):
            if cancel_ev.is_set():
                raise GenerationAborted()
            acc.append(chunk)
            q.put({"event": "chunk", "data": {"text": chunk}})

        prompt = req.message.strip() or "Analise esta imagem brevemente"

        # Semântica do model: None/"auto" = automático; "groq:<id>" = nuvem
        # específica; outra string = modelo Ollama explícito. Modo código
        # continua usando o valor mágico "groq" (ignora o seletor).
        if req.code_mode:
            model_choice = "groq"
        elif req.model and req.model != "auto":
            model_choice = req.model
        else:
            model_choice = None

        start = time.time()
        aborted = False
        try:
            with eve_lock:
                response = eve.generate_response(
                    prompt,
                    model_choice=model_choice,
                    files=req.images or None,
                    max_tokens=2500 if req.code_mode else 1500,
                    temperature=0.7,
                    stream_callback=None if req.images else on_chunk,
                )
        except GenerationAborted:
            # Caminho local: exceção sobe com o parcial acumulado aqui.
            # (No caminho Groq o parcial volta como resposta normal.)
            aborted = True
            response = {
                "text": "".join(acc),
                "model_used": "local",
                "web_search_used": False,
            }
        if cancel_ev.is_set():
            aborted = True
        elapsed_ms = int((time.time() - start) * 1000)

        text = response.get("text", "")
        meta = {
            "model_used": response.get("model_used", "unknown"),
            "web_search_used": bool(response.get("web_search_used")),
            "response_time_ms": response.get("response_time_ms", elapsed_ms),
            "aborted": aborted,
        }

        # Persiste o turno completo (transcript integral fica no servidor;
        # a Eve guarda só a janela de contexto interna)
        chat_id = req.chat_id
        if persist_user:
            _persist_message(chat_id, {
                "role": "user",
                "content": req.message if req.message else "[Imagem]",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "images": req.images or [],
            })
        if text:
            _persist_message(chat_id, {
                "role": "assistant",
                "content": text,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "meta": meta,
            })

        chats = _load_chats()
        title = chats.get(chat_id, {}).get("title", "")

        if aborted:
            # O turno user entrou no contexto interno antes da geração;
            # re-sincroniza com o transcript para não deixar estado torto.
            with eve_lock:
                _sync_eve_context(chats.get(chat_id, {}).get("messages", []))

        q.put({"event": "done", "data": {"text": text, "title": title, **meta}})
    except Exception as e:
        logger.error(f"Erro na geração: {e}", exc_info=True)
        q.put({"event": "error", "data": {"message": str(e)}})
    finally:
        if req.request_id:
            with _gen_lock:
                active_generations.pop(req.request_id, None)
        q.put(None)  # sentinela


def _start_generation(req: ChatRequest, persist_user: bool = True):
    """Registra o cancelamento, dispara o worker e devolve o SSE."""
    if not req.request_id:
        req.request_id = uuid.uuid4().hex
    cancel_ev = threading.Event()
    with _gen_lock:
        active_generations[req.request_id] = cancel_ev

    q: queue.Queue = queue.Queue()
    threading.Thread(
        target=_generate_worker, args=(req, q, cancel_ev, persist_user),
        daemon=True,
    ).start()

    async def event_stream():
        start_payload = {"chat_id": req.chat_id, "request_id": req.request_id}
        yield f"event: start\ndata: {json.dumps(start_payload)}\n\n"
        while True:
            item = await anyio.to_thread.run_sync(q.get)
            if item is None:
                break
            payload = json.dumps(item["data"], ensure_ascii=False)
            yield f"event: {item['event']}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    global active_chat_id
    if not req.message.strip() and not req.images:
        raise HTTPException(400, "Mensagem vazia")

    # Valida caminhos de imagem (só aceita uploads feitos por /api/upload)
    for img in req.images:
        p = Path(img).resolve()
        if not str(p).startswith(str(UPLOADS_DIR.resolve())) or not p.is_file():
            raise HTTPException(400, "Imagem inválida")

    _validate_model_choice(req.model)

    if not req.chat_id:
        req.chat_id = active_chat_id or (
            time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        )
    active_chat_id = req.chat_id

    return _start_generation(req, persist_user=True)


@app.post("/api/chat/stop")
def api_chat_stop(req: StopRequest):
    """Interrompe uma geração em andamento (não usa eve_lock: sem deadlock)."""
    with _gen_lock:
        ev = active_generations.get(req.request_id)
    if ev:
        ev.set()
    return {"ok": True, "stopping": bool(ev)}


@app.post("/api/chat/regenerate")
async def api_chat_regenerate(req: RegenerateRequest):
    """Remove a última resposta e gera outra para o mesmo prompt."""
    global active_chat_id
    _validate_model_choice(req.model)

    chats = _load_chats()
    chat = chats.get(req.chat_id)
    if not chat:
        raise HTTPException(404, "Chat não encontrado")
    msgs = chat.get("messages", [])
    if not msgs or msgs[-1].get("role") != "assistant":
        raise HTTPException(400, "Não há resposta para regenerar")

    last_user = next(
        (m for m in reversed(msgs[:-1]) if m.get("role") == "user"), None)
    if last_user is None:
        raise HTTPException(400, "Não há mensagem de usuário para regenerar")

    # Remove só a resposta final do transcript; a mensagem do usuário fica
    msgs.pop()
    _save_chats(chats)

    prompt_text = str(last_user.get("content", ""))
    _rollback_engine_state(prompt_text)

    active_chat_id = req.chat_id
    images = [p for p in (last_user.get("images") or []) if Path(p).is_file()]
    gen_req = ChatRequest(
        message="" if prompt_text == "[Imagem]" else prompt_text,
        chat_id=req.chat_id,
        code_mode=False,
        images=images,
        model=req.model,
        request_id=req.request_id,
    )
    return _start_generation(gen_req, persist_user=False)


def _rollback_engine_state(prompt_text: str):
    """Desfaz o último turno no contexto interno + memória da Eve
    (inclui o cache do prompt — sem isso a regeneração/edição devolve
    a resposta antiga)."""
    if eve is None:
        return
    with eve_lock:
        eve.rollback_last_exchange()
        if getattr(eve, "layered_memory", None) and prompt_text:
            try:
                eve.layered_memory.forget_cached_response(prompt_text)
            except Exception as e:
                logger.warning(f"Falha ao invalidar cache: {e}")


@app.post("/api/chat/edit")
async def api_chat_edit(req: EditRequest):
    """Edita a última mensagem do usuário e gera uma nova resposta."""
    global active_chat_id
    new_text = req.message.strip()
    if not new_text:
        raise HTTPException(400, "Mensagem vazia")
    _validate_model_choice(req.model)

    chats = _load_chats()
    chat = chats.get(req.chat_id)
    if not chat:
        raise HTTPException(404, "Chat não encontrado")
    msgs = chat.get("messages", [])

    # Remove a resposta final (se houver) e a mensagem editada
    if msgs and msgs[-1].get("role") == "assistant":
        msgs.pop()
    if not msgs or msgs[-1].get("role") != "user":
        raise HTTPException(400, "Não há mensagem do usuário para editar")
    old_user = msgs.pop()
    _save_chats(chats)

    _rollback_engine_state(str(old_user.get("content", "")))

    active_chat_id = req.chat_id
    # Mantém as imagens que acompanhavam a mensagem original
    images = [p for p in (old_user.get("images") or []) if Path(p).is_file()]
    gen_req = ChatRequest(
        message=new_text,
        chat_id=req.chat_id,
        code_mode=False,
        images=images,
        model=req.model,
        request_id=req.request_id,
    )
    return _start_generation(gen_req, persist_user=True)


# ─── Memória ─────────────────────────────────────────────────────────
@app.post("/api/memory/clear")
def clear_memory():
    with eve_lock:
        cleared = []
        if getattr(eve, "memory", None):
            try:
                eve.memory.clear_memory()
                cleared.append("legada")
            except Exception as e:
                logger.error(f"Falha ao limpar memória legada: {e}")
        if getattr(eve, "layered_memory", None):
            try:
                eve.layered_memory.clear_all()
                cleared.append("camadas")
            except Exception as e:
                logger.error(f"Falha ao limpar memória em camadas: {e}")
    return {"cleared": cleared}


# Estáticos por último (não intercepta /api/*)
app.mount("/", StaticFiles(directory=WEB_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("EVE_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("EVE_WEB_PORT", "8765"))
    url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
    print(f"\n  EVE Web — {url}\n  (feche esta janela para encerrar)\n")
    # No executável, abre o navegador sozinho quando o servidor subir
    if FROZEN or os.getenv("EVE_OPEN_BROWSER") == "1":
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
