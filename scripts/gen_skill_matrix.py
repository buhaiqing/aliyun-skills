#!/usr/bin/env python3
"""Generate / drift-check SKILL-MATRIX.md from skill frontmatter.

Motivation (SRE): SKILL-MATRIX.md is hand-maintained and drifts from the
real skill set. This script derives the *objectively verifiable* columns
from each skill's frontmatter + reference files, so CI can detect drift
instead of trusting a stale human-written table.

Objective columns (derived from files on disk):
  - name / product        from SKILL.md frontmatter
  - 生命周期 (lifecycle)   ✅ if SKILL.md exists (every -ops skill is CRUD-capable)
  - 监控告警 (monitoring) ✅ if references/monitoring.md exists
  - 诊断排障 (diagnostics) ✅ if references/troubleshooting.md exists

Subjective columns (not auto-derivable, left to humans):
  - 安全合规 (security)    marked "?" — must be filled in by a maintainer
  - 说明 (notes)           seeded from frontmatter description, editable

Usage:
  python3 scripts/gen_skill_matrix.py generate [--out SKILL-MATRIX.generated.md]
  python3 scripts/gen_skill_matrix.py check    [--matrix SKILL-MATRIX.md]
      exit 1 if the committed matrix disagrees with objective columns.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Skills that are meta/framework/governance/orchestration, not product -ops
# skills. Their capability matrix is hand-authored (subjective), so the
# objective-column drift check skips them.
META_SKILLS = {
    "alicloud-skill-generator",
    "alicloud-runtime-harness-ops",
    "alicloud-skillopt-ops",
    "alicloud-gcl-runner-ops",
    "alicloud-sandbox-dev",
    "alicloud-aiyun-skills",
    "alicloud-aiops-cruise",
    "alicloud-auto-scaling-orch",
    "alicloud-arch-advisor",
    "alicloud-advisor-ops",
    "alicloud-topo-discovery",
}


def _load_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter; fall back to naive parse if pyyaml missing."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    fm = text.split("---", 2)[1]
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(fm) or {}
    except Exception:
        data = {}
        m = re.search(r"^name:\s*(.+)$", fm, re.M)
        if m:
            data["name"] = m.group(1).strip()
        m = re.search(r"^description:\s*([>|][-+]\s*)?(.+)$", fm, re.M)
        if m:
            # Strip YAML block-scalar markers like ">-" / "|" from the value.
            data["description"] = m.group(2).strip()
    return data or {}


def _product_name(skill_dir: Path, fm: dict) -> str:
    """Infer a human product label from the description's first sentence.

    Prefers the parenthetical that follows an "Alibaba Cloud X" phrase, e.g.
    "... Alibaba Cloud ECS instances (Elastic Compute Service) — ..." →
    "Elastic Compute Service". Falls back to the first parenthetical, then to
    the directory stem uppercased.
    """
    desc = str(fm.get("description", "")).replace("\n", " ").strip()
    # Prefer the parenthetical attached to an "Alibaba Cloud <Product>" phrase.
    m = re.search(r"Alibaba Cloud\s+[A-Za-z0-9 ]+?\s*\(([^()]{1,40})\)", desc)
    if m:
        return m.group(1).strip()
    # Otherwise take the first parenthetical, ignoring YAML block markers.
    m = re.search(r"\(([^()]{1,40})\)", desc)
    if m:
        cand = m.group(1).strip()
        if cand not in (">-", "|", ">-", "|-"):
            return cand
    return skill_dir.name.replace("alicloud-", "").replace("-ops", "").upper()


def collect_rows() -> list[dict]:
    rows = []
    for skill in sorted(REPO_ROOT.glob("alicloud-*")):
        if not skill.is_dir() or not (skill / "SKILL.md").is_file():
            continue
        fm = _load_frontmatter(skill / "SKILL.md")
        refs = skill / "references"
        row = {
            "name": skill.name.replace("alicloud-", "").replace("-ops", ""),
            "dir": skill.name,
            "product": _product_name(skill, fm),
            "lifecycle": "✅",
            "monitoring": "✅" if (refs / "monitoring.md").is_file() else "—",
            "diagnostics": "✅" if (refs / "troubleshooting.md").is_file() else "—",
            "security": "?",  # subjective — human-owned
            "meta": skill.name in META_SKILLS,
            "notes": str(fm.get("description", "")).split("\n")[0][:60],
        }
        rows.append(row)
    return rows


def _render_product_table(rows: list[dict]) -> str:
    lines = [
        "## 产品技能 (auto-generated objective columns)",
        "",
        "| 技能 | 产品 | 生命周期 | 监控告警 | 诊断排障 | 安全合规 | 说明 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        if r["meta"]:
            continue
        lines.append(
            f"| `{r['name']}` | {r['product']} | {r['lifecycle']} | "
            f"{r['monitoring']} | {r['diagnostics']} | {r['security']} | {r['notes']} |"
        )
    return "\n".join(lines)


def cmd_generate(out: Path) -> int:
    rows = collect_rows()
    out.write_text(_render_product_table(rows) + "\n", encoding="utf-8")
    print(f"generated {len([r for r in rows if not r['meta']])} product-skill rows -> {out}")
    return 0


def cmd_check(matrix: Path) -> int:
    if not matrix.is_file():
        print(f"[FAIL] matrix not found: {matrix}")
        return 1
    rows = {r["name"]: r for r in collect_rows() if not r["meta"]}
    text = matrix.read_text(encoding="utf-8")
    conflicts: list[str] = []
    for name, r in rows.items():
        # Match the row for this skill in the committed matrix.
        m = re.search(
            rf"^\| `{re.escape(name)}` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|",
            text,
            re.M,
        )
        if not m:
            continue  # not all skills are in the hand-maintained matrix; skip
        committed_mon, committed_diag = m.group(3).strip(), m.group(4).strip()
        if committed_mon != r["monitoring"]:
            conflicts.append(
                f"{name}: monitoring mismatch generated={r['monitoring']} committed={committed_mon}"
            )
        if committed_diag != r["diagnostics"]:
            conflicts.append(
                f"{name}: diagnostics mismatch generated={r['diagnostics']} committed={committed_diag}"
            )
    if conflicts:
        print("[FAIL] SKILL-MATRIX.md drift detected:")
        print("\n".join(conflicts))
        return 1
    print(f"[OK] SKILL-MATRIX.md objective columns match {len(rows)} scanned skills")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "generate":
        out = Path(args[args.index("--out") + 1]) if "--out" in args else (
            REPO_ROOT / "SKILL-MATRIX.generated.md"
        )
        return cmd_generate(out)
    if args[0] == "check":
        matrix = Path(args[args.index("--matrix") + 1]) if "--matrix" in args else (
            REPO_ROOT / "SKILL-MATRIX.md"
        )
        return cmd_check(matrix)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
