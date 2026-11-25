"""Gigwise match score.

A Python port of the scoring used in gigwise/frontend/index.html, so the
server and the browser give the same numbers.

Score (0-100) = weighted blend of five signals:
    skills 45%, profile text similarity 20%, budget fit 20%,
    experience 8%, ratings 7%.

Only profile facts are used. Name, location, photo and other personal
attributes are never read here.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

WEIGHTS = {"skills": 0.45, "text": 0.20, "budget": 0.20, "exp": 0.08, "rating": 0.07}
LABELS = {
    "skills": "Skill coverage",
    "text": "Profile similarity",
    "budget": "Budget fit",
    "exp": "Experience",
    "rating": "Ratings",
}

ALIAS = {
    "node": "node.js", "nodejs": "node.js", "react.js": "react", "reactjs": "react",
    "ui": "ui design", "ui/ux": "ui design", "ux": "ux research", "ml": "machine learning",
    "js": "javascript", "ts": "typescript", "postgres": "postgresql", "gpt": "llm",
    "next": "next.js",
}

STOP = set(
    "the a an and or to of for in on with is are we i our us you your need needs want wants "
    "build building builds looking app apps that this it as be by from will can who which into "
    "plus also simple clean new one using use like get some more all any has have their them "
    "they its per via".split(" ")
)

# Keyword rules used to detect skills when a client leaves them blank.
KW = [
    (r"\bmobile|\bios\b|\bandroid|\biphone", ["Flutter"]),
    (r"chat ?bot|\bai\b|\bgpt|\bllm|language model|\bassistant", ["LLM"]),
    (r"\bwebsite|\bweb ?app|\blanding page", ["React"]),
    (r"\bstore\b|\bshopify|e-?commerce", ["Shopify"]),
    (r"\bpayment|\bcheckout|\bsubscription", ["Stripe"]),
    (r"\bbackend|\bapi\b|\baccounts?\b|\blogin", ["Node.js", "Firebase"]),
    (r"\blogo|\bbrand(ing| kit)", ["Branding"]),
    (r"\bdesign|\bui\b|\bux\b|\binterface", ["UI Design"]),
    (r"\bblog|\bseo\b|\bcopy\b", ["SEO", "Copywriting"]),
    (r"\bdatabase|\bsql\b", ["PostgreSQL"]),
    (r"\brecommend|\bpredict|machine learning|\bml\b", ["Machine Learning"]),
    (r"\bdashboard|\banalytics", ["React", "Data Analysis"]),
    (r"\bpython\b", ["Python"]),
    (r"\brag\b|help (center|articles)|knowledge base", ["NLP"]),
]

CATEGORIES = [
    ("Mobile apps", ["Flutter", "React Native", "Swift", "iOS", "Dart"]),
    ("Web development", ["React", "Next.js", "Node.js", "TypeScript", "PostgreSQL", "REST API", "JavaScript"]),
    ("AI & data", ["LLM", "Python", "Machine Learning", "NLP", "LangChain", "Data Analysis", "SQL"]),
    ("Design", ["UI Design", "Figma", "Branding", "Logo Design", "UX Research", "Illustration"]),
    ("Writing & SEO", ["Copywriting", "SEO", "Blogging", "Content Strategy"]),
    ("E-commerce", ["Shopify", "Liquid", "Stripe"]),
]


def js_round(x: float) -> int:
    """Round like JavaScript's Math.round (halves go up), not Python's banker's rounding."""
    return int(math.floor(x + 0.5))


def nk(skill: str) -> str:
    s = str(skill).lower().strip()
    return ALIAS.get(s, s)


def tok(text: str) -> List[str]:
    out = []
    for w in re.findall(r"[a-z0-9+#.]{3,}", str(text).lower()):
        w = w.rstrip(".")
        if len(w) > 4 and re.search(r"[^s]s$", w):
            w = w[:-1]
        if len(w) >= 3 and w not in STOP:
            out.append(w)
    return out


def all_skills(freelancers: List[Dict[str, Any]]) -> List[str]:
    return sorted({s for f in freelancers for s in f.get("skills") or []})


