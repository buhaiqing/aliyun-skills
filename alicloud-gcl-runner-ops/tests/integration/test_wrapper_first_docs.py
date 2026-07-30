#!/usr/bin/env python3
"""Contract test: every product skill MUST declare both the canonical
harness-wrapper AND the legacy skillopt-wrapper in its SKILL.md,
per AGENTS.md §15.8 (Wrapper-First Execution Rule) and the
``scripts/validate-wrapper-first-docs.sh`` gate.

Earlier session fixed 5 skills (redis + terraform/voice/vpc/waf). This
test now covers all 44 product skills so any future SKILL.md that drops
the legacy-shim literal will fail CI.

Wrapper slugs are taken from the actual `*-harness-wrapper.sh` filenames
in each skill's `scripts/` dir, or from a hard-coded table when the
canonical name differs from the product name (e.g. `dyvmsapi` for voice,
`dysmsapi` for sms).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]

# (skill_dir, wrapper_slug) for every product skill.
# Slug MUST match the basename prefix of the canonical *-harness-wrapper.sh
# shipped in scripts/.
TARGET_SKILLS = [
    # Already-passing (baseline: redis-ops)
    ("alicloud-redis-ops",       "redis"),
    # Earlier batch (terraform/voice/vpc/waf) — these 4 use their
    # canonical product-name wrapper slugs.
    ("alicloud-terraform-ops",   "terraform"),
    ("alicloud-voice-ops",       "dyvmsapi"),
    ("alicloud-vpc-ops",         "vpc"),
    ("alicloud-waf-ops",         "waf"),
    # This batch (the remaining 39 product skills)
    ("alicloud-ack-ops",              "ack"),
    ("alicloud-actiontrail-ops",      "actiontrail"),
    ("alicloud-advisor-ops",          "advisor"),
    ("alicloud-agentrun-ops",         "agentrun"),
    ("alicloud-alb-ops",              "alb"),
    ("alicloud-ask-ops",              "ask"),
    ("alicloud-bailian-ops",          "bailian"),
    ("alicloud-billing-ops",          "billing"),
    ("alicloud-cen-ops",              "cen"),
    ("alicloud-cert-ops",             "cert"),
    ("alicloud-clickhouse-ops",       "clickhouse"),
    ("alicloud-cms-ops",              "cms"),
    ("alicloud-das-ops",              "das"),
    ("alicloud-dms-ops",              "dms"),
    ("alicloud-dns-ops",              "dns"),
    ("alicloud-dts-ops",              "dts"),
    ("alicloud-eci-ops",              "eci"),
    ("alicloud-ecs-ops",              "ecs"),
    ("alicloud-eip-ops",              "vpc"),  # eip reuses vpc-* wrapper (VPC product API)
    ("alicloud-elasticsearch-ops",    "elasticsearch"),
    ("alicloud-ess-ops",              "ess"),
    ("alicloud-fc-ops",               "fc"),
    ("alicloud-gcl-runner-ops",       "gcl-runner"),
    ("alicloud-kms-ops",              "kms"),
    ("alicloud-mongodb-ops",          "mongodb"),
    ("alicloud-nas-ops",              "nas"),
    ("alicloud-nat-ops",              "vpc"),  # nat ships vpc-* wrapper (cross-product reuse)
    ("alicloud-oss-ops",              "oss"),
    ("alicloud-polar-mysql-ops",      "polardb-mysql"),
    ("alicloud-polar-oracle-ops",     "polardb-oracle"),
    ("alicloud-polar-postgresql-ops", "polardb-postgresql"),
    ("alicloud-pts-ops",              "pts"),
    ("alicloud-ram-ops",              "ram"),
    ("alicloud-rds-ops",              "rds"),
    ("alicloud-resourcemanager-ops",  "resourcemanager"),
    ("alicloud-sas-ops",              "sas"),
    ("alicloud-slb-ops",              "slb"),
    ("alicloud-sls-ops",              "sls"),
    ("alicloud-sms-ops",              "dysmsapi"),  # sms uses dysmsapi CLI
]


class TestWrapperFirstDocs(unittest.TestCase):
    """Per-skill contract: SKILL.md must mention BOTH harness-wrapper and
    skillopt-wrapper so the agent knows the preferred entrypoint and
    that the legacy shim still works."""

    def _assert_skill_passes(self, skill_dir: str, product_slug: str) -> None:
        skill_md = _REPO / skill_dir / "SKILL.md"
        self.assertTrue(skill_md.is_file(), f"SKILL.md not found: {skill_md}")
        text = skill_md.read_text(encoding="utf-8")

        # Sanity: the skill should document its own harness wrapper
        # (e.g. terraform-harness-wrapper.sh). This protects against the
        # scenario where someone "fixes" the gate by removing all wrapper
        # references.
        expected_harness = f"{product_slug}-harness-wrapper"
        self.assertRegex(
            text, re.escape(expected_harness),
            f"{skill_dir}/SKILL.md must reference its own harness wrapper "
            f"({expected_harness}); found none.",
        )

        # The gate's exact contract: SKILL.md must contain the literal
        # "harness-wrapper" AND the literal "skillopt-wrapper".
        self.assertIn(
            "harness-wrapper", text,
            f"{skill_dir}/SKILL.md must contain 'harness-wrapper' literal "
            f"(per scripts/validate-wrapper-first-docs.sh contract).",
        )
        self.assertIn(
            "skillopt-wrapper", text,
            f"{skill_dir}/SKILL.md must contain 'skillopt-wrapper' literal "
            f"so the agent knows the legacy shim is still supported.",
        )


def _make_test(skill_dir: str, product_slug: str):
    def test(self):
        self._assert_skill_passes(skill_dir, product_slug)
    test.__name__ = f"test_{skill_dir.replace('-', '_')}_declares_both_wrappers"
    return test


# Dynamically attach one test per target skill so pytest -v shows each
# by name and a single failure points at the right skill.
for _sd, _slug in TARGET_SKILLS:
    _t = _make_test(_sd, _slug)
    setattr(TestWrapperFirstDocs, _t.__name__, _t)


if __name__ == "__main__":
    unittest.main()
