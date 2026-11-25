"""Offers, contracts, milestones, reviews, saved items and profiles, against the in-memory fake.

Run from gigwise/backend:  .venv/bin/python -m unittest discover tests
"""
import unittest
from datetime import date, timedelta
from unittest import mock

from fastapi.testclient import TestClient

from app import main
from seed.seed_data import build_rows
from tests.fake_supabase import FakeSupabase


def due(days):
    return (date.today() + timedelta(days=days)).isoformat()


class Hiring(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSupabase(build_rows())
        self.patch = mock.patch.object(main, "get_client", return_value=self.fake)
        self.patch.start()
        self.api = TestClient(main.app)

    def tearDown(self):
        self.patch.stop()

    def notes(self, rtype, rid):
        return [n["body"] for n in self.api.get("/notifications", params={"recipient_type": rtype, "recipient_id": rid}).json()]

    def test_fixed_price_lifecycle(self):
        # offer on Daniel's proposal (q1, project p1, fixed $3,000)
        bad = self.api.post("/proposals/q1/offers", json={"message": "Let's go"})
        self.assertEqual(bad.status_code, 422)  # fixed needs milestones
        offer = self.api.post("/proposals/q1/offers", json={
            "message": "We'd love to work with you.",
            "milestones": [{"title": "Landing + pricing", "amount": 1300, "due_date": due(10)},
                           {"title": "Blog + launch", "amount": 1900, "due_date": due(21)}]})
        self.assertEqual(offer.status_code, 201, offer.text)
        o = offer.json()
        self.assertIn("sent you an offer", self.notes("freelancer", "f02")[0])
        again = self.api.post("/proposals/q2/offers", json={"milestones": [{"title": "x", "amount": 1, "due_date": due(5)}]})
        self.assertEqual(again.status_code, 409)  # one pending offer per project
        self.assertEqual(len(self.api.get("/offers", params={"role": "client"}).json()), 1)
        self.assertEqual(self.api.get("/offers", params={"role": "freelancer", "freelancer_id": "f02"}).json()[0]["id"], o["id"])

        # only Daniel can accept; a pending offer blocks withdrawing or editing the proposal
        self.assertEqual(self.api.post(f"/offers/{o['id']}/accept", json={"freelancer_id": "f10"}).status_code, 403)
        self.assertEqual(self.api.post("/proposals/q1/withdraw", params={"freelancer_id": "f02"}).status_code, 409)
        c = self.api.post(f"/offers/{o['id']}/accept", json={"freelancer_id": "f02"})
        self.assertEqual(c.status_code, 201, c.text)
        c = c.json()
        self.assertEqual([m["status"] for m in c["milestones"]], ["active", "pending"])
        self.assertEqual(self.api.get("/projects/p1").json()["status"], "hired")
        self.assertEqual(self.fake.tables["proposals"][2]["status"], "accepted")  # q1
        self.assertEqual(self.api.post(f"/offers/{o['id']}/decline", json={"freelancer_id": "f02"}).status_code, 409)

        # submit -> request changes -> resubmit -> approve -> next milestone active
        cid = c["id"]
        self.assertEqual(self.api.post(f"/contracts/{cid}/milestones/2/submit",
                                       json={"freelancer_id": "f02", "note": "too early"}).status_code, 409)
        r = self.api.post(f"/contracts/{cid}/milestones/1/submit",
                          json={"freelancer_id": "f02", "note": "Landing and pricing are on staging.", "link": "staging.example.com"})
        self.assertEqual(r.json()["status"], "submitted")
        self.assertIn("for your review", self.notes("client", "c_pulse")[0])
        r = self.api.post(f"/contracts/{cid}/milestones/1/request-changes", json={"note": "Smaller hero image on mobile."})
        self.assertEqual((r.json()["status"], r.json()["changes_requested"]), ("active", "Smaller hero image on mobile."))
        self.api.post(f"/contracts/{cid}/milestones/1/submit", json={"freelancer_id": "f02", "note": "Fixed the hero image."})
        r = self.api.post(f"/contracts/{cid}/milestones/1/approve").json()
        self.assertEqual([m["status"] for m in r["milestones"]], ["approved", "active"])

        listed = self.api.get("/contracts", params={"role": "freelancer", "freelancer_id": "f02"}).json()
        self.assertEqual((listed[0]["milestones_approved"], listed[0]["milestones_total"], listed[0]["amount_total"]), (1, 2, 3200))

        # reviews only after the contract ends; client review updates Daniel's rating and jobs
        self.assertEqual(self.api.post(f"/contracts/{cid}/reviews",
                                       json={"role": "client", "rating": 5, "body": "Great work"}).status_code, 409)
        ended = self.api.post(f"/contracts/{cid}/end", json={"role": "client"}).json()
        self.assertEqual(ended["status"], "ended")
        self.assertEqual(self.api.get("/projects/p1").json()["status"], "ended")
        before = self.api.get("/freelancers/f02").json()
        r = self.api.post(f"/contracts/{cid}/reviews", json={"role": "client", "rating": 4, "body": "Solid work, quick to respond."})
        self.assertEqual(r.status_code, 201, r.text)
        after = self.api.get("/freelancers/f02").json()
        self.assertEqual((before["rating"], before["jobs"], before["jss"]), (4.8, 52, 95))
        self.assertEqual((after["rating"], after["jobs"], after["jss"]), (4.8, 53, 95))  # same maths as the frontend
        self.assertEqual(after["reviews"][0]["body"], "Solid work, quick to respond.")
        dup = self.api.post(f"/contracts/{cid}/reviews", json={"role": "client", "rating": 5, "body": "Again please"})
        self.assertEqual(dup.status_code, 409)
        wrong = self.api.post(f"/contracts/{cid}/reviews",
                              json={"role": "freelancer", "freelancer_id": "f10", "rating": 5, "body": "Not my contract"})
        self.assertEqual(wrong.status_code, 403)
        ok = self.api.post(f"/contracts/{cid}/reviews",
                           json={"role": "freelancer", "freelancer_id": "f02", "rating": 5, "body": "Clear goals, fast feedback."})
        self.assertEqual(ok.status_code, 201)
        self.assertIn("left you 5★ feedback", self.notes("client", "c_pulse")[0])

        events = [e["event"] for e in self.fake.tables["match_events"]]
        for ev in ("offer", "hire", "review"):
            self.assertIn(ev, events)

    def test_hourly_offer_decline_and_withdraw(self):
        # Maya applies to the hourly RAG project (p3 belongs to another client, so make one of ours)
        p = self.api.post("/projects", json={
            "title": "Chatbot for our app", "description": "An AI chatbot assistant for our fitness app users.",
            "type": "hourly", "rate_min": 40, "rate_max": 60, "hours": 80}).json()["project"]
        q = self.api.post(f"/projects/{p['id']}/proposals", json={
            "freelancer_id": "f01", "cover_letter": "I build LLM chat coaches in Flutter.", "bid": 48, "days": 20}).json()
        self.assertEqual(self.api.post(f"/proposals/{q['id']}/offers", json={"rate": 48}).status_code, 422)
        o = self.api.post(f"/proposals/{q['id']}/offers", json={"rate": 48, "weekly_limit": 20}).json()
        self.assertEqual((o["type"], o["rate"], o["weekly_limit"]), ("hourly", 48, 20))
        self.assertEqual(self.api.post(f"/offers/{o['id']}/decline", json={"freelancer_id": "f01"}).json()["status"], "declined")
        self.assertIn("declined your offer", self.notes("client", "c_pulse")[0])
        o2 = self.api.post(f"/proposals/{q['id']}/offers", json={"rate": 52, "weekly_limit": 25}).json()
        self.assertEqual(self.api.post(f"/offers/{o2['id']}/withdraw").json()["status"], "withdrawn")
        o3 = self.api.post(f"/proposals/{q['id']}/offers", json={"rate": 50, "weekly_limit": 25}).json()
        c = self.api.post(f"/offers/{o3['id']}/accept", json={"freelancer_id": "f01"}).json()
        self.assertEqual((c["type"], c["rate"], c["milestones"]), ("hourly", 50, []))
        end = self.api.post(f"/contracts/{c['id']}/end", json={"role": "freelancer", "freelancer_id": "f01"})
        self.assertEqual(end.json()["status"], "ended")
        self.assertIn("ended the contract", self.notes("client", "c_pulse")[0])

    def test_offer_on_other_clients_project_is_refused(self):
        q = self.api.post("/projects/p6/proposals", json={
            "freelancer_id": "f06", "cover_letter": "Flutter booking apps are my speciality.", "bid": 4000, "days": 30,
            "answers": ["Yoga class app"]}).json()
        r = self.api.post(f"/proposals/{q['id']}/offers", json={"milestones": [{"title": "All", "amount": 4000, "due_date": due(30)}]})
        self.assertEqual(r.status_code, 403)

    def test_saved_items(self):
        self.api.put("/freelancers/f01/saved-jobs/p6")
        self.api.put("/freelancers/f01/saved-jobs/p6")  # saving twice is harmless
        saved = self.api.get("/freelancers/f01/saved-jobs").json()
        self.assertEqual([s["project_id"] for s in saved], ["p6"])
        self.assertEqual(saved[0]["projects"]["title"], "Flutter app for yoga studio bookings")
        self.api.delete("/freelancers/f01/saved-jobs/p6")
        self.assertEqual(self.api.get("/freelancers/f01/saved-jobs").json(), [])
        self.api.put("/saved-freelancers/f03")
        self.assertEqual([s["freelancer_id"] for s in self.api.get("/saved-freelancers").json()], ["f03"])
        self.api.delete("/saved-freelancers/f03")
        self.assertEqual(self.api.get("/saved-freelancers").json(), [])

    def test_create_and_edit_profile(self):
        body = {"name": "Sam T.", "title": "Flutter + AI developer", "skills": ["Flutter", "LLM", "Firebase"],
                "rate": 45, "years": 3, "bio": "I build Flutter apps with chatbot coaches.",
                "portfolio": [{"title": "Coach bot", "description": "LLM coach in Flutter"}],
                "languages": [{"language": "English", "level": "Fluent"}]}
        f = self.api.post("/freelancers", json=body)
        self.assertEqual(f.status_code, 201, f.text)
        f = f.json()
        self.assertEqual((f["connects"], f["rating"], f["jobs"]), (40, None, 0))
        self.assertIn("Rising Talent", f["badges"])
        matches = self.api.get(f"/freelancers/{f['id']}/matches").json()
        self.assertTrue(matches and matches[0]["reason"].startswith(("You match", "You have every skill")))
        upd = self.api.put(f"/freelancers/{f['id']}", json={**body, "rate": 50, "available": False}).json()
        self.assertEqual((upd["rate"], upd["available"], upd["connects"]), (50, False, 40))
        self.assertEqual(self.api.post("/freelancers", json={**body, "skills": []}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
