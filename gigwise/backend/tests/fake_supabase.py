"""A tiny in-memory stand-in for the Supabase client, used only by tests.

Supports the subset the API uses: select (with simple embedded relations like
"*, clients(name)"), eq, neq, gte, in_, order, limit, insert, update, delete, and
auth.get_user(token) for logins made with add_user().
"""
from __future__ import annotations

import copy
import itertools
import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List

NUMERIC_ID = {"match_events", "notifications", "reviews", "milestones", "messages"}
PREFIX = {"clients": "c", "freelancers": "f", "projects": "p", "proposals": "q", "threads": "t", "offers": "o",
          "contracts": "k"}
DEFAULTS = {
    "projects": {"world": "demo", "status": "open", "extra_proposals": 0, "questions": [], "skills_auto": False, "hired_freelancer_id": None},
    "proposals": {"status": "submitted", "answers": [], "links": [], "connects_spent": 0, "edited_at": None},
    "threads": {"invited": False, "client_read_at": None, "freelancer_read_at": None},
    "notifications": {"read": False, "link": ""},
    "freelancers": {"world": "demo", "user_id": None, "connects": 40, "jss": None, "rating": None, "jobs": 0, "available": True, "hours_per_week": 30,
                    "portfolio": [], "employment": [], "education": [], "certifications": [], "languages": []},
    "clients": {"world": "demo", "user_id": None, "is_demo_user": False, "rating": None, "hires": 0},
    "offers": {"status": "pending", "milestones": [], "rate": None, "weekly_limit": None, "message": None, "proposal_id": None},
    "contracts": {"status": "active", "ended_at": None, "rate": None, "weekly_limit": None, "offer_id": None},
    "milestones": {"status": "pending", "note": None, "link": None, "changes_requested": None},
}
# Columns whose database default is now()
NOW_DEFAULTS = {"contracts": "started_at"}


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self.db, self.table_name = db, table
        self.op, self.payload, self.filters, self.orders, self.lim, self.embeds = "select", None, [], [], None, []

    # --- builders
    def select(self, cols="*"):
        self.op = "select"
        self.embeds = re.findall(r"(\w+)\(((?:[^()]|\([^()]*\))*)\)", cols)
        return self

    def insert(self, data, **_):
        self.op, self.payload = "insert", data
        return self

    def update(self, data):
        self.op, self.payload = "update", data
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, c, v):
        self.filters.append(lambda r: r.get(c) == v)
        return self

    def neq(self, c, v):
        self.filters.append(lambda r: r.get(c) != v)
        return self

    def gte(self, c, v):
        self.filters.append(lambda r: r.get(c) is not None and r.get(c) >= v)
        return self

    def in_(self, c, vs):
        vs = list(vs)
        self.filters.append(lambda r: r.get(c) in vs)
        return self

    def order(self, c, desc=False):
        self.orders.append((c, desc))
        return self

    def limit(self, n):
        self.lim = n
        return self

    # --- execution
    def _match(self):
        return [r for r in self.db.tables[self.table_name] if all(f(r) for f in self.filters)]

    def _embed(self, row, table, embeds):
        out = copy.deepcopy(row)
        for name, inner in embeds:
            fk = name[:-1] + "_id"
            target = next((r for r in self.db.tables[name] if r["id"] == row.get(fk)), None)
            out[name] = self._embed(target, name, re.findall(r"(\w+)\(((?:[^()]|\([^()]*\))*)\)", inner)) if target else None
        return out

    def execute(self):
        rows = self.db.tables[self.table_name]
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            created = []
            for item in items:
                row = {**DEFAULTS.get(self.table_name, {}), **copy.deepcopy(item)}
                if "id" not in row:
                    row["id"] = next(self.db.counter) if self.table_name in NUMERIC_ID else \
                        f"{PREFIX.get(self.table_name, 'x')}_{uuid.uuid4().hex[:12]}"
                row.setdefault("created_at", self.db.now())
                if self.table_name in NOW_DEFAULTS:
                    row.setdefault(NOW_DEFAULTS[self.table_name], row["created_at"])
                rows.append(row)
                created.append(copy.deepcopy(row))
            return Result(created)
        matched = self._match()
        if self.op == "update":
            for r in matched:
                r.update(copy.deepcopy(self.payload))
            return Result(copy.deepcopy(matched))
        if self.op == "delete":
            self.db.tables[self.table_name] = [r for r in rows if r not in matched]
            return Result(copy.deepcopy(matched))
        for c, desc in reversed(self.orders):
            matched = sorted(matched, key=lambda r: (r.get(c) is None, r.get(c)), reverse=desc)
        if self.lim is not None:
            matched = matched[: self.lim]
        return Result([self._embed(r, self.table_name, self.embeds) for r in matched])


class FakeSupabase:
    def __init__(self, seed: Dict[str, List[Dict[str, Any]]]):
        names = ["clients", "freelancers", "projects", "proposals", "threads", "messages", "offers", "contracts",
                 "milestones", "reviews", "notifications", "saved_jobs", "saved_freelancers", "match_events"]
        self.tables: Dict[str, List[Dict[str, Any]]] = {n: [] for n in names}
        self._users: Dict[str, Any] = {}
        self.counter = itertools.count(1)
        self._tick = itertools.count()
        self._base = datetime.now(timezone.utc).replace(microsecond=0)  # start at real time, then only move forward
        for table, rows in seed.items():
            Query(self, table).insert(rows).execute()

    def now(self) -> str:
        # strictly increasing timestamps so ordering in tests is deterministic
        return f"{self._base.isoformat()[:-6]}.{next(self._tick):06d}+00:00"

    def table(self, name: str) -> Query:
        return Query(self, name)

    # --- logins: tokens made with add_user() are valid, anything else is rejected like Supabase does
    def add_user(self, token: str, email: str) -> str:
        uid = str(uuid.uuid4())
        self._users[token] = SimpleNamespace(id=uid, email=email)
        return uid

    @property
    def auth(self):
        def get_user(token):
            if token not in self._users:
                raise Exception("invalid JWT")
            return SimpleNamespace(user=self._users[token])
        return SimpleNamespace(get_user=get_user)
