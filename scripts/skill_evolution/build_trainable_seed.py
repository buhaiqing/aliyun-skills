#!/usr/bin/env python3
"""Extract trainable SKILL.md sections for Microsoft SkillOpt seed (Milestone A)."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SEED_HEADER = (
    "<!-- trainable_seed.md — Milestone A export for Microsoft SkillOpt; "
    "NOT a drop-in SKILL.md replacement -->\n\n"
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)

# Inclusive start, exclusive end (stop before Runtime Rules).
_START_HEADING = "overview"
_END_HEADING = "runtime rules"


def resolve_skills_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ALIYUN_SKILLS_ROOT") or os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1).lstrip("\n")


def _norm_heading(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def extract_trainable_body(skill_md: str) -> str:
    """Return Overview .. Product Skill Mission body (exclude Runtime Rules+)."""
    body = strip_frontmatter(skill_md)
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return body.strip()

    start_idx: int | None = None
    end_idx: int | None = None
    for i, m in enumerate(matches):
        heading = _norm_heading(m.group(1))
        if start_idx is None and heading.startswith(_START_HEADING):
            start_idx = m.start()
        if start_idx is not None and heading.startswith(_END_HEADING):
            end_idx = m.start()
            break

    if start_idx is None:
        # Fallback: from first ## to first Runtime Rules or EOF
        start_idx = matches[0].start()
        for m in matches:
            if _norm_heading(m.group(1)).startswith(_END_HEADING):
                end_idx = m.start()
                break

    chunk = body[start_idx : end_idx if end_idx is not None else len(body)]
    return chunk.strip()


def build_seed_text(skill_md: str) -> str:
    body = extract_trainable_body(skill_md)
    if not body:
        raise ValueError("no trainable sections found in SKILL.md")
    return SEED_HEADER + body + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build trainable_seed.md from product SKILL.md")
    p.add_argument("--skill", required=True, help="e.g. alicloud-ecs-ops")
    p.add_argument("--skills-root", default=None)
    p.add_argument("--skill-md", default=None, help="Override SKILL.md path")
    p.add_argument("--out", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    skills_root = resolve_skills_root(args.skills_root)
    skill_md_path = (
        Path(args.skill_md)
        if args.skill_md
        else skills_root / args.skill / "SKILL.md"
    )
    out = (
        Path(args.out)
        if args.out
        else skills_root / ".runtime" / "skill-evolution" / args.skill / "trainable_seed.md"
    )
    if not skill_md_path.is_file():
        print(f"[ERROR] SKILL.md not found: {skill_md_path}", file=sys.stderr)
        return 1
    seed = build_seed_text(skill_md_path.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(seed, encoding="utf-8")
    print(f"[SUMMARY] skill={args.skill} seed_bytes={len(seed.encode('utf-8'))} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
