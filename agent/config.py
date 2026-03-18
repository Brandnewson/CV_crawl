"""Configuration helpers for agent modules."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Load .env file once at import
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"

MODEL_ALIASES = {
    "claude-3-5-haiku": DEFAULT_CLAUDE_MODEL,
    "claude-3-5-haiku-20241022": DEFAULT_CLAUDE_MODEL,
    "claude-haiku-4-5": DEFAULT_CLAUDE_MODEL,
    "claude-haiku-4.5": DEFAULT_CLAUDE_MODEL,
    "haiku": DEFAULT_CLAUDE_MODEL,
}


def get_claude_model() -> str:
    """
    Get the Claude model to use for LLM calls.

    Reads from CLAUDE_MODEL env variable.
    Falls back to a known-valid Haiku 4.5 model if not set.

    Returns: Model name string
    """
    raw_model = os.getenv("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL).strip()
    return MODEL_ALIASES.get(raw_model, raw_model)
