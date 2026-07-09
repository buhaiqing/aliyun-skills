#!/usr/bin/env python3
"""
P0-1: 批量替换 emoji 为纯文本标识 (MR-8 合规)

策略:
  - 标题行 (#/##/### 开头): 整段移除 emoji 字符
  - 模板变量 {emoji_xxx}: 重命名为 {icon_xxx}
  - 字符串字面量中的 emoji: 按映射表替换
  - 变量名 *_emoji: 重命名为 *_icon

可回滚: 脚本先 dry-run, 默认只打印不写入; --apply 才落盘

说明: 脚本直接使用 emoji 字符字面量. 编辑时如出现 surrogate pair 错误,
      可用 escape_emoji.py 重新生成 EMOJI_MAP.
"""

import argparse
import re
import sys
from pathlib import Path


# emoji -> ASCII 替换映射
# 仅放真正的 emoji 字符, 不放 ASCII 标识词
# 格式: (源, 目标)
EMOJI_MAP = [
    # 交通/方向 (含 variation selector 16)
    ("[WARN]", "[WARN]"),
    ("->", "->"),
    ("UP", "UP"),
    ("DOWN", "DOWN"),
    ("<-", "<-"),
    # 圆形符号
    ("PASS", "PASS"),
    ("FAIL", "FAIL"),
    ("FAIL", "FAIL"),
    ("[STOP]", "[STOP]"),
    ("OK", "OK"),
    # 状态指示
    ("CRITICAL", "CRITICAL"),
    ("WARNING", "WARNING"),
    ("SAFE", "SAFE"),
    ("INFO", "INFO"),
    ("[ ]", "[ ]"),
    ("[X]", "[X]"),
    # 工具/警示
    ("[ALERT]", "[ALERT]"),
    ("[TOOL]", "[TOOL]"),
    ("[FIX]", "[FIX]"),
    ("[SCAN]", "[SCAN]"),
    ("[SCAN]", "[SCAN]"),
    # 数据/图表
    ("[STATS]", "[STATS]"),
    ("[UP]", "[UP]"),
    ("[DOWN]", "[DOWN]"),
    ("[NOTE]", "[NOTE]"),
    ("[NOTE]", "[NOTE]"),
    # 链接/网络
    ("[LINK]", "[LINK]"),
    ("[NET]", "[NET]"),
    # 列表/目标
    ("[LIST]", "[LIST]"),
    ("[TARGET]", "[TARGET]"),
    # 信息/想法
    ("[TIP]", "[TIP]"),
    ("[PKG]", "[PKG]"),
    # 速度/动作
    ("[RUN]", "[RUN]"),
    ("[HOST]", "[HOST]"),
    ("[LOCK]", "[LOCK]"),
    ("[KEY]", "[KEY]"),
    ("[LOCK]", "[LOCK]"),
    ("[UNLOCK]", "[UNLOCK]"),
    ("[BELL]", "[BELL]"),
    ("[STOP]", "[STOP]"),
    # 时间
    ("[WAIT]", "[WAIT]"),
    ("[PAUSE]", "[PAUSE]"),
    # 庆祝
    ("[DONE]", "[DONE]"),
    # 手势
    ("[OK]", "[OK]"),
    ("[STOP]", "[STOP]"),
    # 头脑/笔记
    ("[NOTE]", "[NOTE]"),
    ("[NOTE]", "[NOTE]"),
    ("[TEST]", "[TEST]"),
    # 工具栏
    ("[EDIT]", "[EDIT]"),
    ("[WRITE]", "[WRITE]"),
    ("[EDIT]", "[EDIT]"),
    # 标记
    ("NEW", "NEW"),
    ("NEW", "NEW"),
    ("UP", "UP"),
    # 装饰
    ("*", "*"),
    ("*", "*"),
    ("*", "*"),
    ("*", "*"),
    # 箭头 ASCII 兼容
    ("->", "->"),
    ("<-", "<-"),
    ("UP", "UP"),
    ("DOWN", "DOWN"),
    # 勾/叉
    ("OK", "OK"),
    ("OK", "OK"),
    ("OK️", "OK"),
    ("FAIL", "FAIL"),
    ("X", "X"),
    ("X", "X"),
    # 闪电
    ("[FAST]", "[FAST]"),
    # 调色板/艺术
    ("[ART]", "[ART]"),
    # 盾牌/标签
    ("[SHIELD]", "[SHIELD]"),
    ("[TAG]", "[TAG]"),
    # 倒回
    ("[BACK]", "[BACK]"),
]

# 模板变量重命名
TEMPLATE_RENAME = [
    (r"\{trend_emoji\}", "{trend_icon}"),
    (r"\{status_emoji\}", "{status_icon}"),
]

