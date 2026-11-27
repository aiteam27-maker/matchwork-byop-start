"""Gigwise API (FastAPI + Supabase).

Run from gigwise/backend:   .venv/bin/uvicorn app.main:app --reload --port 8000
Interactive docs:           http://localhost:8000/docs

Two separate worlds share the database:
- Demo: requests without a login token. Anyone can try the investor demo: "you" as a client are the
  demo client (Pulse Fit), and freelancer actions name any demo freelancer.
- Real: requests from a signed-in user (Supabase login, see app/auth.py). They only see real data,
  act only as their own client and freelancer profiles, and only see their own private data.
"""
from __future__ import annotations

import contextvars
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import ai, matching
from .auth import AuthMiddleware, current_user, request_cache
from .db import NotConfigured, allowed_origins, get_client, settings_problem

app = FastAPI(title="Gigwise API", version="0.1.0",
              description="Freelance marketplace with explained match scores.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

LEVELS = ("Entry", "Intermediate", "Expert")
DURATIONS = ("Less than 1 month", "1 to 3 months", "3 to 6 months", "More than 6 months")


# ---------------------------------------------------------------- helpers
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def money(x: float) -> str:
    return f"${matching.js_round(float(x)):,}"


def db():
    try:
        return get_client()
    except NotConfigured as e:
        raise HTTPException(503, f"Database not configured: {e}")


def rows(query) -> List[Dict[str, Any]]:
    return query.execute().data or []


WORLD_TABLES = ("clients", "freelancers", "projects")


def one(table: str, id_: str, what: str) -> Dict[str, Any]:
    """One row by id. Clients, freelancers and projects from the other world (demo vs real) count as
    not found, so the two worlds never see each other."""
    r = rows(db().table(table).select("*").eq("id", id_).limit(1))
    if not r or (table in WORLD_TABLES and r[0].get("world", "demo") != world()):
        raise HTTPException(404, f"{what} not found")
    return r[0]


# One shared pool of workers. Each worker keeps its own open Supabase connection (see app/db.py),
# so independent database calls can run at the same time instead of one after another.
_POOL = ThreadPoolExecutor(max_workers=24, thread_name_prefix="gw-db")


def parallel(*calls):
    """Run independent database calls at the same time and return their results in order.
    If one fails, its error is raised (the first failing call in the list wins).
    Each call runs with a copy of this request's context, so it knows who is signed in.
    Don't call parallel() from inside a call passed to parallel()."""
    futures = [_POOL.submit(contextvars.copy_context().run, c) for c in calls]
    return [f.result() for f in futures]


_DEMO = {"client": None, "at": 0.0}


def demo_client() -> Dict[str, Any]:
    """The client you act as until real login exists. Cached for 60 seconds: it's looked up
    on almost every action and almost never changes, so this saves a database round trip."""
    now = time.time()
    if _DEMO["client"] is None or now - _DEMO["at"] > 60:
        r = rows(db().table("clients").select("*").eq("is_demo_user", True).limit(1))
        if not r:
            raise HTTPException(500, "No demo client found. Run the seed script: python -m seed.seed")
        _DEMO.update(client=r[0], at=now)
    return _DEMO["client"]


def forget_demo_client() -> None:
    _DEMO["client"] = None


# ---------------------------------------------------------------- who is asking
class Actor:
    """The person behind this request. world is 'demo' (no login) or 'real' (signed in)."""

    def __init__(self, world: str, user: Optional[Dict[str, Any]] = None,
                 client: Optional[Dict[str, Any]] = None, freelancer: Optional[Dict[str, Any]] = None):
        self.world, self.user, self.client, self.freelancer = world, user, client, freelancer


def actor() -> Actor:
    """Worked out once per request. Signed-in users get their own client and freelancer profiles
    (either may not exist yet). Uses plain sequential queries, so it is safe inside parallel()."""
    cache = request_cache()
    if "actor" not in cache:
        user = current_user()
        if user is None:
            cache["actor"] = Actor("demo")
        else:
            c = rows(db().table("clients").select("*").eq("user_id", user["id"]).limit(1))
            f = rows(db().table("freelancers").select("*").eq("user_id", user["id"]).limit(1))
            cache["actor"] = Actor("real", user, c[0] if c else None, f[0] if f else None)
    return cache["actor"]


def world() -> str:
    return actor().world


def me_client() -> Dict[str, Any]:
    """The client "you" are: the demo client in the demo, your own client profile when signed in."""
    a = actor()
    if a.world == "demo":
        return demo_client()
    if not a.client:
        raise HTTPException(403, "Set up your client profile first")
    return a.client


def as_freelancer(freelancer_id: str) -> Dict[str, Any]:
    """Act as this freelancer. In the demo, any demo freelancer; when signed in, only your own profile."""
    f = one("freelancers", freelancer_id, "Freelancer")
    a = actor()
    if a.world == "real" and (not a.freelancer or a.freelancer["id"] != freelancer_id):
        raise HTTPException(403, "You can only act as your own freelancer profile")
    return f


def is_party(project: Dict[str, Any], freelancer_id: str) -> bool:
    """True if you may see something between this project's client and this freelancer
    (a thread, offer or contract). Everything in the demo is open to demo visitors."""
    a = actor()
    if a.world == "demo":
        return True
    return bool((a.client and project["client_id"] == a.client["id"])
                or (a.freelancer and freelancer_id == a.freelancer["id"]))


def check_party(project: Dict[str, Any], freelancer_id: str) -> None:
    if not is_party(project, freelancer_id):
        raise HTTPException(403, "You're not part of this")


def check_side(side: str, project: Dict[str, Any], freelancer_id: str) -> None:
    """You must be this side ('client' or 'freelancer') of the project + freelancer pair."""
    if side == "client":
        if project["client_id"] != me_client()["id"]:
            raise HTTPException(403, "This belongs to another client")
    else:
        as_freelancer(freelancer_id)


def all_freelancers() -> List[Dict[str, Any]]:
    """Every freelancer in your world (demo or real)."""
    return rows(db().table("freelancers").select("*").eq("world", world()).order("id"))


def with_badges(f: Dict[str, Any]) -> Dict[str, Any]:
    return {**f, "badges": matching.badges(f)}


def own_project(project_id: str) -> Dict[str, Any]:
    p, client = parallel(lambda: one("projects", project_id, "Project"), me_client)
    if p["client_id"] != client["id"]:
        raise HTTPException(403, "This project belongs to another client")
    return p


def log_event(event: str, p: Dict[str, Any], f: Dict[str, Any]) -> None:
    """Feedback loop: record hiring signals with the score at the time (PRD section 7)."""
    db().table("match_events").insert({
        "event": event, "project_id": p["id"], "freelancer_id": f["id"],
        "score": matching.score(f, p)["total"],
    }).execute()


def notify(recipient_type: str, recipient_id: str, body: str, link: str = "") -> None:
    db().table("notifications").insert({
        "recipient_type": recipient_type, "recipient_id": recipient_id, "body": body, "link": link,
    }).execute()


def ensure_thread(project_id: str, freelancer_id: str) -> Dict[str, Any]:
    r = rows(db().table("threads").select("*").eq("project_id", project_id).eq("freelancer_id", freelancer_id))
    if r:
        return r[0]
    return rows(db().table("threads").insert({"project_id": project_id, "freelancer_id": freelancer_id}))[0]


def post_message(thread_id: str, sender: str, body: str) -> Dict[str, Any]:
    return rows(db().table("messages").insert({"thread_id": thread_id, "sender": sender, "body": body}))[0]


def thread_note(project_id: str, freelancer_id: str, *messages, thread: Optional[Dict[str, Any]] = None):
    """Find or open the chat thread, then post messages in order. Returns (thread, [messages])."""
    t = thread or ensure_thread(project_id, freelancer_id)
    return t, [post_message(t["id"], sender, body) for sender, body in messages]


def pending_offer_for(proposal_id: str) -> bool:
    return bool(rows(db().table("offers").select("id").eq("proposal_id", proposal_id).eq("status", "pending")))


def bid_text(bid: float, p: Dict[str, Any]) -> str:
    return f"${bid:g}/hr" if p["type"] == "hourly" else money(bid)


# ---------------------------------------------------------------- request bodies
class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=20, max_length=5000)
    skills: List[str] = Field(default_factory=list, max_length=10,
                              description="Up to 10 skills from GET /taxonomy. Leave empty to detect from the description")
    category: Optional[str] = Field(None, description="A category name from GET /taxonomy. Worked out from the skills if empty")
    type: Literal["fixed", "hourly"] = "fixed"
    budget: Optional[float] = Field(None, gt=0, description="Fixed price total")
    rate_min: Optional[float] = Field(None, gt=0, description="Hourly projects")
    rate_max: Optional[float] = Field(None, gt=0, description="Hourly projects")
    hours: int = Field(gt=0, description="Estimated total hours")
    level: Literal["Entry", "Intermediate", "Expert"] = "Intermediate"
    duration: Literal["Less than 1 month", "1 to 3 months", "3 to 6 months", "More than 6 months"] = "1 to 3 months"
    deadline: Optional[date] = None
    questions: List[str] = Field(default_factory=list, max_length=3)


