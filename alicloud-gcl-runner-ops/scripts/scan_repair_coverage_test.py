#!/usr/bin/env python3
"""Unit tests for scan_repair_coverage.py (Phase 1 of repair-table self-evolution).

Coverage:
- test_parse_repair_table_codes_extracts_known_codes
- test_parse_repair_table_codes_empty_when_no_case_block
- test_parse_repair_table_codes_empty_when_file_missing
- test_is_mapped_in_repair_table_known_code_returns_true
- test_is_mapped_in_repair_table_unknown_code_returns_false
- test_is_mapped_in_repair_table_unknown_skill_fails_open
- test_collect_unmapped_skips_patterns_below_threshold
- test_collect_unmapped_skips_already_mapped_codes
- test_emit_suggestions_writes_patch_and_summary
- test_cmd_scan_dry_run_does_not_write
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scan_repair_coverage as src  # noqa: E402
from gcl_reflexion import (  # noqa: E402
    is_mapped_in_repair_table,
    parse_repair_table_codes,
)

# A minimal but realistic harness-lib.sh used by the file-based tests.
# Mirrors the structure of alicloud-ecs-ops/scripts/harness-lib.sh.
FAKE_HARNESS_LIB = """\
#!/bin/bash
# SkillOpt overlay

skillopt_repair_error() {
    local error_code="$1"; shift
    local product="$1";    shift
    local action="$1";     shift
    local params=("$@")

    case "$error_code" in
        Throttling.User|Throttling)
            sleep 5
            ;;
        InvalidParameter|InvalidJSON|MissingParameter|InvalidParameter.RegionId)
            ;;
        Forbidden|NoPermission)
            ;;
        esac
}
"""


class ParseRepairTableCodesTests(unittest.TestCase):
    def test_parse_repair_table_codes_extracts_known_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "harness-lib.sh"
            path.write_text(FAKE_HARNESS_LIB, encoding="utf-8")
            codes = parse_repair_table_codes(path)
        # Deduplicated set of literals across the four branches.
        self.assertEqual(
            codes,
            {
                "Throttling.User",
                "Throttling",
                "InvalidParameter",
                "InvalidJSON",
                "MissingParameter",
                "InvalidParameter.RegionId",
                "Forbidden",
                "NoPermission",
            },
        )

    def test_parse_repair_table_codes_empty_when_no_case_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "harness-lib.sh"
            path.write_text("#!/bin/bash\necho nothing\n", encoding="utf-8")
            self.assertEqual(parse_repair_table_codes(path), set())

    def test_parse_repair_table_codes_empty_when_file_missing(self):
        self.assertEqual(parse_repair_table_codes("/no/such/file.sh"), set())


class IsMappedInRepairTableTests(unittest.TestCase):
    """Coverage lookup uses repo-resident harness-lib.sh via skills_root.

    These tests point skills_root at a temp dir holding FAKE_HARNESS_LIB under
    ``alicloud-ecs-ops/scripts/harness-lib.sh`` (matching _REPAIR_TABLE_PATH).
    """

    def _write_ecs_overlay(self, root: Path) -> Path:
        skill_dir = root / "alicloud-ecs-ops" / "scripts"
        skill_dir.mkdir(parents=True)
        overlay = skill_dir / "harness-lib.sh"
        overlay.write_text(FAKE_HARNESS_LIB, encoding="utf-8")
        return root

    def test_is_mapped_in_repair_table_known_code_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_ecs_overlay(Path(tmp))
            self.assertTrue(
                is_mapped_in_repair_table("alicloud-ecs-ops", "Throttling.User", skills_root=root)
            )
            self.assertTrue(
                is_mapped_in_repair_table("alicloud-ecs-ops", "NoPermission", skills_root=root)
            )

    def test_is_mapped_in_repair_table_unknown_code_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_ecs_overlay(Path(tmp))
            self.assertFalse(
                is_mapped_in_repair_table(
                    "alicloud-ecs-ops", "IdempotentProcessingInProgress", skills_root=root
                )
            )

    def test_is_mapped_in_repair_table_unknown_skill_fails_open(self):
        # Skill not in _REPAIR_TABLE_PATH → True (do not false-positive).
        self.assertTrue(is_mapped_in_repair_table("alicloud-foo-ops", "Any.Code"))

    def test_is_mapped_in_repair_table_empty_code_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._write_ecs_overlay(Path(tmp))
            self.assertTrue(is_mapped_in_repair_table("alicloud-ecs-ops", "", skills_root=root))


def _seed_reflexion_store(root: Path, patterns: list[dict]) -> None:
    """Write a minimal reflexion.json for the scan tests."""
    from gcl_reflexion import _empty_reflexion_store, _save_store, _store_path

    store = _empty_reflexion_store()
    store["cli_parameter"] = patterns
    _save_store(store, root)
    # _save_store writes to _store_path(root); sanity check.
    assert _store_path(root).is_file()


def _seed_skill_overlay(root: Path, skill: str, codes_block: str) -> None:
    overlay = root / skill / "scripts" / "harness-lib.sh"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(
        "#!/bin/bash\nskillopt_repair_error() {\n  case \"$error_code\" in\n"
        + codes_block
        + "  esac\n}\n",
        encoding="utf-8",
    )


class CollectUnmappedTests(unittest.TestCase):
    def test_collect_unmapped_skips_patterns_below_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reflexion_root = root / "reflexion"
            reflexion_root.mkdir()
            skills_root = root / "skills"
            _seed_skill_overlay(skills_root, "alicloud-ecs-ops", "    Throttling.User)\n        ;;\n")
            _seed_reflexion_store(
                reflexion_root,
                [
                    {
                        "category": "cli_parameter",
                        "skill": "alicloud-ecs-ops",
                        "command": "aliyun ecs DescribeInstances",
                        "error": "IdempotentProcessingInProgress",
                        "error_code": "IdempotentProcessingInProgress",
                        "fix": "see help",
                        "count": 2,
                        "first_seen": "2026-07-01T00:00:00Z",
                        "last_seen": "2026-07-01T00:00:01Z",
                        "unmapped_in_repair": True,
                    },
                ],
            )
            items = src.collect_unmapped_patterns(reflexion_root, threshold=5, skills_root=skills_root)
            self.assertEqual(items, [])

    def test_collect_unmapped_skips_already_mapped_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reflexion_root = root / "reflexion"
            reflexion_root.mkdir()
            skills_root = root / "skills"
            _seed_skill_overlay(skills_root, "alicloud-ecs-ops", "    Throttling.User)\n        ;;\n")
            _seed_reflexion_store(
                reflexion_root,
                [
                    {
                        "category": "cli_parameter",
                        "skill": "alicloud-ecs-ops",
                        "command": "aliyun ecs DescribeInstances",
                        "error": "Throttling.User",
                        "error_code": "Throttling.User",
                        "fix": "backoff",
                        "count": 9,
                        "first_seen": "2026-07-01T00:00:00Z",
                        "last_seen": "2026-07-02T00:00:00Z",
                        "unmapped_in_repair": False,  # already covered
                    },
                ],
            )
            items = src.collect_unmapped_patterns(reflexion_root, threshold=5, skills_root=skills_root)
            self.assertEqual(items, [])

    def test_collect_unmapped_emits_when_unmapped_and_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reflexion_root = root / "reflexion"
            reflexion_root.mkdir()
            skills_root = root / "skills"
            _seed_skill_overlay(skills_root, "alicloud-ecs-ops", "    Throttling.User)\n        ;;\n")
            _seed_reflexion_store(
                reflexion_root,
                [
                    {
                        "category": "cli_parameter",
                        "skill": "alicloud-ecs-ops",
                        "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
                        "error": "IdempotentProcessingInProgress: too soon",
                        "error_code": "IdempotentProcessingInProgress",
                        "fix": "see help",
                        "count": 7,
                        "first_seen": "2026-07-01T00:00:00Z",
                        "last_seen": "2026-07-02T00:00:00Z",
                        "unmapped_in_repair": True,
                    },
                ],
            )
            items = src.collect_unmapped_patterns(reflexion_root, threshold=5, skills_root=skills_root)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["skill"], "alicloud-ecs-ops")
            self.assertEqual(item["code"], "IdempotentProcessingInProgress")
            self.assertEqual(item["count"], 7)
            self.assertEqual(len(item["hash"]), 12)


class EmitSuggestionsTests(unittest.TestCase):
    def test_emit_suggestions_writes_patch_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            items = [
                {
                    "skill": "alicloud-ecs-ops",
                    "code": "IdempotentProcessingInProgress",
                    "count": 7,
                    "first_seen": "2026-07-01T00:00:00Z",
                    "last_seen": "2026-07-02T00:00:00Z",
                    "command": "aliyun ecs DescribeInstances",
                    "hash": "deadbeef0001",
                    "pattern": {
                        "error": "IdempotentProcessingInProgress: too soon",
                        "command": "aliyun ecs DescribeInstances",
                        "count": 7,
                        "first_seen": "2026-07-01T00:00:00Z",
                        "last_seen": "2026-07-02T00:00:00Z",
                    },
                }
            ]
            written = src.emit_suggestions(items, output_dir)
            self.assertEqual(len(written), 1)
            patch_path = Path(written[0]["patch_path"])
            self.assertTrue(patch_path.is_file())
            body = patch_path.read_text(encoding="utf-8")
            self.assertIn("IdempotentProcessingInProgress", body)
            self.assertIn("TODO: replace with real repair logic", body)
            summary_path = output_dir / "summary.json"
            self.assertTrue(summary_path.is_file())
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["code"], "IdempotentProcessingInProgress")
            self.assertEqual(data[0]["hash"], "deadbeef0001")
            # Pattern (the full nested dict) must NOT leak into the summary.
            self.assertNotIn("pattern", data[0])


class CmdScanDryRunTests(unittest.TestCase):
    def test_cmd_scan_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reflexion_root = root / "reflexion"
            reflexion_root.mkdir()
            skills_root = root / "skills"
            _seed_skill_overlay(skills_root, "alicloud-ecs-ops", "    Throttling.User)\n        ;;\n")
            _seed_reflexion_store(
                reflexion_root,
                [
                    {
                        "category": "cli_parameter",
                        "skill": "alicloud-ecs-ops",
                        "command": "aliyun ecs DescribeInstances",
                        "error": "IdempotentProcessingInProgress",
                        "error_code": "IdempotentProcessingInProgress",
                        "fix": "see help",
                        "count": 9,
                        "first_seen": "2026-07-01T00:00:00Z",
                        "last_seen": "2026-07-02T00:00:00Z",
                        "unmapped_in_repair": True,
                    },
                ],
            )
            output_dir = root / "suggestions"
            args = src.build_arg_parser().parse_args(
                [
                    "scan",
                    "--reflexion-root", str(reflexion_root),
                    "--output-dir", str(output_dir),
                    "--skills-root", str(skills_root),
                    "--threshold", "5",
                    "--dry-run",
                ]
            )
            rc = src.cmd_scan(args)
            self.assertEqual(rc, 1)  # EMITTED — but no files
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
