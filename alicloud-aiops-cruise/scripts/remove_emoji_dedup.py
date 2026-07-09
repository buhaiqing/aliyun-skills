#!/usr/bin/env python3
"""
P0-1 二阶段: 清理 emoji 替换后产生的"标识词重复"问题

典型病灶:
  - "WARNING Warning" -> "Warning"
  - "CRITICAL Critical" -> "Critical"
  - "PASS 完成" -> "完成" (PASS 已是状态词, 与"完成"重复)

规则: 标识词 (大写状态词) + 空格 + 同义小写词 -> 只保留小写词
"""

import re
from pathlib import Path

# 标识词 + 空格 + 同义小写词/中文
DEDUP_RULES = [
    # 英文重复
    (re.compile(r"\bWARNING\s+Warning\b"), "Warning"),
    (re.compile(r"\bCRITICAL\s+Critical\b"), "Critical"),
    (re.compile(r"\bSAFE\s+Safe\b"), "Safe"),
    (re.compile(r"\bPASS\s+Pass\b"), "Pass"),
    (re.compile(r"\bFAIL\s+Fail\b"), "Fail"),
    (re.compile(r"\bINFO\s+Info\b"), "Info"),
    # 中文重复 (PASS/FAIL 与"完成"/"失败"语义重叠)
    (re.compile(r"\bPASS\s+完成\b"), "完成"),
    (re.compile(r"\bPASS\s+\*\*完成\*\*\b"), "**完成**"),
    (re.compile(r"\bFAIL\s+失败\b"), "失败"),
    (re.compile(r"\bWIP\s+进行中\b"), "进行中"),
    (re.compile(r"\bWIP\s+调研\b"), "调研"),
    (re.compile(r"\bWIP\s+调研阶段\b"), "调研阶段"),
    (re.compile(r"\bWIP\s+实施阶段\b"), "实施阶段"),
    (re.compile(r"\bWIP\s+未开始\b"), "未开始"),
    # "PASS Normal" 是有意组合 (PASS=状态, Normal=档位), 去 PASS 留 Normal
    (re.compile(r"\bPASS\s+Normal\b"), "Normal"),
    # 表格列里: "状态" 列直接放 PASS, 没必要再加"完成"
    (re.compile(r"\bPASS\s+完成\b"), "完成"),
    (re.compile(r"\bPASS\s+已完成\b"), "已完成"),
    (re.compile(r"\bPASS\s+\*\*完成\*\*\b"), "**完成**"),
    (re.compile(r"\bFAIL\s+\*\*完成\*\*\b"), "**未完成**"),
]


def dedup_text(text: str) -> tuple[str, int]:
    total = 0
    for pat, repl in DEDUP_RULES:
        text, n = pat.subn(repl, text)
        total += n
    return text, total


def main() -> int:
    import sys
    apply = "--apply" in sys.argv
    root = Path(".").resolve()

    total_files = 0
    total_hits = 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in {".md", ".py", ".sh", ".go"}:
            continue
        if any(part in {".git", "__pycache__", ".runtime"} for part in p.relative_to(root).parts):
            continue
        # 跳过 dedup 脚本自身 (避免规则字符串被修改)
        if p.name in {"remove_emoji.py", "remove_emoji_dedup.py"}:
            continue
        try:
            orig = p.read_text(encoding="utf-8")
        except Exception:
            continue
        new, hits = dedup_text(orig)
        if hits:
            total_files += 1
            total_hits += hits
            print(f"[{hits:3d}] {p.relative_to(root)}")
            if apply:
                p.write_text(new, encoding="utf-8")

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n=== {mode} | {total_files} files | {total_hits} dedup replacements ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
