#!/usr/bin/env python3
"""
_extract_resource_dimensions_test.py — Unit tests for the RG/Tags parser.

Independent test file: does NOT modify any existing test in the repo.
Runs with: ``python -m unittest _extract_resource_dimensions_test -v``

Coverage matrix:
  - Happy paths for all three Tag formats
  - Boundary cases: equals-in-value, Unicode, empty input, malformed JSON
  - Mutual exclusivity (RepeatList wins over single KV and JSON)
  - Wrapper-level convenience: ``extract_from_command``

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Allow running directly: ``python _extract_resource_dimensions_test.py``.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import _extract_resource_dimensions as _erd_module  # noqa: E402
from _extract_resource_dimensions import extract, extract_from_command  # noqa: E402


class TestRepeatListFormat(unittest.TestCase):
    """Aliyun CLI canonical Tag form: --Tag.N.Key / --Tag.N.Value."""

    def test_basic_single_pair(self) -> None:
        params = ["--Tag.1.Key", "env", "--Tag.1.Value", "prod"]
        result = extract(params)
        self.assertEqual(
            result,
            {
                "resource_group_id": None,
                "tags": [{"key": "env", "value": "prod"}],
                "tags_raw": None,
                "missing_dimensions": False,
                "warning": None,
                "suggestion": None,
            },
        )

    def test_multiple_pairs_ordered(self) -> None:
        params = [
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
            "--Tag.2.Key", "team", "--Tag.2.Value", "core",
            "--Tag.3.Key", "owner", "--Tag.3.Value", "alice",
        ]
        result = extract(params)
        self.assertEqual(len(result["tags"]), 3)
        self.assertEqual(result["tags"][0], {"key": "env", "value": "prod"})
        self.assertEqual(result["tags"][1], {"key": "team", "value": "core"})
        self.assertEqual(result["tags"][2], {"key": "owner", "value": "alice"})
        self.assertIsNone(result["tags_raw"])

    def test_repeatlist_with_resource_group_id(self) -> None:
        params = [
            "--RegionId", "cn-hangzhou",
            "--ResourceGroupId", "rg-abc123",
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
        ]
        result = extract(params)
        self.assertEqual(result["resource_group_id"], "rg-abc123")
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_unicode_key_and_value(self) -> None:
        params = [
            "--Tag.1.Key", "环境", "--Tag.1.Value", "生产",
            "--Tag.2.Key", "业务线", "--Tag.2.Value", "核心",
        ]
        result = extract(params)
        self.assertEqual(
            result["tags"],
            [
                {"key": "环境", "value": "生产"},
                {"key": "业务线", "value": "核心"},
            ],
        )

    def test_value_containing_equals(self) -> None:
        """Values like 'https://x=y' must split on FIRST '='."""
        params = [
            "--Tag.1.Key", "url",
            "--Tag.1.Value", "https://example.com/?q=1",
        ]
        result = extract(params)
        self.assertEqual(
            result["tags"],
            [{"key": "url", "value": "https://example.com/?q=1"}],
        )


class TestSingleKVFormat(unittest.TestCase):
    """Legacy form: --Tag key=value."""

    def test_basic_single(self) -> None:
        params = ["--Tag", "env=prod"]
        result = extract(params)
        self.assertEqual(
            result,
            {
                "resource_group_id": None,
                "tags": [{"key": "env", "value": "prod"}],
                "tags_raw": None,
                "missing_dimensions": False,
                "warning": None,
                "suggestion": None,
            },
        )

    def test_multiple_single_kv(self) -> None:
        params = ["--Tag", "env=prod", "--Tag", "team=core"]
        result = extract(params)
        self.assertEqual(
            result["tags"],
            [
                {"key": "env", "value": "prod"},
                {"key": "team", "value": "core"},
            ],
        )

    def test_single_kv_value_with_equals(self) -> None:
        params = ["--Tag", "url=https://x=y"]
        result = extract(params)
        self.assertEqual(
            result["tags"],
            [{"key": "url", "value": "https://x=y"}],
        )

    def test_single_kv_malformed_falls_back(self) -> None:
        """Missing '=' should populate tags_raw, not crash."""
        params = ["--Tag", "envprod"]
        result = extract(params)
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["tags_raw"], "envprod")

    def test_single_kv_empty_value(self) -> None:
        """'' is allowed as a value (key='env', value='')."""
        params = ["--Tag", "env="]
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": ""}])


class TestJSONArrayFormat(unittest.TestCase):
    """--Tags '[{...}]' form used by some products/SDK wrappers."""

    def test_basic_json_array(self) -> None:
        params = [
            "--Tags",
            '[{"key":"env","value":"prod"},{"key":"team","value":"core"}]',
        ]
        result = extract(params)
        self.assertEqual(
            result["tags"],
            [
                {"key": "env", "value": "prod"},
                {"key": "team", "value": "core"},
            ],
        )

    def test_json_array_capitalised_keys(self) -> None:
        params = ["--Tags", '[{"Key":"env","Value":"prod"}]']
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_json_array_malformed_falls_back(self) -> None:
        params = ["--Tags", "not-json-at-all"]
        result = extract(params)
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["tags_raw"], "not-json-at-all")

    def test_json_array_missing_key_field_falls_back(self) -> None:
        params = ["--Tags", '[{"value":"prod"}]']
        result = extract(params)
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["tags_raw"], '[{"value":"prod"}]')

    def test_json_array_non_dict_item_falls_back(self) -> None:
        params = ["--Tags", '["env","prod"]']
        result = extract(params)
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["tags_raw"], '["env","prod"]')


class TestMutualExclusivity(unittest.TestCase):
    """When multiple formats appear, RepeatList wins (priority 1)."""

    def test_repeatlist_wins_over_single_kv(self) -> None:
        params = [
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
            "--Tag", "team=core",  # ignored — RepeatList takes priority
        ]
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_repeatlist_wins_over_json(self) -> None:
        params = [
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
            "--Tags", '[{"key":"team","value":"core"}]',
        ]
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_single_kv_wins_over_json(self) -> None:
        params = [
            "--Tag", "env=prod",
            "--Tags", '[{"key":"team","value":"core"}]',
        ]
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])


class TestEdgeCases(unittest.TestCase):
    """Empty inputs, missing fields, defensive behaviour."""

    def test_empty_params(self) -> None:
        result = extract([])
        self.assertEqual(
            result,
            {
                "resource_group_id": None,
                "tags": [],
                "tags_raw": None,
                "missing_dimensions": True,
                "warning": _erd_module.MISSING_DIMENSIONS_WARNING,
                "suggestion": _erd_module.MISSING_DIMENSIONS_SUGGESTION,
            },
        )

    def test_only_resource_group_id(self) -> None:
        result = extract(["--ResourceGroupId", "rg-only"])
        self.assertEqual(result["resource_group_id"], "rg-only")
        self.assertEqual(result["tags"], [])
        self.assertIsNone(result["tags_raw"])

    def test_no_tags_no_rg(self) -> None:
        params = ["--RegionId", "cn-hangzhou", "--PageSize", "10"]
        result = extract(params)
        self.assertEqual(
            result,
            {
                "resource_group_id": None,
                "tags": [],
                "tags_raw": None,
                "missing_dimensions": True,
                "warning": _erd_module.MISSING_DIMENSIONS_WARNING,
                "suggestion": _erd_module.MISSING_DIMENSIONS_SUGGESTION,
            },
        )

    def test_repeatlist_partial_pair_dropped(self) -> None:
        """Tag.2 has Key but no Value → dropped."""
        params = [
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
            "--Tag.2.Key", "team",  # no value
        ]
        result = extract(params)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_does_not_match_dashdash_tag_prefix_collision(self) -> None:
        """Tokens like --TagMore are NOT interpreted as --Tag * value."""
        params = ["--TagMore", "value"]
        result = extract(params)
        # --TagMore is not --Tag, not --Tag.N.Key, not --Tags.
        self.assertEqual(result["tags"], [])

    def test_resource_group_id_flag_without_value(self) -> None:
        """--ResourceGroupId at end of list with no value → None."""
        result = extract(["--RegionId", "cn-hz", "--ResourceGroupId"])
        self.assertIsNone(result["resource_group_id"])


class TestExtractFromCommand(unittest.TestCase):
    """Convenience wrapper that handles full aliyun command strings."""

    def test_strips_aliyun_prefix(self) -> None:
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-x " \
              "--Tag.1.Key env --Tag.1.Value prod"
        result = extract_from_command(cmd)
        self.assertEqual(result["resource_group_id"], "rg-x")
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_empty_command(self) -> None:
        self.assertEqual(
            extract_from_command(""),
            {
                "resource_group_id": None,
                "tags": [],
                "tags_raw": None,
                "missing_dimensions": True,
                "warning": _erd_module.MISSING_DIMENSIONS_WARNING,
                "suggestion": _erd_module.MISSING_DIMENSIONS_SUGGESTION,
            },
        )

    def test_command_without_aliyun_prefix(self) -> None:
        """No 'aliyun' prefix → tokenize as-is."""
        cmd = "--Tag.1.Key env --Tag.1.Value prod"
        result = extract_from_command(cmd)
        self.assertEqual(result["tags"], [{"key": "env", "value": "prod"}])

    def test_command_with_unicode_in_tag_value(self) -> None:
        cmd = "aliyun ecs DescribeInstances --Tag.1.Key 业务线 --Tag.1.Value 核心"
        result = extract_from_command(cmd)
        self.assertEqual(
            result["tags"],
            [{"key": "业务线", "value": "核心"}],
        )


class TestMissingDimensions(unittest.TestCase):
    """missing_dimensions flag + warning/suggestion text."""

    def test_missing_when_neither_rg_nor_tags(self) -> None:
        result = extract(["--RegionId", "cn-hangzhou"])
        self.assertTrue(result["missing_dimensions"])
        self.assertIsNotNone(result["warning"])
        self.assertIsNotNone(result["suggestion"])

    def test_not_missing_when_only_rg(self) -> None:
        result = extract(["--ResourceGroupId", "rg-abc"])
        self.assertFalse(result["missing_dimensions"])
        self.assertIsNone(result["warning"])
        self.assertIsNone(result["suggestion"])

    def test_not_missing_when_only_tags(self) -> None:
        result = extract(["--Tag.1.Key", "env", "--Tag.1.Value", "prod"])
        self.assertFalse(result["missing_dimensions"])
        self.assertIsNone(result["warning"])
        self.assertIsNone(result["suggestion"])

    def test_not_missing_when_both(self) -> None:
        result = extract([
            "--ResourceGroupId", "rg-abc",
            "--Tag.1.Key", "env", "--Tag.1.Value", "prod",
        ])
        self.assertFalse(result["missing_dimensions"])
        self.assertIsNone(result["warning"])
        self.assertIsNone(result["suggestion"])

    def test_warning_text_mentions_no_default_filter(self) -> None:
        """Warning must reference the 'no default resource-group filtering'
        fact so consumers understand WHY missing dims is bad."""
        result = extract(["--RegionId", "cn-hangzhou"])
        self.assertIn("default resource-group filtering", result["warning"])
        self.assertIn("token bloat", result["warning"])

    def test_suggestion_actionable(self) -> None:
        """Suggestion must include a concrete remediation command flag."""
        result = extract(["--RegionId", "cn-hangzhou"])
        self.assertIn("--ResourceGroupId", result["suggestion"])
        self.assertIn("--Tag.1.Key", result["suggestion"])

    def test_command_strip_with_no_rg_or_tags(self) -> None:
        """extract_from_command: full aliyun command missing both dims."""
        result = extract_from_command(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        )
        self.assertTrue(result["missing_dimensions"])
        self.assertIn("default resource-group filtering", result["warning"])

    def test_command_strip_with_rg_present(self) -> None:
        result = extract_from_command(
            "aliyun ecs DescribeInstances --ResourceGroupId rg-x"
        )
        self.assertFalse(result["missing_dimensions"])
        self.assertIsNone(result["warning"])

    def test_parse_failure_does_not_set_warning(self) -> None:
        """When Tag parse fails (tags_raw set), RG present → no warning,
        because caller DID specify at least one dimension."""
        result = extract([
            "--ResourceGroupId", "rg-abc",
            "--Tag", "malformed-no-equals",
        ])
        self.assertFalse(result["missing_dimensions"])
        self.assertIsNotNone(result["tags_raw"])  # parse did fail
        self.assertIsNone(result["warning"])
        self.assertIsNone(result["suggestion"])


if __name__ == "__main__":
    unittest.main()