def detect_skills(text: str, freelancers: List[Dict[str, Any]]) -> List[str]:
    """Detect up to 6 skills from a project title and description."""
    t = str(text).lower()
    found: List[str] = []
    for pattern, skills in KW:
        if re.search(pattern, t):
            found.extend(skills)
    for s in all_skills(freelancers):
        if re.search(r"(^|[^a-z0-9])" + re.escape(s.lower()) + r"($|[^a-z0-9])", t):
            found.append(s)
    seen, res = set(), []
    for s in found:
        k = nk(s)
        if k not in seen:
            seen.add(k)
            res.append(s)
    return res[:6]


def category_of(skills: List[str]) -> str:
    best, best_n = "Other", 0
    for name, cat_skills in CATEGORIES:
        n = sum(1 for s in skills if any(nk(x) == nk(s) for x in cat_skills))
        if n > best_n:
            best, best_n = name, n
    return best


def target_rate(project: Dict[str, Any]) -> float:
    if project.get("type") == "hourly":
        return float(project["rate_max"])
    return float(project["budget"]) / float(project["hours"])


def _portfolio_text(f: Dict[str, Any]) -> str:
    return " ".join(f"{p.get('title', '')} {p.get('description', '')}" for p in f.get("portfolio") or [])


def score(f: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    """Score one freelancer against one project."""
    req = list(p.get("skills") or [])
    fs = {nk(s) for s in f.get("skills") or []}
    matched = [s for s in req if nk(s) in fs]
    missing = [s for s in req if nk(s) not in fs]
    cov = len(matched) / len(req) if req else 0.0

    a = set(tok(f"{p['title']} {p.get('description', '')} {' '.join(req)}"))
    b = set(tok(f"{f['title']} {f.get('bio', '')} {' '.join(f.get('skills') or [])} {_portfolio_text(f)}"))
    shared = [w for w in a if w in b]
    cos = len(shared) / math.sqrt(len(a) * len(b)) if a and b else 0.0
    text = min(1.0, cos / 0.3)

    target = target_rate(p)
    rate = float(f["rate"])
    over = (rate - target) / target
    budget = 1.0 if over <= 0 else max(0.0, 1 - over * 1.25)

    exp = min(int(f.get("years") or 0), 10) / 10
    rating = float(f["rating"]) / 5 if f.get("rating") else 0.7

    parts = {"skills": cov, "text": text, "budget": budget, "exp": exp, "rating": rating}
    total = js_round(100 * sum(WEIGHTS[k] * parts[k] for k in WEIGHTS))

    if not f.get("available", True):
        why = "Not available for new work"
    elif not matched:
        why = "No required skills"
    else:
        why = ""

    port, best = None, 1
    for item in f.get("portfolio") or []:
        n = len([w for w in tok(f"{item.get('title', '')} {item.get('description', '')}") if w in a])
        if n > best:
            best, port = n, item

    return {
        "freelancer_id": f["id"],
        "project_id": p["id"],
        "total": total,
        "tier": tier(total),
        "parts": {k: round(v, 4) for k, v in parts.items()},
        "points": {k: round(parts[k] * WEIGHTS[k] * 100, 1) for k in WEIGHTS},
        "matched": matched,
        "missing": missing,
        "shared_terms": shared[:6],
        "target_rate": target,
        "portfolio_item": port,
        "eligible": not why,
        "filtered_reason": why or None,
        "_f": f,
        "_p": p,
    }


def tier(total: int) -> str:
    if total >= 80:
        return "Top match"
    if total >= 65:
        return "Strong match"
    if total >= 50:
        return "Good match"
    return "Partial match"


def _list3(items: List[str]) -> str:
    return ", ".join(items) if len(items) <= 3 else ", ".join(items[:3]) + f" +{len(items) - 3}"


def _budget_phrase(m: Dict[str, Any], for_freelancer: bool) -> str:
    f, p = m["_f"], m["_p"]
    yr = "their" if for_freelancer else "your"
    lead = "Your " if for_freelancer else ""
    rate = f["rate"]
    rate_s = f"${rate:g}"
    if p.get("type") == "hourly":
        hi, lo = p["rate_max"], p["rate_min"]
        if rate > hi:
            return f"{lead}{rate_s}/hr is {js_round((rate / hi - 1) * 100)}% above {yr} ${hi:g}/hr max"
        where = "below" if rate < lo else "within"
        return f"{lead}{rate_s}/hr is {where} {yr} ${lo:g}–${hi:g}/hr range"
    t = js_round(m["target_rate"])
    if rate <= m["target_rate"]:
        return f"{lead}{rate_s}/hr fits {yr} ~${t}/hr budget"
    return f"{lead}{rate_s}/hr is {js_round((rate / m['target_rate'] - 1) * 100)}% above {yr} ~${t}/hr budget"


def reason_for_client(m: Dict[str, Any]) -> str:
    """Grounded one-line reason shown to the client. Cites profile facts only."""
    f, p, matched = m["_f"], m["_p"], m["matched"]
    s = f"Covers {len(matched)} of {len(p['skills'])} required skills"
    if matched:
        s += f" ({_list3(matched)})"
    s += ". " + _budget_phrase(m, False)
    years = int(f.get("years") or 0)
    s += f", {years} yr{'' if years == 1 else 's'} experience"
    s += f", {float(f['rating']):.1f}★ over {f.get('jobs', 0)} jobs." if f.get("rating") else ", no ratings yet."
    if m["portfolio_item"]:
        s += f" Built “{m['portfolio_item']['title']}”."
    return s


def reason_for_freelancer(m: Dict[str, Any]) -> str:
    """Grounded 'why you fit' note shown to the freelancer."""
    p, matched, missing = m["_p"], m["matched"], m["missing"]
    s = f"You have {len(matched)} of {len(p['skills'])} skills they need"
    if missing:
        s += f" (missing {_list3(missing)})"
    s += ". " + _budget_phrase(m, True) + "."
    if m["portfolio_item"]:
        s += f" Mention your “{m['portfolio_item']['title']}” project."
    return s


def public(m: Dict[str, Any], for_freelancer: bool = False) -> Dict[str, Any]:
    """Strip internal fields and attach the reason text."""
    out = {k: v for k, v in m.items() if not k.startswith("_")}
    out["reason"] = reason_for_freelancer(m) if for_freelancer else reason_for_client(m)
    return out


def rank_freelancers(project: Dict[str, Any], freelancers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rank freelancers for a project. Hard filters first, then score (PRD section 7)."""
    scored = [score(f, project) for f in freelancers]
    ranked = sorted(
        (m for m in scored if m["eligible"]),
        key=lambda m: (-m["total"], -(float(m["_f"].get("rating") or 0))),
    )
    hidden = [m for m in scored if not m["eligible"]]
    return {
        "ranked": [public(m) for m in ranked],
        "hidden": [{"freelancer_id": m["freelancer_id"], "reason": m["filtered_reason"]} for m in hidden],
    }


def rank_projects(freelancer: Dict[str, Any], projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reverse matching: open projects ranked for one freelancer."""
    scored = [score(freelancer, p) for p in projects if p.get("status") == "open"]
    ranked = sorted((m for m in scored if m["matched"]), key=lambda m: -m["total"])
    return [public(m, for_freelancer=True) for m in ranked]


def connects_cost(project: Dict[str, Any]) -> int:
    b = float(project["budget"])
    return 2 if b < 1000 else 4 if b < 5000 else 6


def badges(f: Dict[str, Any]) -> List[str]:
    """Display-only badges. Not part of the match score."""
    out: List[str] = []
    jss: Optional[int] = f.get("jss")
    jobs = int(f.get("jobs") or 0)
    rating = float(f.get("rating") or 0)
    if jss:
        out.append(f"{jss}% Job Success")
    if jss and jss >= 90 and jobs >= 40 and rating >= 4.8:
        out.append("Top Rated Plus")
    elif jss and jss >= 90 and jobs >= 15 and rating >= 4.7:
        out.append("Top Rated")
    elif jobs < 10 and (not f.get("rating") or rating >= 4.5):
        out.append("Rising Talent")
    return out
