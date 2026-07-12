#!/usr/bin/env python3
"""
gcl_memory_test.py — Unit tests for gcl_memory.py.

Pure stdlib unittest. Python 3.10+ compatible.
Run: python3 -m unittest gcl_memory_test -v

Test coverage:
  - memory_store: writes correct JSONL format, auto-extracts operation
  - memory_retrieve: returns top-k newest, filters by skill/operation
  - memory_maintain: prunes entries older than keep_days
  - _extract_operation: CLI command parsing
  - Edge cases: empty traces, missing files, corrupt JSONL lines
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the scripts directory is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_memory import (
    DEFAULT_MEMORY_ROOT,
    MEMORY_KEEP_DAYS_DEFAULT,
    _build_memory_entry,
    _extract_operation,
    _get_memory_file,
    _parse_iso_timestamp,
    _prune_jsonl,
    _read_jsonl_tail,
    _resolve_memory_root,
    main,
    memory_maintain,
    memory_purge_unknown,
    memory_retrieve,
    memory_store,
    memory_store_lite,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_trace(
    skill: str = "alicloud-ecs-ops",
    status: str = "PASS",
    command: str = "aliyun ecs DescribeInstances --PageSize 10",
    exit_code: int = 0,
    has_failure_pattern: bool = False,
) -> dict:
    """Build a minimal GCL trace dict resembling gcl_runner.py output."""
    trace: dict = {
        "skill": skill,
        "request": "list my instances",
        "rubric_version": "v1",
        "final": {
            "status": status,
            "iter": 1,
            "output": "exit_code=0 request_id=abc duration=100ms",
        },
        "iterations": [
            {
                "iter": 1,
                "generator": {
                    "command": command,
                    "exit_code": exit_code,
                    "stdout": "...",
                    "stderr": "",
                    "result_excerpt": "ok",
                    "request_id": "abc-123",
                    "duration_ms": 100,
                    "execution_path": "wrapper",
                    "execution_path_skill": "alicloud-ecs-ops",
                },
                "critic": {
                    "scores": {
                        "correctness": 1.0,
                        "safety": 1.0,
                        "idempotency": 0.5,
                        "traceability": 1.0,
                        "spec_compliance": 1.0,
                    },
                    "suggestions": [],
                    "matched_regexes": [],
                    "blocking": False,
                },
                "decision": status,
            }
        ],
    }
    if has_failure_pattern:
        trace["failure_pattern"] = {
            "category": "destructive-operation",
            "skill": skill,
            "op": "DeleteInstance",
            "command": command,
            "fix": "Add --Force true",
        }
    return trace


# ---------------------------------------------------------------------------
# _extract_operation
# ---------------------------------------------------------------------------

class ExtractOperationTests(unittest.TestCase):
    """Test _extract_operation() command parsing."""

    def test_aliyun_command(self):
        self.assertEqual(_extract_operation("aliyun ecs DescribeInstances --PageSize 10"), "DescribeInstances")

    def test_aliyun_long_product(self):
        self.assertEqual(_extract_operation("aliyun r-kvstore DescribeInstances --RegionId cn-hangzhou"), "DescribeInstances")

    def test_wrapper_command(self):
        self.assertEqual(_extract_operation("./alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh DescribeInstances --PageSize 1"), "DescribeInstances")

    def test_harness_wrapper_command(self):
        self.assertEqual(_extract_operation("./alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh DescribeInstances"), "DescribeInstances")

    def test_data_plane_tool(self):
        self.assertEqual(_extract_operation("redis-cli DEL key1 key2"), "redis-cli")
        self.assertEqual(_extract_operation("mongosh --host localhost --eval 'db.dropDatabase()'"), "mongosh")

    def test_empty_command(self):
        self.assertEqual(_extract_operation(""), "unknown")

    def test_bare_command(self):
        self.assertEqual(_extract_operation("echo hello"), "echo")


# ---------------------------------------------------------------------------
# _resolve_memory_root
# ---------------------------------------------------------------------------

class ResolveMemoryRootTests(unittest.TestCase):
    """Test _resolve_memory_root() resolution priority."""

    def test_explicit_path(self):
        p = _resolve_memory_root("/tmp/test-mem")
        self.assertEqual(p, Path("/tmp/test-mem"))

    def test_env_var(self):
        old = os.environ.get("GCL_MEMORY_ROOT")
        try:
            os.environ["GCL_MEMORY_ROOT"] = "/env/memory"
            p = _resolve_memory_root(None)
            self.assertEqual(p, Path("/env/memory"))
        finally:
            if old is None:
                del os.environ["GCL_MEMORY_ROOT"]
            else:
                os.environ["GCL_MEMORY_ROOT"] = old

    def test_default(self):
        p = _resolve_memory_root(None)
        self.assertEqual(p, DEFAULT_MEMORY_ROOT)

    def test_literal_string_none_falls_back_to_default(self):
        # Regression: passing literal "None" (e.g. from shell expansion of an
        # unset var) must NOT create a directory named "None/" under cwd.
        old = os.environ.get("GCL_MEMORY_ROOT")
        try:
            os.environ.pop("GCL_MEMORY_ROOT", None)
            p = _resolve_memory_root("None")
            self.assertEqual(p, DEFAULT_MEMORY_ROOT)
            self.assertNotEqual(p.name, "None")
        finally:
            if old is not None:
                os.environ["GCL_MEMORY_ROOT"] = old

    def test_env_var_literal_none_falls_back_to_default(self):
        # Same defense for the env var path.
        old = os.environ.get("GCL_MEMORY_ROOT")
        try:
            os.environ["GCL_MEMORY_ROOT"] = "None"
            p = _resolve_memory_root(None)
            self.assertEqual(p, DEFAULT_MEMORY_ROOT)
        finally:
            if old is None:
                del os.environ["GCL_MEMORY_ROOT"]
            else:
                os.environ["GCL_MEMORY_ROOT"] = old


# ---------------------------------------------------------------------------
# _build_memory_entry
# ---------------------------------------------------------------------------

class BuildMemoryEntryTests(unittest.TestCase):
    """Test _build_memory_entry() extraction from trace."""

    def test_extracts_skill_and_operation(self):
        trace = _sample_trace()
        entry = _build_memory_entry(trace, "DescribeInstances", "/tmp/trace.json")
        self.assertEqual(entry["skill"], "alicloud-ecs-ops")
        self.assertEqual(entry["operation"], "DescribeInstances")
        self.assertEqual(entry["gcl_status"], "PASS")
        self.assertTrue(entry["rubric_pass"])

    def test_auto_extract_operation_when_none(self):
        trace = _sample_trace(command="aliyun ecs DeleteInstance --InstanceId i-xxx")
        entry = _build_memory_entry(trace, None, None)
        self.assertEqual(entry["operation"], "DeleteInstance")

    def test_includes_trace_path(self):
        trace = _sample_trace()
        entry = _build_memory_entry(trace, "DescribeInstances", "/tmp/gcl-trace-20260620.json")
        self.assertEqual(entry["trace_path"], "/tmp/gcl-trace-20260620.json")

    def test_includes_scores(self):
        trace = _sample_trace()
        entry = _build_memory_entry(trace, "DescribeInstances", None)
        self.assertEqual(entry["scores"]["correctness"], 1.0)
        self.assertEqual(entry["scores"]["safety"], 1.0)

    def test_failure_pattern_included(self):
        trace = _sample_trace(status="SAFETY_FAIL", has_failure_pattern=True)
        entry = _build_memory_entry(trace, "DeleteInstance", None)
        self.assertIn("failure_pattern", entry)
        self.assertEqual(entry["failure_pattern"]["category"], "destructive-operation")

    def test_timestamp_is_iso_format(self):
        trace = _sample_trace()
        entry = _build_memory_entry(trace, "DescribeInstances", None)
        ts = entry.get("timestamp", "")
        self.assertTrue(ts.endswith("Z") or "+" in ts)
        self.assertIsNotNone(_parse_iso_timestamp(ts))

    def test_missing_iterations(self):
        trace = {"skill": "alicloud-ecs-ops", "final": {"status": "PASS"}}
        entry = _build_memory_entry(trace, "DescribeInstances", None)
        self.assertEqual(entry["exit_code"], -1)
        self.assertEqual(entry["scores"], {})

    def test_rubric_pass_false_on_failure(self):
        trace = _sample_trace(status="SAFETY_FAIL")
        entry = _build_memory_entry(trace, "DeleteInstance", None)
        self.assertFalse(entry["rubric_pass"])

    def test_trace_operation_field_priority(self):
        """trace["operation"] takes priority over auto-extraction."""
        trace = _sample_trace(command="aliyun ecs DescribeInstances --PageSize 10")
        trace["operation"] = "ExplicitOp"
        entry = _build_memory_entry(trace, None, None)
        self.assertEqual(entry["operation"], "ExplicitOp")

    def test_explicit_param_overrides_trace_field(self):
        """Explicit *operation* parameter overrides everything."""
        trace = _sample_trace(command="aliyun ecs DescribeInstances --PageSize 10")
        trace["operation"] = "InTraceOp"
        entry = _build_memory_entry(trace, "ExplicitParam", None)
        self.assertEqual(entry["operation"], "ExplicitParam")

    def test_iterations_count_included(self):
        trace = _sample_trace()
        entry = _build_memory_entry(trace, "DescribeInstances", None)
        self.assertEqual(entry["iterations"], 1)

    def test_iterations_count_empty(self):
        trace = {"skill": "alicloud-ecs-ops", "final": {"status": "PASS"}}
        entry = _build_memory_entry(trace, "DescribeInstances", None)
        self.assertEqual(entry["iterations"], 0)


# ---------------------------------------------------------------------------
# _get_memory_file
# ---------------------------------------------------------------------------

class GetMemoryFileTests(unittest.TestCase):
    """Test _get_memory_file() path resolution."""

    def test_returns_jsonl_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = _get_memory_file(root, "alicloud-ecs-ops", "DescribeInstances")
            self.assertEqual(p, root / "alicloud-ecs-ops" / "DescribeInstances.jsonl")

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = _get_memory_file(root, "alicloud-redis-ops", "FlushInstance")
            self.assertEqual(p, root / "alicloud-redis-ops" / "FlushInstance.jsonl")
            self.assertTrue(p.parent.exists())
            self.assertFalse(p.exists())


# ---------------------------------------------------------------------------
# memory_store + memory_retrieve (integration with temp dir)
# ---------------------------------------------------------------------------

class MemoryStoreRetrieveTests(unittest.TestCase):
    """Integration tests for store → retrieve round-trip."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_store_creates_jsonl(self):
        trace = _sample_trace()
        rc = memory_store(trace, operation="DescribeInstances", memory_root=self.memory_root)
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        self.assertTrue(mem_file.exists())
        lines = mem_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["skill"], "alicloud-ecs-ops")

    def test_store_auto_extract_operation(self):
        trace = _sample_trace(command="aliyun ecs DeleteInstance --InstanceId i-xxx")
        rc = memory_store(trace, memory_root=self.memory_root)
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DeleteInstance.jsonl"
        self.assertTrue(mem_file.exists())

    def test_store_appends_multiple_entries(self):
        trace = _sample_trace()
        for _ in range(3):
            memory_store(trace, operation="DescribeInstances", memory_root=self.memory_root)
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        lines = mem_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)

    def test_retrieve_returns_top_k(self):
        trace = _sample_trace()
        for i in range(10):
            t = dict(trace)
            t["final"] = {"status": "PASS", "iter": 1, "output": f"run-{i}"}
            memory_store(t, operation="DescribeInstances", memory_root=self.memory_root)

        entries = memory_retrieve("alicloud-ecs-ops", operation="DescribeInstances", top_k=3, memory_root=self.memory_root)
        self.assertEqual(len(entries), 3)

    def test_retrieve_all_operations_when_no_filter(self):
        trace1 = _sample_trace(command="aliyun ecs DescribeInstances --PageSize 10")
        trace2 = _sample_trace(command="aliyun ecs DeleteInstance --InstanceId i-xxx")
        memory_store(trace1, memory_root=self.memory_root)
        memory_store(trace2, memory_root=self.memory_root)

        entries = memory_retrieve("alicloud-ecs-ops", top_k=10, memory_root=self.memory_root)
        self.assertEqual(len(entries), 2)
        ops = {e["operation"] for e in entries}
        self.assertIn("DescribeInstances", ops)
        self.assertIn("DeleteInstance", ops)

    def test_retrieve_empty_skill(self):
        entries = memory_retrieve("alicloud-ecs-ops", top_k=5, memory_root=self.memory_root)
        self.assertEqual(entries, [])

    def test_retrieve_bad_operation(self):
        entries = memory_retrieve("alicloud-ecs-ops", operation="NoSuchOp", top_k=5, memory_root=self.memory_root)
        self.assertEqual(entries, [])

    def test_store_minimal_trace_ok(self):
        """A structurally valid but minimal trace is stored successfully."""
        rc = memory_store({"skill": "alicloud-ecs-ops", "final": {"status": "PASS"}}, memory_root=self.memory_root)
        self.assertEqual(rc, 0)
        # The entry is created even with minimal fields
        entries = memory_retrieve("alicloud-ecs-ops", top_k=5, memory_root=self.memory_root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["operation"], "unknown")


