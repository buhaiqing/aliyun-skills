#!/usr/bin/env python3
"""
gcl_actiontrail_crosscheck_test.py — unit tests for
`gcl_actiontrail_crosscheck.py`.

Pure stdlib `unittest`; no third-party dependencies. Run with:
    python3 scripts/gcl_actiontrail_crosscheck_test.py

Test coverage:
- T1  extract_local_op() — `aliyun ecs DeleteInstance --InstanceId i-1` → ("ecs", "DeleteInstance", "i-1")
- T2  extract_local_op() — dry-run `echo ...` → ("", "", "")
- T3  extract_local_op() — unparseable `kubectl get pods` → ("", "", "")
- T4  extract_local_op() — various resource-id flags (DBClusterId, VpcId, etc.)
- T5  find_matching_events() — exact EventName + ServiceName + ResourceName match
- T6  find_matching_events() — RESOURCE_MISMATCH detected when ResourceName is different
- T7  find_matching_events() — AKID mismatch filters out event
- T8  find_matching_events() — unknown service falls back to op as EventName
- T9  crosscheck_one() — PHANTOM_PASS detection (local PASS + no events)
- T10 crosscheck_one() — PHANTOM_FAIL detection (local FAIL + events exist)
- T11 crosscheck_one() — CLEAN (local PASS + matching event exists)
- T12 crosscheck_one() — API_ERROR when LookupEvents returns non-zero
- T13 crosscheck_one() — API_ERROR for "Trail not found"
- T14 crosscheck_one() — RESOURCE_MISMATCH finding
- T15 crosscheck_one() — TIMING_ANOMALY finding (>1h skew)
- T16 aggregate_findings() — count by type / skill
- T17 main() — exit 0 on CLEAN
- T18 main() — exit 1 (PHANTOM_FOUND) with --strict + PHANTOM_PASS
- T19 main() — exit 2 (USAGE_ERROR) on missing trace path
- T20 main() — exit 3 (API_ERROR) surfaced as INTERNAL_ERROR
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import gcl_actiontrail_crosscheck as xchk  # noqa: E402

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_trace(tmpdir: Path, skill="alicloud-ecs-ops", op="DeleteInstance", command=None,
               decision="PASS", mtime=None) -> Path:
    """Write a fixture GCL trace file and return its path."""
    if command is None:
        command = f"aliyun ecs {op} --InstanceId i-bp1xxxxxxxxxx"
    trace = {
        "skill": skill,
        "request": "test request",
        "rubric_version": "1.0.0",
        "iterations": [
            {
                "iter": 1,
                "generator": {
                    "command": command,
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "result_excerpt": "ok",
                    "request_id": "test-req-id",
                    "duration_ms": 1,
                },
                "critic": {
                    "scores": {
                        "correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
                        "traceability": 1.0, "spec_compliance": 1.0,
                        "region_compliance": 1.0, "credential_hygiene": 1.0,
                        "well_architected": 1.0,
                    },
                    "suggestions": [], "matched_regexes": [], "blocking": False,
                },
                "decision": decision,
            }
        ],
        "final": {"status": decision, "iter": 1, "output": "ok"},
    }
    path = tmpdir / f"gcl-trace-test-{op}.json"
    path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    if mtime:
        ts = mtime.timestamp()
        os.utime(path, (ts, ts))
    return path


def make_lookup_proc(events, returncode=0, stderr=""):
    """Build a mock CompletedProcess for subprocess.run."""
    cp = subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=json.dumps({"Events": events}), stderr=stderr,
    )
    return cp


# ---------------------------------------------------------------------------
# T1-T4: extract_local_op()
# ---------------------------------------------------------------------------


class ExtractLocalOpTests(unittest.TestCase):

    def test_ecs_delete_instance(self):
        trace = {"iterations": [{"generator": {"command": "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxx"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual(s, "ecs")
        self.assertEqual(op, "DeleteInstance")
        self.assertEqual(rid, "i-bp1xxxxxx")

    def test_dry_run_returns_empty(self):
        trace = {"iterations": [{"generator": {"command": "echo DRY_RUN"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual((s, op, rid), ("", "", ""))

    def test_unparseable_command(self):
        trace = {"iterations": [{"generator": {"command": "kubectl get pods"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual((s, op, rid), ("", "", ""))

    def test_vpc_with_vpc_id(self):
        trace = {"iterations": [{"generator": {"command": "aliyun vpc DeleteVpc --VpcId vpc-bp1xxxxxx"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual(s, "vpc")
        self.assertEqual(op, "DeleteVpc")
        self.assertEqual(rid, "vpc-bp1xxxxxx")

    def test_rds_with_db_instance_id(self):
        trace = {"iterations": [{"generator": {"command": "aliyun rds DeleteDBInstance --DBInstanceId rm-bp1xxxxxx"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual(s, "rds")
        self.assertEqual(op, "DeleteDBInstance")
        self.assertEqual(rid, "rm-bp1xxxxxx")

    def test_polardb_db_cluster_id(self):
        trace = {"iterations": [{"generator": {"command": "aliyun polardb DeleteDBCluster --DBClusterId pc-bp1xxxxxx"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual(s, "polardb")
        self.assertEqual(op, "DeleteDBCluster")
        self.assertEqual(rid, "pc-bp1xxxxxx")

    def test_eip_allocation_id(self):
        trace = {"iterations": [{"generator": {"command": "aliyun vpc ReleaseEipAddress --AllocationId eip-bp1xxxxxx"}}]}
        s, op, rid = xchk.extract_local_op(trace)
        self.assertEqual(rid, "eip-bp1xxxxxx")


# ---------------------------------------------------------------------------
# T5-T8: find_matching_events()
# ---------------------------------------------------------------------------


class FindMatchingEventsTests(unittest.TestCase):

    def test_exact_match(self):
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": "2026-06-04T10:00:00Z", "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        matched = xchk.find_matching_events(events, "ecs", "DeleteInstance", "i-bp1xxxxxxxxxx", "LTAI5txxxxx")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["EventId"], "evt-1")

    def test_resource_mismatch_flagged(self):
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": "2026-06-04T10:00:00Z", "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-DIFFERENT",
            }
        ]
        matched = xchk.find_matching_events(events, "ecs", "DeleteInstance", "i-bp1xxxxxxxxxx", "LTAI5txxxxx")
        self.assertEqual(len(matched), 1)
        self.assertTrue(matched[0].get("_resource_mismatch"))

    def test_akid_mismatch_filters(self):
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": "2026-06-04T10:00:00Z", "EventAccessKeyId": "LTAI5tOTHER",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        matched = xchk.find_matching_events(events, "ecs", "DeleteInstance", "i-bp1xxxxxxxxxx", "LTAI5txxxxx")
        self.assertEqual(matched, [])

    def test_unknown_service_falls_back_to_op(self):
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteFoo", "ServiceName": "Custom",
                "EventTime": "2026-06-04T10:00:00Z", "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "x",
            }
        ]
        matched = xchk.find_matching_events(events, "custom", "DeleteFoo", "x", "LTAI5txxxxx")
        self.assertEqual(len(matched), 1)


# ---------------------------------------------------------------------------
# T9-T15: crosscheck_one() with mocked subprocess
# ---------------------------------------------------------------------------


class CrosscheckOneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        # Pin mtime to a fixed instant for deterministic timing tests
        self.fixed_mtime = _dt.datetime(2026, 6, 4, 10, 0, 0, tzinfo=_dt.timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def _mock_lookup(self, events):
        """Return a context manager that patches subprocess.run to return
        a successful LookupEvents response with the given events."""
        return mock.patch.object(
            xchk.subprocess, "run",
            return_value=make_lookup_proc(events),
        )

    def test_phantom_pass(self):
        """Local PASS but no events in cloud → PHANTOM_PASS (high)."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        with self._mock_lookup([]):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("PHANTOM_PASS", types)
        phantom = next(f for f in r["findings"] if f["type"] == "PHANTOM_PASS")
        self.assertEqual(phantom["severity"], "high")

    def test_phantom_fail(self):
        """Local FAIL but events exist in cloud → PHANTOM_FAIL (high)."""
        path = make_trace(self.tmp_path, decision="SAFETY_FAIL", mtime=self.fixed_mtime)
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": self.fixed_mtime.isoformat().replace("+00:00", "Z"),
                "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        with self._mock_lookup(events):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("PHANTOM_FAIL", types)

    def test_clean(self):
        """Local PASS + matching event exists → no findings."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": self.fixed_mtime.isoformat().replace("+00:00", "Z"),
                "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        with self._mock_lookup(events):
            r = xchk.crosscheck_one(path)
        self.assertEqual(r["findings"], [])

    def test_api_error_non_zero_exit(self):
        """LookupEvents returns non-zero → API_ERROR finding."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        cp = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="InternalError")
        with mock.patch.object(xchk.subprocess, "run", return_value=cp):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("API_ERROR", types)

    def test_api_error_trail_not_found(self):
        """LookupEvents returns TrailNotFound → API_ERROR finding with helpful msg."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        cp = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="NotFoundTrail: ...")
        with mock.patch.object(xchk.subprocess, "run", return_value=cp):
            r = xchk.crosscheck_one(path)
        api_err = next(f for f in r["findings"] if f["type"] == "API_ERROR")
        self.assertIn("ActionTrail is not enabled", api_err["message"])

    def test_resource_mismatch_finding(self):
        """Event exists but ResourceName differs → RESOURCE_MISMATCH finding."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": self.fixed_mtime.isoformat().replace("+00:00", "Z"),
                "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-DIFFERENT",
            }
        ]
        with self._mock_lookup(events):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("RESOURCE_MISMATCH", types)

    def test_timing_anomaly_finding(self):
        """Event > 1 hour away from trace mtime → TIMING_ANOMALY (low)."""
        path = make_trace(self.tmp_path, decision="PASS", mtime=self.fixed_mtime)
        # Event was 5 hours before trace mtime
        early_time = (self.fixed_mtime - _dt.timedelta(hours=5)).isoformat().replace("+00:00", "Z")
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": early_time,
                "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        with self._mock_lookup(events):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("TIMING_ANOMALY", types)

    def test_unparseable_trace(self):
        """Trace command is not `aliyun ...` → UNPARSEABLE_TRACE."""
        path = make_trace(self.tmp_path, command="kubectl get pods", decision="PASS", mtime=self.fixed_mtime)
        with self._mock_lookup([]):
            r = xchk.crosscheck_one(path)
        types = [f["type"] for f in r["findings"]]
        self.assertIn("UNPARSEABLE_TRACE", types)


