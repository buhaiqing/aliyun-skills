#!/usr/bin/env python3
"""Unit tests for langfuse_token_report.py"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import langfuse_token_report as ltr  # noqa: E402


class TestCredentialLoading(unittest.TestCase):
    """Tests for load_credentials()."""

    def setUp(self):
        for k in ("LANGFUSE_HOST", "LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY",
                  "LANGFUSE_SECRET_KEY", "LANGFUSE_ENV_FILE"):
            os.environ.pop(k, None)

    def test_missing_credentials_exits_with_code_1(self):
        """When all credentials are missing, exit with code 1."""
        buf = io.StringIO()
        with redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                ltr.load_credentials()
        self.assertEqual(cm.exception.code, ltr.EXIT_NO_CREDS)
        self.assertIn("BLOCKED:no-credentials", buf.getvalue())

    def test_credentials_from_env_vars(self):
        """When credentials are set as env vars, return them."""
        os.environ["LANGFUSE_HOST"] = "https://test.langfuse.com"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"
        host, pk, sk = ltr.load_credentials()
        self.assertEqual(host, "https://test.langfuse.com")
        self.assertEqual(pk, "pk-test")
        self.assertEqual(sk, "sk-test")

    def test_credentials_from_env_file(self, tmp_path=None):
        """When LANGFUSE_ENV_FILE points to a .env file, load from it."""
        env_file = Path(SCRIPT_DIR) / ".env.test"
        env_file.write_text(
            "LANGFUSE_HOST=https://from-file.langfuse.com\n"
            "LANGFUSE_PUBLIC_KEY=pk-fromfile\n"
            "LANGFUSE_SECRET_KEY=sk-fromfile\n"
        )
        try:
            os.environ["LANGFUSE_ENV_FILE"] = str(env_file)
            host, pk, sk = ltr.load_credentials()
            self.assertEqual(host, "https://from-file.langfuse.com")
            self.assertEqual(pk, "pk-fromfile")
            self.assertEqual(sk, "sk-fromfile")
        finally:
            env_file.unlink(missing_ok=True)


class TestApiClient(unittest.TestCase):
    """Tests for LangfuseClient."""

    def test_auth_header_uses_base64(self):
        """Auth header is Base64-encoded 'pk:sk' with Basic prefix."""
        c = ltr.LangfuseClient(host="https://x", public_key="pk-abc", secret_key="sk-xyz")
        h = c._auth_header()
        self.assertTrue(h.startswith("Basic "))
        # Decode and verify
        import base64
        raw = base64.b64decode(h.split(" ", 1)[1]).decode()
        self.assertEqual(raw, "pk-abc:sk-xyz")

    def test_fetch_traces_page_parses_response(self):
        """fetch_traces_page should parse JSON response."""
        c = ltr.LangfuseClient(host="https://x", public_key="pk", secret_key="sk")
        fake_resp = json.dumps({"data": [{"id": "t1"}], "meta": {"page": 1, "totalPages": 1}}).encode()

        class MockCtx:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return fake_resp

        with patch("urllib.request.urlopen", return_value=MockCtx()) as mock:
            resp = c.fetch_traces_page(1, 10)
        self.assertEqual(resp["data"][0]["id"], "t1")
        mock.assert_called_once()

    def test_fetch_traces_page_raises_on_401(self):
        """HTTP 401 should raise LangfuseAPIError with EXIT_AUTH code."""
        import urllib.error
        c = ltr.LangfuseClient(host="https://x", public_key="bad", secret_key="bad")
        err = urllib.error.HTTPError(
            url="https://x", code=401, msg="Unauthorized", hdrs={}, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(ltr.LangfuseAPIError) as cm:
                c.fetch_traces_page(1, 10)
        self.assertEqual(cm.exception.exit_code, ltr.EXIT_AUTH)

    def test_fetch_traces_page_raises_on_repeated_429(self):
        """Repeated HTTP 429 should eventually raise LangfuseAPIError."""
        import urllib.error
        c = ltr.LangfuseClient(host="https://x", public_key="pk", secret_key="sk", max_retries=2)
        err = urllib.error.HTTPError(
            url="https://x", code=429, msg="Too Many", hdrs={}, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with patch("time.sleep", return_value=None):
                with self.assertRaises(ltr.LangfuseAPIError) as cm:
                    c.fetch_traces_page(1, 10)
        self.assertEqual(cm.exception.exit_code, ltr.EXIT_RATE)


class TestAggregation(unittest.TestCase):
    """Tests for aggregate_by_session()."""

    def test_empty_input(self):
        self.assertEqual(ltr.aggregate_by_session([]), [])

    def test_filters_out_traces_without_llm_usage(self):
        """Only traces with has_llm_usage=true or total_tokens>0 are kept."""
        traces = [
            {"id": "t1", "metadata": {"session_id": "s1", "has_llm_usage": True,
                                       "llm_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}},
            {"id": "t2", "metadata": {"session_id": "s1", "has_llm_usage": False,
                                       "llm_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}},
        ]
        result = ltr.aggregate_by_session(traces)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].trace_count, 1)
        self.assertEqual(result[0].total_tokens, 150)

    def test_aggregates_multiple_traces_same_session(self):
        """Multiple traces in same session should accumulate tokens."""
        traces = [
            {"id": "t1", "timestamp": "2026-07-30T10:00:00Z",
             "metadata": {"session_id": "sess-A", "has_llm_usage": True,
                          "skill": "ecs", "user_id": "alice",
                          "llm_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}},
            {"id": "t2", "timestamp": "2026-07-30T11:00:00Z",
             "metadata": {"session_id": "sess-A", "has_llm_usage": True,
                          "skill": "rds", "user_id": "alice",
                          "llm_usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}}},
        ]
        result = ltr.aggregate_by_session(traces)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].trace_count, 2)
        self.assertEqual(result[0].total_tokens, 450)
        self.assertEqual(result[0].prompt_tokens, 300)
        self.assertEqual(result[0].skill_set, {"ecs", "rds"})

    def test_buckets_missing_session_id(self):
        """Traces without session_id are bucketed as (no-session)."""
        traces = [
            {"id": "t1", "metadata": {"has_llm_usage": True,
                                       "llm_usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}},
        ]
        result = ltr.aggregate_by_session(traces)
        self.assertEqual(result[0].session_id, "(no-session)")

    def test_sorted_by_total_tokens_descending(self):
        """Sessions are sorted by total_tokens descending."""
        traces = [
            {"id": "t1", "metadata": {"session_id": "small", "has_llm_usage": True,
                                       "llm_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}},
            {"id": "t2", "metadata": {"session_id": "large", "has_llm_usage": True,
                                       "llm_usage": {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600}}},
        ]
        result = ltr.aggregate_by_session(traces)
        self.assertEqual(result[0].session_id, "large")
        self.assertEqual(result[1].session_id, "small")


class TestBuildReport(unittest.TestCase):
    """Tests for build_report()."""

    def test_summary_aggregates_totals(self):
        sess = [
            ltr.SessionAggregate(session_id="s1", trace_count=2,
                                 prompt_tokens=100, completion_tokens=50, total_tokens=150),
            ltr.SessionAggregate(session_id="s2", trace_count=3,
                                 prompt_tokens=200, completion_tokens=80, total_tokens=280),
        ]
        report = ltr.build_report(sess, "2026-07-23T00:00:00Z", "2026-07-30T00:00:00Z")
        self.assertEqual(report["summary"]["total_sessions"], 2)
        self.assertEqual(report["summary"]["total_traces"], 5)
        self.assertEqual(report["summary"]["total_tokens"], 430)
        self.assertEqual(report["summary"]["total_prompt_tokens"], 300)


class TestRenderTable(unittest.TestCase):
    """Tests for render_table()."""

    def test_renders_session_id_and_tokens(self):
        report = {
            "version": "1.0.0",
            "period": {"from": "2026-07-23T00:00:00Z", "to": "2026-07-30T00:00:00Z", "days": 7},
            "summary": {"total_sessions": 1, "total_traces": 5, "total_prompt_tokens": 100,
                        "total_completion_tokens": 50, "total_tokens": 150},
            "sessions": [
                {"session_id": "sess-test", "user_id": "alice", "trace_count": 5,
                 "skill_count": 1, "skills": ["ecs"],
                 "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
                 "first_trace_at": "2026-07-23T00:00:00Z", "last_trace_at": "2026-07-30T00:00:00Z"}
            ],
        }
        out = ltr.render_table(report)
        self.assertIn("sess-test", out)
        self.assertIn("150", out)
        self.assertIn("alice", out)

    def test_empty_sessions_shows_placeholder(self):
        report = {
            "version": "1.0.0",
            "period": {"from": "", "to": "", "days": 0},
            "summary": {"total_sessions": 0, "total_traces": 0,
                        "total_prompt_tokens": 0, "total_completion_tokens": 0,
                        "total_tokens": 0},
            "sessions": [],
        }
        out = ltr.render_table(report)
        self.assertIn("no session records", out)


class TestCliIntegration(unittest.TestCase):
    """Integration tests for CLI commands with mocked Langfuse API."""

    def setUp(self):
        os.environ["LANGFUSE_HOST"] = "https://test.langfuse.com"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"

    def tearDown(self):
        for k in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_pull_command_outputs_table(self):
        """`pull` command should output table by default."""
        fake_traces = [
            {"id": "t1", "timestamp": "2026-07-30T10:00:00Z",
             "metadata": {"session_id": "sess-A", "has_llm_usage": True,
                          "skill": "ecs", "user_id": "alice",
                          "llm_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}}
        ]
        with patch.object(ltr.LangfuseClient, "iter_traces", return_value=fake_traces):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ltr.main(["pull", "--since-days", "1"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("sess-A", out)
        self.assertIn("150", out)

    def test_pull_command_json_output(self):
        """`pull --format json` should output valid JSON."""
        fake_traces = [
            {"id": "t1", "timestamp": "2026-07-30T10:00:00Z",
             "metadata": {"session_id": "s1", "has_llm_usage": True,
                          "skill": "ecs", "user_id": "u",
                          "llm_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}}
        ]
        with patch.object(ltr.LangfuseClient, "iter_traces", return_value=fake_traces):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ltr.main(["pull", "--since-days", "1", "--format", "json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["summary"]["total_tokens"], 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