class ProposalIn(BaseModel):
    freelancer_id: str
    cover_letter: str = Field(min_length=20, max_length=5000)
    bid: float = Field(gt=0, description="Fixed: total USD. Hourly: USD per hour")
    days: int = Field(gt=0)
    answers: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list, max_length=5)


class ProposalEdit(BaseModel):
    freelancer_id: str
    cover_letter: Optional[str] = Field(None, min_length=20, max_length=5000)
    bid: Optional[float] = Field(None, gt=0)
    days: Optional[int] = Field(None, gt=0)
    answers: Optional[List[str]] = None
    links: Optional[List[str]] = Field(None, max_length=5)


class InviteIn(BaseModel):
    freelancer_id: str
    message: str = Field(min_length=1, max_length=2000)


class MessageIn(BaseModel):
    sender: Literal["client", "freelancer"]
    body: str = Field(min_length=1, max_length=5000)


class ReadIn(BaseModel):
    role: Literal["client", "freelancer"]


class NotificationsReadIn(BaseModel):
    recipient_type: Literal["client", "freelancer"]
    recipient_id: str


# ---------------------------------------------------------------- health
@app.get("/health", tags=["system"])
def health():
    problem = settings_problem()
    if problem:
        return {"ok": False, "database": "not configured", "detail": problem}
    try:
        rows(db().table("clients").select("id").limit(1))
        import os
        try:
            rows(db().table("clients").select("world, user_id").limit(1))
        except Exception:
            return {"ok": False, "database": "needs update",
                    "detail": "Run gigwise/backend/sql/002_login.sql in the Supabase SQL Editor."}
        return {"ok": True, "database": "connected",
                "demo_reset": os.getenv("DEMO_RESET_ENABLED", "true").lower() != "false",
                "ai": ai.enabled(), "login": bool(auth_config()["key"])}
    except HTTPException:
        raise
    except Exception as e:  # show the real reason, e.g. tables not created yet
        return {"ok": False, "database": "error", "detail": str(e)[:300]}


def catalog_skills(names: List[str], limit: int) -> List[str]:
    """Map skills to their catalog spelling (accepting known alternative spellings), drop duplicates,
    and reject anything not in the catalog, so clients and freelancers always use the same names."""
    out, unknown = [], []
    for name in names:
        if not str(name).strip():
            continue
        canon = matching.canonical_skill(name)
        if canon is None:
            unknown.append(str(name).strip())
        elif canon not in out:
            out.append(canon)
    if unknown:
        raise HTTPException(422, f"Not in the skill catalog: {', '.join(unknown)}. Pick skills from GET /taxonomy.")
    if len(out) > limit:
        raise HTTPException(422, f"Pick at most {limit} skills")
    return out


@app.get("/taxonomy", tags=["system"])
def taxonomy():
    """The skill catalog: categories > specialties > skills, plus accepted alternative spellings."""
    return matching.TAXONOMY


@app.get("/me", tags=["system"])
def me():
    """Who you are: the demo (no login) or a signed-in user with their client/freelancer profiles."""
    a = actor()
    if a.world == "demo":
        return {"world": "demo", "user": None, "client": demo_client(), "freelancer": None}
    return {"world": "real", "user": a.user, "client": a.client, "freelancer": a.freelancer}


def auth_config() -> Dict[str, str]:
    import os

    from .db import supabase_url
    key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    try:
        url = supabase_url()
    except Exception:
        url = ""
    return {"url": url if key else "", "key": key}


@app.get("/auth/config", tags=["system"])
def get_auth_config():
    """Public settings the browser needs to show login: the Supabase address and its PUBLIC
    (publishable) key. Empty when login isn't set up, and the app then offers only the demo."""
    return auth_config()


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="Your name or your company's name")


@app.post("/clients", status_code=201, tags=["profiles"])
def create_client_profile(body: ClientIn):
    """Signed-in users: create your client profile (one per login)."""
    a = actor()
    if a.world != "real":
        raise HTTPException(401, "Log in to create a client profile")
    if a.client:
        raise HTTPException(409, "You already have a client profile")
    c = rows(db().table("clients").insert({"name": body.name.strip(), "world": "real", "user_id": a.user["id"]}))[0]
    request_cache().pop("actor", None)
    return c


@app.put("/clients/me", tags=["profiles"])
def update_client_profile(body: ClientIn):
    a = actor()
    if a.world != "real" or not a.client:
        raise HTTPException(403, "Set up your client profile first")
    return rows(db().table("clients").update({"name": body.name.strip()}).eq("id", a.client["id"]))[0]


# ---------------------------------------------------------------- freelancers
@app.get("/freelancers", tags=["freelancers"])
def list_freelancers(q: str = "", category: str = "", max_rate: Optional[float] = None,
                     min_rating: Optional[float] = None, available: Optional[bool] = None):
    out = []
    for f in all_freelancers():
        text = f"{f['name']} {f['title']} {' '.join(f['skills'])} {f['bio']}".lower()
        if q and q.lower() not in text:
            continue
        if category and category not in [c for c, sk in matching.CATEGORIES
                                         if any(matching.nk(s) in {matching.nk(x) for x in sk} for s in f["skills"])]:
            continue
        if max_rate is not None and float(f["rate"]) > max_rate:
            continue
        if min_rating is not None and float(f["rating"] or 0) < min_rating:
            continue
        if available is not None and f["available"] != available:
            continue
        out.append(with_badges(f))
    return out


@app.get("/freelancers/{freelancer_id}", tags=["freelancers"])
def get_freelancer(freelancer_id: str):
    f = one("freelancers", freelancer_id, "Freelancer")
    contracts = rows(db().table("contracts").select("id, project_id, projects(title, clients(name))")
                     .eq("freelancer_id", freelancer_id))
    by_id = {c["id"]: c for c in contracts}
    reviews = []
    if by_id:
        for r in rows(db().table("reviews").select("*").in_("contract_id", list(by_id))
                      .eq("direction", "client_to_freelancer").order("created_at", desc=True)):
            proj = by_id[r["contract_id"]].get("projects") or {}
            reviews.append({**r, "project_title": proj.get("title"),
                            "client_name": (proj.get("clients") or {}).get("name")})
    return {**with_badges(f), "reviews": reviews}


