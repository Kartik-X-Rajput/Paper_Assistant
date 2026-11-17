# Paper Assistant — AI Research Paper Assistant (RAG + Citations)

Upload research-paper PDFs, ask questions, and get **fast, streamed answers with page-level citations**.
Built from the *Live Project Report: AI Research Paper Assistant using Generative AI and RAG*.

## One-click start
| OS | Do this |
|----|---------|
| **Windows** | Double-click **`start.bat`** |
| **macOS** | Double-click **`start.command`** (first time: right-click → Open) |
| **Linux** | Run `./start.sh` |

The first run creates a private environment, installs 5 small packages (~30 s), asks once for a **free Gemini key**
(<https://aistudio.google.com/apikey>) and opens your browser. Next runs start in ~2 seconds.
Requires Python 3.10+. You can also paste/change the key later in the app (⚙ Settings).

## Features (report FR-01 … FR-18)
- Login / register, or **“Start instantly”** guest mode; salted PBKDF2 password hashes; per-user data (FR-01, NFR-04)
- Multi-PDF upload with signature + size validation, drag & drop (FR-02, FR-03)
- PyMuPDF extraction, header/footer removal, two-column ordering, section detection, overlapping chunks with doc/page/section metadata (FR-04, FR-05)
- Top-K retrieval, context-only prompt, `[S#]` tags → **Citation Engine** validates every tag against the retrieved set, shows clickable `p.5` chips, flags unsupported claims (⚑) and prints “Not found in the document.” (FR-07 … FR-11, NFR-01/02)
- Sources panel with the exact supporting excerpt (FR-11)
- Study tools: **short / medium / detailed summaries** (cached → instant repeat), **concept explainer**, **quiz** (interactive, scored, sourced), **slide outline** (FR-12 … FR-15)
- Multi-paper questions with per-paper attribution (FR-18); select which papers are in scope
- Persistent chat history, sessions, document delete (FR-16, FR-17)
- Graceful degradation: no key / rate-limit → clear message; without a key you still get the best matching passages (NFR-07)
- Responsive UI (desktop → mobile), dark/light theme (NFR-05)

## Why it is fast
- **Streaming** (tokens appear in ~1 s), `thinkingBudget=0` on Gemini 2.5 Flash, pooled keep-alive HTTP connection
- Retrieval is a local in-memory **BM25 + phrase bonus** (milliseconds, zero model download) → install is tiny and instant
- Only ~6 relevant passages are sent per question; summaries sample the whole paper within a fixed size budget
- Indexing a 10-page paper takes well under a second

## API (report Table 4.6)
`POST /api/auth/register|login|guest` · `POST/GET/DELETE /api/documents` · `POST /api/chat` (NDJSON stream) ·
`GET /api/sessions`, `GET /api/sessions/{id}/messages` · `POST /api/summary|concept|quiz|slides` · `POST /api/settings`
Interactive docs: <http://127.0.0.1:8000/docs>

## Differences from the report (deliberate, for speed & one-click install)
| Report | This build | Why |
|--------|-----------|-----|
| Sentence-Transformers MiniLM + ChromaDB | BM25 keyword ranking in SQLite/memory | avoids a ~2 GB PyTorch download and slow start; answers are equally grounded because the LLM reads 6–10 passages |
| React frontend | dependency-free HTML/CSS/JS served by FastAPI | no Node/npm build step |
| Separate vector store | one SQLite file `data/assistant.db` | zero setup |

To switch to dense embeddings later, replace `retrieval.retrieve()` (one function) — everything else is unchanged.

## Notes
- Scanned/image-only PDFs are rejected with a clear message (OCR is out of scope in the report).
- Models: default `gemini-2.5-flash`; automatically falls back to other Flash models. Change it in Settings.
- Your PDFs’ extracted text and chat history live in `data/` on your machine; only the question and the retrieved passages are sent to Gemini.

## Project layout
```
run.py              launcher (venv + deps + key prompt + server + browser)
start.bat/.command/.sh
app/main.py         FastAPI routes, streaming jobs, quiz parsing
app/ingest.py       PDF → pages → chunks      app/retrieval.py  BM25 + sampling
app/citations.py    Citation Engine            app/llm.py        Gemini streaming client
app/prompts.py      prompt templates           app/db.py         SQLite schema (report ER diagram)
static/             index.html, style.css, app.js, lib.js
```