# ---------------------------------------------------------------------------
# T16: aggregate_findings()
# ---------------------------------------------------------------------------


class AggregateFindingsTests(unittest.TestCase):
    def test_counts(self):
        reports = [
            {"trace_skill": "alicloud-ecs-ops", "findings": [{"type": "PHANTOM_PASS", "severity": "high"}]},
            {"trace_skill": "alicloud-ecs-ops", "findings": []},
            {"trace_skill": "alicloud-rds-ops", "findings": [{"type": "PHANTOM_FAIL", "severity": "high"}]},
            {"trace_skill": "alicloud-rds-ops", "findings": [{"type": "API_ERROR", "severity": "high"}]},
        ]
        s = xchk.aggregate_findings(reports)
        self.assertEqual(s["total_traces"], 4)
        self.assertEqual(s["phantoms"], 2)
        self.assertEqual(s["api_errors"], 1)
        self.assertEqual(s["by_finding_type"]["PHANTOM_PASS"], 1)
        self.assertEqual(s["by_finding_type"]["PHANTOM_FAIL"], 1)
        self.assertEqual(s["by_skill"]["alicloud-ecs-ops"]["total"], 2)
        self.assertEqual(s["by_skill"]["alicloud-ecs-ops"]["with_findings"], 1)
        self.assertEqual(s["by_skill"]["alicloud-rds-ops"]["total"], 2)
        self.assertEqual(s["by_skill"]["alicloud-rds-ops"]["with_findings"], 2)


