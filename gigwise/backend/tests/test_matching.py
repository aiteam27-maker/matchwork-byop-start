"""Checks that the Python match score gives the same results as the frontend.

Expected numbers were captured from gigwise/frontend/index.html in the browser.
Run from gigwise/backend:  python -m unittest discover tests
"""
import unittest

from app import matching
from seed.seed_data import build_rows

ROWS = build_rows()
FL = ROWS["freelancers"]
PJ = {p["id"]: p for p in ROWS["projects"]}

FITNESS = {
    "id": "x1", "title": "AI fitness coaching app", "type": "fixed", "budget": 6000, "hours": 120,
    "description": "We're building an AI fitness coaching app for iOS and Android. Users chat with an AI coach "
                   "that builds personalised workout and nutrition plans, tracks progress and sends reminders. "
                   "We need a clean, motivating UI and a simple backend with user accounts and subscriptions.",
}


def fid(n):
    return f"f{n:02d}"


class MatchesFrontend(unittest.TestCase):
    def test_skill_detection(self):
        skills = matching.detect_skills(FITNESS["title"] + " " + FITNESS["description"], FL)
        self.assertEqual(skills, ["Flutter", "LLM", "Stripe", "Node.js", "Firebase", "UI Design"])

    def test_fixed_price_ranking(self):
        p = dict(FITNESS, skills=matching.detect_skills(FITNESS["title"] + " " + FITNESS["description"], FL))
        r = matching.rank_freelancers(p, FL)
        got = [(m["freelancer_id"], m["total"]) for m in r["ranked"]]
        want = [(fid(a), b) for a, b in [(1, 89), (5, 70), (6, 64), (7, 53), (2, 51), (14, 49), (12, 47), (4, 45), (3, 31)]]
        self.assertEqual(got, want)
        self.assertEqual(sorted(h["freelancer_id"] for h in r["hidden"]), [fid(n) for n in [8, 9, 10, 11, 13]])
        self.assertEqual(
            r["ranked"][0]["reason"],
            "Covers 5 of 6 required skills (Flutter, LLM, Node.js +2). $48/hr fits your ~$50/hr budget, "
            "6 yrs experience, 4.9★ over 31 jobs. Built “Habit coach app”.",
        )

    def test_hourly_ranking(self):
        r = matching.rank_freelancers(PJ["p3"], FL)
        got = [(m["freelancer_id"], m["total"]) for m in r["ranked"]]
        self.assertEqual(got, [(fid(a), b) for a, b in [(3, 96), (7, 49), (8, 47), (1, 46), (14, 44)]])
        self.assertEqual(
            r["ranked"][0]["reason"],
            "Covers 4 of 4 required skills (Python, LLM, NLP +1). $70/hr is within your $50–$75/hr range, "
            "5 yrs experience, 4.9★ over 19 jobs. Built “Help-center RAG bot”.",
        )

    def test_reverse_matching(self):
        maya = next(f for f in FL if f["id"] == "f01")
        got = [(m["project_id"], m["total"]) for m in matching.rank_projects(maya, ROWS["projects"])]
        self.assertEqual(got, [("p6", 79), ("p5", 53), ("p1", 46), ("p2", 46), ("p3", 46)])

    def test_no_personal_attributes(self):
        """Changing name or location must not change the score."""
        p = PJ["p6"]
        f = dict(next(f for f in FL if f["id"] == "f01"))
        before = matching.score(f, p)["total"]
        f.update(name="Someone Else", location="Anywhere")
        self.assertEqual(matching.score(f, p)["total"], before)


if __name__ == "__main__":
    unittest.main()
