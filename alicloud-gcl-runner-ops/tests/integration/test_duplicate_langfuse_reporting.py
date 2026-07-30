#!/usr/bin/env python3
"""Integration test: detect duplicate Langfuse reporting in the gcl-runner pipeline.

Strategy
========
- For direct gcl_runner.py invocation: monkeypatch `urllib.request.urlopen`
  in-process via `unittest.mock.patch`, then call `gcl_runner._report_trace_to_langfuse`
  directly to assert it emits exactly 1 trace-create.
- For wrapper-mediated invocation: spawn gcl_runner.py as a subprocess with a
  `sitecustomize.py` injected that monkeypatches urllib.request.urlopen at
  Python startup; capture every POST in JSONL; assert exactly 1 trace-create.

Both paths assert:
  - The trace-create carries session_id, user_id, skill metadata
  - When invoked via wrapper, the runner's _report_trace_to_langfuse must
    short-circuit if a wrapper-managed trace already exists (or vice versa).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "alicloud-gcl-runner-ops" / "scripts"
_HARNESS = _REPO / "alicloud-runtime-harness-ops" / "scripts"
_WRAPPER = _REPO / "alicloud-gcl-runner-ops" / "scripts" / "gcl-runner-harness-wrapper.sh"


# Path to a sitecustomize module installed into PYTHONPATH that captures urllib
# POSTs to /api/public/* in a JSONL file.
SITECUSTOMIZE_TEMPLATE = '''
import json as _json
import urllib.request as _ur


_CAPTURE_FILE = "__CAPTURE_FILE__"


class _CaptureResp:
    def __init__(self, captured):
        self.captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        try:
            body = _json.loads(self.captured.get("body") or "{}")
        except Exception:
            body = {}
        return _json.dumps({
            "successes": [
                {"id": e.get("id", ""), "status": 201}
                for e in body.get("batch", [])
            ],
            "errors": [],
        }).encode()


def _patched_urlopen(req, timeout=None, **_kw):
    body = req.data
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except Exception:
            pass
    entry = {
        "url": req.full_url,
        "method": getattr(req, "method", "POST") or "POST",
        "body": body,
        "_via": "urllib",
    }
    try:
        with open(_CAPTURE_FILE, "a") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\\n")
    except Exception:
        pass
    return _CaptureResp(entry)


_ur.urlopen = _patched_urlopen
'''.strip()


def _install_urllib_capture(tmp: Path, capture_path: Path) -> Path:
    """Write sitecustomize.py that captures urllib POSTs."""
    sitecustomize = tmp / "sitecustomize.py"
    sitecustomize.write_text(
        SITECUSTOMIZE_TEMPLATE.replace("__CAPTURE_FILE__", str(capture_path))
    )
    return sitecustomize


def _build_mock_curl(mock_dir: Path, capture_path: Path) -> Path:
    """Build a curl stub on PATH that records each call."""
    mock_dir.mkdir(parents=True, exist_ok=True)
    curl_path = mock_dir / "curl"
    curl_path.write_text(f"""#!/bin/bash
LOG={str(capture_path)}
METHOD=""
URL=""
BODY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -X) METHOD="$2"; shift 2;;
        -H) shift 2;;
        -d) BODY="$2"; shift 2;;
        --max-time|-s|-o) shift 2;;
        *) URL="$1"; shift ;;
    esac
done
python3 - "$METHOD" "$URL" "$BODY" <<'PY'
import json, sys
method, url, body = sys.argv[1], sys.argv[2], sys.argv[3]
entry = {{"method": method, "url": url, "body": body, "_via": "curl"}}
with open("{str(capture_path)}", "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\\n")
PY
exit 0
""")
    curl_path.chmod(0o755)
    return curl_path


def _make_capture_path(tmp: Path) -> Path:
    p = tmp / "captured.jsonl"
    if p.exists():
        p.unlink()
    p.touch()
    return p


def _parse_capture(capture: Path) -> list[dict]:
    events: list[dict] = []
    if not capture.exists():
        return events
    for line in capture.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        body = entry.get("body", "")
        url = entry.get("url", "")
        if not body or "/api/public/" not in url:
            continue
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            continue
        for ev in parsed.get("batch", []):
            events.append({
                "type": ev.get("type"),
                "id": ev.get("id"),
                "body_id": ev.get("body", {}).get("id"),
                "traceId": ev.get("body", {}).get("traceId"),
                "name": ev.get("body", {}).get("name"),
                "metadata": ev.get("body", {}).get("metadata", {}),
                "session_id": ev.get("body", {}).get("sessionId")
                    or ev.get("body", {}).get("metadata", {}).get("session_id"),
                "user_id": ev.get("body", {}).get("userId")
                    or ev.get("body", {}).get("metadata", {}).get("user_id"),
                "_via": entry.get("_via", "urllib"),
            })
    return events


class TestGclRunnerDirectInvocation(unittest.TestCase):
    """Direct gcl_runner invocation must emit exactly 1 trace-create."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="dup-direct-", dir="/tmp"))
        self._capture = _make_capture_path(self._tmp)
        _install_urllib_capture(self._tmp, self._capture)

        self._env = {
            **os.environ,
            "PYTHONPATH": f"{self._tmp}:{os.environ.get('PYTHONPATH', '')}",
            # Use the real repo so gcl_runner.py can find rubric.md / skills etc.
            # We only redirect the audit/runtime subdir to the isolated tmp.
            "SKILLS_DIR": str(_REPO),
            "ALIYUN_SKILLS_ROOT": str(_REPO),
            "ALIYUN_SKILLS_RUNTIME_ROOT": str(_REPO / ".runtime"),
            "HARNESS_SESSION_ID": "dup-direct-session",
            "HARNESS_USER_ID": "dup-direct-user",
            # Tests focus on trace reporting — skip LLM DNS call.
            "GCL_CRITIC_MODE": "mechanical",
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            # Direct-invocation path: skip the credential probe, SDK info
            # fetch, and memory preflight disk reads (none of these are
            # asserted in the test). See test_perf_gates.py for contract.
            "SKILLOPT_LANGFUSE_SKIP_VALIDATE": "1",
            "GCL_SKIP_LANGFUSE_INFO": "1",
            "GCL_MEMORY_PREFLIGHT_ENABLED": "false",
            "LANGFUSE_BASE_URL": "http://mock.langfuse.local",
            "LANGFUSE_HOST": "http://mock.langfuse.local",
            "LANGFUSE_PUBLIC_KEY": "pk-direct",
            "LANGFUSE_SECRET_KEY": "sk-direct",
            "SKILLOPT_ENABLED": "false",
        }

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_gcl_runner_emits_exactly_one_trace_create(self):
        cmd = [
            sys.executable, str(_SCRIPTS / "gcl_runner.py"),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ]
        result = subprocess.run(
            cmd, env=self._env, capture_output=True, text=True, timeout=30
        )
        # gcl_runner may exit non-zero on dry-run validation
        events = _parse_capture(self._capture)
        trace_creates_initial = [
            e for e in events
            if e["type"] == "trace-create" and not (e["id"] or "").startswith("upd-")
        ]
        self.assertEqual(
            len(trace_creates_initial), 1,
            f"Expected exactly 1 trace-create (got {len(trace_creates_initial)}): "
            f"{[(e['body_id'], e['metadata'].get('invocation_entrypoint')) for e in trace_creates_initial]}",
        )
        e = trace_creates_initial[0]
        self.assertTrue(e["body_id"], "trace_create must have id")
        self.assertEqual(e["session_id"], "dup-direct-session")
        self.assertEqual(e["user_id"], "dup-direct-user")
        self.assertEqual(e["metadata"].get("skill"), "alicloud-ecs-ops")
        self.assertEqual(e["metadata"].get("trace_source"), "gcl_runner")