@app.get("/freelancers/{freelancer_id}/matches", tags=["matching"])
def matches_for_freelancer(freelancer_id: str):
    """Reverse matching: open projects ranked for this freelancer, with a 'why you fit' note."""
    f = one("freelancers", freelancer_id, "Freelancer")
    projects = rows(db().table("projects").select("*").eq("status", "open").eq("world", world()))
    return matching.rank_projects(f, projects)


# ---------------------------------------------------------------- projects
@app.get("/projects", tags=["projects"])
def list_projects(status: str = "open", mine: bool = False, q: str = "", category: str = "",
                  type: Optional[Literal["fixed", "hourly"]] = None, level: str = "", duration: str = "",
                  min_budget: Optional[float] = None):
    query = db().table("projects").select("*, clients(name, rating, hires)").eq("world", world()) \
        .order("created_at", desc=True)
    if status != "any":
        query = query.eq("status", status)
    if mine:
        query = query.eq("client_id", me_client()["id"])
    out = []
    for p in rows(query):
        if q and q.lower() not in f"{p['title']} {p['description']} {' '.join(p['skills'])}".lower():
            continue
        if (category and p["category"] != category) or (type and p["type"] != type) \
                or (level and p["level"] != level) or (duration and p["duration"] != duration):
            continue
        if min_budget is not None and float(p["budget"]) < min_budget:
            continue
        out.append({**p, "connects_cost": matching.connects_cost(p)})
    return out


@app.get("/projects/{project_id}", tags=["projects"])
def get_project(project_id: str):
    r = rows(db().table("projects").select("*, clients(name, rating, hires)").eq("id", project_id))
    if not r or r[0].get("world", "demo") != world():
        raise HTTPException(404, "Project not found")
    p = r[0]
    count = len(rows(db().table("proposals").select("id").eq("project_id", project_id)))
    return {**p, "proposal_count": count + p["extra_proposals"], "connects_cost": matching.connects_cost(p)}


@app.post("/projects", status_code=201, tags=["projects"])
def create_project(body: ProjectIn):
    """Post a project as yourself (the demo client in the demo). Returns the project and its ranked matches."""
    client, freelancers = parallel(me_client, all_freelancers)
    if body.type == "fixed":
        if not body.budget:
            raise HTTPException(422, "Fixed-price projects need a budget")
        budget = body.budget
    else:
        if not body.rate_min or not body.rate_max:
            raise HTTPException(422, "Hourly projects need rate_min and rate_max")
        if body.rate_max < body.rate_min:
            raise HTTPException(422, "rate_max must be at least rate_min")
        budget = body.rate_max * body.hours
    skills = catalog_skills(body.skills, limit=10)
    if body.category and body.category not in [c for c, _ in matching.CATEGORIES]:
        raise HTTPException(422, f"Unknown category: {body.category}. Pick one from GET /taxonomy.")
    auto = not skills
    if auto:
        skills = matching.detect_skills(f"{body.title} {body.description}", freelancers)
        if not skills:
            raise HTTPException(422, "Couldn't detect skills from the description. Add at least one skill.")
    row = {
        "client_id": client["id"], "world": world(), "title": body.title.strip(), "description": body.description.strip(),
        "skills": skills, "skills_auto": auto, "type": body.type, "budget": budget,
        "rate_min": body.rate_min if body.type == "hourly" else None,
        "rate_max": body.rate_max if body.type == "hourly" else None,
        "hours": body.hours, "level": body.level, "duration": body.duration,
        "deadline": body.deadline.isoformat() if body.deadline else None,
        "questions": [q.strip() for q in body.questions if q.strip()][:3],
        "category": body.category if body.category else matching.category_of(skills),
    }
    p = rows(db().table("projects").insert(row))[0]
    return {"project": p, "matches": matching.rank_freelancers(p, freelancers)}


@app.get("/projects/{project_id}/matches", tags=["matching"])
def matches_for_project(project_id: str):
    """Ranked freelancers with score, breakdown, matched/missing skills and a grounded reason."""
    p = one("projects", project_id, "Project")
    return matching.rank_freelancers(p, all_freelancers())


@app.post("/projects/{project_id}/invites", status_code=201, tags=["projects"])
def invite(project_id: str, body: InviteIn):
    p, client, f = parallel(lambda: one("projects", project_id, "Project"), me_client,
                            lambda: one("freelancers", body.freelancer_id, "Freelancer"))
    if p["client_id"] != client["id"]:
        raise HTTPException(403, "This project belongs to another client")
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")

    def chat():
        t, (_, msg) = thread_note(p["id"], f["id"], ("system", f"{client['name']} invited {f['name']} to this project"),
                                  ("client", body.message.strip()))
        # Read markers use database timestamps, so clock differences can't hide new messages.
        db().table("threads").update({"invited": True, "client_read_at": msg["created_at"]}).eq("id", t["id"]).execute()
        return t

    t, _, _ = parallel(chat,
                       lambda: notify("freelancer", f["id"], f"{client['name']} invited you to “{p['title']}”", f"#/project/{p['id']}"),
                       lambda: log_event("invite", p, f))
    return {"thread_id": t["id"]}


# ---------------------------------------------------------------- proposals
@app.get("/projects/{project_id}/proposals", tags=["proposals"])
def list_proposals(project_id: str):
    """Proposals with each freelancer's match score, for side-by-side comparison."""
    p = own_project(project_id)
    fl = {f["id"]: f for f in all_freelancers()}
    out = []
    for q in rows(db().table("proposals").select("*").eq("project_id", project_id).order("created_at")):
        f = fl[q["freelancer_id"]]
        out.append({**q, "freelancer": with_badges(f), "match": matching.public(matching.score(f, p))})
    return out


@app.post("/projects/{project_id}/proposals", status_code=201, tags=["proposals"])
def submit_proposal(project_id: str, body: ProposalIn):
    p, f, already, thread = parallel(
        lambda: one("projects", project_id, "Project"),
        lambda: as_freelancer(body.freelancer_id),
        lambda: rows(db().table("proposals").select("id").eq("project_id", project_id).eq("freelancer_id", body.freelancer_id)),
        lambda: rows(db().table("threads").select("*").eq("project_id", project_id).eq("freelancer_id", body.freelancer_id)),
    )
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")
    if already:
        raise HTTPException(409, "You already applied to this project")
    answers = [a.strip() for a in body.answers]
    if len(answers) != len(p["questions"]) or any(not a for a in answers):
        raise HTTPException(422, f"Answer all {len(p['questions'])} screening question(s)")
    invited = bool(thread and thread[0]["invited"])
    cost = 0 if invited else matching.connects_cost(p)
    if f["connects"] < cost:
        raise HTTPException(402, f"Not enough Connects: this costs {cost}, you have {f['connects']}")
    insert = lambda: rows(db().table("proposals").insert({
        "project_id": p["id"], "freelancer_id": f["id"], "cover_letter": body.cover_letter.strip(),
        "bid": body.bid, "days": body.days, "answers": answers,
        "links": [l.strip() for l in body.links if l.strip()], "connects_spent": cost,
    }))[0]
    pay = lambda: db().table("freelancers").update({"connects": f["connects"] - cost}).eq("id", f["id"]).execute()
    q = parallel(insert, *([pay] if cost else []))[0]
    parallel(lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} submitted a proposal: {bid_text(body.bid, p)} · {body.days} days"),
                                 thread=thread[0] if thread else None),
             lambda: notify("client", p["client_id"], f"New proposal from {f['name']} on “{p['title']}”", f"#/proposals/{p['id']}"),
             lambda: log_event("proposal", p, f))
    return {**q, "connects_left": f["connects"] - cost}


