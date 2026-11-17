"""Fast local retrieval: BM25 (+ phrase bonus + abstract prior). Pure Python, no model download."""
from __future__ import annotations
import math, re
from collections import Counter, defaultdict

STOP = set("""a an the of and or to in on for with by is are was were be been being this that these those it its as at from
which what who whom how why when where do does did can could should would will shall may might into than then there their
they them we our you your i me my not no yes also such via per using use used please give tell explain describe show""".split())
GENERIC = {"summary", "summarize", "summarise", "overview", "about", "main", "contribution", "contributions", "abstract",
           "conclusion", "conclusions", "findings", "key", "idea", "ideas", "tldr", "purpose", "goal", "objective", "novel"}

_tok_cache: dict[str, list[str]] = {}


def _stem(w: str) -> str:
    for suf in ("izations", "ization", "ations", "ation", "ings", "ing", "edly", "ed", "ies", "es", "ly", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]{2,}", text.lower()) if w not in STOP]


def _tokens(chunk) -> list[str]:
    t = _tok_cache.get(chunk["chunk_id"])
    if t is None:
        t = tokenize(chunk["text"] + " " + (chunk.get("section") or ""))
        _tok_cache[chunk["chunk_id"]] = t
    return t


def retrieve(query: str, chunks: list[dict], k: int = 6, k1: float = 1.4, b: float = 0.75):
    """Return top-k chunks (document/page order). `chunks` = all candidate chunks of selected docs."""
    if not chunks:
        return []
    qtok = tokenize(query)
    raw_words = set(re.findall(r"[a-z]+", query.lower()))
    generic = bool(raw_words & GENERIC)
    N = len(chunks)
    toks = [_tokens(c) for c in chunks]
    avgdl = (sum(len(t) for t in toks) / N) or 1.0
    df = defaultdict(int)
    qset = set(qtok)
    for t in toks:
        for w in qset.intersection(t):
            df[w] += 1
    low_q = " ".join(re.findall(r"[a-z0-9]+", query.lower()))
    bigrams = {" ".join(p) for p in zip(low_q.split(), low_q.split()[1:]) if not (p[0] in STOP and p[1] in STOP)}
    scored = []
    for c, t in zip(chunks, toks):
        if not t:
            continue
        tf = Counter(t)
        s = 0.0
        for w in qset:
            f = tf.get(w, 0)
            if f:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(t) / avgdl))
        if s and bigrams:
            lt = c["text"].lower()
            s += 0.6 * sum(1 for g in bigrams if g in lt)
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    picked = {}
    if generic or not scored or scored[0][0] <= 0:
        # overview-style questions: abstract / intro / conclusion carry the signal
        by_doc = defaultdict(list)
        for c in chunks:
            by_doc[c["doc_id"]].append(c)
        for lst in by_doc.values():
            for c in lst[:2] + lst[-1:]:
                picked[c["chunk_id"]] = c
    for s, c in scored:
        if len(picked) >= k:
            break
        if s > 0:
            picked[c["chunk_id"]] = c
    if len(picked) < min(k, N):  # pad with highest-scored leftovers
        for s, c in scored:
            if len(picked) >= k:
                break
            picked.setdefault(c["chunk_id"], c)
    res = list(picked.values())[: max(k, 3 * len(set(c["doc_id"] for c in chunks)))]
    res.sort(key=lambda c: (c["doc_id"], c["idx"]))
    return res


def sample(chunks: list[dict], budget_chars: int, per_chunk: int = 800):
    """Evenly sample chunks across each document (for summaries / quiz / slides)."""
    by_doc = defaultdict(list)
    for c in chunks:
        by_doc[c["doc_id"]].append(c)
    if not by_doc:
        return []
    per_doc = budget_chars // len(by_doc)
    out = []
    for lst in by_doc.values():
        n = max(4, per_doc // per_chunk)
        if len(lst) <= n:
            out.extend(lst)
            continue
        step = (len(lst) - 1) / (n - 1)
        idxs = sorted({round(i * step) for i in range(n)})
        out.extend(lst[i] for i in idxs)
    return out