class TestWrapperDoesNotDoubleReport(unittest.TestCase):
    """The gcl-runner-harness-wrapper.sh path must not cause duplicate trace-creates."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="dup-wrap-", dir="/tmp"))
        self._capture = _make_capture_path(self._tmp)
        _install_urllib_capture(self._tmp, self._capture)
        _build_mock_curl(self._tmp / "bin", self._capture)

        self._env = {
            **os.environ,
            "PATH": f"{self._tmp}/bin:{os.environ.get('PATH', '')}",
            "PYTHONPATH": f"{self._tmp}:{os.environ.get('PYTHONPATH', '')}",
            # Use the real repo for SKILLS_DIR/ALIYUN_SKILLS_ROOT.
            "SKILLS_DIR": str(_REPO),
            "ALIYUN_SKILLS_ROOT": str(_REPO),
            "ALIYUN_SKILLS_RUNTIME_ROOT": str(_REPO / ".runtime"),
            "HARNESS_SESSION_ID": "dup-wrap-session",
            "HARNESS_USER_ID": "dup-wrap-user",
            # Tests focus on trace reporting — skip LLM DNS call.
            "GCL_CRITIC_MODE": "mechanical",
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            "SKILLOPT_LANGFUSE_APP": "skillopt",
            # Wrapper path: only skip the credential probe and SDK info
            # fetch. Memory preflight stays enabled — the wrapper exercises
            # real preflight state and we want to keep coverage.
            "SKILLOPT_LANGFUSE_SKIP_VALIDATE": "1",
            "GCL_SKIP_LANGFUSE_INFO": "1",
            "LANGFUSE_BASE_URL": "http://mock.langfuse.local",
            "LANGFUSE_HOST": "http://mock.langfuse.local",
            "LANGFUSE_PUBLIC_KEY": "pk-wrap",
            "LANGFUSE_SECRET_KEY": "sk-wrap",
            "SKILLOPT_ENABLED": "true",
        }

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_wrapper_then_runner_emits_single_trace_create(self):
        if not _WRAPPER.exists():
            self.skipTest(f"wrapper not found: {_WRAPPER}")

        cmd = [
            "bash", str(_WRAPPER),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ]
        result = subprocess.run(
            cmd, env=self._env, capture_output=True, text=True, timeout=30
        )

        events = _parse_capture(self._capture)
        # All trace-create events whose event id does NOT start with "upd-"
        # (which marks wrapper-side trace-update events). Multiple events with
        # the same body.id are an upsert pattern (Langfuse merges them onto a
        # single trace) and therefore do NOT count as duplicates.
        trace_creates_initial = [
            e for e in events
            if e["type"] == "trace-create" and not (e["id"] or "").startswith("upd-")
        ]
        unique_body_ids = {e["body_id"] for e in trace_creates_initial}

        # Logical operation key for the assertion
        from collections import Counter
        keys = Counter(
            (e["session_id"], e["user_id"], e["metadata"].get("skill"))
            for e in trace_creates_initial
        )
        dupes = [(k, n) for k, n in keys.items() if n > 1]
        self.assertEqual(
            len(dupes), 0,
            "Duplicate trace-create for logical operation(s): "
            + ", ".join(f"{k} x{n}" for k, n in dupes)
            + f". All trace_ids: {[(e['body_id'], e['metadata'].get('invocation_entrypoint')) for e in trace_creates_initial]}",
        )
        self.assertEqual(
            len(unique_body_ids), 1,
            f"Expected exactly 1 unique trace-create body.id (got {len(unique_body_ids)}): "
            f"{[(e['body_id'], e['metadata'].get('invocation_entrypoint')) for e in trace_creates_initial]}",
        )


if __name__ == "__main__":
    unittest.main()
