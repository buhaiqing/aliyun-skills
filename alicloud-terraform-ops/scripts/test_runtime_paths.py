#!/usr/bin/env python3
"""Tests for runtime_paths.py — .runtime/terraform-ops/ layout."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(SCRIPT_DIR))

import runtime_paths as rp


class RuntimePathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self._tmpdir.name).resolve()
        self._old_skills = os.environ.get("SKILLS_DIR")
        os.environ["SKILLS_DIR"] = str(self.skills_dir)

    def tearDown(self) -> None:
        if self._old_skills is None:
            os.environ.pop("SKILLS_DIR", None)
        else:
            os.environ["SKILLS_DIR"] = self._old_skills
        self._tmpdir.cleanup()

    def test_skill_runtime_root(self) -> None:
        root = rp.get_skill_runtime_root()
        self.assertEqual(root.resolve(), (self.skills_dir / ".runtime" / "terraform-ops").resolve())

    def test_nl2hcl_output_dir(self) -> None:
        path = rp.nl2hcl_output_dir("dev")
        self.assertEqual(path.resolve(), (self.skills_dir / ".runtime" / "terraform-ops" / "nl2hcl" / "dev").resolve())

    def test_import_output_dir_uses_batch(self) -> None:
        path = rp.import_output_dir("vpc")
        self.assertEqual(path.resolve(), (self.skills_dir / ".runtime" / "terraform-ops" / "import" / "vpc").resolve())

    def test_env_runtime_dir(self) -> None:
        path = rp.env_runtime_dir("staging")
        self.assertEqual(
            path.resolve(),
            (self.skills_dir / ".runtime" / "terraform-ops" / "environments" / "staging").resolve(),
        )

    def test_audit_dir(self) -> None:
        path = rp.audit_dir()
        self.assertEqual(path.resolve(), (self.skills_dir / ".runtime" / "audit" / "terraform-ops").resolve())

    def test_resolve_output_dir_explicit(self) -> None:
        explicit = self.skills_dir / "custom"
        resolved = rp.resolve_output_dir(explicit, kind="nl2hcl", environment="dev")
        self.assertEqual(resolved, explicit.resolve())

    def test_legacy_runtime_dirs_includes_skill_generated(self) -> None:
        legacy = rp.legacy_runtime_dirs()
        self.assertIn(rp.SKILL_DIR / "generated", legacy)
        self.assertIn(rp.SKILL_DIR / "output", legacy)


if __name__ == "__main__":
    unittest.main()
