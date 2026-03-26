"""Settings loader for API credentials used by agents."""

from __future__ import annotations

import os

import streamlit as st


def _read_secret(name: str) -> str | None:
    """Fetch a secret from Streamlit secrets first, then environment vars."""
    value = None
    try:
        if name in st.secrets:
            value = st.secrets[name]
    except Exception:
        value = None

    if value:
        return str(value)
    return os.getenv(name)


def _required_secret(name: str) -> str:
    # Fail fast at import time so missing credentials are surfaced immediately.
    value = _read_secret(name)
    if value:
        return value
    raise RuntimeError(
        f"Missing required secret '{name}'. Set it in .streamlit/secrets.toml "
        f"or as an environment variable."
    )


GEMINI_API_KEY: str = _required_secret("GEMINI_API_KEY")
SERPER_API_KEY: str = _required_secret("SERPER_API_KEY")
