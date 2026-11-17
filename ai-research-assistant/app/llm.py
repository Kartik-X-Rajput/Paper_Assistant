"""Gemini REST client: streaming with automatic non-streaming fallback, model fallback, friendly errors."""
from __future__ import annotations
import json, re
import httpx
from .config import settings, FALLBACK_MODELS

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_client: httpx.AsyncClient | None = None
NET_ERRORS = (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError)


class LLMError(Exception):
    pass


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10),
                                    limits=httpx.Limits(max_keepalive_connections=5))
    return _client


_all_models: set | None = None      # every model name that supports generateContent (None = unknown)
_ranked: list = []                  # best Flash models, newest first
_dead: set = set()                  # models that returned 404 this session
_nothink: set = set()               # models that reject thinkingConfig


async def discover(force: bool = False):
    """Ask Google which models exist right now, so we never depend on hard-coded (retired) names."""
    global _all_models, _ranked
    if _all_models is not None and not force:
        return
    try:
        r = await client().get(BASE, params={"pageSize": 200}, headers={"x-goog-api-key": settings.api_key},
                               timeout=httpx.Timeout(15, connect=10))
        if r.status_code != 200:
            return
        names, ranked = set(), []
        for m in r.json().get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            n = m["name"].split("/", 1)[-1]
            names.add(n)
            mm = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash(-lite)?(-[a-z0-9]+)?", n)
            if not mm or re.search(r"image|tts|live|audio|native|robot|computer|embed|thinking|exp", n):
                continue
            ranked.append((-float(mm.group(1)), bool(mm.group(2)), bool(mm.group(3)), n))
        ranked.sort()
        _all_models, _ranked = names, [x[3] for x in ranked]
    except httpx.HTTPError:
        pass


async def _attempts():
    await discover()
    models = []
    if settings.model not in _dead and (_all_models is None or settings.model in _all_models):
        models.append(settings.model)
    models += [m for m in _ranked[:4] if m not in models and m not in _dead]
    if not models:
        models = [m for m in [settings.model] + FALLBACK_MODELS]
    out = []
    for m in models:
        if m not in _nothink:
            out.append((m, True))
        out.append((m, False))
    return out


def _body(system, contents, max_tokens, temperature, json_mode, thinking_off):
    gc = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        gc["responseMimeType"] = "application/json"
    if thinking_off:
        gc["thinkingConfig"] = {"thinkingBudget": 0}  # no hidden reasoning => much faster first token
    return {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gc}


def _err_text(raw: bytes) -> str:
    try:
        return json.loads(raw)["error"]["message"]
    except Exception:
        return raw[:200].decode("utf-8", "ignore")


def _net_msg(e: Exception) -> str:
    n = type(e).__name__
    if isinstance(e, (httpx.ConnectTimeout, httpx.ConnectError)):
        return ("Cannot reach Google's Gemini servers. Check your internet connection, VPN/proxy or firewall "
                f"(generativelanguage.googleapis.com must be reachable). [{n}]")
    if isinstance(e, httpx.TimeoutException):
        return ("Gemini did not respond in time. Your network, VPN, proxy or antivirus may be blocking or slowing "
                f"Google API traffic. Try another network (e.g. phone hotspot). [{n}]")
    return f"Network error while contacting Gemini. [{n}: {e}]"


def _parts_text(d) -> str:
    out = []
    for cand in d.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("text"):
                out.append(part["text"])
    return "".join(out)


def _check_status(code, raw: bytes, think_off, model=None):
    """Returns (retry_next:bool, message). Raises LLMError for fatal errors."""
    msg = _err_text(raw)
    low = msg.lower()
    if code in (400, 401, 403) and ("api key" in low or "permission" in low or "api_key" in low):
        raise LLMError("Your Gemini API key was rejected. Open Settings and paste a valid key.")
    last = f"{code}: {msg}"
    if code == 404 and model:
        _dead.add(model)
    if code == 400 and think_off and model:
        _nothink.add(model)
    if code in (404, 429, 500, 503) or (code == 400 and think_off):
        return True, last
    raise LLMError(last)


async def _once(model, body):
    url = f"{BASE}/{model}:generateContent"
    r = await client().post(url, headers={"x-goog-api-key": settings.api_key, "Content-Type": "application/json"},
                            json=body, timeout=httpx.Timeout(45, connect=10))
    if r.status_code != 200:
        return None, r
    d = r.json()
    pf = d.get("promptFeedback", {})
    if pf.get("blockReason"):
        raise LLMError(f"The request was blocked by the model safety filter ({pf['blockReason']}).")
    return _parts_text(d), r


async def stream(system: str, contents: list, max_tokens: int = 1500, temperature: float = 0.2, json_mode: bool = False):
    """Async generator yielding text deltas."""
    if not settings.api_key:
        raise LLMError("NO_KEY")
    last = "Unknown error"
    net_err = None
    for model, think_off in await _attempts():
        body = _body(system, contents, max_tokens, temperature, json_mode, think_off)
        headers = {"x-goog-api-key": settings.api_key, "Content-Type": "application/json"}
        got = False
        try:
            async with client().stream("POST", f"{BASE}/{model}:streamGenerateContent?alt=sse",
                                       headers=headers, json=body) as r:
                if r.status_code != 200:
                    retry, last = _check_status(r.status_code, await r.aread(), think_off, model)
                    continue
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        d = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    pf = d.get("promptFeedback", {})
                    if pf.get("blockReason"):
                        raise LLMError(f"The request was blocked by the model safety filter ({pf['blockReason']}).")
                    t = _parts_text(d)
                    if t:
                        got = True
                        yield t
            if got:
                return
            last = "Empty response from model"
        except httpx.HTTPError as e:
            if got:
                raise LLMError(_net_msg(e))
            net_err = e
            # Some proxies / antivirus tools buffer streamed (SSE) responses: retry once without streaming.
            if isinstance(e, NET_ERRORS):
                try:
                    text, resp = await _once(model, body)
                except httpx.HTTPError as e2:
                    net_err = e2
                    continue
                if text is None:
                    _, last = _check_status(resp.status_code, resp.content, think_off, model)
                    continue
                if text:
                    yield text
                    return
                last = "Empty response from model"
            elif isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
                break  # no point trying other models if we cannot connect at all
    if net_err is not None and "Empty" not in last and last == "Unknown error":
        raise LLMError(_net_msg(net_err))
    if "429" in last or "quota" in last.lower():
        raise LLMError("Rate limit reached on the free Gemini tier. Wait a few seconds and try again.")
    raise LLMError(f"Gemini error - {last}")


async def generate(system, contents, **kw) -> str:
    return "".join([t async for t in stream(system, contents, **kw)])
