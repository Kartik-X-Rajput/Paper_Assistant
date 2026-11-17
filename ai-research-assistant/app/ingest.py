"""PDF ingestion: text extraction (PyMuPDF), header/footer removal, section detection, chunking."""
from __future__ import annotations
import re
from collections import Counter

CHUNK_CHARS = 900
OVERLAP_CHARS = 150
MIN_CHUNK = 120

KNOWN_HEADINGS = {
    "abstract", "introduction", "background", "related work", "literature review", "methodology", "methods",
    "method", "approach", "experiments", "experimental setup", "results", "evaluation", "discussion",
    "conclusion", "conclusions", "limitations", "future work", "acknowledgements", "acknowledgments",
    "references", "bibliography", "appendix", "preliminaries", "model", "implementation", "analysis",
}
NUM_HEADING = re.compile(r"^(\d{1,2}(\.\d{1,2}){0,3}\.?|[IVX]{1,5}\.|[A-Z]\.)\s+[A-Z][^\n]{2,90}$")


class IngestError(Exception):
    pass


def _norm_hf(t: str) -> str:
    return re.sub(r"\d+", "#", t.strip().lower())


def _order_blocks(blocks, width):
    """Order text blocks reading-order aware (handles two-column papers)."""
    blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
    mid = width / 2
    left = [b for b in blocks if b[2] <= mid * 1.08]
    right = [b for b in blocks if b[0] >= mid * 0.92]
    if len(left) < 3 or len(right) < 3:
        return blocks
    out, lbuf, rbuf = [], [], []

    def flush():
        out.extend(sorted(lbuf, key=lambda b: b[1]))
        out.extend(sorted(rbuf, key=lambda b: b[1]))
        lbuf.clear(); rbuf.clear()

    for b in blocks:
        if b[2] <= mid * 1.08:
            lbuf.append(b)
        elif b[0] >= mid * 0.92:
            rbuf.append(b)
        else:  # spanning block (title, wide figure caption, ...)
            flush()
            out.append(b)
    flush()
    return out


def _clean(t: str) -> str:
    t = t.replace("\u00ad", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def _is_heading(p: str) -> str | None:
    s = p.strip()
    if len(s) > 100 or len(s) < 3:
        return None
    low = re.sub(r"^[\dIVX.\s]+", "", s).strip(" .:").lower()
    if low in KNOWN_HEADINGS:
        return s.strip(" :")
    if NUM_HEADING.match(s) and not s.endswith((".", ",")) and len(s.split()) <= 12:
        return s
    if s.isupper() and 3 <= len(s) <= 60 and re.search(r"[A-Z]{3}", s):
        return s.title()
    return None


def extract_pages(data: bytes):
    """Returns list of (page_no, [paragraph strings with optional ('H', heading) markers])."""
    import fitz  # PyMuPDF (imported lazily)

    if not data[:5] == b"%PDF-":
        raise IngestError("This file is not a valid PDF.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # noqa
        raise IngestError(f"Could not open PDF: {e}")
    if doc.needs_pass:
        raise IngestError("This PDF is password protected.")
    n = len(doc)
    raw_pages = []
    for pno in range(n):
        page = doc[pno]
        H = page.rect.height
        W = page.rect.width
        blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        blocks = _order_blocks(blocks, W)
        raw_pages.append((pno + 1, H, blocks))
    # repeated header/footer detection
    counter = Counter()
    for _, H, blocks in raw_pages:
        seen = set()
        for b in blocks:
            if b[1] < H * 0.09 or b[3] > H * 0.92:
                seen.add(_norm_hf(b[4]))
        counter.update(seen)
    thresh = max(3, int(0.4 * n)) if n >= 4 else 10 ** 9
    repeated = {k for k, v in counter.items() if v >= thresh}
    pages = []
    for pno, H, blocks in raw_pages:
        paras = []
        for b in blocks:
            txt = b[4]
            edge = b[1] < H * 0.09 or b[3] > H * 0.92
            if edge and (_norm_hf(txt) in repeated or re.fullmatch(r"\s*(page\s*)?\d{1,4}\s*", txt, re.I)):
                continue
            c = _clean(txt)
            if c:
                paras.append(c)
        pages.append((pno, paras))
    doc.close()
    return pages


def _split_sentences(t: str):
    return re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])", t)


def _pack(paras, section):
    """Pack paragraphs of one page into overlapping chunks. paras: list[str]."""
    pieces = []
    for p in paras:
        if len(p) <= CHUNK_CHARS:
            pieces.append(p)
        else:
            cur = ""
            for s in _split_sentences(p):
                if len(cur) + len(s) + 1 > CHUNK_CHARS and cur:
                    pieces.append(cur); cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur:
                pieces.append(cur)
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) + 1 > CHUNK_CHARS:
            chunks.append(cur)
            tail = cur[-OVERLAP_CHARS:]
            sp = tail.find(" ")
            cur = (tail[sp + 1:] + " " + p) if sp != -1 else p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) < MIN_CHUNK:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()
    return chunks


def build_chunks(doc_id: int, pages):
    """pages -> list of dict(chunk_id, doc_id, page, section, idx, text)."""
    out, section, skipping, idx = [], "Front matter", False, 0
    for pno, paras in pages:
        buf, buf_section = [], section
        page_chunks = []

        def flush():
            nonlocal buf
            if buf:
                for ch in _pack(buf, buf_section):
                    page_chunks.append((buf_section, ch))
                buf = []

        for p in paras:
            h = _is_heading(p)
            if h:
                flush()
                low = h.lower()
                skipping = bool(re.search(r"\b(references|bibliography)\b", low))
                if "appendix" in low:
                    skipping = False
                section = h[:80]
                buf_section = section
                continue
            if skipping:
                continue
            if not buf:
                buf_section = section
            buf.append(p)
        flush()
        for sec, text in page_chunks:
            if len(text.strip()) < 40:
                continue
            out.append({"chunk_id": f"d{doc_id}_p{pno}_c{idx}", "doc_id": doc_id, "page": pno,
                        "section": sec, "idx": idx, "text": text})
            idx += 1
    return out


def process_pdf(doc_id: int, data: bytes):
    pages = extract_pages(data)
    total = sum(len(p) for _, ps in pages for p in ps)
    if total < 200:
        raise IngestError("No extractable text found. This looks like a scanned/image-only PDF (OCR is not supported).")
    chunks = build_chunks(doc_id, pages)
    if not chunks:
        raise IngestError("Could not extract usable text from this PDF.")
    return len(pages), chunks