def _proposal_for(proposal_id: str, freelancer_id: Optional[str] = None):
    q = one("proposals", proposal_id, "Proposal")
    if freelancer_id is not None:
        if q["freelancer_id"] != freelancer_id:
            raise HTTPException(403, "This proposal belongs to another freelancer")
        as_freelancer(freelancer_id)
    p, f = parallel(lambda: one("projects", q["project_id"], "Project"),
                    lambda: one("freelancers", q["freelancer_id"], "Freelancer"))
    return q, p, f


@app.patch("/proposals/{proposal_id}", tags=["proposals"])
def edit_proposal(proposal_id: str, body: ProposalEdit):
    q, p, f = _proposal_for(proposal_id, body.freelancer_id)
    if q["status"] not in ("submitted", "shortlisted") or p["status"] != "open":
        raise HTTPException(409, "This proposal can't be edited any more")
    if pending_offer_for(q["id"]):
        raise HTTPException(409, "You have an offer on this proposal. Reply to it instead.")
    changes: Dict[str, Any] = {k: v for k, v in body.model_dump(exclude={"freelancer_id"}).items() if v is not None}
    if "answers" in changes and (len(changes["answers"]) != len(p["questions"]) or any(not a.strip() for a in changes["answers"])):
        raise HTTPException(422, f"Answer all {len(p['questions'])} screening question(s)")
    changes["edited_at"] = now_iso()
    updated = rows(db().table("proposals").update(changes).eq("id", q["id"]))[0]
    parallel(lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} updated their proposal: {bid_text(updated['bid'], p)} · {updated['days']} days")),
             lambda: notify("client", p["client_id"], f"{f['name']} updated their proposal on “{p['title']}”", f"#/proposals/{p['id']}"))
    return updated


def _set_status(proposal_id: str, status: str, by_client: bool, freelancer_id: Optional[str] = None):
    q, p, f = _proposal_for(proposal_id, freelancer_id)
    client, has_offer = parallel(lambda: one("clients", p["client_id"], "Client"),
                                 lambda: pending_offer_for(q["id"]))
    me = me_client() if by_client else None
    if by_client and p["client_id"] != me["id"]:
        raise HTTPException(403, "This project belongs to another client")
    allowed_from = {"shortlisted": ("submitted",), "declined": ("submitted", "shortlisted"),
                    "withdrawn": ("submitted", "shortlisted")}[status]
    if q["status"] not in allowed_from:
        raise HTTPException(409, f"Can't change a {q['status']} proposal to {status}")
    if has_offer:
        raise HTTPException(409, "There's a pending offer on this proposal. Withdraw or answer it first.")
    update = lambda: rows(db().table("proposals").update({"status": status}).eq("id", q["id"]))[0]
    if status == "withdrawn":
        updated, _, _ = parallel(
            update,
            lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} withdrew their proposal")),
            lambda: notify("client", p["client_id"], f"{f['name']} withdrew their proposal on “{p['title']}”", f"#/proposals/{p['id']}"))
    else:
        updated, _, _, _ = parallel(
            update,
            lambda: thread_note(p["id"], f["id"], ("system", f"{client['name']} {status} {f['name']}'s proposal")),
            lambda: notify("freelancer", f["id"], f"Your proposal for “{p['title']}” was {status}", f"#/project/{p['id']}"),
            lambda: log_event("shortlist" if status == "shortlisted" else "decline", p, f))
    return updated


@app.post("/proposals/{proposal_id}/shortlist", tags=["proposals"])
def shortlist(proposal_id: str):
    return _set_status(proposal_id, "shortlisted", by_client=True)


@app.post("/proposals/{proposal_id}/decline", tags=["proposals"])
def decline(proposal_id: str):
    return _set_status(proposal_id, "declined", by_client=True)


@app.post("/proposals/{proposal_id}/withdraw", tags=["proposals"])
def withdraw(proposal_id: str, freelancer_id: str = Query(...)):
    """Connects spent are not refunded."""
    return _set_status(proposal_id, "withdrawn", by_client=False, freelancer_id=freelancer_id)


# ---------------------------------------------------------------- chat
@app.get("/threads", tags=["chat"])
def list_threads(role: Literal["client", "freelancer"], freelancer_id: Optional[str] = None):
    """One thread per project + freelancer pair, newest activity first, with unread counts."""
    query = db().table("threads").select("*, projects(title, client_id, clients(name)), freelancers(name)")
    if role == "freelancer":
        if not freelancer_id:
            raise HTTPException(422, "freelancer_id is required for role=freelancer")
        as_freelancer(freelancer_id)
        threads = rows(query.eq("freelancer_id", freelancer_id))
    else:
        mine = me_client()["id"]
        threads = [t for t in rows(query) if (t.get("projects") or {}).get("client_id") == mine]
    if not threads:
        return []
    msgs = rows(db().table("messages").select("*").in_("thread_id", [t["id"] for t in threads]).order("created_at"))
    other = "freelancer" if role == "client" else "client"
    read_key = "client_read_at" if role == "client" else "freelancer_read_at"
    out = []
    for t in threads:
        mine_msgs = [m for m in msgs if m["thread_id"] == t["id"]]
        last = mine_msgs[-1] if mine_msgs else None
        unread = sum(1 for m in mine_msgs if m["sender"] == other and (not t[read_key] or m["created_at"] > t[read_key]))
        out.append({**t, "last_message": last, "unread": unread})
    out.sort(key=lambda t: (t["last_message"] or {}).get("created_at") or t["created_at"], reverse=True)
    return out


def _thread(thread_id: str, side: Optional[str] = None) -> Dict[str, Any]:
    """A chat thread you're part of (as `side`, if given)."""
    t = one("threads", thread_id, "Thread")
    p = one("projects", t["project_id"], "Project")
    if side:
        check_side(side, p, t["freelancer_id"])
    else:
        check_party(p, t["freelancer_id"])
    return t


@app.get("/threads/{thread_id}/messages", tags=["chat"])
def get_messages(thread_id: str):
    _thread(thread_id)
    return rows(db().table("messages").select("*").eq("thread_id", thread_id).order("created_at"))


@app.post("/threads/{thread_id}/messages", status_code=201, tags=["chat"])
def send_message(thread_id: str, body: MessageIn):
    t = _thread(thread_id, body.sender)
    msg = post_message(t["id"], body.sender, body.body.strip())
    db().table("threads").update({f"{body.sender}_read_at": msg["created_at"]}).eq("id", t["id"]).execute()
    return msg


@app.post("/threads/{thread_id}/read", tags=["chat"])
def mark_thread_read(thread_id: str, body: ReadIn):
    _thread(thread_id, body.role)
    latest = rows(db().table("messages").select("created_at").eq("thread_id", thread_id)
                  .order("created_at", desc=True).limit(1))
    if latest:
        db().table("threads").update({f"{body.role}_read_at": latest[0]["created_at"]}).eq("id", thread_id).execute()
    return {"ok": True}


# ---------------------------------------------------------------- notifications
def _check_recipient(recipient_type: str, recipient_id: str) -> None:
    if recipient_type == "client":
        if recipient_id != me_client()["id"]:
            raise HTTPException(403, "These notifications belong to someone else")
    else:
        as_freelancer(recipient_id)


@app.get("/notifications", tags=["notifications"])
def list_notifications(recipient_type: Literal["client", "freelancer"], recipient_id: str, limit: int = 20):
    _check_recipient(recipient_type, recipient_id)
    return rows(db().table("notifications").select("*").eq("recipient_type", recipient_type)
                .eq("recipient_id", recipient_id).order("created_at", desc=True).limit(limit))


