"""AI Research Paper Assistant - FastAPI backend (RAG + citations + study tools), serves the web UI."""
from __future__ import annotations
import json, re, time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import citations, db, ingest, llm, prompts, retrieval
from .config import MAX_UPLOAD_MB, ROOT, settings

STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield
    if llm._client:
        await llm._client.aclose()


app = FastAPI(title="AI Research Paper Assistant", lifespan=lifespan)


# ------------------------------------------------------------------ auth
def current_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    u = db.user_by_token(authorization[7:].strip())
    if not u:
        raise HTTPException(401, "Session expired - please log in again")
    return u


class RegisterReq(BaseModel):
    name: str
    email: str
    password: str


class LoginReq(BaseModel):
    email: str
    password: str


def _auth_payload(uid, name, email):
    return {"token": db.new_token(uid), "user": {"user_id": uid, "name": name, "email": email}}


@app.post("/api/auth/register")
def register(r: RegisterReq):
    email = r.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Enter a valid email address")
    if len(r.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.user_by_email(email):
        raise HTTPException(400, "An account with this email already exists")
    uid = db.create_user(r.name.strip() or email.split("@")[0], email, r.password)
    return _auth_payload(uid, r.name.strip() or email.split("@")[0], email)


@app.post("/api/auth/login")
def login(r: LoginReq):
    u = db.user_by_email(r.email.strip())
    if not u or not db.check_hash(r.password, u["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    return _auth_payload(u["user_id"], u["name"], u["email"])


@app.post("/api/auth/guest")
def guest():
    """One-click start: creates a private local account."""
    import secrets
    tag = secrets.token_hex(4)
    email = f"guest-{tag}@local"
    uid = db.create_user("Guest", email, secrets.token_urlsafe(16))
    return _auth_payload(uid, "Guest", email)


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"user": user, "has_key": bool(settings.api_key), "model": settings.model}


class SettingsReq(BaseModel):
    api_key: str | None = None
    model: str | None = None


@app.post("/api/settings")
def save_settings(r: SettingsReq, user=Depends(current_user)):
    settings.save(api_key=r.api_key, model=r.model)
    return {"has_key": bool(settings.api_key), "model": settings.model}


@app.get("/api/diagnose")
async def diagnose(user=Depends(current_user)):
    """Quick connectivity/key test used by the Settings > Test connection button."""
    if not settings.api_key:
        return {"ok": False, "error": "No API key saved yet."}
    t0 = time.time()
    try:
        out = await llm.generate("Reply with the single word OK.", [{"role": "user", "parts": [{"text": "OK?"}]}],
                                 max_tokens=16)
        return {"ok": True, "seconds": round(time.time() - t0, 2), "model": settings.model, "reply": out.strip()[:40]}
    except llm.LLMError as e:
        return {"ok": False, "error": str(e), "seconds": round(time.time() - t0, 2)}
    except Exception as e:  # noqa
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------ documents
def _label(d):
    if not d:
        return "Paper"
    n = re.sub(r"\.pdf$", "", d["filename"], flags=re.I)
    return n if len(n) <= 34 else n[:32] + "..."


@app.post("/api/documents")
def upload(files: list[UploadFile] = File(...), user=Depends(current_user)):
    results = []
    for f in files:
        data = f.file.read()
        name = (f.filename or "paper.pdf")[:200]
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            results.append({"filename": name, "error": f"File larger than {MAX_UPLOAD_MB} MB"})
            continue
        doc_id = db.ins("INSERT INTO documents(user_id,filename,status) VALUES(?,?, 'indexing')", (user["user_id"], name))
        t0 = time.time()
        try:
            pages, chunks = ingest.process_pdf(doc_id, data)
            c = db.conn()
            c.executemany("INSERT INTO chunks(chunk_id,doc_id,page,section,idx,text) VALUES(?,?,?,?,?,?)",
                          [(x["chunk_id"], doc_id, x["page"], x["section"], x["idx"], x["text"]) for x in chunks])
            c.execute("UPDATE documents SET status='ready',page_count=?,chunk_count=? WHERE doc_id=?",
                      (pages, len(chunks), doc_id))
            c.commit()
            results.append({"filename": name, "doc_id": doc_id, "pages": pages, "chunks": len(chunks),
                            "seconds": round(time.time() - t0, 2)})
        except ingest.IngestError as e:
            db.q("UPDATE documents SET status='failed' WHERE doc_id=?", (doc_id,))
            db.q("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            results.append({"filename": name, "error": str(e)})
        except Exception as e:  # noqa
            db.q("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            results.append({"filename": name, "error": f"Failed to process PDF: {e}"})
    return {"results": results}


@app.get("/api/documents")
def list_docs(user=Depends(current_user)):
    return db.user_docs(user["user_id"], ready_only=False)


@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: int, user=Depends(current_user)):
    if not db.delete_doc(user["user_id"], doc_id):
        raise HTTPException(404, "Document not found")
    return {"ok": True}


# ------------------------------------------------------------------ sessions
@app.get("/api/sessions")
def sessions(user=Depends(current_user)):
    return db.q("SELECT session_id,title,created_at FROM sessions WHERE user_id=? ORDER BY session_id DESC LIMIT 100",
                (user["user_id"],))


@app.get("/api/sessions/{sid}/messages")
def session_msgs(sid: int, user=Depends(current_user)):
    if not db.q("SELECT 1 FROM sessions WHERE session_id=? AND user_id=?", (sid, user["user_id"]), one=True):
        raise HTTPException(404, "Session not found")
    return db.session_messages(sid)


@app.delete("/api/sessions/{sid}")
def del_session(sid: int, user=Depends(current_user)):
    if db.q("SELECT 1 FROM sessions WHERE session_id=? AND user_id=?", (sid, user["user_id"]), one=True):
        for m in db.q("SELECT msg_id FROM messages WHERE session_id=?", (sid,)):
            db.q("DELETE FROM citations WHERE msg_id=?", (m["msg_id"],))
        db.q("DELETE FROM messages WHERE session_id=?", (sid,))
        db.q("DELETE FROM sessions WHERE session_id=?", (sid,))
    return {"ok": True}


def _ensure_session(user, sid, title):
    if sid and db.q("SELECT 1 FROM sessions WHERE session_id=? AND user_id=?", (sid, user["user_id"]), one=True):
        return sid
    return db.ins("INSERT INTO sessions(user_id,title) VALUES(?,?)", (user["user_id"], title[:70]))


# ------------------------------------------------------------------ generation core
def nd(o) -> str:
    return json.dumps(o, ensure_ascii=False) + "\n"


HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _history(session_id, limit=6):
    rows = db.q("SELECT role,content,kind FROM messages WHERE session_id=? AND kind='text' ORDER BY msg_id DESC LIMIT ?",
                (session_id, limit))
    out = []
    for r in reversed(rows):
        txt = re.sub(r"\[\[(?:c:[^\]]*|u)\]\]", "", r["content"]).strip()[:1500]
        if txt:
            out.append({"role": "user" if r["role"] == "user" else "model", "parts": [{"text": txt}]})
    merged = []  # merge consecutive same-role turns (tool outputs have no user turn stored as text)
    for t in out:
        if merged and merged[-1]["role"] == t["role"]:
            merged[-1]["parts"][0]["text"] += "\n\n" + t["parts"][0]["text"]
        else:
            merged.append(t)
    while merged and merged[0]["role"] != "user":  # Gemini requires the first turn to be 'user'
        merged.pop(0)
    return merged


def _resolve_docs(user, doc_ids):
    docs = db.user_docs(user["user_id"], doc_ids or None)
    if not docs:
        raise HTTPException(400, "Upload a paper first (PDF), then ask your question.")
    return docs, {d["doc_id"]: d for d in docs}


def _extractive_fallback(sources):
    lines = ["**AI key not set - showing the most relevant passages from your paper.** "
             "Add a free Gemini key in *Settings* to get written answers.\n"]
    for s in sources[:4]:
        snippet = s["text"][:380].rsplit(" ", 1)[0] + "..."
        lines.append(f"- {snippet} [S{s['n']}]")
    return "\n".join(lines)


async def run_job(user, session_id, user_text, system, prompt, sources, *, history=None, flag=False,
                  max_tokens=1400, kind="text", on_saved=None, temperature=0.2, user_kind="text"):
    """Async generator of NDJSON events: meta -> d* -> done | err."""
    mid = db.add_message(session_id, "user", user_text, user_kind)
    yield nd({"t": "meta", "session_id": session_id, "user_msg_id": mid, "sources": sources})
    contents = (history or []) + [{"role": "user", "parts": [{"text": prompt}]}]
    full = ""
    try:
        if kind == "quiz":
            full = await llm.generate(system, contents, max_tokens=max_tokens, temperature=0.4, json_mode=True)
        else:
            async for delta in llm.stream(system, contents, max_tokens=max_tokens, temperature=temperature):
                full += delta
                yield nd({"t": "d", "x": delta})
    except llm.LLMError as e:
        if str(e) == "NO_KEY":
            if kind == "text" and system == prompts.CHAT_SYSTEM:
                full = _extractive_fallback(sources)
                yield nd({"t": "d", "x": full})
            else:
                yield nd({"t": "err", "message": "Add your free Gemini API key in Settings to use this feature."})
                return
        else:
            yield nd({"t": "err", "message": str(e)})
            return
    except Exception as e:  # noqa
        yield nd({"t": "err", "message": f"Unexpected error: {type(e).__name__}: {e}"})
        return

    if kind == "quiz":
        content, used = _finish_quiz(full, sources)
        if content is None:
            yield nd({"t": "err", "message": "The model returned an unreadable quiz. Please try again."})
            return
    else:
        content, used = citations.process(full, sources, flag=flag)
    amid = db.add_message(session_id, "assistant", content, kind)
    db.add_citations(amid, used)
    if on_saved:
        on_saved(content)
    yield nd({"t": "done", "msg_id": amid, "kind": kind, "content": content, "sources": used})


def _finish_quiz(raw, sources):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else None
        except ValueError:
            data = None
    if not data:
        return None, []
    by_n = {s["n"]: s for s in sources}
    used, qs = {}, []

    def conv(txt):
        out, u = citations.process(str(txt), sources, flag=False)
        for s in u:
            used[s["id"]] = s
        return out

    for q in data.get("questions", []):
        opts = q.get("options") or []
        ans = q.get("answer")
        if len(opts) < 2 or not isinstance(ans, int) or not (0 <= ans < len(opts)):
            continue
        src = ""
        m = re.search(r"(\d+)", str(q.get("source", "")))
        if m and int(m.group(1)) in by_n:
            s = by_n[int(m.group(1))]
            used[s["id"]] = s
            src = s["id"]
        qs.append({"q": str(q.get("q", "")).strip(), "options": [str(o) for o in opts], "answer": ans,
                   "explanation": conv(q.get("explanation", "")), "source": src})
    if not qs:
        return None, []
    return json.dumps({"questions": qs}, ensure_ascii=False), list(used.values())


def _sources_for(chunks, docs_by_id):
    return citations.build_sources(chunks, docs_by_id, _label)


def _stream(gen):
    return StreamingResponse(gen, media_type="application/x-ndjson", headers=HEADERS)


# ------------------------------------------------------------------ chat
class ChatReq(BaseModel):
    question: str
    doc_ids: list[int] = []
    session_id: int | None = None


@app.post("/api/chat")
async def chat(r: ChatReq, user=Depends(current_user)):
    question = r.question.strip()
    if not question:
        raise HTTPException(400, "Type a question first")
    docs, by_id = _resolve_docs(user, r.doc_ids)
    sid = _ensure_session(user, r.session_id, question)
    hist = _history(sid)
    query = question
    if len(question.split()) < 6 and hist:  # follow-up: enrich retrieval with the previous user turn
        prev = [h for h in hist if h["role"] == "user"]
        if prev:
            query = prev[-1]["parts"][0]["text"][:300] + " " + question
    k = 6 if len(docs) == 1 else min(10, 4 + 2 * len(docs))
    chunks = retrieval.retrieve(query, db.chunks_for([d["doc_id"] for d in docs]), k=k)
    sources = _sources_for(chunks, by_id)
    prompt = f"CONTEXT:\n{citations.context_block(sources)}\n\nQUESTION:\n{question}"
    return _stream(run_job(user, sid, question, prompts.CHAT_SYSTEM, prompt, sources, history=hist, flag=True,
                           max_tokens=1200))


# ------------------------------------------------------------------ study tools
class SummaryReq(BaseModel):
    level: str = "medium"
    doc_ids: list[int] = []
    session_id: int | None = None


@app.post("/api/summary")
async def summary(r: SummaryReq, user=Depends(current_user)):
    level = r.level if r.level in prompts.SUMMARY_LEVELS else "medium"
    docs, by_id = _resolve_docs(user, r.doc_ids)
    names = ", ".join(_label(d) for d in docs)[:80]
    label = f"{level.capitalize()} summary - {names}"
    sid = _ensure_session(user, r.session_id, label)
    single = docs[0]["doc_id"] if len(docs) == 1 else None
    if single:
        cached = db.q("SELECT content FROM summaries WHERE doc_id=? AND level=?", (single, level), one=True)
        if cached:  # instant repeat
            async def instant():
                db.add_message(sid, "user", label, "tool")
                ids = citations.source_ids(cached["content"])
                chunks = [c for c in db.chunks_for([single]) if c["chunk_id"] in ids]
                srcs = _sources_for(chunks, by_id)
                yield nd({"t": "meta", "session_id": sid, "sources": srcs, "cached": True})
                amid = db.add_message(sid, "assistant", cached["content"], "text")
                db.add_citations(amid, srcs)
                yield nd({"t": "done", "msg_id": amid, "kind": "text", "content": cached["content"], "sources": srcs})
            return _stream(instant())
    instr, max_tok = prompts.SUMMARY_LEVELS[level]
    budget = {"short": 12000, "medium": 20000, "detailed": 30000}[level]
    chunks = retrieval.sample(db.chunks_for([d["doc_id"] for d in docs]), budget)
    sources = _sources_for(chunks, by_id)
    prompt = f"CONTEXT:\n{citations.context_block(sources, 800)}\n\nTASK:\n{instr}"
    if len(docs) > 1:
        prompt += " Summarize each paper separately, then add a short comparison."

    def save(content):
        if single:
            db.q("INSERT OR REPLACE INTO summaries(doc_id,level,content) VALUES(?,?,?)", (single, level, content))

    return _stream(run_job(user, sid, label, prompts.RULES, prompt, sources, flag=False, max_tokens=max_tok,
                           on_saved=save, user_kind="tool"))


class ConceptReq(BaseModel):
    concept: str
    doc_ids: list[int] = []
    session_id: int | None = None


@app.post("/api/concept")
async def concept(r: ConceptReq, user=Depends(current_user)):
    c = r.concept.strip()
    if not c:
        raise HTTPException(400, "Enter a concept or equation to explain")
    docs, by_id = _resolve_docs(user, r.doc_ids)
    sid = _ensure_session(user, r.session_id, f"Explain: {c}")
    chunks = retrieval.retrieve(c, db.chunks_for([d["doc_id"] for d in docs]), k=7)
    sources = _sources_for(chunks, by_id)
    prompt = f"CONTEXT:\n{citations.context_block(sources)}\n\nCONCEPT:\n{c}"
    return _stream(run_job(user, sid, f"Explain simply: {c}", prompts.CONCEPT_SYSTEM, prompt, sources, flag=False,
                           max_tokens=1300, user_kind="tool"))


class QuizReq(BaseModel):
    count: int = 5
    doc_ids: list[int] = []
    session_id: int | None = None


@app.post("/api/quiz")
async def quiz(r: QuizReq, user=Depends(current_user)):
    n = max(3, min(10, r.count))
    docs, by_id = _resolve_docs(user, r.doc_ids)
    sid = _ensure_session(user, r.session_id, "Quiz")
    chunks = retrieval.sample(db.chunks_for([d["doc_id"] for d in docs]), 16000)
    sources = _sources_for(chunks, by_id)
    prompt = f"CONTEXT:\n{citations.context_block(sources, 800)}\n\nCreate {n} multiple-choice questions."
    return _stream(run_job(user, sid, f"Quiz me ({n} questions)", prompts.QUIZ_SYSTEM, prompt, sources, kind="quiz",
                           max_tokens=2500, user_kind="tool"))


class SlidesReq(BaseModel):
    count: int = 8
    doc_ids: list[int] = []
    session_id: int | None = None


@app.post("/api/slides")
async def slides(r: SlidesReq, user=Depends(current_user)):
    n = max(4, min(15, r.count))
    docs, by_id = _resolve_docs(user, r.doc_ids)
    sid = _ensure_session(user, r.session_id, "Slide outline")
    chunks = retrieval.sample(db.chunks_for([d["doc_id"] for d in docs]), 20000)
    sources = _sources_for(chunks, by_id)
    prompt = f"CONTEXT:\n{citations.context_block(sources, 800)}\n\nCreate a {n}-slide outline."
    return _stream(run_job(user, sid, f"Slide outline ({n} slides)", prompts.SLIDES_SYSTEM, prompt, sources,
                           flag=False, max_tokens=2200, user_kind="tool"))


# ------------------------------------------------------------------ static UI
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
