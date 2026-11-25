"""Supabase connection. Settings come from gigwise/backend/.env (never committed)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class NotConfigured(RuntimeError):
    pass


def settings_problem() -> Optional[str]:
    """Return a human-readable problem with the settings, or None if they look fine."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url:
        return "SUPABASE_URL is missing from gigwise/backend/.env"
    if not url.startswith("https://") or ".supabase.co" not in url:
        return "SUPABASE_URL should look like https://<project>.supabase.co"
    if not key:
        return "SUPABASE_SERVICE_ROLE_KEY is missing from gigwise/backend/.env"
    return None


@lru_cache(maxsize=1)
def get_client():
    problem = settings_problem()
    if problem:
        raise NotConfigured(problem)
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip())


def allowed_origins() -> list:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765")
    return [o.strip() for o in raw.split(",") if o.strip()]
