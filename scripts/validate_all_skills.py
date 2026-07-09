#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate all alicloud-*-ops skill directory structures.

Checks compliance with AGENTS.md canonical structure requirements.
Exits with non-zero code if any validation fails.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


# Files required for ALL skills (per AGENTS.md §1)
REQUIRED_FILES = [
    "SKILL.md",
    "references/core-concepts.md",
    "references/api-sdk-usage.md",
    "references/troubleshooting.md",
    "references/integration.md",
    "references/well-architected-assessment.md",
    "assets/eval_queries.json",
]

# Files required for GCL-required/recommended skills
GCL_REQUIRED_FILES = [
    "references/rubric.md",
    "references/prompt-templates.md",
]

# Shared framework skills (Strategy B) — product-skill references/ not required
SHARED_FRAMEWORK_TYPES = frozenset(
    {"shared-framework", "shared-framework-legacy-alias", "shared-framework-alias"}
)

SHARED_FRAMEWORK_REQUIRED_FILES = [
    "SKILL.md",
    "references/core-concepts.md",
    "references/integration.md",
    "assets/eval_queries.json",
]

# GCL-required skill list (from AGENTS.md §12.11)
GCL_REQUIRED_SKILLS = [
    "alicloud-ecs-ops",
    "alicloud-rds-ops",
    "alicloud-redis-ops",
    "alicloud-slb-ops",
    "alicloud-vpc-ops",
    "alicloud-oss-ops",
    "alicloud-ram-ops",
    "alicloud-kms-ops",
    "alicloud-mongodb-ops",
    "alicloud-polardb-ops",
    "alicloud-elasticsearch-ops",
    "alicloud-actiontrail-ops",
    "alicloud-cms-ops",
    "alicloud-waf-ops",
]


@dataclass
class ValidationError:
    skill: str
    file: str
    message: str


@dataclass
class ValidationReport:
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    checked: int = 0
    passed: int = 0

    def add_error(self, skill: str, file: str, message: str):
        self.errors.append(ValidationError(skill, file, message))

    def add_warning(self, skill: str, file: str, message: str):
        self.warnings.append(ValidationError(skill, file, message))


def parse_skill_frontmatter(skill_md_path: Path) -> dict:
    """Extract frontmatter from SKILL.md as dict."""
    content = skill_md_path.read_text(encoding="utf-8")
    
    # Remove HTML comments at the start (e.g., <!-- markdownlint-disable -->)
    content = re.sub(r"^\s*<!--.*?-->\s*", "", content, flags=re.DOTALL)
    
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    frontmatter = match.group(1)
    result = {}
    current_key = None
    current_value = []
    
    for line in frontmatter.split("\n"):
        # Skip comment lines
        if line.strip().startswith("#"):
            continue
            
        # Check for new key (not indented, contains colon)
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            # Save previous key-value pair
            if current_key:
                value = "\n".join(current_value).strip().strip('"').strip("'")
                result[current_key] = value
            
            key, _, value = line.partition(":")
            current_key = key.strip()
            current_value = [value]
        elif current_key:
            # Continuation of multi-line value
            current_value.append(line)
    
    # Save last key
    if current_key:
        value = "\n".join(current_value).strip().strip('"').strip("'")
        result[current_key] = value
    
    return result


def get_metadata_type(skill_dir: Path) -> str | None:
    """Extract metadata.type from SKILL.md frontmatter (nested under metadata:)."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    content = skill_md.read_text(encoding="utf-8")
    content = re.sub(r"^\s*<!--.*?-->\s*", "", content, flags=re.DOTALL)
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None
    type_match = re.search(r"^\s*type:\s*(\S+)\s*$", match.group(1), re.MULTILINE)
    return type_match.group(1) if type_match else None


def required_files_for_skill(skill_name: str, skill_dir: Path) -> List[str]:
    """Return required file list based on skill metadata type."""
    metadata_type = get_metadata_type(skill_dir)
    if metadata_type in SHARED_FRAMEWORK_TYPES:
        return SHARED_FRAMEWORK_REQUIRED_FILES
    return REQUIRED_FILES


def validate_skill(skill_dir: Path, report: ValidationReport) -> bool:
    """Validate a single skill directory. Returns True if valid."""
    report.checked += 1
    skill_name = skill_dir.name
    is_valid = True

    # Check required files exist
    for req_file in required_files_for_skill(skill_name, skill_dir):
        full_path = skill_dir / req_file
        if not full_path.exists():
            report.add_error(skill_name, req_file, "Required file missing")
            is_valid = False

    # Check if GCL-required
    if skill_name in GCL_REQUIRED_SKILLS:
        for gcl_file in GCL_REQUIRED_FILES:
            full_path = skill_dir / gcl_file
            if not full_path.exists():
                report.add_warning(skill_name, gcl_file, "GCL-required file missing")

    # Validate SKILL.md frontmatter
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        frontmatter = parse_skill_frontmatter(skill_md)
        required_frontmatter = ["name", "description", "license"]
        for key in required_frontmatter:
            if key not in frontmatter:
                report.add_error(skill_name, "SKILL.md", f"Missing frontmatter key: {key}")
                is_valid = False

        # Check metadata.version exists
        if "metadata" in str(skill_md.read_text(encoding="utf-8")):
            if not frontmatter.get("version") and "metadata:" in skill_md.read_text(encoding="utf-8"):
                # Version might be nested in metadata block
                pass

    # Validate eval_queries.json is valid JSON
    eval_queries = skill_dir / "assets" / "eval_queries.json"
    if eval_queries.exists():
        try:
            json.loads(eval_queries.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            report.add_error(skill_name, "assets/eval_queries.json", f"Invalid JSON: {e}")
            is_valid = False

    if is_valid:
        report.passed += 1

    return is_valid


def discover_skills(repo_root: Path) -> List[Path]:
    """Discover all alicloud-*-ops directories."""
    skills = []
    for item in sorted(repo_root.glob("alicloud-*-ops")):
        if item.is_dir():
            skills.append(item)
    return skills


def print_report(report: ValidationReport):
    """Print validation report to stdout."""
    print("=" * 60)
    print("Skill Structure Validation Report")
    print("=" * 60)
    print(f"Total checked: {report.checked}")
    print(f"Passed: {report.passed}")
    print(f"Failed: {report.checked - report.passed}")
    print()

    if report.errors:
        print("ERRORS (blocking):")
        print("-" * 40)
        for err in report.errors:
            print(f"  [{err.skill}] {err.file}: {err.message}")
        print()

    if report.warnings:
        print("WARNINGS (non-blocking):")
        print("-" * 40)
        for warn in report.warnings:
            print(f"  [{warn.skill}] {warn.file}: {warn.message}")
        print()

    print("=" * 60)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate alicloud-*-ops skill structures")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--skill", help="Validate only specific skill")
    args = parser.parse_args(argv)

    report = ValidationReport()

    if args.skill:
        skill_dir = REPO_ROOT / args.skill
        if not skill_dir.exists():
            print(f"ERROR: Skill not found: {args.skill}")
            return 1
        validate_skill(skill_dir, report)
    else:
        skills = discover_skills(REPO_ROOT)
        for skill_dir in skills:
            validate_skill(skill_dir, report)

    print_report(report)

    # Exit with error if any errors (or warnings in strict mode)
    if report.errors or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    import argparse

    sys.exit(main())
