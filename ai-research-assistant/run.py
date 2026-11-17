#!/usr/bin/env python3
"""One-click launcher: creates a virtual-env, installs dependencies (first run only), asks for the
free Gemini key (first run only), starts the server and opens your browser."""
import hashlib, os, socket, subprocess, sys, threading, time, venv, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQ = ROOT / "requirements.txt"
ENV = ROOT / ".env"
IS_WIN = os.name == "nt"
PY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def say(msg=""):
    print(msg, flush=True)


def banner():
    say("\n  ┌──────────────────────────────────────────────┐")
    say("  │   Paper Assistant · AI Research Paper Helper │")
    say("  └──────────────────────────────────────────────┘\n")


def ensure_python():
    if sys.version_info < (3, 10):
        say(f"  ✗ Python 3.10+ is required (you have {sys.version.split()[0]}).")
        say("    Download it from https://www.python.org/downloads/  (tick 'Add Python to PATH').")
        sys.exit(1)


def ensure_venv_and_deps():
    if not PY.exists():
        say("  • Creating private environment (first run only)…")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV)
    stamp = VENV / ".req_hash"
    h = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if stamp.exists() and stamp.read_text() == h:
        return
    say("  • Installing dependencies (first run only, about 30 seconds)…")
    cmd = [str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check", "--prefer-binary", "-r", str(REQ)]
    if subprocess.call(cmd) != 0:
        say("\n  ✗ Dependency install failed. Check your internet connection and run this again.")
        sys.exit(1)
    stamp.write_text(h)


def read_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"\'')
    return ""


def ask_key():
    if read_key() or not sys.stdin or not sys.stdin.isatty():
        return
    say("  Fast AI answers use Google Gemini (free key, takes 30 seconds):")
    say("    1) Open  https://aistudio.google.com/apikey   2) Click 'Create API key'   3) Paste it below.\n")
    try:
        key = input("  Paste your Gemini API key (or press Enter to add it later in the app): ").strip()
    except EOFError:
        key = ""
    if key:
        lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
        lines = [l for l in lines if not l.startswith("GEMINI_API_KEY=")]
        lines.append(f"GEMINI_API_KEY={key}")
        ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
        say("  ✓ Key saved to .env\n")


def free_port(start=8000):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def open_when_ready(port, proc):
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        if proc.poll() is not None:
            return
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                say(f"\n  ✓ Running at {url}   (press Ctrl+C to stop)\n")
                webbrowser.open(url)
                return
        time.sleep(0.2)


def main():
    os.chdir(ROOT)
    banner()
    ensure_python()
    ensure_venv_and_deps()
    ask_key()
    port = free_port()
    say("  • Starting server…")
    proc = subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
                             "--log-level", "warning"], cwd=ROOT)
    threading.Thread(target=open_when_ready, args=(port, proc), daemon=True).start()
    try:
        proc.wait()
    except KeyboardInterrupt:
        say("\n  Stopping…")
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    main()
