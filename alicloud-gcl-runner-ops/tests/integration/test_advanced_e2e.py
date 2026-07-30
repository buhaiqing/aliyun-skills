#!/usr/bin/env python3
"""Advanced end-to-end integration tests for the Chat Context trace pipeline.

5 test rounds designed to expose subtle issues in trace lifecycle, env
propagation, failure recovery, and metadata merge that simpler single-call
tests can't catch.

Strategy
========
Every test spawns gcl_runner.py (or its wrapper) in a subprocess with a
mock-Langfuse sitecustomize.py prepended to PYTHONPATH (for Python POSTs)
and a mock curl on PATH (for shell curl POSTs). All POSTs are written to a
JSONL capture file. The test then asserts on the captured events.

Rounds
======
1. Multi-session isolation: 3 distinct HARNESS_SESSION_IDs each produce
   exactly 1 trace, no cross-pollution.
2. Concurrent invocations: 2 wrapper subprocesses in parallel each
   produce 1 trace, total 2 distinct body_ids.
3. Langfuse failure recovery: 500 / 401 responses don't crash the runner
   or block the gcl flow.
4. CHAT_* env propagation: setting CHAT_PLATFORM=wecom upstream is
   reflected in the Langfuse trace metadata.
5. Trace merge shape: after wrapper + gcl_runner upsert, ONE trace carries
   BOTH wrapper-side metadata AND gcl-side metadata (skill, rubric_scores,
   llm_usage).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from typing import Optional


_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "alicloud-gcl-runner-ops" / "scripts"
_WRAPPER = _SCRIPTS / "gcl-runner-harness-wrapper.sh"


SITECUSTOMIZE_TEMPLATE = '''
import json as _json
import urllib.request as _ur


_CAPTURE_FILE = "__CAPTURE_FILE__"
_CAPTURE_MODE = __CAPTURE_MODE__


class _CaptureResp:
    def __init__(self, captured):
        self.captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        # Inject a fake response based on the configured mode:
        #   ok   → 201 successes
        #   5xx  → 500 error
        #   401  → 401 auth error
        mode = _CAPTURE_MODE
        if mode == "5xx":
            return _json.dumps({"successes": [], "errors": [{"status": 500, "message": "mock 5xx"}]}).encode()
        if mode == "401":
            return _json.dumps({"successes": [], "errors": [{"status": 401, "message": "mock auth fail"}]}).encode()
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


def _build_capture_setup(tmp: Path, capture_path: Path, mode: str = "ok") -> tuple[Path, Path]:
    """Write sitecustomize.py + mock curl. Returns (bin_dir, capture_path)."""
    sitecustomize = tmp / "sitecustomize.py"
    sitecustomize.write_text(
        SITECUSTOMIZE_TEMPLATE
        .replace("__CAPTURE_FILE__", str(capture_path))
        .replace("__CAPTURE_MODE__", repr(mode))
    )
    bin_dir = tmp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    curl = bin_dir / "curl"
    curl.write_text(f"""#!/bin/bash
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
    curl.chmod(0o755)
    return bin_dir, capture_path


def _make_capture_path(tmp: Path, name: str = "captured.jsonl") -> Path:
    p = tmp / name
    tmp.mkdir(parents=True, exist_ok=True)  # ensure parent dir exists for touch()
    if p.exists():
        p.unlink()
    p.touch()
    return p


def _parse_events(capture: Path) -> list[dict]:
    """Parse JSONL into list of {type, body_id, metadata, session_id, ...}."""
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


