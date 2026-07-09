#!/usr/bin/env python3
"""SkillOpt train CI smoke — requires skillopt pip package."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_EVOLUTION = Path(__file__).resolve().parent


class TrainSmokeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("skillopt"), "skillopt not installed")
    def test_train_ci_produces_best_skill_md(self) -> None:
        sys.path.insert(0, str(_EVOLUTION))
        from train_ci import run_train_smoke

        path = run_train_smoke()
        self.assertTrue(path.is_file())
        self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 10)


if __name__ == "__main__":
    unittest.main()
