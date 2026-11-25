"""Claude-written match explanations and proposal drafts.

Grounding rules (PRD section 7):
- Claude only sees the facts behind the match score: skills matched and missing, rate vs budget,
  experience, rating, Job Success, portfolio items and the profile bio. Never names or locations.
- The prompt tells it to cite only those facts, be honest about gaps, and never mention personal
  attributes.
- If there is no ANTHROPIC_API_KEY, or a call fails, is refused or is slow, the functions return None
  and the app keeps its template explanations. AI is an upgrade, never a dependency.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from . import matching

log = logging.getLogger("gigwise.ai")

MODEL = "claude-opus-5-5"
# Fall back to another model automatically if a request is declined by a safety classifier.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Without login anyone can trigger these calls, so cap them per server process.
MAX_CALLS_PER_MINUTE = int(os.getenv("AI_MAX_CALLS_PER_MINUTE", "30"))

EXPLAIN_SYSTEM = """You write short match explanations for Gigwise, a freelance marketplace.
For each candidate in the input, write:
- client_reason: one or two sentences, at most 45 words, telling the client why this freelancer was suggested for their project.
- freelancer_reason: one sentence, at most 35 words, telling the freelancer why they fit this project, addressed as "you".

Rules:
- Use only facts in the input. Never invent experience, clients, results, tools or numbers.
- Lead with the strongest reasons, and be honest about gaps: if required skills are missing or the rate is above the budget, say so plainly.
- Never mention or guess a person's name, gender, age, nationality, location, religion or any other personal attribute, even if the bio hints at one.
- Plain, friendly English. No markdown, emojis or exclamation marks."""

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "explanations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "client_reason": {"type": "string"},
                    "freelancer_reason": {"type": "string"},
                },
                "required": ["id", "client_reason", "freelancer_reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["explanations"],
    "additionalProperties": False,
}

DRAFT_SYSTEM = """You draft proposals (cover letters) for freelancers on Gigwise, a freelance marketplace.
Write in the freelancer's voice, first person, 110 to 170 words, as plain text.