@app.post("/notifications/read", tags=["notifications"])
def mark_notifications_read(body: NotificationsReadIn):
    _check_recipient(body.recipient_type, body.recipient_id)
    db().table("notifications").update({"read": True}).eq("recipient_type", body.recipient_type) \
        .eq("recipient_id", body.recipient_id).eq("read", False).execute()
    return {"ok": True}


# ================================================================ offers, contracts, reviews
# Amounts track the work only. No payments happen in Gigwise.

class MilestoneIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0)
    due_date: date


class OfferIn(BaseModel):
    milestones: List[MilestoneIn] = Field(default_factory=list, max_length=5, description="Fixed-price projects")
    rate: Optional[float] = Field(None, gt=0, description="Hourly projects: USD per hour")
    weekly_limit: Optional[int] = Field(None, gt=0, le=80, description="Hourly projects: max hours a week")
    message: str = Field("", max_length=2000)


class FreelancerAction(BaseModel):
    freelancer_id: str


class SubmitWorkIn(BaseModel):
    freelancer_id: str
    note: str = Field(min_length=5, max_length=3000)
    link: str = Field("", max_length=500)


class ChangesIn(BaseModel):
    note: str = Field(min_length=5, max_length=3000)


class EndIn(BaseModel):
    role: Literal["client", "freelancer"]
    freelancer_id: Optional[str] = None


class ReviewIn(BaseModel):
    role: Literal["client", "freelancer"]
    freelancer_id: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=5, max_length=3000)


def offer_terms(o: Dict[str, Any]) -> str:
    if o["type"] == "hourly":
        return f"${o['rate']:g}/hr, up to {o['weekly_limit']} hrs/week"
    total = sum(float(m["amount"]) for m in o["milestones"])
    n = len(o["milestones"])
    return f"{money(total)} in {n} milestone{'' if n == 1 else 's'}"


def check_role(role: str, project: Dict[str, Any], contract_or_offer: Dict[str, Any], freelancer_id: Optional[str]):
    """The client side must own the project. The freelancer side must name the offer's or contract's
    freelancer, and when signed in that must be your own profile."""
    if role == "client":
        if project["client_id"] != me_client()["id"]:
            raise HTTPException(403, "This belongs to another client")
    else:
        if freelancer_id != contract_or_offer["freelancer_id"]:
            raise HTTPException(403, "This belongs to another freelancer")
        as_freelancer(freelancer_id)


@app.post("/proposals/{proposal_id}/offers", status_code=201, tags=["offers"])
def send_offer(proposal_id: str, body: OfferIn):
    """Client sends an offer on a proposal. One pending offer per project at a time."""
    q, p, f = _proposal_for(proposal_id)
    client, pending = parallel(me_client,
                               lambda: rows(db().table("offers").select("id").eq("project_id", p["id"]).eq("status", "pending")))
    if p["client_id"] != client["id"]:
        raise HTTPException(403, "This project belongs to another client")
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")
    if q["status"] not in ("submitted", "shortlisted"):
        raise HTTPException(409, f"Can't send an offer on a {q['status']} proposal")
    if pending:
        raise HTTPException(409, "You already have an offer out on this project")
    if p["type"] == "hourly":
        if not body.rate or not body.weekly_limit:
            raise HTTPException(422, "Hourly offers need a rate and a weekly limit")
        terms = {"milestones": [], "rate": body.rate, "weekly_limit": body.weekly_limit}
    else:
        if not body.milestones:
            raise HTTPException(422, "Fixed-price offers need at least one milestone")
        terms = {"milestones": [{"title": m.title.strip(), "amount": m.amount, "due_date": m.due_date.isoformat()}
                                for m in body.milestones], "rate": None, "weekly_limit": None}
    o = rows(db().table("offers").insert({
        "project_id": p["id"], "freelancer_id": f["id"], "proposal_id": q["id"], "type": p["type"],
        "message": body.message.strip(), **terms,
    }))[0]
    msgs = [("system", f"{client['name']} sent an offer: {offer_terms(o)}")] + ([("client", o["message"])] if o["message"] else [])
    parallel(lambda: thread_note(p["id"], f["id"], *msgs),
             lambda: notify("freelancer", f["id"], f"{client['name']} sent you an offer for “{p['title']}”", f"#/offer/{o['id']}"),
             lambda: log_event("offer", p, f))
    return o


@app.get("/offers", tags=["offers"])
def list_offers(role: Literal["client", "freelancer"], freelancer_id: Optional[str] = None, status: str = "pending"):
    query = db().table("offers").select("*, projects(title, client_id, clients(name)), freelancers(name)") \
        .order("created_at", desc=True)
    if status != "any":
        query = query.eq("status", status)
    if role == "freelancer":
        if not freelancer_id:
            raise HTTPException(422, "freelancer_id is required for role=freelancer")
        as_freelancer(freelancer_id)
        return rows(query.eq("freelancer_id", freelancer_id))
    mine = me_client()["id"]
    return [o for o in rows(query) if (o.get("projects") or {}).get("client_id") == mine]


@app.get("/offers/{offer_id}", tags=["offers"])
def get_offer(offer_id: str):
    r = rows(db().table("offers").select("*, projects(title, type, client_id, clients(name)), freelancers(name)")
             .eq("id", offer_id))
    if not r:
        raise HTTPException(404, "Offer not found")
    check_party(one("projects", r[0]["project_id"], "Offer"), r[0]["freelancer_id"])
    return r[0]


def _pending_offer(offer_id: str):
    o = one("offers", offer_id, "Offer")
    if o["status"] != "pending":
        raise HTTPException(409, f"This offer was already {o['status']}")
    p, f = parallel(lambda: one("projects", o["project_id"], "Project"),
                    lambda: one("freelancers", o["freelancer_id"], "Freelancer"))
    return o, p, f


@app.post("/offers/{offer_id}/accept", status_code=201, tags=["offers"])
def accept_offer(offer_id: str, body: FreelancerAction):
    """Freelancer accepts: the project is filled and a contract starts with the first milestone active."""
    o, p, f = _pending_offer(offer_id)
    check_role("freelancer", p, o, body.freelancer_id)
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")

    def count_hire():
        client = one("clients", p["client_id"], "Client")
        db().table("clients").update({"hires": int(client["hires"] or 0) + 1}).eq("id", client["id"]).execute()

    updates = [
        lambda: rows(db().table("contracts").insert({
            "project_id": p["id"], "freelancer_id": f["id"], "offer_id": o["id"], "type": o["type"],
            "rate": o.get("rate"), "weekly_limit": o.get("weekly_limit"),
        }))[0],
        lambda: db().table("offers").update({"status": "accepted"}).eq("id", o["id"]).execute(),
        lambda: db().table("projects").update({"status": "hired", "hired_freelancer_id": f["id"]}).eq("id", p["id"]).execute(),
        count_hire,
    ]
    if o.get("proposal_id"):
        updates.append(lambda: db().table("proposals").update({"status": "accepted"}).eq("id", o["proposal_id"]).execute())
    c = parallel(*updates)[0]
    after = [
        lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} accepted the offer. Contract started.")),
        lambda: notify("client", p["client_id"], f"{f['name']} accepted your offer for “{p['title']}”", f"#/contract/{c['id']}"),
        lambda: log_event("hire", p, f),
    ]
    if o["milestones"]:
        after.append(lambda: db().table("milestones").insert([
            {"contract_id": c["id"], "position": i + 1, "title": m["title"], "amount": m["amount"],
             "due_date": m["due_date"], "status": "active" if i == 0 else "pending"}
            for i, m in enumerate(o["milestones"])
        ]).execute())
    parallel(*after)
    return get_contract(c["id"])


