#!/usr/bin/env python3
"""Tests for build_trainable_seed.py."""

from __future__ import annotations

import unittest
from pathlib import Path

from build_trainable_seed import build_seed_text, extract_trainable_body, strip_frontmatter

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class BuildTrainableSeedTests(unittest.TestCase):
    def test_strip_frontmatter(self) -> None:
        text = FIXTURES.joinpath("skill_md_header.md").read_text(encoding="utf-8")
        self.assertFalse(strip_frontmatter(text).startswith("---"))

    def test_extract_excludes_runtime_rules(self) -> None:
        text = FIXTURES.joinpath("skill_md_header.md").read_text(encoding="utf-8")
        body = extract_trainable_body(text)
        self.assertIn("## Overview", body)
        self.assertIn("Product Skill Mission", body)
        self.assertNotIn("Runtime Rules", body)

    def test_build_seed_has_header_comment(self) -> None:
        text = FIXTURES.joinpath("skill_md_header.md").read_text(encoding="utf-8")
        seed = build_seed_text(text)
        self.assertTrue(seed.startswith("<!-- trainable_seed.md"))


if __name__ == "__main__":
    unittest.main()