# ---------------------------------------------------------------------------
# T17-T20: main() CLI integration
# ---------------------------------------------------------------------------


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_exit_0(self):
        path = make_trace(self.tmp_path, decision="PASS")
        events = [
            {
                "EventId": "evt-1", "EventName": "DeleteInstances", "ServiceName": "Ecs",
                "EventTime": _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "EventAccessKeyId": "LTAI5txxxxx",
                "ResourceName": "i-bp1xxxxxxxxxx",
            }
        ]
        with mock.patch.object(xchk.subprocess, "run", return_value=make_lookup_proc(events)):
            code = xchk.main(["--trace", str(path)])
        self.assertEqual(code, xchk.EXIT_CLEAN)

    def test_strict_phantom_pass_exit_1(self):
        path = make_trace(self.tmp_path, decision="PASS")
        with mock.patch.object(xchk.subprocess, "run", return_value=make_lookup_proc([])):
            code = xchk.main(["--trace", str(path), "--strict"])
        self.assertEqual(code, xchk.EXIT_PHANTOM_FOUND)

    def test_missing_trace_exit_2(self):
        code = xchk.main(["--trace", "/nonexistent/trace.json"])
        self.assertEqual(code, xchk.EXIT_USAGE_ERROR)

    def test_api_error_exit_0_with_finding(self):
        """API_ERROR is NOT a phantom; should exit 0 even in --strict mode."""
        path = make_trace(self.tmp_path, decision="PASS")
        cp = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="InternalError")
        with mock.patch.object(xchk.subprocess, "run", return_value=cp):
            code = xchk.main(["--trace", str(path), "--strict"])
        # API_ERROR does not count as a phantom
        self.assertEqual(code, xchk.EXIT_CLEAN)

    def test_trace_dir_with_report(self):
        # Two traces: one PASS (no event → PHANTOM_PASS), one FAIL (with event → PHANTOM_FAIL)
        mtime = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=1)
        make_trace(self.tmp_path, decision="PASS", mtime=mtime)
        make_trace(self.tmp_path, decision="SAFETY_FAIL", op="StopInstance",
                            command="aliyun ecs StopInstance --InstanceId i-bp1xxxxxxxxxx", mtime=mtime)
        report_path = self.tmp_path / "report.json"

        # Mock: LookupEvents for DeleteInstances returns empty,
        # for StopInstances returns one event
        def fake_run(cmd, **kwargs):
            if "DeleteInstances" in cmd:
                return make_lookup_proc([])
            if "StopInstances" in cmd:
                return make_lookup_proc([
                    {
                        "EventId": "evt-2", "EventName": "StopInstances", "ServiceName": "Ecs",
                        "EventTime": mtime.isoformat().replace("+00:00", "Z"),
                        "EventAccessKeyId": "LTAI5txxxxx",
                        "ResourceName": "i-bp1xxxxxxxxxx",
                    }
                ])
            return make_lookup_proc([])

        with mock.patch.object(xchk.subprocess, "run", side_effect=fake_run):
            code = xchk.main(["--trace-dir", str(self.tmp_path), "--report", str(report_path), "--strict"])
        self.assertEqual(code, xchk.EXIT_PHANTOM_FOUND)
        self.assertTrue(report_path.exists())
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"]["phantoms"], 2)
        self.assertEqual(rep["summary"]["total_traces"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
