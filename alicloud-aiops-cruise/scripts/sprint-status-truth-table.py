#!/usr/bin/env python3
"""
sprint-status-truth-table.py — Sprint 状态真值表生成器

扫描 alicloud-aiops-cruise/TODO/sprint-*.md，提取任务/质量门状态，
生成 Markdown 真值表，并可与 TODO.md 索引做一致性校验。

使用:
  python3 sprint-status-truth-table.py
  python3 sprint-status-truth-table.py --json
  python3 sprint-status-truth-table.py --verify
  python3 sprint-status-truth-table.py --sprint 17

版本: 1.0.0  关联: references/self-assessment-framework.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TODO_DIR = SKILL_DIR / "TODO"
TODO_MD = SKILL_DIR / "TODO.md"

# ── regex patterns ──────────────────────────────────────────────
RE_SPRINT_HEADER = re.compile(
    r"^#\s+Sprint\s+(?P<num>\d+)\s*[:—-]\s+(?P<rest>.+)"
)
# support both Chinese and English parens, optional suffix like P0-4, P1 (运维效率)
RE_PRIORITY = re.compile(r"[（(](P\d+(?:[-/]\d+)?)[）)]")
RE_TASK_ITEM = re.compile(
    r"^\s*-\s+\[(?P<checked>[xX ])\]\s+(?:\*\*(?P<id>[\d.]+|PASS)\*\*\s+)?(?P<title>.+)"
)
RE_QUALITY_HEADER = re.compile(r"^###\s+质量门")
def _split_table_row(line: str) -> list[str]:
    """Split a markdown table row by '|', respecting backtick spans."""
    parts: list[str] = []
    current = ""
    in_backticks = False
    for ch in line:
        if ch == "`":
            in_backticks = not in_backticks
            current += ch
        elif ch == "|" and not in_backticks:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [p.strip() for p in parts]
RE_SPRINT_STATUS = re.compile(
    r">\s*\*\*状态\*\*[:：]\s*(?P<status>.+)"
)
RE_SELF_REVIEW = re.compile(
    r"^\s*-\s+\[(?P<checked>[xX ])\]\s+F\d+"
)


# ── data models ─────────────────────────────────────────────────
@dataclass
class Task:
    """单个 Sprint 任务项."""

    id: str
    title: str
    done: bool


@dataclass
class QualityGate:
    """质量门检查项."""

    id: str
    description: str
    method: str
    result: str


@dataclass
class SprintTruth:
    """单个 Sprint 的真值表数据."""

    number: int
    name: str
    priority: str
    file_status: str = ""
    tasks: list[Task] = field(default_factory=list)
    quality_gates: list[QualityGate] = field(default_factory=list)
    self_review_pass: int = 0
    self_review_total: int = 0

    @property
    def task_done(self) -> int:
        """已完成任务数."""
        return sum(1 for t in self.tasks if t.done)

    @property
    def task_total(self) -> int:
        """任务总数."""
        return len(self.tasks)

    @property
    def qg_pass(self) -> int:
        """通过的质量门数."""
        return sum(
            1
            for q in self.quality_gates
            if "PASS" in q.result.upper() and "FAIL" not in q.result.upper()
        )

    @property
    def qg_total(self) -> int:
        """质量门总数."""
        return len(self.quality_gates)

    @property
    def overall_pass(self) -> bool:
        """综合 verdict: 任务、质量门、文件状态全部通过."""
        if self.task_total > 0:
            tasks_ok = self.task_done == self.task_total
        elif self.self_review_total > 0:
            tasks_ok = self.self_review_pass == self.self_review_total
        else:
            tasks_ok = True
        qg_ok = self.qg_total == 0 or self.qg_pass == self.qg_total
        file_ok = self.file_status == "" or (
            "FAIL" not in self.file_status.upper() and "[ ]" not in self.file_status
        )
        return tasks_ok and qg_ok and file_ok

    @property
    def truth_vector(self) -> dict[str, bool]:
        """真值向量: 各维度通过状态"""
        if self.task_total > 0:
            tasks_ok = self.task_done == self.task_total
        elif self.self_review_total > 0:
            tasks_ok = self.self_review_pass == self.self_review_total
        else:
            tasks_ok = True
        return {
            "tasks_complete": tasks_ok,
            "quality_gates_pass": self.qg_total == 0 or self.qg_pass == self.qg_total,
            "self_review_pass": self.self_review_total == 0
            or self.self_review_pass == self.self_review_total,
            "file_status_pass": self.file_status == "" or (
                "FAIL" not in self.file_status.upper() and "[ ]" not in self.file_status
            ),
            "overall": self.overall_pass,
        }


# ── parser ──────────────────────────────────────────────────────
def parse_sprint_file(path: Path) -> SprintTruth | None:
    """解析单个 Sprint Markdown 文件为 SprintTruth."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # header
    m = RE_SPRINT_HEADER.search(text)
    if not m:
        return None
    rest = m.group("rest").strip()
    pm = RE_PRIORITY.search(rest)
    priority = pm.group(1) if pm else "—"
    name = RE_PRIORITY.sub("", rest).strip()
    if not name:
        name = rest
    sp = SprintTruth(
        number=int(m.group("num")),
        name=name,
        priority=priority,
    )

    # file-level status (e.g. "> **状态**: PASS 4/4")
    for line in lines:
        m2 = RE_SPRINT_STATUS.match(line)
        if m2:
            sp.file_status = m2.group("status").strip()
            break

    in_quality = False
    for line in lines:
        # quality gate section boundary
        if RE_QUALITY_HEADER.match(line):
            in_quality = True
            continue
        if in_quality and line.startswith("#"):
            in_quality = False

        # task item
        tm = RE_TASK_ITEM.match(line)
        if tm:
            task_id = tm.group("id")
            sp.tasks.append(
                Task(
                    id=task_id.strip() if task_id else "—",
                    title=tm.group("title").strip(),
                    done=tm.group("checked").lower() == "x",
                )
            )
            continue

        # self-review F-check
        srm = RE_SELF_REVIEW.match(line)
        if srm:
            sp.self_review_total += 1
            if srm.group("checked").lower() == "x":
                sp.self_review_pass += 1
            continue

        # quality gate row
        if in_quality:
            cols = _split_table_row(line)
            if len(cols) >= 4 and cols[0].startswith("Q"):
                sp.quality_gates.append(
                    QualityGate(
                        id=cols[0],
                        description=cols[1],
                        method=cols[2],
                        result=cols[3],
                    )
                )

    return sp


