#!/usr/bin/env python3
"""
gcl_memory_e2e_test.py — E2E-M1: Layer 1 → Layer 2 → report full data flow.

Quality gate E2E-M1 (docs/gcl-spec.md §16.7):
  memory_store() → reflexion_extract() → reflexion_store() → reflexion_report()
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

from gcl_memory import memory_retrieve, memory_store  # noqa: E402
from gcl_reflexion import (  # noqa: E402
    reflexion_extract,
    reflexion_report,
    reflexion_retrieve,
    reflexion_store,
)
from memory_preflight import preflight_retrieve  # noqa: E402


def _sample_trace(skill: str = "alicloud-ecs-ops", op: str = "DeleteInstance") -> dict:
    return {
        "skill": skill,
        "operation": op,
        "rubric_version": "v1",
        "final": {"status": "SAFETY_FAIL", "iter": 1},
        "iterations": [
            {
                "iter": 1,
                "generator": {
                    "command": f"aliyun ecs {op} --InstanceId.1 i-test",
                    "exit_code": 1,
                    "duration_ms": 120,
                    "execution_path": "cli",
                },
                "critic": {
                    "scores": {
                        "correctness": 0.0,
                        "safety": 0.0,
                        "idempotency": 1.0,
                        "traceability": 1.0,
                        "spec_compliance": 1.0,
                    },
                    "suggestions": ["MissingParam: InstanceId format invalid"],
                },
            }
        ],
        "failure_pattern": {
            "category": "cli_parameter",
            "skill": skill,
            "command": f"aliyun ecs {op} --InstanceId i-test",
            "error": "MissingParam: InstanceId format invalid",
            "root_cause": "safety=0 during DeleteInstance",
            "fix": "Use --InstanceId.1 suffix for RepeatList params",
        },
    }


class E2EM1MemoryReflexionTests(unittest.TestCase):
    """E2E-M1: full Layer 1 → Layer 2 → report pipeline."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.memory_root = self.root / "memory"
        self.reflexion_root = self.root / "reflexion"
        self.report_path = self.root / "failure-patterns.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_e2e_m1_store_reflexion_report_retrieve(self) -> None:
        trace = _sample_trace()
        trace_path = self.root / "trace.json"
        trace_path.write_text(json.dumps(trace), encoding="utf-8")

        # Layer 1
        rc = memory_store(trace, trace_path=trace_path, memory_root=self.memory_root)
        self.assertEqual(rc, 0)
        recent = memory_retrieve(
            "alicloud-ecs-ops",
            operation="DeleteInstance",
            top_k=3,
            memory_root=self.memory_root,
        )
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["gcl_status"], "SAFETY_FAIL")

        # Layer 2
        pattern = reflexion_extract(trace)
        self.assertIsNotNone(pattern)
        assert pattern is not None
        self.assertEqual(pattern["category"], "cli_parameter")
        rc = reflexion_store(pattern, root=self.reflexion_root)
        self.assertEqual(rc, 0)

        traps = reflexion_retrieve(
            "alicloud-ecs-ops",
            operation="DeleteInstance",
            top_k=5,
            root=self.reflexion_root,
        )
        self.assertEqual(len(traps), 1)
        self.assertGreaterEqual(traps[0].get("count", 0), 1)

        # Report
        rc = reflexion_report(
            root=self.reflexion_root,
            output_path=self.report_path,
        )
        self.assertEqual(rc, 0)
        report_text = self.report_path.read_text(encoding="utf-8")
        self.assertIn("CLI Parameter Errors", report_text)
        self.assertIn("MissingParam", report_text)

    def test_e2e_m1_preflight_retrieve_unified(self) -> None:
        trace = _sample_trace()
        memory_store(trace, memory_root=self.memory_root)
        pattern = reflexion_extract(trace)
        # Store 3 times to reach MIN_PATTERN_COUNT threshold (3)
        reflexion_store(pattern, root=self.reflexion_root)
        reflexion_store(pattern, root=self.reflexion_root)
        reflexion_store(pattern, root=self.reflexion_root)

        baseline = self.root / "strategy-baseline.json"
        baseline.write_text(
            json.dumps(
                {
                    "skill_trends": {
                        "alicloud-ecs-ops": {
                            "failure_rate": 0.2,
                            "risk_score": 0.35,
                            "confidence": "low",
                        }
                    },
                    "actionable_items": [],
                }
            ),
            encoding="utf-8",
        )

        result = preflight_retrieve(
            skill="alicloud-ecs-ops",
            operation="DeleteInstance",
            skills_root=self.root,
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
            baseline_path=baseline,
        )
        self.assertFalse(result["empty"])
        self.assertIn("known_traps", result["slots"])
        self.assertIn("success_patterns", result["slots"])
        self.assertIn("recent_executions", result["slots"])
        self.assertIn("strategy_hints", result["slots"])
        self.assertIn("MissingParam", result["slots"]["known_traps"])

    def test_e2e_m1_generator_prompt_with_memory(self) -> None:
        """P0 Local path: preflight slots fill ecs Generator template on trace."""
        repo_root = _SCRIPT_DIR.parent.parent
        ecs_template = repo_root / "alicloud-ecs-ops" / "references" / "prompt-templates.md"
        if not ecs_template.is_file():
            self.skipTest("alicloud-ecs-ops prompt-templates.md not present")

        trace = _sample_trace()
        memory_store(trace, memory_root=self.memory_root)
        pattern = reflexion_extract(trace)
        # Store 3 times to reach MIN_PATTERN_COUNT threshold (3)
        reflexion_store(pattern, root=self.reflexion_root)
        reflexion_store(pattern, root=self.reflexion_root)
        reflexion_store(pattern, root=self.reflexion_root)

        preflight = preflight_retrieve(
            skill="alicloud-ecs-ops",
            operation="DeleteInstance",
            skills_root=repo_root,
            memory_root=self.memory_root,
            reflexion_root=self.reflexion_root,
        )
        out_trace: dict = {}
        import gcl_runner  # noqa: E402

        gcl_runner.attach_memory_preflight_to_trace(
            out_trace,
            preflight,
            repo_root,
            "alicloud-ecs-ops",
        )
        self.assertIn("generator_prompt_with_memory", out_trace)
        filled = out_trace["generator_prompt_with_memory"]
        self.assertNotIn("{{known_traps}}", filled)
        self.assertIn("MissingParam", filled)


if __name__ == "__main__":
    unittest.main()
