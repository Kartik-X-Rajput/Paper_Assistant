"""Configuration: reads/writes a simple .env file in the project root."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "assistant.db"

MAX_UPLOAD_MB = 50
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.5-flash"]


def _read_env() -> dict:
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Settings:
    def __init__(self):
        self.reload()

    def reload(self):
        env = _read_env()
        self.api_key = os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_MODEL") or env.get("GEMINI_MODEL", "") or DEFAULT_MODEL

    def save(self, api_key: str | None = None, model: str | None = None):
        env = _read_env()
        if api_key is not None:
            env["GEMINI_API_KEY"] = api_key.strip()
        if model is not None:
            env["GEMINI_MODEL"] = model.strip() or DEFAULT_MODEL
        ENV_FILE.write_text(
            "# Free key: https://aistudio.google.com/apikey\n"
            + "".join(f"{k}={v}\n" for k, v in env.items()),
            encoding="utf-8",
        )
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GEMINI_MODEL", None)
        self.reload()


settings = Settings()