def parse_all_sprints(todo_dir: Path) -> list[SprintTruth]:
    """扫描 TODO 目录下所有 sprint-*.md 文件."""
    sprints: list[SprintTruth] = []
    for path in sorted(todo_dir.glob("sprint-*.md")):
        sp = parse_sprint_file(path)
        if sp:
            sprints.append(sp)
    return sprints


# ── renderers ───────────────────────────────────────────────────
def render_truth_table(sprints: list[SprintTruth]) -> str:
    """渲染 Markdown 真值汇总表."""
    lines: list[str] = []
    lines.append("# Sprint 状态真值表")
    lines.append("")
    lines.append(
        "| Sprint | 名称 | P | 任务 | 质量门 | 自检 | 文件状态 | 总 verdict |"
    )
    lines.append(
        "|--------|------|---|------|--------|------|----------|------------|"
    )

    for sp in sprints:
        tv = sp.truth_vector
        verdict = "✅ PASS" if tv["overall"] else "❌ FAIL"
        if sp.task_total > 0:
            task_str = f"{sp.task_done}/{sp.task_total}" + (" ✅" if tv["tasks_complete"] else "")
        elif sp.self_review_total > 0:
            task_str = f"F{sp.self_review_pass}/{sp.self_review_total}" + (" ✅" if tv["tasks_complete"] else "")
        else:
            task_str = "N/A"
        qg_str = (
            f"{sp.qg_pass}/{sp.qg_total}" + (" ✅" if tv["quality_gates_pass"] else "")
            if sp.qg_total
            else "N/A"
        )
        review_str = (
            f"{sp.self_review_pass}/{sp.self_review_total}" + (" ✅" if tv["self_review_pass"] else "")
            if sp.self_review_total
            else "N/A"
        )
        status_str = (sp.file_status if sp.file_status else "—") + (" ✅" if tv["file_status_pass"] else "")

        lines.append(
            f"| {sp.number} | {sp.name} | {sp.priority} | {task_str} | "
            f"{qg_str} | {review_str} | {status_str} | {verdict} |"
        )

    # summary
    total = len(sprints)
    passed = sum(1 for sp in sprints if sp.overall_pass)
    lines.append("")
    lines.append(f"**汇总**: {passed}/{total} Sprint 全部通过 | 通过率 {passed/total*100:.1f}%")
    return "\n".join(lines)


