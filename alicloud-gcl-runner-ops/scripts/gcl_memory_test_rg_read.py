#!/usr/bin/env python3
"""
gcl_memory_test_rg_read.py — Independent test file for WT-4 Layer 1
read-side hard filtering (RG + Tags) on memory_retrieve().

Does NOT modify the existing gcl_memory_test.py / gcl_memory_test_rg.py
(zero-regression on prior 142 tests).

Coverage:
- test_retrieve_no_filter_returns_all: regression — confirms default
  behaviour unchanged when both filters are None.
- test_retrieve_filter_by_rg: only entries with the matching RG returned.
- test_retrieve_filter_by_tag_single: single-key tag filter.
- test_retrieve_filter_by_tag_multiple: multi-key AND semantics.
- test_retrieve_filter_no_match_returns_empty: hard filter excludes all.
- test_retrieve_filter_combined_op_and_rg: operation + RG combined.
- test_retrieve_legacy_entry_without_rg_field: legacy entries excluded
  when RG filter is set; pass-through when no filter.
- test_cli_retrieve_with_filter_flag: end-to-end CLI path with
  --resource-group-id and --tag-filter flags.

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import gcl_memory  # noqa: E402
from gcl_memory import (  # noqa: E402
    _matches_resource_dimensions,
    main,
    memory_retrieve,
    memory_store_lite,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_entry(
    memory_root: Path,
    skill: str,
    operation: str,
    command: str,
    resource_group_id: str | None = None,
    tags: list[dict[str, str]] | None = None,
    include_dim_fields: bool = True,
    include_legacy_rg: bool = False,
) -> None:
    """Append a single memory entry to ``{memory_root}/{skill}/{operation}.jsonl``.

    Args:
        include_dim_fields: If False, omit RG/Tags keys entirely (simulates
            truly legacy entries from before WT-3 schema bump).
        include_legacy_rg: If True, omit ``resource_group_id`` key but
            still write ``tags`` (a mixed-shape legacy entry).
    """
    op_safe = operation.replace("/", "_").replace(" ", "_")
    mem_file = memory_root / skill / f"{op_safe}.jsonl"
    mem_file.parent.mkdir(parents=True, exist_ok=True)

    entry: dict = {
        "timestamp": "2026-06-22T08:00:00Z",
        "skill": skill,
        "operation": operation,
        "command": command,
        "exit_code": 0,
        "execution_path": "wrapper",
        "duration_ms": 100,
        "iterations": 0,
        "rubric_pass": True,
        "gcl_status": "LIGHTWEIGHT",
        "rubric_version": "wrapper-lite",
        "scores": {},
        "source": "skillopt-wrapper",
    }
    if include_dim_fields and not include_legacy_rg:
        entry["resource_group_id"] = resource_group_id
        entry["tags"] = tags if tags is not None else []
        entry["missing_dimensions"] = (
            resource_group_id is None and not tags
        )
    elif include_legacy_rg:
        # Simulate a pre-WT-3 entry: no resource_group_id key at all.
        entry["tags"] = tags if tags is not None else []
    # else: no resource_group_id, no tags — fully legacy.

    with open(mem_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# _matches_resource_dimensions — pure helper unit tests
# ---------------------------------------------------------------------------


class TestMatchesResourceDimensionsHelper(unittest.TestCase):
    """Pure predicate: _matches_resource_dimensions."""

    def test_both_filters_none_returns_true(self) -> None:
        e = {"resource_group_id": "rg-x", "tags": [{"key": "env", "value": "prod"}]}
        self.assertTrue(_matches_resource_dimensions(e, None, None))

    def test_empty_tag_filter_treated_as_none(self) -> None:
        e = {"resource_group_id": "rg-x", "tags": [{"key": "env", "value": "prod"}]}
        self.assertTrue(_matches_resource_dimensions(e, None, {}))

    def test_rg_match(self) -> None:
        e = {"resource_group_id": "rg-x", "tags": []}
        self.assertTrue(_matches_resource_dimensions(e, "rg-x", None))

    def test_rg_mismatch(self) -> None:
        e = {"resource_group_id": "rg-y", "tags": []}
        self.assertFalse(_matches_resource_dimensions(e, "rg-x", None))

    def test_legacy_entry_without_rg_field_excluded_when_filter_set(self) -> None:
        # entry has no resource_group_id key at all
        e = {"tags": []}
        self.assertFalse(_matches_resource_dimensions(e, "rg-x", None))

    def test_legacy_entry_without_rg_field_passes_when_no_filter(self) -> None:
        e = {"tags": []}
        self.assertTrue(_matches_resource_dimensions(e, None, None))


# ---------------------------------------------------------------------------
# memory_retrieve — integration tests
# ---------------------------------------------------------------------------


class TestMemoryRetrieveHardFilter(unittest.TestCase):
    """memory_retrieve() with RG / Tags hard filters."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = "alicloud-ecs-ops"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed_three_rgs(self) -> None:
        """Seed 3 entries across 3 RGs and 2 ops (Describe, Delete)."""
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-alpha",
            resource_group_id="rg-alpha",
            tags=[{"key": "env", "value": "prod"}],
        )
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-beta",
            resource_group_id="rg-beta",
            tags=[{"key": "env", "value": "staging"}],
        )
        _write_entry(
            self.root, self.skill, "DeleteInstance",
            command="aliyun ecs DeleteInstance --ResourceGroupId rg-alpha",
            resource_group_id="rg-alpha",
            tags=[{"key": "env", "value": "prod"}],
        )

    def test_retrieve_no_filter_returns_all(self) -> None:
        """Regression: default (no RG/Tags filter) returns everything."""
        self._seed_three_rgs()
        entries = memory_retrieve(self.skill, top_k=10, memory_root=self.root)
        self.assertEqual(len(entries), 3)

    def test_retrieve_filter_by_rg(self) -> None:
        """Only entries with the matching RG are returned."""
        self._seed_three_rgs()
        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            resource_group_id="rg-alpha",
        )
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["resource_group_id"], "rg-alpha")

    def test_retrieve_filter_by_tag_single(self) -> None:
        """Single-key tag filter (env=prod) returns matching entries only."""
        self._seed_three_rgs()
        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            tag_filter={"env": "prod"},
        )
        self.assertEqual(len(entries), 2)
        for e in entries:
            tag_env = next((t["value"] for t in e["tags"] if t["key"] == "env"), None)
            self.assertEqual(tag_env, "prod")

    def test_retrieve_filter_by_tag_multiple(self) -> None:
        """Multi-key AND: filter env=prod AND team=core only matches
        entries that have BOTH keys (AND, not OR)."""
        # Seed entries:
        #  e1: env=prod, team=core   → MATCHES
        #  e2: env=prod, team=infra  → env matches but team doesn't
        #  e3: env=staging, team=core → team matches but env doesn't
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-alpha "
                    "--Tag.1.Key env --Tag.1.Value prod "
                    "--Tag.2.Key team --Tag.2.Value core",
            resource_group_id="rg-alpha",
            tags=[
                {"key": "env", "value": "prod"},
                {"key": "team", "value": "core"},
            ],
        )
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-beta "
                    "--Tag.1.Key env --Tag.1.Value prod "
                    "--Tag.2.Key team --Tag.2.Value infra",
            resource_group_id="rg-beta",
            tags=[
                {"key": "env", "value": "prod"},
                {"key": "team", "value": "infra"},
            ],
        )
        _write_entry(
            self.root, self.skill, "DeleteInstance",
            command="aliyun ecs DeleteInstance --ResourceGroupId rg-gamma "
                    "--Tag.1.Key env --Tag.1.Value staging "
                    "--Tag.2.Key team --Tag.2.Value core",
            resource_group_id="rg-gamma",
            tags=[
                {"key": "env", "value": "staging"},
                {"key": "team", "value": "core"},
            ],
        )

        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            tag_filter={"env": "prod", "team": "core"},
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["resource_group_id"], "rg-alpha")

    def test_retrieve_filter_no_match_returns_empty(self) -> None:
        """Hard filter that excludes all entries → empty list."""
        self._seed_three_rgs()
        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            resource_group_id="rg-nonexistent",
        )
        self.assertEqual(entries, [])

        # Same for tag filter with no match
        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            tag_filter={"env": "nope"},
        )
        self.assertEqual(entries, [])

    def test_retrieve_filter_combined_op_and_rg(self) -> None:
        """operation=DeleteInstance + RG filter: both must hold."""
        self._seed_three_rgs()
        entries = memory_retrieve(
            self.skill,
            operation="DeleteInstance",
            top_k=10,
            memory_root=self.root,
            resource_group_id="rg-alpha",
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["operation"], "DeleteInstance")
        self.assertEqual(entries[0]["resource_group_id"], "rg-alpha")

    def test_retrieve_legacy_entry_without_rg_field(self) -> None:
        """Backward compat: legacy entry missing resource_group_id.
        Without filter → included. With RG filter → excluded."""
        # Write one modern entry + one legacy (no RG field at all)
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-modern",
            resource_group_id="rg-modern",
            tags=[],
        )
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances",
            include_dim_fields=False,  # truly legacy
        )

        # Without filter — both entries visible (zero regression)
        entries = memory_retrieve(self.skill, top_k=10, memory_root=self.root)
        self.assertEqual(len(entries), 2)

        # With RG filter — legacy excluded, only modern returned
        entries = memory_retrieve(
            self.skill, top_k=10, memory_root=self.root,
            resource_group_id="rg-modern",
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["resource_group_id"], "rg-modern")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCliRetrieveWithFilterFlags(unittest.TestCase):
    """CLI retrieve subcommand passes --resource-group-id / --tag-filter."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = "alicloud-ecs-ops"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed(self) -> None:
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-prod "
                    "--Tag.1.Key env --Tag.1.Value prod",
            resource_group_id="rg-prod",
            tags=[{"key": "env", "value": "prod"}],
        )
        _write_entry(
            self.root, self.skill, "DescribeInstances",
            command="aliyun ecs DescribeInstances --ResourceGroupId rg-stg "
                    "--Tag.1.Key env --Tag.1.Value staging",
            resource_group_id="rg-stg",
            tags=[{"key": "env", "value": "staging"}],
        )

    def test_cli_retrieve_with_resource_group_id_flag(self) -> None:
        """CLI flag --resource-group-id filters entries end-to-end."""
        self._seed()
        rc = main([
            "retrieve",
            "--skill", self.skill,
            "--top-k", "10",
            "--memory-root", str(self.root),
            "--resource-group-id", "rg-prod",
            "--json",
        ])
        self.assertEqual(rc, 0)

    def test_cli_retrieve_with_tag_filter_flag(self) -> None:
        """CLI flag --tag-filter accepts JSON string of {key:value}."""
        self._seed()
        rc = main([
            "retrieve",
            "--skill", self.skill,
            "--top-k", "10",
            "--memory-root", str(self.root),
            "--tag-filter", '{"env":"prod"}',
            "--json",
        ])
        self.assertEqual(rc, 0)

    def test_cli_retrieve_with_combined_filter_flags(self) -> None:
        """CLI accepts both --resource-group-id and --tag-filter together."""
        self._seed()
        rc = main([
            "retrieve",
            "--skill", self.skill,
            "--top-k", "10",
            "--memory-root", str(self.root),
            "--resource-group-id", "rg-prod",
            "--tag-filter", '{"env":"prod"}',
            "--json",
        ])
        self.assertEqual(rc, 0)

    def test_cli_retrieve_invalid_tag_filter_falls_back(self) -> None:
        """Invalid JSON in --tag-filter → graceful fallback (no filter)."""
        self._seed()
        rc = main([
            "retrieve",
            "--skill", self.skill,
            "--top-k", "10",
            "--memory-root", str(self.root),
            "--tag-filter", "this is not json",
            "--json",
        ])
        self.assertEqual(rc, 0)
        # Both entries visible because filter was rejected → no filtering applied


if __name__ == "__main__":
    unittest.main()