@app.post("/offers/{offer_id}/decline", tags=["offers"])
def decline_offer(offer_id: str, body: FreelancerAction):
    o, p, f = _pending_offer(offer_id)
    check_role("freelancer", p, o, body.freelancer_id)
    updated = parallel(
        lambda: rows(db().table("offers").update({"status": "declined"}).eq("id", o["id"]))[0],
        lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} declined the offer")),
        lambda: notify("client", p["client_id"], f"{f['name']} declined your offer for “{p['title']}”", f"#/proposals/{p['id']}"),
        lambda: log_event("offer_declined", p, f))[0]
    return updated


@app.post("/offers/{offer_id}/withdraw", tags=["offers"])
def withdraw_offer(offer_id: str):
    o, p, f = _pending_offer(offer_id)
    check_role("client", p, o, None)
    client = me_client()
    updated = parallel(
        lambda: rows(db().table("offers").update({"status": "withdrawn"}).eq("id", o["id"]))[0],
        lambda: thread_note(p["id"], f["id"], ("system", f"{client['name']} withdrew the offer")),
        lambda: notify("freelancer", f["id"], f"{client['name']} withdrew their offer for “{p['title']}”", f"#/project/{p['id']}"))[0]
    return updated


# ---------------------------------------------------------------- contracts and milestones
@app.get("/contracts", tags=["contracts"])
def list_contracts(role: Literal["client", "freelancer"], freelancer_id: Optional[str] = None, status: str = "any"):
    query = db().table("contracts").select("*, projects(title, client_id, clients(name)), freelancers(name)") \
        .order("started_at", desc=True)
    if status != "any":
        query = query.eq("status", status)
    if role == "freelancer":
        if not freelancer_id:
            raise HTTPException(422, "freelancer_id is required for role=freelancer")
        as_freelancer(freelancer_id)
        contracts = rows(query.eq("freelancer_id", freelancer_id))
    else:
        mine = me_client()["id"]
        contracts = [c for c in rows(query) if (c.get("projects") or {}).get("client_id") == mine]
    if not contracts:
        return []
    ms = rows(db().table("milestones").select("*").in_("contract_id", [c["id"] for c in contracts]))
    for c in contracts:
        mine_ms = [m for m in ms if m["contract_id"] == c["id"]]
        c["milestones_total"] = len(mine_ms)
        c["milestones_approved"] = sum(1 for m in mine_ms if m["status"] == "approved")
        c["amount_total"] = sum(float(m["amount"]) for m in mine_ms)
        c["needs_client_review"] = any(m["status"] == "submitted" for m in mine_ms)
    return contracts


@app.get("/contracts/{contract_id}", tags=["contracts"])
def get_contract(contract_id: str):
    r, ms, rv = parallel(
        lambda: rows(db().table("contracts").select("*, projects(title, client_id, clients(name)), freelancers(name)")
                     .eq("id", contract_id)),
        lambda: rows(db().table("milestones").select("*").eq("contract_id", contract_id).order("position")),
        lambda: rows(db().table("reviews").select("*").eq("contract_id", contract_id)))
    if not r:
        raise HTTPException(404, "Contract not found")
    check_party(one("projects", r[0]["project_id"], "Contract"), r[0]["freelancer_id"])
    return {**r[0], "milestones": ms, "reviews": rv}


def _milestone(contract_id: str, position: int):
    c, r = parallel(lambda: one("contracts", contract_id, "Contract"),
                    lambda: rows(db().table("milestones").select("*").eq("contract_id", contract_id).eq("position", position)))
    if c["status"] != "active":
        raise HTTPException(409, "This contract has ended")
    if not r:
        raise HTTPException(404, "Milestone not found")
    p, f = parallel(lambda: one("projects", c["project_id"], "Project"),
                    lambda: one("freelancers", c["freelancer_id"], "Freelancer"))
    return c, r[0], p, f


@app.post("/contracts/{contract_id}/milestones/{position}/submit", tags=["contracts"])
def submit_milestone(contract_id: str, position: int, body: SubmitWorkIn):
    c, m, p, f = _milestone(contract_id, position)
    check_role("freelancer", p, c, body.freelancer_id)
    if m["status"] != "active":
        raise HTTPException(409, f"Only the active milestone can be submitted (this one is {m['status']})")
    updated = parallel(
        lambda: rows(db().table("milestones").update({
            "status": "submitted", "note": body.note.strip(), "link": body.link.strip() or None, "changes_requested": None,
        }).eq("id", m["id"]))[0],
        lambda: thread_note(p["id"], f["id"], ("system", f"{f['name']} submitted “{m['title']}” for review")),
        lambda: notify("client", p["client_id"], f"{f['name']} submitted “{m['title']}” for your review", f"#/contract/{c['id']}"))[0]
    return updated


@app.post("/contracts/{contract_id}/milestones/{position}/approve", tags=["contracts"])
def approve_milestone(contract_id: str, position: int):
    c, m, p, f = _milestone(contract_id, position)
    check_role("client", p, c, None)
    if m["status"] != "submitted":
        raise HTTPException(409, "Only submitted work can be approved")
    client = me_client()
    _, nxt = parallel(
        lambda: db().table("milestones").update({"status": "approved"}).eq("id", m["id"]).execute(),
        lambda: rows(db().table("milestones").select("*").eq("contract_id", contract_id).eq("status", "pending")
                     .order("position").limit(1)))
    after = [
        lambda: thread_note(p["id"], f["id"], ("system", f"{client['name']} approved “{m['title']}”")),
        lambda: notify("freelancer", f["id"],
                       f"{client['name']} approved “{m['title']}”" + (f". Next up: “{nxt[0]['title']}”" if nxt else ""),
                       f"#/contract/{c['id']}"),
    ]
    if nxt:
        after.append(lambda: db().table("milestones").update({"status": "active"}).eq("id", nxt[0]["id"]).execute())
    parallel(*after)
    return get_contract(contract_id)


@app.post("/contracts/{contract_id}/milestones/{position}/request-changes", tags=["contracts"])
def request_changes(contract_id: str, position: int, body: ChangesIn):
    c, m, p, f = _milestone(contract_id, position)
    check_role("client", p, c, None)
    if m["status"] != "submitted":
        raise HTTPException(409, "You can only request changes on submitted work")
    client = me_client()
    updated = parallel(
        lambda: rows(db().table("milestones").update({"status": "active", "changes_requested": body.note.strip()})
                     .eq("id", m["id"]))[0],
        lambda: thread_note(p["id"], f["id"], ("system", f"{client['name']} requested changes on “{m['title']}”")),
        lambda: notify("freelancer", f["id"], f"{client['name']} requested changes on “{m['title']}”", f"#/contract/{c['id']}"))[0]
    return updated


@app.post("/contracts/{contract_id}/end", tags=["contracts"])
def end_contract(contract_id: str, body: EndIn):
    """Either side can end an active contract. Both are then asked for feedback."""
    c = one("contracts", contract_id, "Contract")
    p, f = parallel(lambda: one("projects", c["project_id"], "Project"),
                    lambda: one("freelancers", c["freelancer_id"], "Freelancer"))
    check_role(body.role, p, c, body.freelancer_id)
    if c["status"] != "active":
        raise HTTPException(409, "This contract has already ended")
    client = one("clients", p["client_id"], "Client") if body.role == "client" else None
    who = client["name"] if client else f["name"]
    message = f"{who} ended the contract for “{p['title']}”. Leave feedback."
    parallel(lambda: db().table("contracts").update({"status": "ended", "ended_at": now_iso()}).eq("id", c["id"]).execute(),
             lambda: db().table("projects").update({"status": "ended"}).eq("id", p["id"]).execute(),
             lambda: thread_note(p["id"], f["id"], ("system", f"{who} ended the contract")),
             lambda: (notify("freelancer", f["id"], message, f"#/contract/{c['id']}") if body.role == "client"
                      else notify("client", p["client_id"], message, f"#/contract/{c['id']}")))
    return get_contract(contract_id)


