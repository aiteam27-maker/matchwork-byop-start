"""Claude-written text, tested with a stand-in for the Claude API (no key or network needed).

Run from gigwise/backend:  .venv/bin/python -m unittest discover tests
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app import ai, main
from seed.seed_data import build_rows
from tests.fake_supabase import FakeSupabase


class FakeClaude:
    """Records each request and replies like the Messages API would."""

    def __init__(self, reply=None, stop_reason="end_turn", error=None):
        self.requests = []
        self.reply, self.stop_reason, self.error = reply, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        payload = json.loads(kwargs["messages"][0]["content"])
        if callable(self.reply):
            text = self.reply(payload)
        else:
            text = self.reply
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])


def explain_reply(payload):
    return json.dumps({"explanations": [
        {"id": c["id"], "client_reason": f"Strong fit: covers {len(c['matched_required_skills'])} skills.",
         "freelancer_reason": f"You cover {len(c['matched_required_skills'])} of the skills they need."}
        for c in payload["candidates"]]})


class AiTests(unittest.TestCase):
    def setUp(self):
        self.fake_db = FakeSupabase(build_rows())
        self.patches = [mock.patch.object(main, "get_client", return_value=self.fake_db),
                        mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"})]
        for p in self.patches:
            p.start()
        ai._cache.clear()
        ai._calls.clear()
        self.api = TestClient(main.app)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def use(self, claude):
        patcher = mock.patch.object(ai, "_get_client", return_value=claude)
        patcher.start()
        self.addCleanup(patcher.stop)
        return claude

    def test_explanations_are_grounded_and_mapped(self):
        claude = self.use(FakeClaude(reply=explain_reply))
        r = self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01", "f06", "f05"]}).json()
        self.assertTrue(r["enabled"])
        self.assertEqual(set(r["explanations"]), {"f01", "f06", "f05"})
        self.assertIn("covers 3 skills", r["explanations"]["f01"]["client_reason"])  # Flutter, Firebase, UI Design

        req = claude.requests[0]
        self.assertEqual(req["model"], "claude-opus-5-5")
        self.assertEqual(req["output_config"]["effort"], "low")
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(req["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(req["fallbacks"], "default")
        sent = req["messages"][0]["content"]
        for private in ("Maya", "Sofia", "Wei", "Lisbon", "Portugal", "Kraków", "Singapore"):
            self.assertNotIn(private, sent, f"{private} must never be sent to Claude")
        self.assertNotIn("location", sent)

        # asking again is served from the cache: no new request
        self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01"]})
        self.assertEqual(len(claude.requests), 1)

    def test_draft_proposal(self):
        claude = self.use(FakeClaude(reply="I build Flutter booking apps with Firebase and calm, clear interfaces."))
        r = self.api.post("/ai/draft-proposal", json={"project_id": "p6", "freelancer_id": "f01", "bid": 4800, "days": 26}).json()
        self.assertEqual(r["cover_letter"], "I build Flutter booking apps with Firebase and calm, clear interfaces.")
        payload = json.loads(claude.requests[0]["messages"][0]["content"])
        self.assertEqual(payload["proposed_bid_usd"], 4800)
        self.assertNotIn("Maya", json.dumps(payload))
        self.assertNotIn("Lisbon", json.dumps(payload))

    def test_failures_fall_back_to_templates(self):
        self.use(FakeClaude(reply="{}", stop_reason="refusal"))
        r = self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01"]}).json()
        self.assertEqual(r["explanations"], {})
        self.use(FakeClaude(reply="not json"))
        self.assertEqual(self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01"]}).json()["explanations"], {})
        import anthropic
        err = anthropic.APIConnectionError(request=mock.Mock())
        self.use(FakeClaude(error=err))
        r = self.api.post("/ai/draft-proposal", json={"project_id": "p6", "freelancer_id": "f01"}).json()
        self.assertIsNone(r["cover_letter"])

    def test_unknown_ids_in_reply_are_ignored(self):
        self.use(FakeClaude(reply=json.dumps({"explanations": [{"id": "Z", "client_reason": "x", "freelancer_reason": "y"}]})))
        r = self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01"]}).json()
        self.assertEqual(r["explanations"], {})

    def test_rate_cap(self):
        claude = self.use(FakeClaude(reply="Draft text for this project."))
        with mock.patch.object(ai, "MAX_CALLS_PER_MINUTE", 2):
            results = [self.api.post("/ai/draft-proposal", json={"project_id": "p6", "freelancer_id": "f01", "bid": b}).json()
                       for b in (1000, 2000, 3000)]
        self.assertEqual([r["cover_letter"] is not None for r in results], [True, True, False])
        self.assertEqual(len(claude.requests), 2)

    def test_disabled_without_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertEqual(self.api.post("/ai/explain", json={"project_id": "p6", "freelancer_ids": ["f01"]}).json(),
                             {"enabled": False, "explanations": {}})
            self.assertFalse(ai.enabled())


if __name__ == "__main__":
    unittest.main()