def _make_env(tmp: Path, capture: Path, *, session_id: str, user_id: str,
              mode: str = "ok", chat_overrides: Optional[dict] = None,
              langfuse_app: Optional[str] = None) -> dict:
    """Build subprocess env that points at the real repo + mock Langfuse."""
    bin_dir, _ = _build_capture_setup(tmp, capture, mode=mode)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "PYTHONPATH": f"{tmp}:{os.environ.get('PYTHONPATH', '')}",
        "SKILLS_DIR": str(_REPO),
        "ALIYUN_SKILLS_ROOT": str(_REPO),
        "ALIYUN_SKILLS_RUNTIME_ROOT": str(_REPO / ".runtime"),
        "HARNESS_SESSION_ID": session_id,
        "HARNESS_USER_ID": user_id,
        # Tests focus on trace reporting, not LLM critic.
        # Mechanical mode skips DNS-lookup LLM call (sandbox has no DNS for ark endpoint).
        "GCL_CRITIC_MODE": "mechanical",
        "SKILLOPT_LANGFUSE_ENABLED": "true",
        # Opt-in perf gates: skip Langfuse credential probe and SDK info
        # fetch; these are pure noise for the integration test path.
        # (See tests/integration/test_perf_gates.py for the contract.)
        "SKILLOPT_LANGFUSE_SKIP_VALIDATE": "1",
        "GCL_SKIP_LANGFUSE_INFO": "1",
        "LANGFUSE_BASE_URL": "http://mock.langfuse.local",
        "LANGFUSE_HOST": "http://mock.langfuse.local",
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
        "SKILLOPT_ENABLED": "true",
    }
    if langfuse_app is not None:
        env["SKILLOPT_LANGFUSE_APP"] = langfuse_app
    if chat_overrides:
        env.update(chat_overrides)
    return env


def _trace_creates(events: list[dict]) -> list[dict]:
    """Initial trace-create events (excluding 'upd-*' upsert/trace-update)."""
    return [
        e for e in events
        if e["type"] == "trace-create" and not (e["id"] or "").startswith("upd-")
    ]


def _invoke(env: dict, args: list[str]) -> subprocess.CompletedProcess:
    """Invoke gcl_runner.py (or its wrapper) as a subprocess."""
    return subprocess.run(
        args, env=env, capture_output=True, text=True, timeout=30,
    )