Rules:
- Use only facts in the input about the freelancer. Never invent clients, results, numbers, tools or experience.
- Open with why they fit this specific project, mention their most relevant portfolio work, and briefly explain how they would approach the work.
- If required skills are missing, acknowledge it honestly and say how they would cover it.
- If the client asked screening questions, do not answer them here; they are answered separately.
- No placeholders such as [Client name], no greeting line with a name, no sign-off with a name, no markdown or emojis.
- End with a short next step, such as offering a quick call."""

_client = None
_client_lock = threading.Lock()
_cache: "OrderedDict[str, Any]" = OrderedDict()
_cache_lock = threading.Lock()
_calls: List[float] = []


def api_key() -> str:
    # Remove spaces, line breaks and invisible characters that sneak in when pasting a key.
    return "".join(ch for ch in os.getenv("ANTHROPIC_API_KEY", "") if ch.isprintable() and not ch.isspace())


def enabled() -> bool:
    return bool(api_key())


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            import anthropic

            _client = anthropic.Anthropic(api_key=api_key(), timeout=25.0, max_retries=1)
        return _client


def _allow_call() -> bool:
    now = time.time()
    with _cache_lock:
        while _calls and now - _calls[0] > 60:
            _calls.pop(0)
        if len(_calls) >= MAX_CALLS_PER_MINUTE:
            return False
        _calls.append(now)
        return True


def _cache_get(key: str):
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key: str, value: Any) -> None:
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > 1000:
            _cache.popitem(last=False)


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _call(system: str, payload: Dict[str, Any], max_tokens: int, schema: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """One Claude request. Returns the text, or None on any failure (the caller falls back)."""
    if not enabled() or not _allow_call():
        return None
    import anthropic

    output_config: Dict[str, Any] = {"effort": "low"}  # short, factual writing: keep it quick
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config=output_config,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except anthropic.AuthenticationError:
        log.warning("Claude API key was rejected; using template text")
        return None
    except anthropic.RateLimitError:
        log.warning("Claude API rate limit reached; using template text")
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s; using template text: %s", e.status_code, str(e)[:200])
        return None
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
        log.warning("Could not reach the Claude API; using template text: %s", e)
        return None
    if response.stop_reason in ("refusal", "max_tokens"):
        log.warning("Claude response ended with %s; using template text", response.stop_reason)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    return text or None


def _rate_fact(m: Dict[str, Any]) -> Dict[str, Any]:
    f, p = m["_f"], m["_p"]
    fact = {"hourly_rate_usd": float(f["rate"])}
    if p.get("type") == "hourly":
        fact["client_hourly_range_usd"] = [float(p["rate_min"]), float(p["rate_max"])]
    else:
        fact["client_budget_usd"] = float(p["budget"])
        fact["budget_per_hour_usd"] = round(float(p["budget"]) / float(p["hours"]), 2)
    fact["within_budget"] = float(f["rate"]) <= m["target_rate"]
    return fact


def _candidate_facts(m: Dict[str, Any], label: str) -> Dict[str, Any]:
    """The only freelancer facts Claude sees. No name, no location."""
    f = m["_f"]
    return {
        "id": label,
        "professional_title": f["title"],
        "match_score_out_of_100": m["total"],
        "matched_required_skills": m["matched"],
        "missing_required_skills": m["missing"],
        "other_skills": [s for s in f.get("skills", []) if s not in m["matched"]],
        **_rate_fact(m),
        "years_experience": f.get("years"),
        "average_rating": float(f["rating"]) if f.get("rating") else None,
        "completed_jobs": f.get("jobs", 0),
        "job_success_percent": f.get("jss"),
        "portfolio": [{"title": x.get("title"), "description": x.get("description")} for x in f.get("portfolio") or []],
        "bio": f.get("bio", ""),
    }


def _project_facts(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": p["title"],
        "description": p.get("description", ""),
        "required_skills": p.get("skills", []),
        "payment_type": p.get("type"),
        "estimated_hours": p.get("hours"),
        "experience_level": p.get("level"),
        "project_length": p.get("duration"),
    }


def explain(project: Dict[str, Any], freelancers: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Return {freelancer_id: {"client_reason", "freelancer_reason"}} for as many as possible.
    Freelancers missing from the result keep their template explanation."""
    results: Dict[str, Dict[str, str]] = {}
    todo = []
    for f in freelancers[:8]:
        m = matching.score(f, project)
        facts = _candidate_facts(m, "?")
        key = "explain:" + _digest([_project_facts(project), facts])
        cached = _cache_get(key)
        if cached:
            results[f["id"]] = cached
        else:
            todo.append((f, m, key))
    if not todo or not enabled():
        return results
    labels = {chr(ord("A") + i): item for i, item in enumerate(todo)}
    payload = {"project": _project_facts(project),
               "candidates": [_candidate_facts(m, label) for label, (_, m, _) in labels.items()]}
    text = _call(EXPLAIN_SYSTEM, payload, max_tokens=6000, schema=EXPLAIN_SCHEMA)
    if not text:
        return results
    try:
        items = json.loads(text)["explanations"]
    except (ValueError, KeyError, TypeError):
        log.warning("Claude returned unexpected JSON; using template text")
        return results
    for item in items:
        if item.get("id") not in labels:
            continue
        f, _, key = labels[item["id"]]
        client_reason = " ".join(str(item.get("client_reason", "")).split())[:400]
        freelancer_reason = " ".join(str(item.get("freelancer_reason", "")).split())[:300]
        if client_reason and freelancer_reason:
            value = {"client_reason": client_reason, "freelancer_reason": freelancer_reason}
            _cache_put(key, value)
            results[f["id"]] = value
    return results


def draft_proposal(project: Dict[str, Any], freelancer: Dict[str, Any], bid: Optional[float] = None,
                   days: Optional[int] = None) -> Optional[str]:
    """A cover letter grounded in the freelancer's profile, or None (the app then uses its template)."""
    m = matching.score(freelancer, project)
    facts = _candidate_facts(m, "you")
    facts.pop("id")
    payload = {"project": _project_facts(project), "freelancer": facts,
               "proposed_bid_usd": bid, "proposed_delivery_days": days}
    key = "draft:" + _digest(payload)
    cached = _cache_get(key)
    if cached:
        return cached
    text = _call(DRAFT_SYSTEM, payload, max_tokens=4000)
    if not text:
        return None
    text = text.strip()[:2500]
    _cache_put(key, text)
    return text
