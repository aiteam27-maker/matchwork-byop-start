"""Gigwise API (FastAPI + Supabase).

Run from gigwise/backend:   .venv/bin/uvicorn app.main:app --reload --port 8000
Interactive docs:           http://localhost:8000/docs

Until real login exists, "you" as a client are the demo client (Pulse Fit), and freelancer
actions take a freelancer_id. Offers, contracts, milestones and reviews come in the next step.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import matching
from .db import NotConfigured, allowed_origins, get_client, settings_problem

app = FastAPI(title="Gigwise API", version="0.1.0",
              description="Freelance marketplace with explained match scores.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def one(table: str, id_: str, what: str) -> Dict[str, Any]:
    r = rows(db().table(table).select("*").eq("id", id_).limit(1))
    if not r:
        raise HTTPException(404, f"{what} not found")
    return r[0]


def demo_client() -> Dict[str, Any]:
    r = rows(db().table("clients").select("*").eq("is_demo_user", True).limit(1))
    if not r:
        raise HTTPException(500, "No demo client found. Run the seed script: python -m seed.seed")
    return r[0]


def all_freelancers() -> List[Dict[str, Any]]:
    return rows(db().table("freelancers").select("*").order("id"))


def with_badges(f: Dict[str, Any]) -> Dict[str, Any]:
    return {**f, "badges": matching.badges(f)}


def own_project(project_id: str) -> Dict[str, Any]:
    p = one("projects", project_id, "Project")
    if p["client_id"] != demo_client()["id"]:
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


def pending_offer_for(proposal_id: str) -> bool:
    return bool(rows(db().table("offers").select("id").eq("proposal_id", proposal_id).eq("status", "pending")))


def bid_text(bid: float, p: Dict[str, Any]) -> str:
    return f"${bid:g}/hr" if p["type"] == "hourly" else money(bid)


# ---------------------------------------------------------------- request bodies
class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=20, max_length=5000)
    skills: List[str] = Field(default_factory=list, description="Leave empty to detect from the description")
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
        return {"ok": True, "database": "connected"}
    except HTTPException:
        raise
    except Exception as e:  # show the real reason, e.g. tables not created yet
        return {"ok": False, "database": "error", "detail": str(e)[:300]}


@app.get("/me", tags=["system"])
def me():
    """The demo client you act as until real login exists."""
    return demo_client()


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
    projects = rows(db().table("projects").select("*").eq("status", "open"))
    return matching.rank_projects(f, projects)


# ---------------------------------------------------------------- projects
@app.get("/projects", tags=["projects"])
def list_projects(status: str = "open", mine: bool = False, q: str = "", category: str = "",
                  type: Optional[Literal["fixed", "hourly"]] = None, level: str = "", duration: str = "",
                  min_budget: Optional[float] = None):
    query = db().table("projects").select("*, clients(name, rating, hires)").order("created_at", desc=True)
    if status != "any":
        query = query.eq("status", status)
    if mine:
        query = query.eq("client_id", demo_client()["id"])
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
    if not r:
        raise HTTPException(404, "Project not found")
    p = r[0]
    count = len(rows(db().table("proposals").select("id").eq("project_id", project_id)))
    return {**p, "proposal_count": count + p["extra_proposals"], "connects_cost": matching.connects_cost(p)}


@app.post("/projects", status_code=201, tags=["projects"])
def create_project(body: ProjectIn):
    """Post a project as the demo client. Returns the project and its ranked matches."""
    freelancers = all_freelancers()
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
    skills = [s.strip() for s in body.skills if s.strip()]
    auto = not skills
    if auto:
        skills = matching.detect_skills(f"{body.title} {body.description}", freelancers)
        if not skills:
            raise HTTPException(422, "Couldn't detect skills from the description. Add at least one skill.")
    row = {
        "client_id": demo_client()["id"], "title": body.title.strip(), "description": body.description.strip(),
        "skills": skills, "skills_auto": auto, "type": body.type, "budget": budget,
        "rate_min": body.rate_min if body.type == "hourly" else None,
        "rate_max": body.rate_max if body.type == "hourly" else None,
        "hours": body.hours, "level": body.level, "duration": body.duration,
        "deadline": body.deadline.isoformat() if body.deadline else None,
        "questions": [q.strip() for q in body.questions if q.strip()][:3],
        "category": matching.category_of(skills),
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
    p = own_project(project_id)
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")
    f = one("freelancers", body.freelancer_id, "Freelancer")
    client = demo_client()
    t = ensure_thread(p["id"], f["id"])
    post_message(t["id"], "system", f"{client['name']} invited {f['name']} to this project")
    msg = post_message(t["id"], "client", body.message.strip())
    # Read markers use database timestamps, so clock differences can't hide new messages.
    db().table("threads").update({"invited": True, "client_read_at": msg["created_at"]}).eq("id", t["id"]).execute()
    notify("freelancer", f["id"], f"{client['name']} invited you to “{p['title']}”", f"#/project/{p['id']}")
    log_event("invite", p, f)
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
    p = one("projects", project_id, "Project")
    f = one("freelancers", body.freelancer_id, "Freelancer")
    if p["status"] != "open":
        raise HTTPException(409, "This project is no longer open")
    if rows(db().table("proposals").select("id").eq("project_id", p["id"]).eq("freelancer_id", f["id"])):
        raise HTTPException(409, "You already applied to this project")
    answers = [a.strip() for a in body.answers]
    if len(answers) != len(p["questions"]) or any(not a for a in answers):
        raise HTTPException(422, f"Answer all {len(p['questions'])} screening question(s)")
    thread = rows(db().table("threads").select("*").eq("project_id", p["id"]).eq("freelancer_id", f["id"]))
    invited = bool(thread and thread[0]["invited"])
    cost = 0 if invited else matching.connects_cost(p)
    if f["connects"] < cost:
        raise HTTPException(402, f"Not enough Connects: this costs {cost}, you have {f['connects']}")
    if cost:
        db().table("freelancers").update({"connects": f["connects"] - cost}).eq("id", f["id"]).execute()
    q = rows(db().table("proposals").insert({
        "project_id": p["id"], "freelancer_id": f["id"], "cover_letter": body.cover_letter.strip(),
        "bid": body.bid, "days": body.days, "answers": answers,
        "links": [l.strip() for l in body.links if l.strip()], "connects_spent": cost,
    }))[0]
    t = thread[0] if thread else ensure_thread(p["id"], f["id"])
    post_message(t["id"], "system", f"{f['name']} submitted a proposal: {bid_text(body.bid, p)} · {body.days} days")
    notify("client", p["client_id"], f"New proposal from {f['name']} on “{p['title']}”", f"#/proposals/{p['id']}")
    log_event("proposal", p, f)
    return {**q, "connects_left": f["connects"] - cost}


def _proposal_for(proposal_id: str, freelancer_id: Optional[str] = None):
    q = one("proposals", proposal_id, "Proposal")
    if freelancer_id is not None and q["freelancer_id"] != freelancer_id:
        raise HTTPException(403, "This proposal belongs to another freelancer")
    return q, one("projects", q["project_id"], "Project"), one("freelancers", q["freelancer_id"], "Freelancer")


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
    t = ensure_thread(p["id"], f["id"])
    post_message(t["id"], "system", f"{f['name']} updated their proposal: {bid_text(updated['bid'], p)} · {updated['days']} days")
    notify("client", p["client_id"], f"{f['name']} updated their proposal on “{p['title']}”", f"#/proposals/{p['id']}")
    return updated


def _set_status(proposal_id: str, status: str, by_client: bool, freelancer_id: Optional[str] = None):
    q, p, f = _proposal_for(proposal_id, freelancer_id)
    if by_client:
        own_project(p["id"])
    allowed_from = {"shortlisted": ("submitted",), "declined": ("submitted", "shortlisted"),
                    "withdrawn": ("submitted", "shortlisted")}[status]
    if q["status"] not in allowed_from:
        raise HTTPException(409, f"Can't change a {q['status']} proposal to {status}")
    if pending_offer_for(q["id"]):
        raise HTTPException(409, "There's a pending offer on this proposal. Withdraw or answer it first.")
    updated = rows(db().table("proposals").update({"status": status}).eq("id", q["id"]))[0]
    t = ensure_thread(p["id"], f["id"])
    client = one("clients", p["client_id"], "Client")
    if status == "withdrawn":
        post_message(t["id"], "system", f"{f['name']} withdrew their proposal")
        notify("client", p["client_id"], f"{f['name']} withdrew their proposal on “{p['title']}”", f"#/proposals/{p['id']}")
    else:
        post_message(t["id"], "system", f"{client['name']} {status} {f['name']}'s proposal")
        notify("freelancer", f["id"], f"Your proposal for “{p['title']}” was {status}", f"#/project/{p['id']}")
        log_event("shortlist" if status == "shortlisted" else "decline", p, f)
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
        threads = rows(query.eq("freelancer_id", freelancer_id))
    else:
        mine = demo_client()["id"]
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


@app.get("/threads/{thread_id}/messages", tags=["chat"])
def get_messages(thread_id: str):
    one("threads", thread_id, "Thread")
    return rows(db().table("messages").select("*").eq("thread_id", thread_id).order("created_at"))


@app.post("/threads/{thread_id}/messages", status_code=201, tags=["chat"])
def send_message(thread_id: str, body: MessageIn):
    t = one("threads", thread_id, "Thread")
    msg = post_message(t["id"], body.sender, body.body.strip())
    db().table("threads").update({f"{body.sender}_read_at": msg["created_at"]}).eq("id", t["id"]).execute()
    return msg


@app.post("/threads/{thread_id}/read", tags=["chat"])
def mark_thread_read(thread_id: str, body: ReadIn):
    one("threads", thread_id, "Thread")
    latest = rows(db().table("messages").select("created_at").eq("thread_id", thread_id)
                  .order("created_at", desc=True).limit(1))
    if latest:
        db().table("threads").update({f"{body.role}_read_at": latest[0]["created_at"]}).eq("id", thread_id).execute()
    return {"ok": True}


# ---------------------------------------------------------------- notifications
@app.get("/notifications", tags=["notifications"])
def list_notifications(recipient_type: Literal["client", "freelancer"], recipient_id: str, limit: int = 20):
    return rows(db().table("notifications").select("*").eq("recipient_type", recipient_type)
                .eq("recipient_id", recipient_id).order("created_at", desc=True).limit(limit))


@app.post("/notifications/read", tags=["notifications"])
def mark_notifications_read(body: NotificationsReadIn):
    db().table("notifications").update({"read": True}).eq("recipient_type", body.recipient_type) \
        .eq("recipient_id", body.recipient_id).eq("read", False).execute()
    return {"ok": True}
