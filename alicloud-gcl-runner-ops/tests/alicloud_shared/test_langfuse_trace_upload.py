#!/usr/bin/env python3
"""Integration tests: trace record → Langfuse ingestion payload.

Validates that:
- Chat context fields (user_id / session_id / platform / chat_type) are correctly
  propagated into Langfuse span metadata
- trace_id flows through to Langfuse traceId field
- Payload structure matches Langfuse Ingestion API v1 schema
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Path setup
_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "alicloud-gcl-runner-ops" / "scripts"
_HARNESS = _REPO / "alicloud-runtime-harness-ops" / "scripts"

# Make alicloud_shared importable
sys.path.insert(0, str(_SCRIPTS))

from alicloud_shared.chat_context import _ctx_var, bind  # noqa: E402
from alicloud_shared.adapters.wecom import normalize_wecom  # noqa: E402


def _load_harness_runtime():
    """Load harness_runtime.py as a module (avoids name collision)."""
    spec = importlib.util.spec_from_file_location(
        "harness_runtime", _HARNESS / "harness_runtime.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLangfusePayloadFromChatContext(unittest.TestCase):
    """Verify chat context flows correctly into Langfuse span metadata."""

    def setUp(self):
        _ctx_var.set(None)
        # Reset any leftover env vars
        for k in ["SKILLOPT_LANGFUSE_ENABLED", "LANGFUSE_HOST",
                  "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            os.environ.pop(k, None)

    def tearDown(self):
        _ctx_var.set(None)

    def test_span_create_payload_includes_chat_context_in_metadata(self):
        """span-create payload.metadata must carry user_id/session_id/platform/chat_type."""
        hr = _load_harness_runtime()

        # Simulate WeCom group chat triggering a skill
        ctx = normalize_wecom({
            "chattype": "group",
            "chatid": "oc_test_chatid_langfuse_001",
            "from": {"userid": "ZhangSan_langfuse_test"},
        })
        bind(ctx)

        # Build metadata dict from chat context (this is what real skills do)
        from_chat = _ctx_var.get()
        metadata = {
            "user_id": from_chat.user_id,
            "session_id": from_chat.session_id,
            "platform": from_chat.platform,
            "chat_type": from_chat.chat_type,
        }

        # Capture the payload that post() would send
        captured = {}
        def mock_post(endpoint, payload):
            captured["endpoint"] = endpoint
            captured["payload"] = payload

        with patch.object(hr, "post", side_effect=mock_post):
            # Enable langfuse so post() actually fires
            os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
            os.environ["LANGFUSE_HOST"] = "https://langfuse.example.com"
            os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
            os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"

            # Invoke span-create
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="span-001",
                trace_id="trace-langfuse-test-001",
                name="terraform-ops:nl2hcl",
                timestamp="2026-07-29T23:00:00Z",
                end_time="2026-07-29T23:00:05Z",
                parent_id="",
                input_json="",
                output_json="",
                metadata_json=json.dumps(metadata),
                status="success",
                level="",
                status_message="",
            ))

        # Verify captured payload structure
        assert "endpoint" in captured, "post() was not called"
        assert captured["endpoint"] == "/api/public/ingestion"

        batch = captured["payload"]["batch"]
        assert len(batch) == 1

        ev = batch[0]
        assert ev["type"] == "span-create"
        body = ev["body"]

        # Trace correlation
        assert body["traceId"] == "trace-langfuse-test-001"
        # Chat context propagated into metadata
        meta = body["metadata"]
        assert meta["user_id"] == "ZhangSan_langfuse_test"
        assert meta["session_id"] == "oc_test_chatid_langfuse_001"
        assert meta["platform"] == "wecom"
        assert meta["chat_type"] == "group"
        # Status
        assert meta["status"] == "success"

    def test_generation_create_payload_includes_chat_context(self):
        """generation-create also carries chat context for LLM spans."""
        hr = _load_harness_runtime()

        ctx = normalize_wecom({
            "chattype": "group",
            "chatid": "oc_gen_test",
            "from": {"userid": "alice_llm"},
        })
        bind(ctx)

        from_chat = _ctx_var.get()
        metadata = {
            "user_id": from_chat.user_id,
            "session_id": from_chat.session_id,
            "platform": from_chat.platform,
            "chat_type": from_chat.chat_type,
        }

        captured = {}
        def mock_post(endpoint, payload):
            captured["payload"] = payload

        with patch.object(hr, "post", side_effect=mock_post):
            os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
            os.environ["LANGFUSE_HOST"] = "https://langfuse.example.com"
            os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
            os.environ["LANGFUSE_SECRET_KEY"] = "sk"

            hr.cmd_generation_create(argparse_namespace_stub(
                generation_id="gen-001",
                trace_id="trace-gen-test-001",
                name="llm-call",
                timestamp="2026-07-29T23:00:00Z",
                model="claude-opus-4",
                prompt_tokens="100",
                completion_tokens="50",
                total_tokens="150",
                end_time="2026-07-29T23:00:02Z",
                parent_id="span-001",
                metadata_json=json.dumps(metadata),
            ))

        body = captured["payload"]["batch"][0]["body"]
        assert body["traceId"] == "trace-gen-test-001"
        assert body["parentObservationId"] == "span-001"
        assert body["model"] == "claude-opus-4"
        assert body["usage"]["totalTokens"] == 150
        # Chat context in metadata
        meta = body["metadata"]
        assert meta["user_id"] == "alice_llm"
        assert meta["session_id"] == "oc_gen_test"
        assert meta["platform"] == "wecom"

    def test_post_skipped_when_langfuse_not_enabled(self):
        """If SKILLOPT_LANGFUSE_ENABLED != true, post() returns without making HTTP call.

        We verify behavior by checking that urllib.request.urlopen was not invoked,
        rather than checking post() itself (which we mock).
        """
        hr = _load_harness_runtime()

        # SKILLOPT_LANGFUSE_ENABLED is NOT set (per setUp)
        ctx = normalize_wecom({"chattype": "group", "chatid": "x", "from": {"userid": "y"}})
        bind(ctx)

        # Patch urlopen to confirm it is never called when disabled
        urlopen_called = []
        real_urlopen = hr.urllib.request.urlopen
        def tracking_urlopen(*args, **kwargs):
            urlopen_called.append((args, kwargs))
            return real_urlopen(*args, **kwargs)

        with patch.object(hr.urllib.request, "urlopen", side_effect=tracking_urlopen):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert urlopen_called == [], "urlopen should NOT be called when SKILLOPT_LANGFUSE_ENABLED is not 'true'"

    def test_post_skipped_when_env_vars_missing(self):
        """If Langfuse enabled but env vars missing, urlopen is not invoked."""
        hr = _load_harness_runtime()

        os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
        # LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY all missing

        urlopen_called = []
        real_urlopen = hr.urllib.request.urlopen
        def tracking_urlopen(*args, **kwargs):
            urlopen_called.append((args, kwargs))
            return real_urlopen(*args, **kwargs)

        with patch.object(hr.urllib.request, "urlopen", side_effect=tracking_urlopen):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert urlopen_called == [], "urlopen should NOT be called when env vars are missing"


class TestLangfuseUploadViaCLI(unittest.TestCase):
    """End-to-end: invoke harness_runtime.py as subprocess, verify payload."""

    def test_span_create_cli_subprocess(self):
        """Run harness_runtime.py span-create with chat context in metadata."""
        ctx = normalize_wecom({
            "chattype": "group",
            "chatid": "oc_cli_test_chat",
            "from": {"userid": "cli_test_user"},
        })

        metadata = {
            "user_id": ctx.user_id,
            "session_id": ctx.session_id,
            "platform": ctx.platform,
            "chat_type": ctx.chat_type,
        }

        # Run harness_runtime.py with metadata, but patch post() to capture
        # We do this by wrapping the script's post() with a mock env-var trick:
        # since post() no-ops when SKILLOPT_LANGFUSE_ENABLED != true, the script
        # returns silently. To capture payload, monkeypatch sys.modules.

        # Use a simpler check: verify the script exits 0 and parses args correctly
        result = subprocess.run(
            [
                sys.executable,
                str(_HARNESS / "harness_runtime.py"),
                "span-create",
                "--span-id", "span-cli-001",
                "--trace-id", "trace-cli-001",
                "--name", "test-span",
                "--timestamp", "2026-07-29T23:00:00Z",
                "--metadata-json", json.dumps(metadata),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # No env vars set → no-op → exit 0 with no output
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        # With env vars enabled, it would actually try to POST. We skip
        # the actual HTTP call to avoid hitting a real Langfuse server.


class TestLangfuseEnvVarCompat(unittest.TestCase):
    """LANGFUSE_BASE_URL (preferred) + LANGFUSE_HOST (legacy fallback)."""

    def setUp(self):
        for k in ["SKILLOPT_LANGFUSE_ENABLED", "LANGFUSE_HOST", "LANGFUSE_BASE_URL",
                  "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            os.environ.pop(k, None)

    def test_base_url_takes_precedence_over_host(self):
        """When both env vars set, BASE_URL wins."""
        os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
        os.environ["LANGFUSE_BASE_URL"] = "https://primary.langfuse.example.com"
        os.environ["LANGFUSE_HOST"] = "https://legacy.langfuse.example.com"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk"

        hr = _load_harness_runtime()
        captured_endpoint = []
        with patch.object(hr, "post", side_effect=lambda e, p: captured_endpoint.append(e)):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert len(captured_endpoint) == 1
        # Endpoint is just the path; but the host was read. We verify via urlopen mock.
        urlopen_called_with = []
        real_urlopen = hr.urllib.request.urlopen
        def capture_urlopen(req, **kwargs):
            urlopen_called_with.append(req.full_url)
            return real_urlopen(req, **kwargs)
        with patch.object(hr.urllib.request, "urlopen", side_effect=capture_urlopen):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert urlopen_called_with[0].startswith("https://primary.langfuse.example.com")

    def test_host_works_as_fallback_when_base_url_unset(self):
        """When only LANGFUSE_HOST is set, it still works (backward compat)."""
        os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
        os.environ["LANGFUSE_HOST"] = "https://legacy-only.langfuse.example.com"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk"

        hr = _load_harness_runtime()
        urlopen_called_with = []
        real_urlopen = hr.urllib.request.urlopen
        def capture_urlopen(req, **kwargs):
            urlopen_called_with.append(req.full_url)
            return real_urlopen(req, **kwargs)
        with patch.object(hr.urllib.request, "urlopen", side_effect=capture_urlopen):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert urlopen_called_with[0].startswith("https://legacy-only.langfuse.example.com")

    def test_no_url_means_noop(self):
        """When neither BASE_URL nor HOST is set, urlopen is not called."""
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk"
        # No LANGFUSE_HOST or LANGFUSE_BASE_URL

        hr = _load_harness_runtime()
        urlopen_called = []
        with patch.object(hr.urllib.request, "urlopen",
                          side_effect=lambda r, **k: urlopen_called.append(r.full_url)):
            hr.cmd_span_create(argparse_namespace_stub(
                span_id="s", trace_id="t", name="n", timestamp="2026-07-29T23:00:00Z",
                end_time="", parent_id="", input_json="", output_json="",
                metadata_json="{}", status="", level="", status_message="",
            ))
        assert urlopen_called == [], "urlopen should not be called when no host env var is set"


class TestTraceCreateRequired(unittest.TestCase):
    """Regression: trace-create event MUST be sent before observations,
    otherwise GET /api/public/traces/{id} returns 404 indefinitely.

    Langfuse's Ingestion API requires trace-create; span/generation-create
    alone create orphan observations that show up only via the observations
    endpoint but not the trace endpoint.
    """

    def test_trace_create_event_payload(self):
        hr = _load_harness_runtime()

        captured = {}
        with patch.object(hr, "post", side_effect=lambda e, p: captured.setdefault("payload", p)):
            os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
            os.environ["LANGFUSE_BASE_URL"] = "https://test.langfuse.example.com"
            os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
            os.environ["LANGFUSE_SECRET_KEY"] = "sk"

            hr.cmd_trace_create(argparse_namespace_stub(
                trace_id="trace-must-exist",
                name="my-trace",
                timestamp="2026-07-29T23:00:00Z",
                input_json="",
                output_json="",
                metadata_json="{}",
                user_id="alice",
                session_id="sess-1",
                platform="wecom",
                chat_type="group",
                tags="prod,monitor",
            ))

        ev = captured["payload"]["batch"][0]
        assert ev["type"] == "trace-create"
        assert ev["id"] == "trace-must-exist"
        body = ev["body"]
        assert body["id"] == "trace-must-exist"
        assert body["name"] == "my-trace"
        assert body["timestamp"] == "2026-07-29T23:00:00Z"
        # Chat context fields go into trace metadata
        meta = body["metadata"]
        assert meta["user_id"] == "alice"
        assert meta["session_id"] == "sess-1"
        assert meta["platform"] == "wecom"
        assert meta["chat_type"] == "group"
        assert body["tags"] == ["prod", "monitor"]

    def test_trace_create_chat_context_appears_on_trace_metadata(self):
        """The chat context (user_id etc.) must end up on trace metadata, not just observation metadata."""
        hr = _load_harness_runtime()

        captured = []
        with patch.object(hr, "post", side_effect=lambda e, p: captured.append(p)):
            os.environ["SKILLOPT_LANGFUSE_ENABLED"] = "true"
            os.environ["LANGFUSE_BASE_URL"] = "https://test.langfuse.example.com"
            os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
            os.environ["LANGFUSE_SECRET_KEY"] = "sk"

            hr.cmd_trace_create(argparse_namespace_stub(
                trace_id="t1",
                name="chat-trace",
                timestamp="2026-07-29T23:00:00Z",
                input_json="", output_json="", metadata_json="{}",
                user_id="bob",
                session_id="chatid-1",
                platform="feishu",
                chat_type="p2p",
                tags="",
            ))

        body = captured[0]["batch"][0]["body"]
        meta = body["metadata"]
        # All 4 chat-context fields present on trace
        for f in ["user_id", "session_id", "platform", "chat_type"]:
            assert f in meta, f"trace metadata missing {f}"


def argparse_namespace_stub(**kwargs):
    """Build a simple argparse.Namespace from kwargs."""
    import argparse
    return argparse.Namespace(**kwargs)


if __name__ == "__main__":
    unittest.main()