@app.post("/contracts/{contract_id}/reviews", status_code=201, tags=["contracts"])
def leave_review(contract_id: str, body: ReviewIn):
    """Two-way feedback after a contract ends. A client's rating updates the freelancer's rating
    and Job Success, which feeds the Ratings signal (7%) of future match scores."""
    direction = "client_to_freelancer" if body.role == "client" else "freelancer_to_client"
    c, existing = parallel(lambda: one("contracts", contract_id, "Contract"),
                           lambda: rows(db().table("reviews").select("id").eq("contract_id", contract_id).eq("direction", direction)))
    p, f = parallel(lambda: one("projects", c["project_id"], "Project"),
                    lambda: one("freelancers", c["freelancer_id"], "Freelancer"))
    check_role(body.role, p, c, body.freelancer_id)
    if c["status"] != "ended":
        raise HTTPException(409, "Feedback opens once the contract has ended")
    if existing:
        raise HTTPException(409, "You already left feedback on this contract")
    review, client = parallel(
        lambda: rows(db().table("reviews").insert({
            "contract_id": c["id"], "direction": direction, "rating": body.rating, "body": body.body.strip(),
        }))[0],
        lambda: one("clients", p["client_id"], "Client"))
    r = body.rating
    if body.role == "client":
        n, old = int(f["jobs"] or 0), f.get("rating")
        new_rating = js_round1((float(old) * n + r) / (n + 1)) if old else float(r)
        new_jss = matching.js_round(((f.get("jss") or 100) * n + (100 if r >= 4 else r * 20)) / (n + 1))
        parallel(lambda: db().table("freelancers").update({"rating": new_rating, "jobs": n + 1, "jss": new_jss}).eq("id", f["id"]).execute(),
                 lambda: notify("freelancer", f["id"], f"{client['name']} left you {r}★ feedback", f"#/contract/{c['id']}"),
                 lambda: log_event("review", p, f))
    else:
        n, old = int(client["hires"] or 1), client.get("rating")
        new_rating = js_round1((float(old) * n + r) / (n + 1)) if old else float(r)
        parallel(lambda: db().table("clients").update({"rating": new_rating}).eq("id", client["id"]).execute(),
                 lambda: notify("client", p["client_id"], f"{f['name']} left you {r}★ feedback", f"#/contract/{c['id']}"))
        forget_demo_client()
    return review


def js_round1(x: float) -> float:
    """Round to 1 decimal place the way the frontend does (Math.round(x*10)/10)."""
    return matching.js_round(x * 10) / 10


# ---------------------------------------------------------------- saved items
@app.get("/freelancers/{freelancer_id}/saved-jobs", tags=["saved"])
def list_saved_jobs(freelancer_id: str):
    as_freelancer(freelancer_id)
    return rows(db().table("saved_jobs").select("project_id, created_at, projects(*)")
                .eq("freelancer_id", freelancer_id).order("created_at", desc=True))


@app.put("/freelancers/{freelancer_id}/saved-jobs/{project_id}", tags=["saved"])
def save_job(freelancer_id: str, project_id: str):
    as_freelancer(freelancer_id)
    one("projects", project_id, "Project")
    if not rows(db().table("saved_jobs").select("project_id").eq("freelancer_id", freelancer_id).eq("project_id", project_id)):
        db().table("saved_jobs").insert({"freelancer_id": freelancer_id, "project_id": project_id}).execute()
    return {"saved": True}


@app.delete("/freelancers/{freelancer_id}/saved-jobs/{project_id}", tags=["saved"])
def unsave_job(freelancer_id: str, project_id: str):
    as_freelancer(freelancer_id)
    db().table("saved_jobs").delete().eq("freelancer_id", freelancer_id).eq("project_id", project_id).execute()
    return {"saved": False}


@app.get("/saved-freelancers", tags=["saved"])
def list_saved_freelancers():
    return rows(db().table("saved_freelancers").select("freelancer_id, created_at, freelancers(*)")
                .eq("client_id", me_client()["id"]).order("created_at", desc=True))


@app.put("/saved-freelancers/{freelancer_id}", tags=["saved"])
def save_freelancer(freelancer_id: str):
    one("freelancers", freelancer_id, "Freelancer")
    cid = me_client()["id"]
    if not rows(db().table("saved_freelancers").select("freelancer_id").eq("client_id", cid).eq("freelancer_id", freelancer_id)):
        db().table("saved_freelancers").insert({"client_id": cid, "freelancer_id": freelancer_id}).execute()
    return {"saved": True}


@app.delete("/saved-freelancers/{freelancer_id}", tags=["saved"])
def unsave_freelancer(freelancer_id: str):
    db().table("saved_freelancers").delete().eq("client_id", me_client()["id"]).eq("freelancer_id", freelancer_id).execute()
    return {"saved": False}


# ---------------------------------------------------------------- freelancer profiles
class PortfolioItem(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=500)


class FreelancerIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    skills: List[str] = Field(min_length=1, max_length=15, description="1 to 15 skills from GET /taxonomy")
    rate: float = Field(gt=0, le=1000)
    years: int = Field(0, ge=0, le=60)
    hours_per_week: int = Field(30, ge=0, le=80)
    available: bool = True
    location: str = Field("", max_length=120)
    bio: str = Field("", max_length=3000)
    portfolio: List[PortfolioItem] = Field(default_factory=list, max_length=20)
    employment: List[Dict[str, str]] = Field(default_factory=list, max_length=20)
    education: List[Dict[str, str]] = Field(default_factory=list, max_length=20)
    certifications: List[Dict[str, str]] = Field(default_factory=list, max_length=20)
    languages: List[Dict[str, str]] = Field(default_factory=list, max_length=20)


def _profile_row(body: FreelancerIn) -> Dict[str, Any]:
    row = body.model_dump()
    row["skills"] = catalog_skills(row["skills"], limit=15)
    row["bio"] = row["bio"].strip() or row["title"]
    return row


@app.post("/freelancers", status_code=201, tags=["freelancers"])
def create_freelancer(body: FreelancerIn):
    """Create a freelancer profile. New profiles start with 40 Connects and no ratings.
    Signed in: it becomes your own profile (one per login). In the demo: a new demo profile."""
    a = actor()
    row = _profile_row(body)
    if a.world == "real":
        if a.freelancer:
            raise HTTPException(409, "You already have a freelancer profile")
        row.update(world="real", user_id=a.user["id"])
    f = rows(db().table("freelancers").insert(row))[0]
    request_cache().pop("actor", None)
    return with_badges(f)


@app.put("/freelancers/{freelancer_id}", tags=["freelancers"])
def update_freelancer(freelancer_id: str, body: FreelancerIn):
    """Replace a freelancer's editable profile fields. Rating, jobs, Job Success and Connects are not editable."""
    as_freelancer(freelancer_id)
    return with_badges(rows(db().table("freelancers").update(_profile_row(body)).eq("id", freelancer_id))[0])


# ================================================================ data for the frontend
# The frontend loads everything it may see in one call, then sends each action to the endpoints above.
# Demo visitors get the whole demo world. Signed-in users get the real world's public data (people,
# projects, reviews) plus only their own private data (proposals, offers, contracts, chats, alerts).

