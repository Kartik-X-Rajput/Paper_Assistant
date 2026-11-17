"""SQLite persistence (users, documents, chunks, sessions, messages, citations, summaries)."""
from __future__ import annotations
import hashlib, hmac, os, secrets, sqlite3, threading
from .config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS tokens(
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS documents(
  doc_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, filename TEXT NOT NULL,
  page_count INTEGER, chunk_count INTEGER DEFAULT 0, status TEXT DEFAULT 'uploaded',
  uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chunks(
  chunk_id TEXT PRIMARY KEY, doc_id INTEGER NOT NULL, page INTEGER, section TEXT,
  idx INTEGER, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(doc_id, idx);
CREATE TABLE IF NOT EXISTS sessions(
  session_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(
  msg_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, role TEXT NOT NULL,
  kind TEXT DEFAULT 'text', content TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS citations(
  cit_id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER NOT NULL, doc_id INTEGER,
  page_no INTEGER, section TEXT, chunk_id TEXT, excerpt TEXT);
CREATE INDEX IF NOT EXISTS ix_cit_msg ON citations(msg_id);
CREATE TABLE IF NOT EXISTS summaries(
  summary_id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER NOT NULL, level TEXT NOT NULL,
  content TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(doc_id, level));
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        _local.c = c
    return c


def init():
    conn().executescript(SCHEMA)
    conn().commit()


def q(sql, args=(), one=False):
    cur = conn().execute(sql, args)
    rows = cur.fetchall()
    conn().commit()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def ins(sql, args=()):
    cur = conn().execute(sql, args)
    conn().commit()
    return cur.lastrowid


# ---------- auth ----------
def _hash(pw: str, salt: bytes) -> str:
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000).hex()


def make_hash(pw: str) -> str:
    return _hash(pw, os.urandom(16))


def check_hash(pw: str, stored: str) -> bool:
    try:
        salt = bytes.fromhex(stored.split("$")[0])
    except ValueError:
        return False
    return hmac.compare_digest(_hash(pw, salt), stored)


def create_user(name, email, pw):
    return ins("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", (name, email.lower(), make_hash(pw)))


def user_by_email(email):
    return q("SELECT * FROM users WHERE email=?", (email.lower(),), one=True)


def new_token(user_id):
    t = secrets.token_urlsafe(32)
    ins("INSERT INTO tokens(token,user_id) VALUES(?,?)", (t, user_id))
    return t


def user_by_token(t):
    return q("SELECT u.user_id,u.name,u.email FROM tokens k JOIN users u ON u.user_id=k.user_id WHERE k.token=?",
             (t,), one=True)


# ---------- documents ----------
def user_docs(user_id, doc_ids=None, ready_only=True):
    rows = q("SELECT * FROM documents WHERE user_id=? ORDER BY doc_id DESC", (user_id,))
    if ready_only:
        rows = [r for r in rows if r["status"] == "ready"]
    if doc_ids:
        s = set(doc_ids)
        rows = [r for r in rows if r["doc_id"] in s]
    return rows


def chunks_for(doc_ids):
    if not doc_ids:
        return []
    ph = ",".join("?" * len(doc_ids))
    return q(f"SELECT * FROM chunks WHERE doc_id IN ({ph}) ORDER BY doc_id, idx", tuple(doc_ids))


def delete_doc(user_id, doc_id):
    d = q("SELECT doc_id FROM documents WHERE doc_id=? AND user_id=?", (doc_id, user_id), one=True)
    if not d:
        return False
    for t in ("chunks", "summaries", "citations"):
        conn().execute(f"DELETE FROM {t} WHERE doc_id=?", (doc_id,))
    conn().execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
    conn().commit()
    return True


# ---------- sessions / messages ----------
def add_message(session_id, role, content, kind="text"):
    return ins("INSERT INTO messages(session_id,role,kind,content) VALUES(?,?,?,?)", (session_id, role, kind, content))


def add_citations(msg_id, sources):
    c = conn()
    for s in sources:
        c.execute("INSERT INTO citations(msg_id,doc_id,page_no,section,chunk_id,excerpt) VALUES(?,?,?,?,?,?)",
                  (msg_id, s["doc_id"], s["page"], s["section"], s["id"], s["text"]))
    c.commit()


def session_messages(session_id):
    msgs = q("SELECT msg_id,role,kind,content,created_at FROM messages WHERE session_id=? ORDER BY msg_id", (session_id,))
    for m in msgs:
        m["sources"] = q("""SELECT c.chunk_id id,c.doc_id,c.page_no page,c.section,c.excerpt text,
                    COALESCE(d.filename,'(deleted)') doc FROM citations c
                    LEFT JOIN documents d ON d.doc_id=c.doc_id WHERE c.msg_id=?""", (m["msg_id"],))
    return msgs