def render_detail_table(sprints: list[SprintTruth]) -> str:
    """渲染布尔真值向量明细表."""
    lines: list[str] = []
    lines.append("## 真值向量明细")
    lines.append("")
    lines.append(
        "| Sprint | tasks_complete | quality_gates_pass | self_review_pass | file_status_pass | overall |"
    )
    lines.append(
        "|--------|----------------|--------------------|------------------|------------------|---------|"
    )
    for sp in sprints:
        tv = sp.truth_vector
        def fmt(b: bool) -> str:
            """布尔值格式化为 T/F 标记."""
            return "✅ T" if b else "❌ F"
        lines.append(
            f"| {sp.number} | {fmt(tv['tasks_complete'])} | {fmt(tv['quality_gates_pass'])} | "
            f"{fmt(tv['self_review_pass'])} | {fmt(tv['file_status_pass'])} | {fmt(tv['overall'])} |"
        )
    return "\n".join(lines)


# ── verifier ────────────────────────────────────────────────────
def parse_todo_index(todo_md: Path) -> dict[int, str]:
    """从 TODO.md 解析 Sprint 索引行，返回 {number: status_text}."""
    """从 TODO.md 解析 Sprint 索引行，返回 {number: status_text}"""
    text = todo_md.read_text(encoding="utf-8")
    mapping: dict[int, str] = {}
    # 匹配形如:
    #   | [**17**](...) | Baseline 重采样 | P2 | ... | Sprint 16 | PASS **4/4** |
    #   | **6** | 预授权白名单 | P2 | 半自动修复 | Sprint 1 | PASS **8/8** |
    pat = re.compile(
        r"^\|\s*(?:\[)?(?:\*\*)?(?P<num>\d+)(?:\*\*)?(?:\])?(?:\([^)]*\))?\s*\|"
        r"\s*(?P<name>[^|]+)\|\s*(?P<priority>[^|]+)\|"
        r"\s*(?P<value>[^|]+)\|\s*(?P<deps>[^|]+)\|"
        r"\s*(?P<status>[^|]+)\|",
        re.MULTILINE,
    )
    for m in pat.finditer(text):
        num = int(m.group("num"))
        status = m.group("status").strip()
        mapping[num] = status
    return mapping


def verify_todo_consistency(sprints: list[SprintTruth]) -> list[str]:
    """校验 TODO.md 索引与 Sprint 文件的一致性."""
    issues: list[str] = []
    if not TODO_MD.exists():
        issues.append(f"[ERROR] {TODO_MD} 不存在，无法校验")
        return issues

    index = parse_todo_index(TODO_MD)
    sprint_nums = {sp.number for sp in sprints}
    index_nums = set(index.keys())

    # 文件存在但索引缺失
    for num in sorted(sprint_nums - index_nums):
        sp = next(s for s in sprints if s.number == num)
        issues.append(f"[WARN] Sprint {num} ({sp.name}) 有文件但 TODO.md 索引缺失")

    # 索引存在但文件缺失
    for num in sorted(index_nums - sprint_nums):
        issues.append(f"[WARN] Sprint {num} 在 TODO.md 索引中但无对应 sprint 文件")

    # 状态一致性
    for sp in sprints:
        if sp.number not in index:
            continue
        idx_status = index[sp.number]
        file_pass = "PASS" in sp.file_status.upper()
        idx_pass = "PASS" in idx_status.upper()
        if file_pass != idx_pass:
            issues.append(
                f"[MISMATCH] Sprint {sp.number}: 文件状态='{sp.file_status}' vs TODO.md='{idx_status}'"
            )

    return issues


# ── main ────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 入口."""
    parser = argparse.ArgumentParser(
        description="Sprint 状态真值表生成器",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="校验 TODO.md 索引一致性",
    )
    parser.add_argument(
        "--sprint",
        type=int,
        metavar="N",
        help="仅解析指定 Sprint 编号",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="附加真值向量明细表",
    )
    args = parser.parse_args(argv)

    if not TODO_DIR.is_dir():
        print(f"[ERROR] TODO 目录不存在: {TODO_DIR}", file=sys.stderr)
        return 1

    sprints = parse_all_sprints(TODO_DIR)
    if args.sprint is not None:
        sprints = [sp for sp in sprints if sp.number == args.sprint]
        if not sprints:
            print(f"[ERROR] Sprint {args.sprint} 未找到", file=sys.stderr)
            return 1

    if args.json:
        payload = [asdict(sp) for sp in sprints]
        # add computed fields
        for sp, p in zip(sprints, payload):
            p["truth_vector"] = sp.truth_vector
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # markdown output
    print(render_truth_table(sprints))
    if args.detail:
        print()
        print(render_detail_table(sprints))

    if args.verify:
        print()
        print("---")
        print("## TODO.md 一致性校验")
        print()
        issues = verify_todo_consistency(sprints)
        if issues:
            for issue in issues:
                print(f"- {issue}")
        else:
            print("✅ 全部一致，无问题")

    return 0


if __name__ == "__main__":
    sys.exit(main())