_STATE_TABLES = {
    "clients": "id", "freelancers": "id", "projects": "created_at", "proposals": "created_at",
    "offers": "created_at", "contracts": "started_at", "milestones": "position", "reviews": "created_at",
    "threads": "created_at", "messages": "created_at", "notifications": "created_at",
    "saved_jobs": "created_at", "saved_freelancers": "created_at",
}


def _load_table(item):
    table, order = item
    # db() inside the worker: each thread has its own connection (see app/db.py)
    return table, db().table(table).select("*").order(order).execute().data or []


def scope_state(data: Dict[str, List[Dict[str, Any]]], a: Actor) -> Dict[str, Any]:
    """Keep only what this person may see. Pure function, so it is easy to test."""
    w = a.world
    in_world = lambda r: r.get("world", "demo") == w
    clients = [c for c in data["clients"] if in_world(c)]
    freelancers = [f for f in data["freelancers"] if in_world(f)]
    projects = [p for p in data["projects"] if in_world(p)]
    pids, fids, cids = {p["id"] for p in projects}, {f["id"] for f in freelancers}, {c["id"] for c in clients}
    pair_ok = lambda r: r["project_id"] in pids and r["freelancer_id"] in fids
    out = {
        "proposals": [r for r in data["proposals"] if pair_ok(r)],
        "offers": [r for r in data["offers"] if pair_ok(r)],
        "contracts": [r for r in data["contracts"] if pair_ok(r)],
        "threads": [r for r in data["threads"] if pair_ok(r)],
        "saved_jobs": [r for r in data["saved_jobs"] if r["project_id"] in pids and r["freelancer_id"] in fids],
        "saved_freelancers": [r for r in data["saved_freelancers"] if r["client_id"] in cids and r["freelancer_id"] in fids],
        "notifications": [n for n in data["notifications"]
                          if n["recipient_id"] in (cids if n["recipient_type"] == "client" else fids)],
    }
    if w == "real":
        my_c = a.client["id"] if a.client else None
        my_f = a.freelancer["id"] if a.freelancer else None
        my_pids = {p["id"] for p in projects if my_c and p["client_id"] == my_c}
        mine = lambda r: r["project_id"] in my_pids or (my_f is not None and r["freelancer_id"] == my_f)
        for t in ("proposals", "offers", "threads"):
            out[t] = [r for r in out[t] if mine(r)]
        # Reviews are public (they show on profiles), so keep the contracts they belong to as well.
        reviewed = {r["contract_id"] for r in data["reviews"]}
        out["contracts"] = [c for c in out["contracts"] if mine(c) or c["id"] in reviewed]
        out["saved_jobs"] = [r for r in out["saved_jobs"] if r["freelancer_id"] == my_f]
        out["saved_freelancers"] = [r for r in out["saved_freelancers"] if r["client_id"] == my_c]
        out["notifications"] = [n for n in out["notifications"]
                                if (n["recipient_type"] == "client" and n["recipient_id"] == my_c)
                                or (n["recipient_type"] == "freelancer" and n["recipient_id"] == my_f)]
        my_contracts = {c["id"] for c in out["contracts"] if mine(c)}
    else:
        my_contracts = {c["id"] for c in out["contracts"]}
    cset, tset = {c["id"] for c in out["contracts"]}, {t["id"] for t in out["threads"]}
    out["milestones"] = [m for m in data["milestones"] if m["contract_id"] in my_contracts]
    out["reviews"] = [r for r in data["reviews"] if r["contract_id"] in cset]
    out["messages"] = [m for m in data["messages"] if m["thread_id"] in tset]
    hide = lambda r: {k: v for k, v in r.items() if k != "user_id"}  # never hand out login ids
    out["clients"] = [hide(c) for c in clients]
    out["freelancers"] = [hide(f) for f in freelancers]
    out["projects"] = projects
    out["world"] = w
    if w == "demo":
        out["me"] = next((c for c in clients if c.get("is_demo_user")), None)
        out["me_freelancer"] = None
        out["user"] = None
    else:
        out["me"] = hide(a.client) if a.client else None
        out["me_freelancer"] = hide(a.freelancer) if a.freelancer else None
        out["user"] = {"email": a.user["email"]}
    return out


@app.get("/state", tags=["frontend"])
def state():
    """Everything the frontend needs to draw every screen for you, loaded in parallel."""
    db()  # fail fast with a clear message if not configured
    a = actor()
    data = dict(_POOL.map(lambda item: contextvars.copy_context().run(_load_table, item), _STATE_TABLES.items()))
    out = scope_state(data, a)
    if a.world == "demo" and not out["me"]:
        raise HTTPException(500, "No demo client found. Run the seed script: python -m seed.seed")
    return out


@app.get("/demo/state", tags=["demo"], include_in_schema=False)
def demo_state():
    """Older name for GET /state."""
    return state()


@app.post("/demo/reset", tags=["demo"])
def demo_reset():
    """Delete the demo data and load it fresh. Real accounts and their data are never touched.
    Turn off with DEMO_RESET_ENABLED=false in .env."""
    import os

    if os.getenv("DEMO_RESET_ENABLED", "true").lower() == "false":
        raise HTTPException(403, "Demo reset is turned off on this server")
    if world() != "demo":
        raise HTTPException(403, "Only the demo can be reset")
    from seed.seed import reset_demo

    counts = reset_demo(db(), log=lambda *_: None)
    forget_demo_client()
    return {"ok": True, "rows": counts}


# Serve the frontend from this server too, so one command runs everything:
# open http://localhost:8000 and the app talks to the API on the same address.
from pathlib import Path as _Path

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

_FRONTEND = _Path(__file__).resolve().parents[2] / "frontend"
if _FRONTEND.is_dir():
    app.mount("/app", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    def _root():
        return RedirectResponse("/app/")



# ================================================================ Claude-written text
# Optional: needs ANTHROPIC_API_KEY. Without it (or if Claude fails) the responses say so and the
# app keeps its template text, so nothing depends on these endpoints.

class ExplainIn(BaseModel):
    project_id: str
    freelancer_ids: List[str] = Field(min_length=1, max_length=8)


class DraftIn(BaseModel):
    project_id: str
    freelancer_id: str
    bid: Optional[float] = Field(None, gt=0)
    days: Optional[int] = Field(None, gt=0)


@app.post("/ai/explain", tags=["ai"])
def ai_explain(body: ExplainIn):
    """Claude-written match reasons for up to 8 freelancers on one project, grounded only in the facts
    behind the score. Freelancers missing from the result should keep their template reason."""
    if not ai.enabled():
        return {"enabled": False, "explanations": {}}
    p, fl = parallel(lambda: one("projects", body.project_id, "Project"),
                     lambda: rows(db().table("freelancers").select("*").in_("id", body.freelancer_ids)
                                  .eq("world", world())))
    order = {fid: i for i, fid in enumerate(body.freelancer_ids)}
    fl.sort(key=lambda f: order.get(f["id"], 99))
    return {"enabled": True, "explanations": ai.explain(p, fl)}


@app.post("/ai/draft-proposal", tags=["ai"])
def ai_draft_proposal(body: DraftIn):
    """A Claude-written cover letter in the freelancer's voice, grounded only in their profile.
    cover_letter is null when AI is off or fails; the app then uses its template draft."""
    if not ai.enabled():
        return {"enabled": False, "cover_letter": None}
    p, f = parallel(lambda: one("projects", body.project_id, "Project"),
                    lambda: as_freelancer(body.freelancer_id))
    return {"enabled": True, "cover_letter": ai.draft_proposal(p, f, body.bid, body.days)}