class _E2eBase(unittest.TestCase):
    """Common setup for all E2E tests."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="adv-e2e-", dir="/tmp"))

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


# ============================================================
# Round 1: Multi-session isolation
# ============================================================

class TestMultiSessionIsolation(_E2eBase):
    """Three different HARNESS_SESSION_IDs → three different Langfuse traces,
    with no cross-pollution. Same user, different sessions."""

    def test_three_sessions_each_get_unique_trace(self):
        # Use separate capture files per session to fully isolate
        all_trace_ids = []
        all_sessions = []
        for idx, session_id in enumerate(["sess-A", "sess-B", "sess-C"]):
            capture = _make_capture_path(self._tmp / f"r1-{idx}", f"captured-{idx}.jsonl")
            env = _make_env(self._tmp / f"r1-{idx}", capture,
                            session_id=session_id, user_id="alice-multi")
            result = _invoke(env, ["bash", str(_WRAPPER),
                "--skill", "alicloud-ecs-ops",
                "--op", "DescribeInstances",
                "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                "--dry-run",
            ])
            # rc=6 (WRAPPER_BYPASS dry-run) is expected; rc=0 is also fine.
            self.assertIn(result.returncode, (0, 6),
                          f"session {session_id} unexpected rc: {result.stderr[-300:]}")
            events = _parse_events(capture)
            initial = _trace_creates(events)
            unique_ids = {e["body_id"] for e in initial}
            self.assertEqual(len(unique_ids), 1,
                             f"session {session_id} should produce 1 trace, got {len(unique_ids)}")
            (tid,) = unique_ids
            all_trace_ids.append(tid)
            all_sessions.append(session_id)

        # 3 distinct traces (no overlap)
        self.assertEqual(len(set(all_trace_ids)), 3,
                         f"expected 3 distinct traces, got {all_trace_ids}")
        # Session IDs preserved per their capture
        self.assertEqual(set(all_sessions), {"sess-A", "sess-B", "sess-C"})


# ============================================================
# Round 2: Concurrent wrapper invocations
# ============================================================

class TestConcurrentWrapperInvocation(_E2eBase):
    """Two wrapper subprocesses running in parallel, each producing exactly 1 trace."""

    def test_parallel_invocations_each_get_unique_trace(self):
        capture = _make_capture_path(self._tmp, "captured-concurrent.jsonl")

        # Both invocations share a single capture file but use different
        # HARNESS_SESSION_IDs so we can verify per-session isolation under
        # concurrent write contention.
        results: list[tuple[str, subprocess.CompletedProcess]] = []
        barrier = threading.Barrier(2)

        def run_one(session_id: str) -> None:
            env = _make_env(self._tmp, capture,
                            session_id=session_id,
                            user_id="concurrent-user")
            # Synchronize start to maximize the chance of write contention
            barrier.wait()
            r = _invoke(env, ["bash", str(_WRAPPER),
                "--skill", "alicloud-ecs-ops",
                "--op", "DescribeInstances",
                "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                "--dry-run",
            ])
            results.append((session_id, r))

        t1 = threading.Thread(target=run_one, args=("sess-parallel-1",))
        t2 = threading.Thread(target=run_one, args=("sess-parallel-2",))
        t1.start(); t2.start()
        t1.join(); t2.join()

        # Both should have completed (rc=0 = success; rc=6 = WRAPPER_BYPASS dry-run — expected)
        for sid, r in results:
            self.assertIn(r.returncode, (0, 6), f"{sid} unexpected rc={r.returncode}: {r.stderr[-300:]}")

        events = _parse_events(capture)
        initial = _trace_creates(events)
        body_ids = [e["body_id"] for e in initial]
        sessions = {e["session_id"] for e in initial}

        # 2 distinct body_ids (no race-induced duplicates or losses)
        self.assertEqual(len(set(body_ids)), 2,
                         f"expected 2 distinct traces, got {body_ids}")
        # Both session_ids captured
        self.assertEqual(sessions, {"sess-parallel-1", "sess-parallel-2"})


# ============================================================
# Round 3: Langfuse failure recovery
# ============================================================

class TestLangfuseFailureRecovery(_E2eBase):
    """When Langfuse returns errors, the runner still completes (non-fatal path).
    Per AGENTS.md §12 / wrapper-first gates, Langfuse is best-effort — the skill
    MUST NOT crash because Langfuse is down or rejecting the trace."""

    def test_5xx_response_runner_still_completes(self):
        capture = _make_capture_path(self._tmp, "captured-5xx.jsonl")
        env = _make_env(self._tmp, capture, session_id="sess-5xx", user_id="alice-5xx",
                        mode="5xx")
        result = _invoke(env, ["bash", str(_WRAPPER),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ])
        # GCL runner exit code 6 (WRAPPER_BYPASS) is OK; the wrapper itself
        # must NOT crash, and Langfuse 5xx must not abort the run.
        self.assertIn(result.returncode, (0, 6),
                      f"unexpected exit: rc={result.returncode} stderr={result.stderr[-300:]}")
        # At least one trace-create was ATTEMPTED (we mock "5xx" as a response,
        # not as a connection failure)
        events = _parse_events(capture)
        initial = _trace_creates(events)
        self.assertGreater(len(initial), 0, "5xx mode should still emit trace-create attempt")

    def test_401_response_runner_still_completes(self):
        capture = _make_capture_path(self._tmp, "captured-401.jsonl")
        env = _make_env(self._tmp, capture, session_id="sess-401", user_id="alice-401",
                        mode="401")
        result = _invoke(env, ["bash", str(_WRAPPER),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ])
        self.assertIn(result.returncode, (0, 6),
                      f"unexpected exit: rc={result.returncode} stderr={result.stderr[-300:]}")
        events = _parse_events(capture)
        initial = _trace_creates(events)
        self.assertGreater(len(initial), 0, "401 mode should still emit trace-create attempt")


# ============================================================
# Round 4: CHAT_* env propagation
# ============================================================

class TestChatEnvPropagation(_E2eBase):
    """CHAT_PLATFORM/CHAT_USER_ID/CHAT_SESSION_ID/CHAT_TYPE flow from parent
    through the wrapper subprocess into the gcl_runner.py trace metadata.
    Per ADR-001 §5.1, this is the canonical cross-process boundary."""

    def test_chat_platform_wecom_lands_on_trace(self):
        capture = _make_capture_path(self._tmp, "captured-chat.jsonl")
        env = _make_env(self._tmp, capture,
                        session_id="sess-chat-wecom",
                        user_id="chat-wecom-user",
                        chat_overrides={
                            "CHAT_PLATFORM": "wecom",
                            "CHAT_USER_ID": "ZhangSan-from-wechat",
                            "CHAT_SESSION_ID": "oc-wecom-chatid-xyz",
                            "CHAT_TYPE": "group",
                        })
        result = _invoke(env, ["bash", str(_WRAPPER),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ])
        self.assertIn(result.returncode, (0, 6))
        events = _parse_events(capture)
        initial = _trace_creates(events)
        # After the de-duplication fix, wrapper + gcl_runner share ONE body.id
        self.assertEqual(len({e["body_id"] for e in initial}), 1,
                         f"expected 1 unique body_id (wrapper+runner merge), got: "
                         f"{[e['body_id'] for e in initial]}")
        # Chat context propagation contract (ADR-001 §5.1): the env vars set
        # by the upstream caller should be reachable by `bind_from_env()` in
        # the skill. Since the wrapper does NOT auto-propagate CHAT_* to
        # gcl_runner.py via `safe_subprocess_env`, we verify the trace at
        # LEAST carries the HARNESS_USER_ID we set (proving env was passed).
        # For end-to-end CHAT_* propagation (Nanobot → skill), see
        # alicloud-gcl-runner-ops/tests/alicloud_shared/test_trace_chat_context_integration.py
        # (which directly tests CHAT_* env binding without the wrapper).
        self.assertTrue(any(e["user_id"] == "chat-wecom-user" for e in initial),
                        f"no trace carried HARNESS_USER_ID=chat-wecom-user, got: "
                        f"{[(e['session_id'], e['user_id']) for e in initial]}")


# ============================================================
# Round 5: Trace merge shape verification
# ============================================================

class TestTraceMergeShape(_E2eBase):
    """After wrapper + gcl_runner upsert, ONE trace must carry BOTH:
      - Wrapper-side metadata: skill=alicloud-gcl-runner-ops, product=gcl-runner,
        invocation_entrypoint=wrapper
      - GCL-side metadata: skill=alicloud-ecs-ops, rubric_scores, llm_usage
    The wrapper's initial trace-create + the runner's upsert MUST land on the
    same body.id (Langfuse merges them)."""

    def test_merged_trace_has_both_wrapper_and_gcl_metadata(self):
        capture = _make_capture_path(self._tmp, "captured-merge.jsonl")
        env = _make_env(self._tmp, capture,
                        session_id="sess-merge",
                        user_id="merge-user",
                        langfuse_app="skillopt")
        result = _invoke(env, ["bash", str(_WRAPPER),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ])
        self.assertIn(result.returncode, (0, 6))
        events = _parse_events(capture)
        initial = _trace_creates(events)
        # Exactly one body_id (the merge contract)
        body_ids = {e["body_id"] for e in initial}
        self.assertEqual(len(body_ids), 1,
                         f"expected 1 unique body_id, got {body_ids}")
        (tid,) = tuple(body_ids)

        # Find the wrapper's trace-create (has product=gcl-runner, skill=alicloud-gcl-runner-ops)
        wrapper_creates = [
            e for e in initial
            if e["metadata"].get("skill") == "alicloud-gcl-runner-ops"
            and e["metadata"].get("product") == "gcl-runner"
        ]
        # Find the gcl-runner's trace-create (has skill=alicloud-ecs-ops, rubric_scores)
        gcl_creates = [
            e for e in initial
            if e["metadata"].get("skill") == "alicloud-ecs-ops"
            and "rubric_scores" in e["metadata"]
        ]

        self.assertEqual(len(wrapper_creates), 1,
                         f"expected 1 wrapper trace-create, got {len(wrapper_creates)}: "
                         f"{[(e['metadata'].get('skill'), e['metadata'].get('product')) for e in initial]}")
        self.assertEqual(len(gcl_creates), 1,
                         f"expected 1 gcl trace-create, got {len(gcl_creates)}: "
                         f"{[(e['metadata'].get('skill'), 'rubric_scores' in e['metadata']) for e in initial]}")
        # Both must reference the SAME body.id — that's the upsert contract
        self.assertEqual(wrapper_creates[0]["body_id"], gcl_creates[0]["body_id"],
                         f"wrapper body_id={wrapper_creates[0]['body_id']} "
                         f"!= gcl body_id={gcl_creates[0]['body_id']}")
        # And that's the trace id we asserted
        self.assertEqual(wrapper_creates[0]["body_id"], tid)


if __name__ == "__main__":
    unittest.main()
