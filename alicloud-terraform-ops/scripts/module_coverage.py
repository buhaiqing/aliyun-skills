#!/usr/bin/env python3
"""Module coverage manifest — NL2HCL gap detection + developer verification.

Manifest: assets/module-coverage.json (single source of truth).
Full spec: references/module-coverage.md
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
MANIFEST_PATH = SKILL_DIR / "assets" / "module-coverage.json"
MODULES_ROOT = SKILL_DIR / "modules"


@dataclass
class CoverageGap:
    tf_type: str
    reason: str
    detected_by: str  # intent | keyword
    remediation: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    intent_resources: list[str]
    keyword_hits: list[str]
    gaps: list[CoverageGap] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def must_halt(self) -> bool:
        return bool(self.gaps)


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or MANIFEST_PATH
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "resources" not in data:
        raise ValueError(f"invalid manifest: {manifest_path}")
    return data


def manifest_resources(manifest: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    manifest = manifest or load_manifest()
    return manifest["resources"]


def _compile_keyword_patterns(
    resources: dict[str, dict[str, Any]],
) -> list[tuple[re.Pattern[str], str]]:
    patterns: list[tuple[re.Pattern[str], str]] = []
    for tf_type, meta in resources.items():
        for kw in meta.get("keywords", []):
            if not kw:
                continue
            patterns.append((re.compile(kw, re.IGNORECASE), tf_type))
    return patterns


def detect_keyword_resources(
    request: str,
    manifest: dict[str, Any] | None = None,
) -> set[str]:
    """Scan raw request for product keywords not caught by parse_intent."""
    resources = manifest_resources(manifest)
    patterns = _compile_keyword_patterns(resources)
    hits: set[str] = set()
    for pattern, tf_type in patterns:
        if pattern.search(request):
            hits.add(tf_type)
    return hits


def _remediation_for(tf_type: str, meta: dict[str, Any]) -> list[str]:
    registry_name = meta.get("registry_name")
    lines = [
        f"资源 {tf_type} 尚无 NL2HCL module 模板（modules/ 缺失或未编排）。",
    ]
    if meta.get("import_supported") and registry_name:
        lines.append(
            f"已有实例 → terraform_ops import -t {registry_name} -i <id> -e dev"
        )
    lines.extend([
        "新建实例（NL2HCL）→ 按 AGENTS.md §4 添加 module 四件套后再 create",
        "详情 → references/module-coverage.md",
    ])
    return lines


def check_nl2hcl_coverage(
    intent: dict[str, Any],
    request: str,
    manifest: dict[str, Any] | None = None,
) -> CoverageReport:
    """Detect silent omissions and NL2HCL module gaps."""
    resources = manifest_resources(manifest)
    intent_types = list(intent.get("resources") or [])
    keyword_hits = sorted(detect_keyword_resources(request, manifest))
    report = CoverageReport(
        intent_resources=intent_types,
        keyword_hits=keyword_hits,
    )

    # Keyword mentioned but parse_intent missed → silent omission
    intent_set = set(intent_types)
    for tf_type in keyword_hits:
        if tf_type not in intent_set:
            meta = resources.get(tf_type, {})
            report.gaps.append(
                CoverageGap(
                    tf_type=tf_type,
                    reason="用户请求含该产品关键词，但 NL2HCL 意图解析未识别",
                    detected_by="keyword",
                    remediation=_remediation_for(tf_type, meta),
                )
            )

    # Intent includes type without NL2HCL module
    for tf_type in intent_types:
        meta = resources.get(tf_type)
        if meta is None:
            report.warnings.append(
                f"{tf_type} 未在 module-coverage.json 登记 — 请更新 manifest"
            )
            continue
        if meta.get("nl2hcl_module"):
            continue
        report.gaps.append(
            CoverageGap(
                tf_type=tf_type,
                reason="已识别资源类型，但无 NL2HCL module 模板",
                detected_by="intent",
                remediation=_remediation_for(tf_type, meta),
            )
        )

    return report


def format_coverage_halt(report: CoverageReport) -> str:
    lines = [
        "⛔ NL2HCL Module Coverage Gate — 已中止（防止静默遗漏）",
        "",
    ]
    for gap in report.gaps:
        lines.append(f"  • [{gap.detected_by}] {gap.tf_type}: {gap.reason}")
        for step in gap.remediation:
            lines.append(f"      → {step}")
        lines.append("")
    if report.warnings:
        lines.append("警告:")
        for w in report.warnings:
            lines.append(f"  ⚠ {w}")
    return "\n".join(lines)


def verify_manifest(manifest: dict[str, Any] | None = None) -> list[str]:
    """Developer gate: manifest ↔ modules/ ↔ resource_registry ↔ NL2HCL patterns."""
    errors: list[str] = []
    manifest = manifest or load_manifest()
    resources = manifest_resources(manifest)

    # 1) nl2hcl_module must exist on disk
    for tf_type, meta in resources.items():
        mod = meta.get("nl2hcl_module")
        if not mod:
            continue
        mod_dir = MODULES_ROOT / mod
        if not (mod_dir / "main.tf").is_file():
            errors.append(f"{tf_type}: nl2hcl_module '{mod}' missing {mod_dir}/main.tf")

    # 2) registry sync
    try:
        from resource_registry import get_registry

        registry = get_registry()
        for tf_type, meta in resources.items():
            rname = meta.get("registry_name")
            if not rname:
                continue
            info = registry.get(rname)
            if info is None:
                errors.append(f"{tf_type}: registry_name '{rname}' not in resource_registry")
            else:
                expected_tf = meta.get("registry_tf_type") or tf_type
                if info.tf_type != expected_tf:
                    errors.append(
                        f"{tf_type}: registry tf_type mismatch "
                        f"(expected {expected_tf}, got {info.tf_type})"
                    )
    except ImportError:
        errors.append("resource_registry not importable — skip registry sync")

    # 3) NL2HCL RESOURCE_PATTERNS values should have nl2hcl_module in manifest
    try:
        from nl2hcl_generator import NL2HCLGenerator

        pattern_types = set(NL2HCLGenerator.RESOURCE_PATTERNS.values())
        for tf_type in sorted(pattern_types):
            meta = resources.get(tf_type)
            if meta is None:
                errors.append(f"NL2HCL pattern maps to {tf_type} but manifest has no entry")
            elif not meta.get("nl2hcl_module"):
                errors.append(
                    f"NL2HCL pattern maps to {tf_type} but nl2hcl_module is null"
                )
    except ImportError:
        errors.append("nl2hcl_generator not importable — skip pattern sync")

    # 4) Each modules/ subdir (except README) should appear as nl2hcl_module somewhere
    declared_modules = {
        meta["nl2hcl_module"]
        for meta in resources.values()
        if meta.get("nl2hcl_module")
    }
    declared_modules.add("web-stack")
    for child in MODULES_ROOT.iterdir():
        if not child.is_dir():
            continue
        if child.name not in declared_modules:
            errors.append(
                f"modules/{child.name}/ exists but not referenced in module-coverage.json"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Module coverage verification")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Validate manifest ↔ modules ↔ registry ↔ NL2HCL patterns",
    )
    parser.add_argument(
        "--check-request",
        metavar="TEXT",
        help="Dry-run coverage gate for a natural language request",
    )
    args = parser.parse_args(argv)

    if args.verify:
        errors = verify_manifest()
        if errors:
            print("Module coverage verification FAILED:", file=sys.stderr)
            for err in errors:
                print(f"  ✗ {err}", file=sys.stderr)
            return 1
        print("Module coverage verification OK")
        return 0

    if args.check_request:
        from nl2hcl_generator import NL2HCLGenerator

        gen = NL2HCLGenerator()
        intent = gen.parse_intent(args.check_request)
        report = check_nl2hcl_coverage(intent, args.check_request)
        if report.must_halt:
            print(format_coverage_halt(report), file=sys.stderr)
            return 6
        print("Coverage OK")
        print(f"  intent: {report.intent_resources}")
        print(f"  keywords: {report.keyword_hits}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
