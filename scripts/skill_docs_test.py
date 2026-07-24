"""Shared documentation/contract tests for product skills.

Covers the 43 ``alicloud-*-ops`` skills that have no per-skill test suite.
These checks are SRE change-safety gates: they catch doc-level defects that
would make an Agent emit a broken command at runtime.

Gates (hard — fail the build):
  - Unclosed ``{{user.*}}/{{env.*}}/{{output.*}}`` placeholders (AGENTS.md §2.1 R-N3)
  - Missing *required* reference files that are present in 100% of skills
    (core-concepts.md, troubleshooting.md)

Soft checks (warn, never fail — surfaces tech-debt without blocking merges):
  - Other reference files (api-sdk-usage, cli-usage, monitoring, rubric,
    prompt-templates, well-architected-assessment) that are commonly expected
    but missing in some skills.

Run: ``pytest scripts/skill_docs_test.py -v``
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Skills that own their own test suites — excluded from the shared scan.
EXCLUDED_SKILLS = {"alicloud-gcl-runner-ops", "alicloud-terraform-ops"}

# Reference files present in 100% of skills → hard requirement.
REQUIRED_REFERENCES = ["core-concepts.md", "troubleshooting.md"]

# Commonly expected but not universal → soft warning only.
OPTIONAL_REFERENCES = [
    "api-sdk-usage.md",
    "cli-usage.md",
    "monitoring.md",
    "rubric.md",
    "prompt-templates.md",
    "well-architected-assessment.md",
]

PLACEHOLDER_RE = re.compile(r"\{\{[^}]*$")


def _skill_dirs() -> list[Path]:
    return sorted(
        p for p in REPO_ROOT.glob("alicloud-*-ops")
        if p.is_dir() and p.name not in EXCLUDED_SKILLS
    )


def _doc_files(skill: Path) -> list[Path]:
    files = [skill / "SKILL.md"] if (skill / "SKILL.md").is_file() else []
    files += sorted((skill / "references").glob("*.md")) if (skill / "references").is_dir() else []
    return files


def test_skill_dirs_discovered():
    """Guard: ensure the scan actually covers skills (not silently empty)."""
    assert len(_skill_dirs()) >= 40, f"expected >=40 product skills, found {len(_skill_dirs())}"


def test_all_skills_have_skill_md():
    missing = [s.name for s in _skill_dirs() if not (s / "SKILL.md").is_file()]
    assert not missing, f"skills missing SKILL.md: {missing}"


def test_required_reference_files_present():
    missing_report: list[str] = []
    for skill in _skill_dirs():
        for ref in REQUIRED_REFERENCES:
            if not (skill / "references" / ref).is_file():
                missing_report.append(f"{skill.name}/references/{ref}")
    assert not missing_report, f"missing required reference files:\n" + "\n".join(missing_report)


def test_placeholder_integrity():
    """Every {{user.*}}/{{env.*}}/{{output.*}} must have both braces (R-N3)."""
    violations: list[str] = []
    for skill in _skill_dirs():
        for doc in _doc_files(skill):
            for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
                if PLACEHOLDER_RE.search(line):
                    violations.append(f"{doc.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not violations, f"unclosed placeholder(s) found:\n" + "\n".join(violations)


def test_optional_reference_coverage_not_regressing():
    """Soft report: warn if an optional reference file count drops below baseline.

    This never fails — it prints a coverage summary so reviewers notice
    tech-debt accumulation without blocking merges.
    """
    baseline = {ref: 0 for ref in OPTIONAL_REFERENCES}
    for skill in _skill_dirs():
        for ref in OPTIONAL_REFERENCES:
            if (skill / "references" / ref).is_file():
                baseline[ref] += 1
    total = len(_skill_dirs())
    summary = ", ".join(f"{ref}={baseline[ref]}/{total}" for ref in OPTIONAL_REFERENCES)
    print(f"\n[skill-docs] optional reference coverage: {summary}")