# ---------------------------------------------------------------------------
# _read_jsonl_tail
# ---------------------------------------------------------------------------

class ReadJsonlTailTests(unittest.TestCase):
    """Test _read_jsonl_tail() reverse reading."""

    def test_reads_last_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.jsonl"
            lines = [json.dumps({"i": i}, sort_keys=True) for i in range(10)]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            entries = _read_jsonl_tail(p, 3)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0]["i"], 9)
            self.assertEqual(entries[-1]["i"], 7)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.jsonl"
            p.write_text("", encoding="utf-8")
            entries = _read_jsonl_tail(p, 5)
            self.assertEqual(entries, [])

    def test_skips_bad_json_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "mixed.jsonl"
            p.write_text('{"i": 1}\nnot json\n{"i": 2}\n', encoding="utf-8")
            entries = _read_jsonl_tail(p, 5)
            # Should skip the non-json line and return entries in newest-first order
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["i"], 2)
            self.assertEqual(entries[1]["i"], 1)

    def test_non_existent_file(self):
        entries = _read_jsonl_tail(Path("/nonexistent/file.jsonl"), 5)
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# memory_maintain
# ---------------------------------------------------------------------------

class MemoryMaintainTests(unittest.TestCase):
    """Test memory_maintain() TTL pruning."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write_entry(self, skill: str, op: str, days_ago: int) -> None:
        """Write a memory entry with a timestamp *days_ago* in the past."""
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
        entry = {
            "timestamp": ts,
            "skill": skill,
            "operation": op,
            "command": f"aliyun {skill.split('-')[1]} {op}",
            "exit_code": 0,
            "rubric_pass": True,
        }
        mem_file = self.memory_root / skill / f"{op}.jsonl"
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        with open(mem_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def test_dry_run_reports_counts(self):
        """Dry-run correctly reports pruned count without modifying files."""
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 60)
        result = memory_maintain(memory_root=self.memory_root, keep_days=30, apply=False)
        self.assertEqual(result["entries_pruned"], 1)
        self.assertEqual(result["entries_before"], 1)
        self.assertEqual(result["entries_after"], 1)  # dry-run: file unchanged → before == after
        self.assertFalse(result["applied"])
        # File content is unchanged
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        self.assertTrue(mem_file.exists())

    def test_apply_prunes_old_entries(self):
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 60)
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 10)  # recent

        result = memory_maintain(memory_root=self.memory_root, keep_days=30, apply=True)
        self.assertEqual(result["entries_pruned"], 1)
        self.assertEqual(result["entries_after"], 1)
        self.assertEqual(result["applied"], True)

        # Verify the file was rewritten
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        remaining = [json.loads(l) for l in mem_file.read_text(encoding="utf-8").strip().splitlines()]
        self.assertEqual(len(remaining), 1)
        # The remaining entry should be the recent one
        self.assertEqual(remaining[0]["operation"], "DescribeInstances")

    def test_keeps_recent_entries(self):
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 5)
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 1)

        result = memory_maintain(memory_root=self.memory_root, keep_days=30, apply=True)
        self.assertEqual(result["entries_pruned"], 0)
        self.assertEqual(result["entries_after"], 2)

    def test_multi_skill_prune(self):
        self._write_entry("alicloud-ecs-ops", "DescribeInstances", 60)
        self._write_entry("alicloud-redis-ops", "FlushInstance", 45)
        self._write_entry("alicloud-rds-ops", "DescribeDBInstances", 5)

        result = memory_maintain(memory_root=self.memory_root, keep_days=30, apply=True)
        self.assertEqual(result["scanned_files"], 3)
        self.assertEqual(result["entries_pruned"], 2)
        self.assertEqual(result["entries_after"], 1)

    def test_empty_root(self):
        result = memory_maintain(memory_root=self.memory_root, keep_days=30, apply=True)
        self.assertEqual(result["scanned_files"], 0)

    def test_skip_entries_without_timestamp(self):
        # Entry without timestamp should NOT be pruned (conservative)
        entry = {"skill": "alicloud-ecs-ops", "operation": "DescribeInstances"}
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        mem_file.parent.mkdir(parents=True)
        with open(mem_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

        result = memory_maintain(memory_root=self.memory_root, keep_days=1, apply=True)
        self.assertEqual(result["entries_pruned"], 0)
        self.assertEqual(result["entries_after"], 1)


# ---------------------------------------------------------------------------
# _parse_iso_timestamp
# ---------------------------------------------------------------------------

class ParseIsoTimestampTests(unittest.TestCase):
    """Test _parse_iso_timestamp() edge cases."""

    def test_z_suffix(self):
        dt = _parse_iso_timestamp("2026-06-20T10:30:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 6)

    def test_positive_offset(self):
        dt = _parse_iso_timestamp("2026-06-20T10:30:00+08:00")
        self.assertIsNotNone(dt)

    def test_utc_offset(self):
        dt = _parse_iso_timestamp("2026-06-20T10:30:00+00:00")
        self.assertIsNotNone(dt)

    def test_bad_string(self):
        dt = _parse_iso_timestamp("not-a-date")
        self.assertIsNone(dt)

    def test_empty_string(self):
        dt = _parse_iso_timestamp("")
        self.assertIsNone(dt)


# ---------------------------------------------------------------------------
# _prune_jsonl
# ---------------------------------------------------------------------------

class PruneJsonlTests(unittest.TestCase):
    """Test _prune_jsonl() low-level pruning."""

    def test_prune_exact_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.jsonl"
            now = datetime.now(timezone.utc)
            old_ts = (now - timedelta(days=31)).isoformat().replace("+00:00", "Z")
            new_ts = (now - timedelta(days=29)).isoformat().replace("+00:00", "Z")
            lines = [
                json.dumps({"timestamp": old_ts}, sort_keys=True),
                json.dumps({"timestamp": new_ts}, sort_keys=True),
            ]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")

            before, after, pruned = _prune_jsonl(p, now - timedelta(days=30), apply=True)
            self.assertEqual(before, 2)
            self.assertEqual(after, 1)
            self.assertEqual(pruned, 1)

    def test_dry_run_counts_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.jsonl"
            old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
            p.write_text(json.dumps({"timestamp": old_ts}, sort_keys=True) + "\n", encoding="utf-8")

            before, after, pruned = _prune_jsonl(p, datetime.now(timezone.utc) - timedelta(days=30), apply=False)
            self.assertEqual(before, 1)
            self.assertEqual(pruned, 1)
            # after = entries that pass filter (file unchanged on disk, but conceptually 0 would remain)
            self.assertEqual(after, 0)


# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------

class DefaultConstantsTests(unittest.TestCase):
    """Test that module-level constants are reasonable."""

    def test_default_keep_days(self):
        self.assertEqual(MEMORY_KEEP_DAYS_DEFAULT, 30)

    def test_default_memory_root(self):
        self.assertEqual(str(DEFAULT_MEMORY_ROOT), ".runtime/memory")


# ---------------------------------------------------------------------------
# Smoke test: module importable
# ---------------------------------------------------------------------------

class ModuleSmokeTests(unittest.TestCase):
    """Minimal smoke tests."""

    def test_module_importable(self):
        import gcl_memory
        self.assertTrue(hasattr(gcl_memory, "memory_store"))
        self.assertTrue(hasattr(gcl_memory, "memory_retrieve"))
        self.assertTrue(hasattr(gcl_memory, "memory_maintain"))
        self.assertTrue(hasattr(gcl_memory, "build_arg_parser"))


# ---------------------------------------------------------------------------
# Main CLI tests
# ---------------------------------------------------------------------------

class MainCliTests(unittest.TestCase):
    """Test gcl_memory.main() CLI entry point with subcommand argv."""

    def test_store_nonexistent_trace_returns_1(self):
        rc = main(["store", "--trace", "/tmp/nonexistent-gcl-trace.json"])
        self.assertEqual(rc, 1)

    def test_retrieve_no_entries(self):
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            rc = main(["retrieve", "--skill", "alicloud-ecs-ops", "--memory-root", "/tmp/gcl-mem-empty-20260620"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        output = captured.getvalue()
        self.assertIn("no memory entries found", output)

    def test_maintain_dry_run(self):
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            rc = main(["maintain", "--memory-root", "/tmp/gcl-mem-empty-20260620"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        output = captured.getvalue()
        self.assertIn("DRY-RUN", output)
        self.assertIn("scanned 0 files", output)

    def test_no_subcommand_returns_1(self):
        """No subcommand / argparse error returns exit code 1."""
        with self.assertRaises(SystemExit):
            main([])

    def test_bad_subcommand_returns_1(self):
        with self.assertRaises(SystemExit):
            main(["unknown-subcommand"])

    def test_purge_unknown_dry_run_empty(self):
        """purge-unknown on empty memory root returns zeros."""
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            rc = main(["purge-unknown", "--memory-root", "/tmp/gcl-mem-empty-20260620"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        output = captured.getvalue()
        self.assertIn("DRY-RUN", output)
        self.assertIn("scanned 0 skills", output)
        self.assertIn("found 0 unknown.jsonl", output)

    def test_store_lite_cli_basic(self):
        """store-lite CLI writes a JSONL entry."""
        from io import StringIO
        with tempfile.TemporaryDirectory() as tmp:
            captured = StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = captured
                rc = main([
                    "store-lite",
                    "--skill", "alicloud-test-ops",
                    "--operation", "DoFoo",
                    "--command", "aliyun test DoFoo --PageSize 10",
                    "--duration-ms", "123",
                    "--memory-root", tmp,
                ])
            finally:
                sys.stdout = old_stdout
            self.assertEqual(rc, 0)
            output = captured.getvalue()
            self.assertIn("lite: alicloud-test-ops DoFoo", output)
            # Verify file
            mem_file = Path(tmp) / "alicloud-test-ops" / "DoFoo.jsonl"
            self.assertTrue(mem_file.exists())
            entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
            self.assertEqual(entry["source"], "skillopt-wrapper")
            self.assertEqual(entry["duration_ms"], 123)
            self.assertEqual(entry["gcl_status"], "LIGHTWEIGHT")

    def test_store_lite_cli_failed_status(self):
        """store-lite CLI with status=failed records exit_code != 0."""
        from io import StringIO
        with tempfile.TemporaryDirectory() as tmp:
            captured = StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = captured
                rc = main([
                    "store-lite",
                    "--skill", "alicloud-test-ops",
                    "--operation", "FailOp",
                    "--command", "aliyun test FailOp",
                    "--status", "failed",
                    "--exit-code", "1",
                    "--memory-root", tmp,
                ])
            finally:
                sys.stdout = old_stdout
            self.assertEqual(rc, 0)
            mem_file = Path(tmp) / "alicloud-test-ops" / "FailOp.jsonl"
            entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
            self.assertEqual(entry["gcl_status"], "FAILED")
            self.assertEqual(entry["exit_code"], 1)
            self.assertFalse(entry["rubric_pass"])


# ---------------------------------------------------------------------------
# memory_purge_unknown
# ---------------------------------------------------------------------------

class MemoryStoreLiteTests(unittest.TestCase):
    """Test memory_store_lite() — lightweight entry writer for direct wrapper calls."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_basic_lite_store(self):
        rc = memory_store_lite(
            skill="alicloud-slb-ops",
            operation="DescribeLoadBalancers",
            command="aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou",
            exit_code=0,
            duration_ms=423,
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-slb-ops" / "DescribeLoadBalancers.jsonl"
        self.assertTrue(mem_file.exists())
        lines = mem_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["skill"], "alicloud-slb-ops")
        self.assertEqual(entry["operation"], "DescribeLoadBalancers")
        self.assertEqual(entry["exit_code"], 0)
        self.assertEqual(entry["duration_ms"], 423)
        self.assertEqual(entry["source"], "skillopt-wrapper")
        self.assertEqual(entry["gcl_status"], "LIGHTWEIGHT")
        self.assertTrue(entry["rubric_pass"])
        self.assertEqual(entry["scores"], {})
        self.assertEqual(entry["iterations"], 0)

    def test_failed_invocation_records_failure(self):
        rc = memory_store_lite(
            skill="alicloud-ecs-ops",
            operation="DescribeInstances",
            command="aliyun ecs DescribeInstances",
            exit_code=1,
            status="failed",
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
        self.assertFalse(entry["rubric_pass"])
        self.assertEqual(entry["gcl_status"], "FAILED")
        self.assertEqual(entry["exit_code"], 1)

    def test_error_code_persisted_on_failed_lite(self):
        rc = memory_store_lite(
            skill="alicloud-ecs-ops",
            operation="DescribeInstances",
            command="aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            exit_code=1,
            status="failed",
            error_code="InvalidParameter",
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["error_code"], "InvalidParameter")

    def test_exit_code_prefix_not_stored_as_error_code(self):
        rc = memory_store_lite(
            skill="alicloud-ecs-ops",
            operation="DescribeInstances",
            command="aliyun ecs DescribeInstances",
            exit_code=1,
            status="failed",
            error_code="exit_code_1",
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        entry = json.loads(
            (self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertNotIn("error_code", entry)

    def test_auto_extracts_operation_when_unknown(self):
        """If operation is 'unknown', auto-extract from command."""
        rc = memory_store_lite(
            skill="alicloud-rds-ops",
            operation="unknown",
            command="aliyun rds DescribeDBInstances --PageSize 10",
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-rds-ops" / "DescribeDBInstances.jsonl"
        self.assertTrue(mem_file.exists())
        entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["operation"], "DescribeDBInstances")

    def test_coexists_with_full_gcl_entries(self):
        """Lite and full entries for the same (skill, op) coexist in same JSONL."""
        # Full GCL-style entry first
        trace = _sample_trace(command="aliyun ecs DescribeInstances --PageSize 10")
        memory_store(trace, memory_root=self.memory_root)
        # Then lite entry
        memory_store_lite(
            skill="alicloud-ecs-ops",
            operation="DescribeInstances",
            command="aliyun ecs DescribeInstances --PageSize 5",
            exit_code=0,
            duration_ms=150,
            memory_root=self.memory_root,
        )
        mem_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        lines = mem_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        full = json.loads(lines[0])
        lite = json.loads(lines[1])
        self.assertEqual(full.get("source", "gcl-runner"), "gcl-runner")
        self.assertEqual(lite["source"], "skillopt-wrapper")
        self.assertEqual(lite["gcl_status"], "LIGHTWEIGHT")
        self.assertTrue(lite["rubric_pass"])

    def test_execution_path_propagates(self):
        """execution_path is recorded for later analysis."""
        memory_store_lite(
            skill="alicloud-vpc-ops",
            operation="DescribeVpcs",
            command="aliyun vpc DescribeVpcs",
            execution_path="direct_aliyun",
            memory_root=self.memory_root,
        )
        mem_file = self.memory_root / "alicloud-vpc-ops" / "DescribeVpcs.jsonl"
        entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["execution_path"], "direct_aliyun")

    def test_no_failure_on_missing_args(self):
        """Missing optional args use defaults and don't raise."""
        rc = memory_store_lite(
            skill="alicloud-test-ops",
            operation="TestOp",
            command="aliyun test TestOp",
            memory_root=self.memory_root,
        )
        self.assertEqual(rc, 0)
        mem_file = self.memory_root / "alicloud-test-ops" / "TestOp.jsonl"
        entry = json.loads(mem_file.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["exit_code"], 0)
        self.assertEqual(entry["duration_ms"], 0)
        self.assertEqual(entry["execution_path"], "wrapper")


class MemoryPurgeUnknownTests(unittest.TestCase):
    """Test memory_purge_unknown() removes unknown.jsonl test artifacts."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.memory_root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write_unknown(self, skill: str) -> None:
        """Write an unknown.jsonl file for a skill."""
        entry = {
            "timestamp": "2026-06-20T13:01:27Z",
            "skill": skill,
            "operation": "unknown",
            "command": "",
            "exit_code": -1,
            "rubric_pass": False,
        }
        mem_file = self.memory_root / skill / "unknown.jsonl"
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        with open(mem_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def test_dry_run_reports_found(self):
        """Dry-run finds unknown.jsonl files without deleting them."""
        self._write_unknown("alicloud-ecs-ops")
        result = memory_purge_unknown(memory_root=self.memory_root, apply=False)
        self.assertEqual(result["scanned_skills"], 1)
        self.assertEqual(result["files_found"], 1)
        self.assertEqual(result["files_removed"], 0)  # dry-run
        self.assertEqual(result["dirs_cleaned"], 0)
        self.assertFalse(result["applied"])
        # File still exists
        self.assertTrue((self.memory_root / "alicloud-ecs-ops" / "unknown.jsonl").exists())

    def test_apply_removes_unknown_file(self):
        """Apply deletes unknown.jsonl."""
        self._write_unknown("alicloud-ecs-ops")
        result = memory_purge_unknown(memory_root=self.memory_root, apply=True)
        self.assertEqual(result["files_found"], 1)
        self.assertEqual(result["files_removed"], 1)
        self.assertTrue(result["applied"])
        self.assertFalse((self.memory_root / "alicloud-ecs-ops" / "unknown.jsonl").exists())

    def test_cleans_empty_skill_dir(self):
        """When unknown.jsonl is the only file, the skill dir is also removed."""
        self._write_unknown("alicloud-ecs-ops")
        result = memory_purge_unknown(memory_root=self.memory_root, apply=True)
        self.assertEqual(result["dirs_cleaned"], 1)
        self.assertFalse((self.memory_root / "alicloud-ecs-ops").exists())

    def test_keeps_other_files_in_dir(self):
        """Only unknown.jsonl is removed; other JSONL files and dir are kept."""
        self._write_unknown("alicloud-ecs-ops")
        # Also write a real operation file
        real_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text('{"operation": "DescribeInstances", "command": "aliyun ecs DescribeInstances"}\n')

        result = memory_purge_unknown(memory_root=self.memory_root, apply=True)
        self.assertEqual(result["files_removed"], 1)
        self.assertEqual(result["dirs_cleaned"], 0)  # dir has other files
        self.assertFalse((self.memory_root / "alicloud-ecs-ops" / "unknown.jsonl").exists())
        self.assertTrue((self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl").exists())

    def test_no_unknown_does_nothing(self):
        """No unknown.jsonl → zero removals."""
        # Create a real operation file
        real_file = self.memory_root / "alicloud-ecs-ops" / "DescribeInstances.jsonl"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text('{"operation": "DescribeInstances"}\n')

        result = memory_purge_unknown(memory_root=self.memory_root, apply=True)
        self.assertEqual(result["files_found"], 0)
        self.assertEqual(result["files_removed"], 0)

    def test_empty_root_returns_early(self):
        """Non-existent memory root returns zeros."""
        result = memory_purge_unknown(memory_root=Path("/nonexistent/path"), apply=True)
        self.assertEqual(result["scanned_skills"], 0)
        self.assertEqual(result["files_found"], 0)

    def test_multiple_skills(self):
        """Multiple skills with unknown.jsonl are all cleaned."""
        self._write_unknown("alicloud-ecs-ops")
        self._write_unknown("alicloud-slb-ops")
        self._write_unknown("alicloud-rds-ops")
        # One skill also has a real file
        real_file = self.memory_root / "alicloud-rds-ops" / "DescribeDBInstances.jsonl"
        real_file.write_text('{"operation": "DescribeDBInstances"}\n')

        result = memory_purge_unknown(memory_root=self.memory_root, apply=True)
        self.assertEqual(result["files_found"], 3)
        self.assertEqual(result["files_removed"], 3)
        self.assertEqual(result["dirs_cleaned"], 2)  # ecs + slb, not rds
        # Verify artifacts
        self.assertFalse((self.memory_root / "alicloud-ecs-ops").exists())
        self.assertFalse((self.memory_root / "alicloud-slb-ops").exists())
        self.assertTrue((self.memory_root / "alicloud-rds-ops").exists())
        self.assertTrue((self.memory_root / "alicloud-rds-ops" / "DescribeDBInstances.jsonl").exists())

    def test_purge_unknown_subcommand_cli(self):
        """CLI subcommand purge-unknown works in dry-run."""
        self._write_unknown("alicloud-ecs-ops")
        self._write_unknown("alicloud-slb-ops")
        # Run via CLI (dry-run)
        with tempfile.TemporaryDirectory() as env_dir:
            # Write memory_root path to a temp marker
            # We call main() with args
            import io
            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                rc = main(["purge-unknown", "--memory-root", str(self.memory_root)])
            finally:
                sys.stdout = old_stdout
            self.assertEqual(rc, 0)
            output = captured.getvalue()
            self.assertIn("DRY-RUN", output)
            self.assertIn("found 2 unknown.jsonl", output)
            # Files still exist (dry-run)
            self.assertTrue((self.memory_root / "alicloud-ecs-ops" / "unknown.jsonl").exists())

    def test_purge_unknown_subcommand_cli_apply(self):
        """CLI subcommand purge-unknown --apply deletes files."""
        self._write_unknown("alicloud-ecs-ops")
        import io
        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured
        try:
            rc = main(["purge-unknown", "--memory-root", str(self.memory_root), "--apply"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        output = captured.getvalue()
        self.assertIn("APPLY", output)
        self.assertIn("removed 1 files", output)
        self.assertFalse((self.memory_root / "alicloud-ecs-ops" / "unknown.jsonl").exists())


# ---------------------------------------------------------------------------
# gcl_runner integration tests
# ---------------------------------------------------------------------------

class RunnerIntegrationTests(unittest.TestCase):
    """Test that gcl_runner.py can import and call memory_store() correctly."""

    def test_memory_store_importable(self):
        """memory_store can be imported from gcl_memory."""
        import gcl_memory
        self.assertTrue(callable(gcl_memory.memory_store))

    def test_memory_purge_unknown_importable(self):
        """memory_purge_unknown can be imported from gcl_memory."""
        import gcl_memory
        self.assertTrue(callable(gcl_memory.memory_purge_unknown))

    def test_memory_store_fallback_noop(self):
        """Simulate gcl_runner's ImportError fallback — no-op should return 0."""
        def fallback(*args: object, **kwargs: object) -> int:
            return 0
        self.assertEqual(fallback(), 0)
        self.assertEqual(fallback("extra", trace_path="/tmp/x"), 0)

    def test_memory_purge_unknown_fallback_noop(self):
        """Simulate gcl_runner's ImportError fallback — no-op returns zeros."""
        def fallback(*args: object, **kwargs: object) -> dict:
            return {"files_removed": 0, "dirs_cleaned": 0, "applied": False}
        result = fallback()
        self.assertEqual(result["files_removed"], 0)
        self.assertEqual(result["dirs_cleaned"], 0)
        self.assertFalse(result["applied"])

    def test_store_trace_from_runner_import(self):
        """Full round-trip: memory_store called with a trace dict (like gcl_runner does)."""
        import gcl_memory
        with tempfile.TemporaryDirectory() as tmp:
            trace = _sample_trace()
            rc = gcl_memory.memory_store(trace, operation="DescribeInstances",
                                         trace_path="/tmp/fake-trace.json",
                                         memory_root=tmp)
            self.assertEqual(rc, 0)

    def test_memory_store_operation_auto_extract(self):
        """memory_store without explicit operation, using gcl_runner import."""
        import gcl_memory
        with tempfile.TemporaryDirectory() as tmp:
            trace = _sample_trace(command="aliyun ecs DeleteInstance --InstanceId i-xxx")
            rc = gcl_memory.memory_store(trace, memory_root=tmp)
            self.assertEqual(rc, 0)


class FormatPerItemTruncationTests(unittest.TestCase):
    """A2.2 — per-item truncation to item_max_chars (default 200) before joining."""

    def test_known_traps_truncates_single_long_row(self) -> None:
        from gcl_reflexion import format_known_traps

        # Combine multiple fields whose per-field slices still exceed 200 chars
        # after concatenation — guarantees the row triggers item-level truncation.
        long_error = "E_" + ("x" * 200)
        long_cmd = "aliyun ecs " + ("a" * 200)
        long_fix = ("f" * 200)
        patterns = [
            {
                "category": "cli_parameter",
                "error": long_error,
                "command": long_cmd,
                "fix": long_fix,
                "root_cause": "RC",
                "count": 5,
            },
        ]
        text = format_known_traps(patterns)
        rows = [ln for ln in text.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(rows), 1)
        self.assertLessEqual(len(rows[0]), 200)
        self.assertTrue(rows[0].endswith("..."))

    def test_known_traps_truncates_each_row_independently(self) -> None:
        from gcl_reflexion import format_known_traps

        patterns = [
            {
                "category": "cli_parameter",
                "error": "E1",
                "fix": "x" * 500,
                "root_cause": "RC",
                "count": 5,
            },
            {
                "category": "runtime",
                "error": "E2",
                "fix": "y" * 500,
                "root_cause": "RC",
                "count": 7,
            },
            {
                "category": "skill_generation",
                "error": "E3",
                "fix": "z" * 500,
                "root_cause": "RC",
                "count": 9,
            },
        ]
        text = format_known_traps(patterns)
        rows = [ln for ln in text.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertLessEqual(len(row), 200, f"row exceeds 200 chars: {row[:60]}...")

    def test_success_patterns_truncates_single_long_row(self) -> None:
        from gcl_reflexion import format_success_patterns

        long_hint = "y" * 400
        patterns = [
            {
                "capture_reason": "max_iter_pass",
                "count": 4,
                "hint": long_hint,
            },
        ]
        text = format_success_patterns(patterns)
        rows = [ln for ln in text.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(rows), 1)
        self.assertLessEqual(len(rows[0]), 200)

    def test_success_patterns_truncates_each_row_independently(self) -> None:
        from gcl_reflexion import format_success_patterns

        patterns = [
            {"capture_reason": "a", "count": 1, "hint": "x" * 400},
            {"capture_reason": "b", "count": 2, "hint": "y" * 400},
            {"capture_reason": "c", "count": 3, "hint": "z" * 400},
        ]
        text = format_success_patterns(patterns)
        rows = [ln for ln in text.splitlines() if ln.startswith("- ")]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertLessEqual(len(row), 200)

    def test_preflight_retrieve_clamps_per_item(self) -> None:
        """preflight_retrieve() must pass item_max_chars=200 through to formatters."""
        from memory_preflight import preflight_retrieve

        # Build a temp reflexion root with one overflowing trap and one
        # overflowing success pattern.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reflexion.json").write_text(
                json.dumps(
                    {
                        "cli_parameter": [
                            {
                                "skill": "alicloud-ecs-ops",
                                "category": "cli_parameter",
                                "error": "E_LONG",
                                "fix": "x" * 500,
                                "root_cause": "RC",
                                "count": 5,
                                "last_seen": "2026-07-01T00:00:00Z",
                            }
                        ],
                        "skill_generation": [],
                        "cross_skill": [],
                        "runtime": [],
                        "token_efficiency": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "success_patterns.json").write_text(
                json.dumps(
                    {
                        "patterns": [
                            {
                                "capture_reason": "max_iter_pass",
                                "skill": "alicloud-ecs-ops",
                                "count": 4,
                                "hint": "y" * 500,
                                "last_seen": "2026-07-01T00:00:00Z",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = preflight_retrieve(
                skill="alicloud-ecs-ops",
                skills_root=root.parent,
                reflexion_root=root,
                baseline_path=root / "missing.json",
                traps_top_k=5,
                success_top_k=3,
                traps_max_chars=800,
                success_max_chars=600,
            )

            trap_rows = [
                ln for ln in result["slots"]["known_traps"].splitlines()
                if ln.startswith("- ")
            ]
            success_rows = [
                ln for ln in result["slots"]["success_patterns"].splitlines()
                if ln.startswith("- ")
            ]
            for row in trap_rows + success_rows:
                self.assertLessEqual(
                    len(row), 200,
                    f"preflight slot row exceeded 200 chars: {row[:60]}...",
                )


if __name__ == "__main__":
    unittest.main()
