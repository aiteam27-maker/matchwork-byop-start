"""Who is making this request.

Requests with an "Authorization: Bearer <token>" header come from a signed-in user. The token is a
Supabase login session, checked with Supabase (so this server never sees or stores passwords).
Requests without one come from a demo visitor, who only ever sees the investor demo data.

The token is kept per request in a context variable, so any helper can ask for the current user
without passing it through every function. app.main.parallel() copies the context into its workers.
"""
from __future__ import annotations

import contextvars
import hashlib
import threading
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException

from .db import get_client

_TOKEN: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("gw_token", default=None)
_CACHE: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("gw_request_cache", default=None)


class AuthMiddleware:
    """Reads the login token from each request. It never rejects a request itself: endpoints decide
    what a demo visitor or a signed-in user may do."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = None
        for name, value in scope.get("headers") or []:
            if name == b"authorization":
                v = value.decode("latin-1").strip()
                if v.lower().startswith("bearer ") and len(v) > 7:
                    token = v[7:].strip()
                break
        t1, t2 = _TOKEN.set(token), _CACHE.set({})
        try:
            await self.app(scope, receive, send)
        finally:
            _TOKEN.reset(t1)
            _CACHE.reset(t2)


def request_cache() -> Dict[str, Any]:
    """A dict that lives for one request (shared by the workers that request starts)."""
    c = _CACHE.get()
    if c is None:  # called outside a request (tests, scripts)
        c = {}
        _CACHE.set(c)
    return c


# Checked tokens are remembered for a few minutes, so most requests skip the round trip to Supabase.
_SEEN: Dict[str, Any] = {}
_SEEN_LOCK = threading.Lock()
SEEN_SECONDS = 300
SEEN_MAX = 5000


def _check_with_supabase(token: str) -> Optional[Dict[str, Any]]:
    try:
        res = get_client().auth.get_user(token)
    except Exception:
        return None
    u = getattr(res, "user", None)
    if not u:
        return None
    return {"id": str(u.id), "email": getattr(u, "email", None) or ""}


def current_user() -> Optional[Dict[str, Any]]:
    """The signed-in user ({id, email}), None for a demo visitor. A token that isn't valid (expired,
    signed out, made up) gets a 401 so the app can ask the person to log in again."""
    token = _TOKEN.get()
    if not token:
        return None
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    with _SEEN_LOCK:
        hit = _SEEN.get(key)
        if hit and hit[1] > now:
            return hit[0]
    user = _check_with_supabase(token)
    if not user:
        raise HTTPException(401, "Your login has expired. Please log in again.")
    with _SEEN_LOCK:
        if len(_SEEN) >= SEEN_MAX:
            for k in [k for k, v in _SEEN.items() if v[1] <= now] or list(_SEEN)[: SEEN_MAX // 10]:
                _SEEN.pop(k, None)
        _SEEN[key] = (user, now + SEEN_SECONDS)
    return user


def forget_tokens() -> None:
    with _SEEN_LOCK:
        _SEEN.clear()
