"""Supabase connection. Settings come from gigwise/backend/.env (never committed)."""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class NotConfigured(RuntimeError):
    pass


def _clean(value: str) -> str:
    """Remove spaces, line breaks and invisible characters that sneak in when a key is pasted
    into a web form (Render, a text editor). Keys never contain them."""
    return re.sub(r"[\s\u200b-\u200d\u2060\ufeff]+", "", value or "")


def supabase_url() -> str:
    return _clean(os.getenv("SUPABASE_URL", "")).rstrip("/")


def supabase_key() -> str:
    return _clean(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


def settings_problem() -> Optional[str]:
    """Return a human-readable problem with the settings, or None if they look fine."""
    url, key = supabase_url(), supabase_key()
    if not url:
        return "SUPABASE_URL is missing"
    if not url.startswith("https://") or ".supabase.co" not in url:
        return "SUPABASE_URL should look like https://<project>.supabase.co"
    if not key:
        return "SUPABASE_SERVICE_ROLE_KEY is missing"
    if not key.isascii() or not key.isprintable():
        return "SUPABASE_SERVICE_ROLE_KEY contains unusual characters. Copy it again with Supabase's copy button."
    if key.startswith("sb_publishable_"):
        return "SUPABASE_SERVICE_ROLE_KEY is the public (publishable) key. Use the secret key instead."
    return None


_local = threading.local()


def get_client():
    """One Supabase client per thread (FastAPI runs requests on several threads at once).

    The connection uses plain HTTP/1.1: HTTP/2 to Supabase failed on Render with protocol
    errors, and HTTP/1.1 behaves the same everywhere."""
    client = getattr(_local, "client", None)
    if client is None:
        problem = settings_problem()
        if problem:
            raise NotConfigured(problem)
        import httpx
        from supabase import ClientOptions, create_client

        http = httpx.Client(http2=False, timeout=httpx.Timeout(30.0, connect=10.0))
        client = create_client(supabase_url(), supabase_key(), options=ClientOptions(httpx_client=http))
        _local.client = client
    return client


def _clear_clients():
    _local.__dict__.clear()


get_client.cache_clear = _clear_clients  # used by tests


def allowed_origins() -> list:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765")
    return [o.strip() for o in raw.split(",") if o.strip()]
