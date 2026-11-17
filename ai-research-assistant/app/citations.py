"""Citation Engine: validates [S#] tags against retrieved chunks and converts them to [[c:CHUNK_ID]]."""
from __future__ import annotations
import re

TAG = re.compile(r"\[\s*((?:S\s*\d+)(?:\s*[,;/&]\s*(?:S\s*\d+))*)\s*\]", re.I)
NOT_FOUND = "Not found in the document"


def build_sources(chunks, docs_by_id, label_fn):
    out = []
    for i, c in enumerate(chunks, 1):
        out.append({"n": i, "id": c["chunk_id"], "doc_id": c["doc_id"],
                    "doc": label_fn(docs_by_id.get(c["doc_id"])), "page": c["page"],
                    "section": c["section"], "text": c["text"]})
    return out


def context_block(sources, max_chars=1100):
    return "\n\n".join(f"[S{s['n']}] ({s['doc']}, Page {s['page']}, Section: {s['section']})\n{s['text'][:max_chars]}"
                       for s in sources)


def process(text: str, sources, flag: bool = True):
    """Return (processed_text, used_sources)."""
    by_n = {s["n"]: s for s in sources}
    used = {}

    def repl(m):
        parts = []
        for n in re.findall(r"S\s*(\d+)", m.group(1), re.I):
            s = by_n.get(int(n))
            if s:
                used[s["id"]] = s
                parts.append(f"[[c:{s['id']}]]")
            else:
                parts.append("[[c:?]]")
        return "".join(parts)

    out = TAG.sub(repl, text)
    if flag:
        lines = out.split("\n")
        in_code = False
        for i, ln in enumerate(lines):
            st = ln.strip()
            if st.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not st or st.startswith("#") or st.startswith("|"):
                continue
            words = re.sub(r"\[\[c:[^\]]*\]\]", "", st).split()
            if len(words) >= 12 and not re.search(r"\[\[c:(?!\?)", st) and NOT_FOUND.lower() not in st.lower():
                lines[i] = ln + " [[u]]"
        out = "\n".join(lines)
    return out, list(used.values())


def source_ids(text: str):
    return {m for m in re.findall(r"\[\[c:([^\]?]+)\]\]", text)}
