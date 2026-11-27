"""End-to-end API tests against an in-memory fake of Supabase (no keys or network needed).

Run from gigwise/backend:  .venv/bin/python -m unittest discover tests
"""
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import main
from seed.seed_data import build_rows
from tests.fake_supabase import FakeSupabase

FITNESS = {
    "title": "AI fitness coaching app", "hours": 120, "budget": 6000,
    "description": "We're building an AI fitness coaching app for iOS and Android. Users chat with an AI coach "
                   "that builds personalised workout and nutrition plans, tracks progress and sends reminders. "
                   "We need a clean, motivating UI and a simple backend with user accounts and subscriptions.",
    "questions": ["Which apps have you published?"],
}


class ApiFlow(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSupabase(build_rows())
        self.patch = mock.patch.object(main, "get_client", return_value=self.fake)
        self.patch.start()
        self.api = TestClient(main.app)

    def tearDown(self):
        self.patch.stop()

    def test_health_and_me(self):
        me = self.api.get("/me").json()
        self.assertEqual((me["world"], me["client"]["name"]), ("demo", "Pulse Fit"))

    def test_freelancer_filters_and_badges(self):
        r = self.api.get("/freelancers", params={"category": "Mobile Development", "available": True}).json()
        self.assertIn("f01", [f["id"] for f in r])
        self.assertNotIn("f11", [f["id"] for f in r])  # Lucas is booked
        maya = self.api.get("/freelancers/f01").json()
        self.assertIn("Top Rated", maya["badges"])
        omar = self.api.get("/freelancers/f13").json()
        self.assertEqual(omar["reviews"][0]["client_name"], "Pulse Fit")

    def test_full_client_and_freelancer_flow(self):
        # post with skills left blank -> detected, ranked
        r = self.api.post("/projects", json=FITNESS)
        self.assertEqual(r.status_code, 201, r.text)
        p, matches = r.json()["project"], r.json()["matches"]
        self.assertEqual(p["skills"], ["Flutter", "LLM", "Stripe", "Node.js", "Firebase", "UI Design"])
        self.assertTrue(p["skills_auto"])
        self.assertEqual((matches["ranked"][0]["freelancer_id"], matches["ranked"][0]["total"]), ("f01", 89))

        # invite Maya -> thread + notification + feedback event
        r = self.api.post(f"/projects/{p['id']}/invites", json={"freelancer_id": "f01", "message": "Would love a proposal!"})
        self.assertEqual(r.status_code, 201, r.text)
        notes = self.api.get("/notifications", params={"recipient_type": "freelancer", "recipient_id": "f01"}).json()
        self.assertIn("invited you", notes[0]["body"])

        # invited -> applying is free; missing screening answer is rejected
        bad = self.api.post(f"/projects/{p['id']}/proposals", json={
            "freelancer_id": "f01", "cover_letter": "I build Flutter apps with AI coaches.", "bid": 5800, "days": 28})
        self.assertEqual(bad.status_code, 422)
        ok = self.api.post(f"/projects/{p['id']}/proposals", json={
            "freelancer_id": "f01", "cover_letter": "I build Flutter apps with AI coaches.", "bid": 5800, "days": 28,
            "answers": ["Habit coach app on both stores"]})
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual(ok.json()["connects_spent"], 0)
        dup = self.api.post(f"/projects/{p['id']}/proposals", json={
            "freelancer_id": "f01", "cover_letter": "I build Flutter apps with AI coaches.", "bid": 5800, "days": 28,
            "answers": ["x"]})
        self.assertEqual(dup.status_code, 409)

        # not invited -> costs Connects
        r = self.api.post("/projects/p6/proposals", json={
            "freelancer_id": "f01", "cover_letter": "Yoga booking apps are my thing.", "bid": 4800, "days": 26,
            "answers": ["FitLab coach app"]})
        self.assertEqual(r.json()["connects_spent"], 6)
        self.assertEqual(self.api.get("/freelancers/f01").json()["connects"], 34)

        # client compares, shortlists; freelancer edits, then withdraws the other one
        props = self.api.get(f"/projects/{p['id']}/proposals").json()
        self.assertEqual(props[0]["match"]["total"], 89)
        qid = props[0]["id"]
        self.assertEqual(self.api.post(f"/proposals/{qid}/shortlist").json()["status"], "shortlisted")
        e = self.api.patch(f"/proposals/{qid}", json={"freelancer_id": "f01", "bid": 5600})
        self.assertEqual(e.json()["bid"], 5600)
        wrong = self.api.patch(f"/proposals/{qid}", json={"freelancer_id": "f02", "bid": 1})
        self.assertEqual(wrong.status_code, 403)
        other = r.json()["id"]
        self.assertEqual(self.api.post(f"/proposals/{other}/withdraw", params={"freelancer_id": "f01"}).json()["status"], "withdrawn")

        # chat
        threads = self.api.get("/threads", params={"role": "freelancer", "freelancer_id": "f01"}).json()
        t = next(t for t in threads if t["project_id"] == p["id"])
        self.assertTrue(t["invited"])
        self.assertEqual(t["unread"], 1)  # the client's invite message
        self.api.post(f"/threads/{t['id']}/read", json={"role": "freelancer"})
        self.api.post(f"/threads/{t['id']}/messages", json={"sender": "freelancer", "body": "Thanks! Proposal sent."})
        client_threads = self.api.get("/threads", params={"role": "client"}).json()
        ct = next(x for x in client_threads if x["id"] == t["id"])
        self.assertEqual(ct["unread"], 1)
        self.assertEqual(ct["last_message"]["body"], "Thanks! Proposal sent.")

        # feedback loop recorded hiring signals with scores
        events = [(e["event"], e["score"]) for e in self.fake.tables["match_events"]]
        self.assertIn(("invite", 89), events)
        self.assertIn(("shortlist", 89), events)

    def test_hourly_validation_and_reverse_matching(self):
        r = self.api.post("/projects", json={**FITNESS, "type": "hourly", "rate_min": 60, "rate_max": 40})
        self.assertEqual(r.status_code, 422)
        r = self.api.post("/projects", json={**FITNESS, "type": "hourly", "rate_min": 40, "rate_max": 55})
        self.assertEqual(r.json()["project"]["budget"], 55 * 120)
        rev = self.api.get("/freelancers/f01/matches").json()
        self.assertEqual(rev[0]["project_id"], r.json()["project"]["id"])
        self.assertTrue(rev[0]["reason"].startswith("You match 5 of the 6 skills they need"))

    def test_skill_catalog_rules(self):
        tax = self.api.get("/taxonomy").json()
        self.assertGreaterEqual(len(tax["categories"]), 10)
        # alternative spellings are converted to the catalog name, duplicates dropped
        r = self.api.post("/projects", json={**FITNESS, "skills": ["Flutter", "reactjs", "React", "postgres"],
                                             "category": "Mobile Development"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["project"]["skills"], ["Flutter", "React", "PostgreSQL"])
        self.assertEqual(r.json()["project"]["category"], "Mobile Development")
        # unknown skills, too many skills and unknown categories are refused
        self.assertEqual(self.api.post("/projects", json={**FITNESS, "skills": ["Basket weaving"]}).status_code, 422)
        many = [s for c in tax["categories"] for sp in c["specialties"] for s in sp["skills"]][:11]
        self.assertEqual(self.api.post("/projects", json={**FITNESS, "skills": many}).status_code, 422)
        self.assertEqual(self.api.post("/projects", json={**FITNESS, "category": "Underwater"}).status_code, 422)
        # with no category, it's worked out from the skills (first skill breaks ties)
        r = self.api.post("/projects", json=FITNESS).json()["project"]
        self.assertEqual(r["category"], "Mobile Development")

    def test_not_configured_message(self):
        self.patch.stop()
        with mock.patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}):
            main.get_client.cache_clear()
            r = TestClient(main.app).get("/freelancers")
            self.assertEqual(r.status_code, 503)
            self.assertIn("SUPABASE", r.json()["detail"])
            self.assertFalse(TestClient(main.app).get("/health").json()["ok"])
        self.patch.start()


if __name__ == "__main__":
    unittest.main()
