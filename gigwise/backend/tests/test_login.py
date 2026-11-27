"""Real login: signed-in users and the investor demo never see each other's data, and signed-in
users only see and act on their own private data. Uses the in-memory fake (no keys or network).

Run from gigwise/backend:  .venv/bin/python -m unittest discover tests
"""
import unittest
from datetime import date, timedelta
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, main
from seed.seed import reset_demo
from seed.seed_data import build_rows
from tests.fake_supabase import FakeSupabase

PROJECT = {
    "title": "Booking app for a yoga studio", "hours": 80, "budget": 4000, "skills": ["Flutter", "Firebase"],
    "description": "A mobile app where members book yoga classes, pay for passes and get reminders before class.",
}
PROFILE = {"name": "Ana Real", "title": "Flutter developer", "skills": ["Flutter", "Firebase", "Dart"], "rate": 45,
           "years": 4, "bio": "I build Flutter apps with Firebase backends."}
COVER = "Hi! I've built two class-booking apps in Flutter with Firebase and would love to help."


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSupabase(build_rows())
        self.patches = [mock.patch.object(main, "get_client", return_value=self.fake),
                        mock.patch.object(auth, "get_client", return_value=self.fake)]
        for p in self.patches:
            p.start()
        auth.forget_tokens()
        self.api = TestClient(main.app)
        for token, email in (("tok-client", "client@example.com"), ("tok-free", "free@example.com"),
                             ("tok-other", "other@example.com")):
            self.fake.add_user(token, email)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    # --- helpers
    def as_(self, token):
        return {"Authorization": f"Bearer {token}"}

    def call(self, method, path, token=None, **kw):
        headers = self.as_(token) if token else {}
        return self.api.request(method, path, headers=headers, **kw)

    def make_pair(self):
        """A real client with an open project, and a real freelancer who applied to it."""
        self.assertEqual(self.call("POST", "/clients", "tok-client", json={"name": "Lotus Yoga"}).status_code, 201)
        p = self.call("POST", "/projects", "tok-client", json=PROJECT).json()["project"]
        f = self.call("POST", "/freelancers", "tok-free", json=PROFILE).json()
        r = self.call("POST", f"/projects/{p['id']}/proposals", "tok-free",
                      json={"freelancer_id": f["id"], "cover_letter": COVER, "bid": 3800, "days": 30})
        self.assertEqual(r.status_code, 201, r.text)
        return p, f, r.json()

    # --- tests
    def test_bad_token_is_rejected_and_no_token_means_demo(self):
        self.assertEqual(self.call("GET", "/me", "made-up").status_code, 401)
        self.assertEqual(self.call("GET", "/state", "made-up").status_code, 401)
        me = self.call("GET", "/me").json()
        self.assertEqual((me["world"], me["client"]["name"]), ("demo", "Pulse Fit"))

    def test_new_user_starts_in_an_empty_real_world(self):
        me = self.call("GET", "/me", "tok-client").json()
        self.assertEqual((me["world"], me["user"]["email"], me["client"], me["freelancer"]),
                         ("real", "client@example.com", None, None))
        s = self.call("GET", "/state", "tok-client").json()
        self.assertEqual(s["world"], "real")
        self.assertEqual((s["freelancers"], s["projects"], s["clients"]), ([], [], []))
        # demo people and projects don't exist for a signed-in user
        self.assertEqual(self.call("GET", "/freelancers/f01", "tok-client").status_code, 404)
        self.assertEqual(self.call("GET", "/projects/p0", "tok-client").status_code, 404)
        # and they can't act as the demo client
        self.assertEqual(self.call("POST", "/projects", "tok-client", json=PROJECT).status_code, 403)

    def test_profiles_are_one_per_login(self):
        self.assertEqual(self.call("POST", "/clients", "tok-client", json={"name": "Lotus Yoga"}).status_code, 201)
        self.assertEqual(self.call("POST", "/clients", "tok-client", json={"name": "Again"}).status_code, 409)
        self.assertEqual(self.call("POST", "/clients", json={"name": "Demo visitor"}).status_code, 401)
        f = self.call("POST", "/freelancers", "tok-free", json=PROFILE).json()
        self.assertEqual(self.call("POST", "/freelancers", "tok-free", json=PROFILE).status_code, 409)
        # someone else can't edit it
        self.assertEqual(self.call("PUT", f"/freelancers/{f['id']}", "tok-other", json=PROFILE).status_code, 403)
        self.assertEqual(self.call("PUT", f"/freelancers/{f['id']}", "tok-free", json={**PROFILE, "rate": 50}).json()["rate"], 50)

    def test_real_and_demo_worlds_never_mix(self):
        p, f, _ = self.make_pair()
        demo = self.call("GET", "/state").json()
        self.assertNotIn(p["id"], [x["id"] for x in demo["projects"]])
        self.assertNotIn(f["id"], [x["id"] for x in demo["freelancers"]])
        self.assertEqual(self.call("GET", f"/projects/{p['id']}").status_code, 404)
        self.assertEqual(self.call("GET", f"/freelancers/{f['id']}").status_code, 404)
        self.assertNotIn(f["id"], [m["freelancer_id"] for m in self.call("GET", "/projects/p0/matches").json()["ranked"]])
        # a real freelancer can't apply to a demo project, and nobody can apply as them without their login
        self.assertEqual(self.call("POST", "/projects/p0/proposals", "tok-free",
                                   json={"freelancer_id": f["id"], "cover_letter": COVER, "bid": 3800, "days": 30}).status_code, 404)
        self.assertEqual(self.call("POST", f"/projects/{p['id']}/proposals",
                                   json={"freelancer_id": f["id"], "cover_letter": COVER, "bid": 3800, "days": 30}).status_code, 404)
        # real users only see real people
        real = self.call("GET", "/state", "tok-client").json()
        self.assertEqual([x["id"] for x in real["freelancers"]], [f["id"]])
        self.assertEqual([x["name"] for x in real["clients"]], ["Lotus Yoga"])
        self.assertTrue(all("user_id" not in x for x in real["clients"] + real["freelancers"]))

    def test_private_data_is_only_for_the_two_sides(self):
        p, f, q = self.make_pair()
        self.call("POST", "/freelancers", "tok-other", json={**PROFILE, "name": "Ben Other"})
        thread = self.call("GET", "/state", "tok-client").json()["threads"][0]

        # both sides see the proposal and the chat
        for tok in ("tok-client", "tok-free"):
            s = self.call("GET", "/state", tok).json()
            self.assertEqual([x["id"] for x in s["proposals"]], [q["id"]], tok)
            self.assertEqual(len(s["threads"]), 1, tok)
        # a third user sees the public project, but none of the private data
        other = self.call("GET", "/state", "tok-other").json()
        self.assertIn(p["id"], [x["id"] for x in other["projects"]])
        self.assertEqual((other["proposals"], other["threads"], other["messages"], other["notifications"]), ([], [], [], []))
        self.assertEqual(self.call("GET", f"/threads/{thread['id']}/messages", "tok-other").status_code, 403)
        self.assertEqual(self.call("POST", f"/threads/{thread['id']}/messages", "tok-other",
                                   json={"sender": "client", "body": "hi"}).status_code, 403)
        self.assertEqual(self.call("GET", f"/projects/{p['id']}/proposals", "tok-other").status_code, 403)
        self.assertEqual(self.call("GET", "/notifications", "tok-other",
                                   params={"recipient_type": "freelancer", "recipient_id": f["id"]}).status_code, 403)
        # each side may only speak as itself
        self.assertEqual(self.call("POST", f"/threads/{thread['id']}/messages", "tok-free",
                                   json={"sender": "client", "body": "pretending"}).status_code, 403)
        self.assertEqual(self.call("POST", f"/threads/{thread['id']}/messages", "tok-free",
                                   json={"sender": "freelancer", "body": "Happy to share examples."}).status_code, 201)

    def test_offer_and_contract_only_by_the_right_people(self):
        p, f, q = self.make_pair()
        due = (date.today() + timedelta(days=20)).isoformat()
        offer_body = {"milestones": [{"title": "App", "amount": 3800, "due_date": due}]}
        self.assertEqual(self.call("POST", f"/proposals/{q['id']}/offers", "tok-free", json=offer_body).status_code, 403)
        o = self.call("POST", f"/proposals/{q['id']}/offers", "tok-client", json=offer_body).json()
        self.assertEqual(self.call("GET", f"/offers/{o['id']}", "tok-other").status_code, 403)
        # the client can't accept on the freelancer's behalf (the demo's auto-accept can't run here)
        self.assertEqual(self.call("POST", f"/offers/{o['id']}/accept", "tok-client", json={"freelancer_id": f["id"]}).status_code, 403)
        self.assertEqual(self.call("POST", f"/offers/{o['id']}/accept", "tok-other", json={"freelancer_id": f["id"]}).status_code, 403)
        c = self.call("POST", f"/offers/{o['id']}/accept", "tok-free", json={"freelancer_id": f["id"]})
        self.assertEqual(c.status_code, 201, c.text)
        cid = c.json()["id"]
        self.assertEqual(self.call("GET", f"/contracts/{cid}", "tok-other").status_code, 403)
        self.assertEqual(self.call("POST", f"/contracts/{cid}/milestones/1/approve", "tok-free").status_code, 403)
        sub = self.call("POST", f"/contracts/{cid}/milestones/1/submit", "tok-free",
                        json={"freelancer_id": f["id"], "note": "First build is ready."})
        self.assertEqual(sub.status_code, 200, sub.text)
        self.assertEqual(self.call("POST", f"/contracts/{cid}/milestones/1/approve", "tok-client").status_code, 200)

    def test_demo_reset_keeps_real_accounts(self):
        p, f, q = self.make_pair()
        self.call("POST", "/projects", json=PROJECT)  # something new in the demo
        before = len(self.call("GET", "/state").json()["projects"])
        reset_demo(self.fake, log=lambda *_: None)
        demo = self.call("GET", "/state").json()
        self.assertEqual(len(demo["projects"]), before - 1)  # the demo is back to its original projects
        real = self.call("GET", "/state", "tok-client").json()
        self.assertEqual([x["id"] for x in real["projects"]], [p["id"]])
        self.assertEqual([x["id"] for x in real["proposals"]], [q["id"]])
        self.assertEqual(len(real["messages"]), 1)
        # and signed-in users can't trigger a reset at all
        self.assertEqual(self.call("POST", "/demo/reset", "tok-client").status_code, 403)


if __name__ == "__main__":
    unittest.main()
