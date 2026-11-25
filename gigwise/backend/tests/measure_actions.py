"""Measure how long each user action takes against the real database, and how many
database calls it makes. Run from gigwise/backend:

    .venv/bin/python -m tests.measure_actions

It creates demo data along the way and resets the demo data at the end.
"""
import time
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import main
from seed.seed import reset_demo

CALLS = {"n": 0}


def count_calls():
    """Wrap the Supabase request so every database round trip is counted."""
    from postgrest._sync.request_builder import SyncQueryRequestBuilder, SyncSingleRequestBuilder

    for cls in (SyncQueryRequestBuilder, SyncSingleRequestBuilder):
        original = cls.execute

        def wrapped(self, *a, _orig=original, **k):
            CALLS["n"] += 1
            return _orig(self, *a, **k)

        cls.execute = wrapped


def timed(api, label, method, path, **kw):
    CALLS["n"] = 0
    start = time.time()
    r = getattr(api, method)(path, **kw)
    ms = round((time.time() - start) * 1000)
    assert r.status_code < 300, (label, r.status_code, r.text[:200])
    print(f"  {label:<26} {ms:>5} ms  {CALLS['n']:>2} database calls")
    return r.json(), ms


def run():
    count_calls()
    api = TestClient(main.app)
    api.get("/health")
    api.get("/demo/state")  # warm up connections
    due = (date.today() + timedelta(days=10)).isoformat()
    total = 0
    desc = ("We're building an AI fitness coaching app for iOS and Android. Users chat with an AI coach. "
            "We need a clean UI and a simple backend with user accounts and subscriptions.")
    r, ms = timed(api, "post project", "post", "/projects",
                  json={"title": "AI fitness coaching app", "description": desc, "budget": 6000, "hours": 120}); total += ms
    pid = r["project"]["id"]
    _, ms = timed(api, "invite", "post", f"/projects/{pid}/invites", json={"freelancer_id": "f01", "message": "Hi!"}); total += ms
    q, ms = timed(api, "submit proposal", "post", f"/projects/{pid}/proposals",
                  json={"freelancer_id": "f01", "cover_letter": "I build Flutter apps with AI coaches.", "bid": 5800, "days": 28}); total += ms
    _, ms = timed(api, "shortlist", "post", f"/proposals/{q['id']}/shortlist"); total += ms
    o, ms = timed(api, "send offer", "post", f"/proposals/{q['id']}/offers",
                  json={"milestones": [{"title": "Prototype", "amount": 2000, "due_date": due},
                                       {"title": "Launch", "amount": 3800, "due_date": due}]}); total += ms
    c, ms = timed(api, "accept offer", "post", f"/offers/{o['id']}/accept", json={"freelancer_id": "f01"}); total += ms
    _, ms = timed(api, "submit milestone", "post", f"/contracts/{c['id']}/milestones/1/submit",
                  json={"freelancer_id": "f01", "note": "Prototype is ready."}); total += ms
    _, ms = timed(api, "approve milestone", "post", f"/contracts/{c['id']}/milestones/1/approve"); total += ms
    _, ms = timed(api, "end contract", "post", f"/contracts/{c['id']}/end", json={"role": "client"}); total += ms
    _, ms = timed(api, "leave review", "post", f"/contracts/{c['id']}/reviews",
                  json={"role": "client", "rating": 5, "body": "Great work, thanks!"}); total += ms
    _, ms = timed(api, "reload all data", "get", "/demo/state"); total += ms
    print(f"  {'TOTAL':<26} {total:>5} ms")
    reset_demo(main.db(), log=lambda *_: None)
    print("  (demo data reset)")


if __name__ == "__main__":
    run()