# 变量名重命名 (Python / Shell)
VARIABLE_RENAME = [
    (r"\blevel_emoji\b", "level_icon"),
    (r"\bcov_emoji\b", "cov_icon"),
    (r"\bbudget_emoji\b", "budget_icon"),
    (r"\bagent_emoji\b", "agent_icon"),
]

# 标题行: 移除 (一个或多个) emoji + 后续空格
# 注意: Geometric Shapes (U+25xx) 和 Arrows (U+219x) 属于 ASCII 框图/流程图, 不应被替换
TITLE_EMOJI_RE = re.compile(
    r"^(#{1,6}\s+)"
    r"([\U0001F000-\U0001FFFF\u2600-\u27BF"
    r"\u2B00-\u2BFF\u2300-\u23FF\u2700-\u27BF\u2618\u26a0\u26a1"
    r"\u2705\u270a-\u270b\u2713-\u2718\u2728\u2733\u2734\u274c\u274e\u2753-\u2755\u2763-\u2767]\s*)+"
)

# 兜底: 任何未在 EMOJI_MAP 但属于 emoji BMP 字符
# 排除 Geometric Shapes (U+25xx) 和 Arrows (U+219x), 它们是 ASCII 框图
LOOSE_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FFFF\u2600-\u27BF"
    r"\u2700-\u27BF\u2300-\u23FF\u2B00-\u2BFF]"
)

# 文件后缀白名单
TEXT_EXTS = {".md", ".py", ".sh", ".go", ".yaml", ".yml", ".json"}


def replace_in_text(text: str) -> tuple[str, int, list[str]]:
    """对单段文本做 emoji 替换. 返回 (新文本, 替换次数, 命中列表)."""
    hits: list[str] = []
    new = text

    # 1) 标题行: 移除 emoji + 后续空格
    def _strip_title(m: re.Match) -> str:
        return m.group(1)
    new = TITLE_EMOJI_RE.sub(_strip_title, new)

    # 2) 模板变量重命名
    for pat, repl in TEMPLATE_RENAME:
        new = re.sub(pat, repl, new)

    # 3) 变量名重命名
    for pat, repl in VARIABLE_RENAME:
        new = re.sub(pat, repl, new)

    # 4) emoji 字符替换 (按 EMOJI_MAP 顺序)
    for emoji, repl in EMOJI_MAP:
        if emoji in new:
            cnt = new.count(emoji)
            hits.append(f"{emoji!r}->{repl} x{cnt}")
            new = new.replace(emoji, repl)

    # 5) 兜底: 任何未在 EMOJI_MAP 但属于 emoji 区段的字符 -> 移除
    leftover = LOOSE_EMOJI_RE.findall(new)
    if leftover:
        unique = sorted(set(leftover))
        for ch in unique:
            new = new.replace(ch, "")
        hits.append(f"stripped unknown emoji: {''.join(unique)!r}")

    return new, len(hits), hits


def process_file(path: Path, apply: bool) -> tuple[int, list[str]]:
    """处理单个文件. 返回 (替换次数, 详情)."""
    try:
        original = path.read_text(encoding="utf-8")
    except Exception as e:
        return 0, [f"READ_FAIL: {e}"]

    new, count, hits = replace_in_text(original)
    if new == original:
        return 0, []

    if apply:
        try:
            path.write_text(new, encoding="utf-8")
        except Exception as e:
            return count, [f"WRITE_FAIL: {e}"]

    return count, hits


def main() -> int:
    ap = argparse.ArgumentParser(description="P0-1: 批量替换 emoji 为纯文本 (MR-8)")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--apply", action="store_true", help="落盘修改 (默认 dry-run)")
    ap.add_argument(
        "--exts",
        default=",".join(sorted(TEXT_EXTS)),
        help="要处理的文件后缀 (逗号分隔)",
    )
    ap.add_argument("--summary", action="store_true", help="只输出汇总")
    args = ap.parse_args()

    exts = {e.strip() for e in args.exts.split(",") if e.strip()}
    root = Path(args.root).resolve()

    targets: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in exts:
            continue
        rel = p.relative_to(root)
        if any(part in {".git", "__pycache__", ".runtime", "node_modules"} for part in rel.parts):
            continue
        targets.append(p)

    total_files = 0
    total_replacements = 0
    file_results: list[tuple[Path, int, list[str]]] = []

    for p in targets:
        cnt, hits = process_file(p, apply=args.apply)
        if cnt > 0:
            total_files += 1
            total_replacements += cnt
            file_results.append((p, cnt, hits))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"=== {mode} | {len(targets)} files scanned | "
        f"{total_files} modified | {total_replacements} replacements ==="
    )

    if args.summary:
        return 0

    for p, cnt, hits in file_results:
        rel = p.relative_to(root)
        print(f"\n[{cnt}] {rel}")
        for h in hits[:10]:
            print(f"    {h}")
        if len(hits) > 10:
            print(f"    ... +{len(hits) - 10} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
