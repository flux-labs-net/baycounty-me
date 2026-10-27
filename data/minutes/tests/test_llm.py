"""Unit tests for data/llm.py batch handling on both providers (no network). Run: python3 -m unittest discover data/minutes/tests"""
import io
import json
import os
import sys
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import llm  # noqa: E402

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["meetings"],
          "properties": {"meetings": {"type": "array", "items": {"type": "string"}}}}


class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


class Fake:
    """Answers by URL; records each request."""
    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def __call__(self, req, timeout=0):
        self.seen.append(req)
        for key, out in self.routes:
            if key in req.full_url and (req.get_method() == key.split(" ")[0] if " " in key else True):
                return FakeResp(out if isinstance(out, bytes) else json.dumps(out).encode())
        raise AssertionError("unexpected " + req.full_url)


class T(unittest.TestCase):
    def setUp(self):
        self._open = urllib.request.urlopen
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ANTHROPIC_API_KEY"] = "test"

    def tearDown(self):
        urllib.request.urlopen = self._open
        os.environ.pop("OPENAI_API_KEY", None)

    def test_provider_and_keys(self):
        self.assertEqual(llm.provider("gpt-6.1-sol"), "openai")
        self.assertEqual(llm.provider("o4-mini"), "openai")
        self.assertEqual(llm.provider("claude-sonnet-5-5"), "anthropic")
        self.assertEqual(llm.key_name("gpt-5-mini"), "OPENAI_API_KEY")
        self.assertEqual(llm.batch_model(None, "batch_abc"), "gpt-5")
        self.assertEqual(llm.batch_model(None, "msgbatch_abc"), "claude-sonnet-5-5")
        self.assertIsNone(llm.price("gpt-unknown", 1, 1))

    def test_reasoning_settings(self):
        b = llm.openai_body("gpt-6.1-sol", "sys", "hi", SCHEMA, "x", 1000)
        self.assertEqual(b["reasoning_effort"], "low")
        self.assertEqual(b["messages"][0]["role"], "developer")
        self.assertGreater(b["max_completion_tokens"], 1000)
        b = llm.openai_body("gpt-4.1-mini", "sys", "hi", SCHEMA, "x", 1000)
        self.assertNotIn("reasoning_effort", b)
        self.assertEqual(b["max_completion_tokens"], 1000)

    def test_openai_batch_round_trip(self):
        good = {"choices": [{"message": {"content": json.dumps({"meetings": ["a"]})}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}
        cut = {"choices": [{"message": {"content": "{"}, "finish_reason": "length"}], "usage": {"prompt_tokens": 900, "completion_tokens": 50}}
        out = "\n".join(json.dumps(x) for x in [
            {"custom_id": "r1-c0", "response": {"status_code": 200, "body": good}, "error": None},
            {"custom_id": "r2-c0", "response": {"status_code": 200, "body": cut}, "error": None}]).encode()
        err = json.dumps({"custom_id": "r3-c0", "response": None, "error": {"code": "batch_expired", "message": "x"}}).encode()
        fake = Fake([("/files/out1/content", out), ("/files/err1/content", err),
                     ("/v1/files", {"id": "file-1"}),
                     ("/v1/batches/batch_1", {"id": "batch_1", "status": "completed", "output_file_id": "out1", "error_file_id": "err1",
                                              "request_counts": {"total": 3, "completed": 2, "failed": 1}}),
                     ("/v1/batches", {"id": "batch_1"})])
        urllib.request.urlopen = fake
        reqs = [llm.batch_request("gpt-6.1-sol", "r%d-c0" % i, "sys", "text", SCHEMA, "minutes", 1000) for i in (1, 2, 3)]
        self.assertEqual(reqs[0]["url"], "/v1/chat/completions")
        self.assertEqual(llm.batch_submit("gpt-6.1-sol", reqs), "batch_1")
        upload = fake.seen[0]
        self.assertIn(b'name="purpose"', upload.data)
        self.assertIn(b'"custom_id": "r1-c0"', upload.data)
        self.assertEqual(json.loads(fake.seen[1].data)["endpoint"], "/v1/chat/completions")
        self.assertEqual(llm.batch_state("gpt-6.1-sol", "batch_1"), ("ended", None))
        res = {r.custom_id: r for r in llm.batch_results("gpt-6.1-sol", "batch_1")}
        self.assertEqual(res["r1-c0"].answer, {"meetings": ["a"]})
        self.assertEqual((res["r1-c0"].tin, res["r1-c0"].tout), (1000, 200))
        self.assertEqual(res["r2-c0"].error, "model stopped: max_tokens")
        self.assertEqual(res["r2-c0"].tin, 900)   # a cut-off answer is still billed
        self.assertIn("batch_expired", res["r3-c0"].error)

    def test_openai_batch_running_and_failed(self):
        urllib.request.urlopen = Fake([("/v1/batches/b", {"status": "in_progress", "request_counts": {"total": 5, "completed": 2, "failed": 0}})])
        self.assertEqual(llm.batch_state("gpt-5", "b")[0], "running")
        urllib.request.urlopen = Fake([("/v1/batches/b", {"status": "failed", "errors": {"data": [{"message": "token limit"}]}})])
        state, note = llm.batch_state("gpt-5", "b")
        self.assertEqual(state, "failed")
        self.assertIn("token limit", note)

    def test_anthropic_batch_round_trip(self):
        msg = {"content": [{"type": "text", "text": json.dumps({"meetings": []})}], "stop_reason": "end_turn",
               "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 5}}
        lines = json.dumps({"custom_id": "r1-c0", "result": {"type": "succeeded", "message": msg}}).encode()
        urllib.request.urlopen = Fake([("results", lines),
                                       ("/messages/batches/mb", {"processing_status": "ended", "results_url": "https://api.anthropic.com/v1/messages/batches/mb/results"})])
        self.assertEqual(llm.batch_state("claude-sonnet-5-5", "mb"), ("ended", None))
        r = llm.batch_results("claude-sonnet-5-5", "mb")[0]
        self.assertEqual((r.answer, r.tin, r.tout, r.error), ({"meetings": []}, 100, 5, None))
        req = llm.batch_request("claude-sonnet-5-5", "r1-c0", "sys", "text", SCHEMA, "minutes", 1000)
        self.assertEqual(req["params"]["system"][0]["cache_control"], {"type": "ephemeral"})


if __name__ == "__main__":
    unittest.main()
