#!/usr/bin/env python3
"""Sprint 16 测试 — baseline-manager.py --compare-with 行为验证.

覆盖场景:
  T1: LocalBackend.get_by_date 正常返回存在目录
  T2: LocalBackend.get_by_date 不存在日期返回 None
  T3: LocalBackend.get_by_date 无效格式返回 None
  T4: parse_args 接受 --compare-with
  T5: parse_args 缺省值 (向后兼容)
  T6: _compute_diff 集成 (ADDED 资源)
  T7: _compute_diff 集成 (REMOVED 资源)
  T8: CLI 端到端 — --compare-with 不存在日期 (exit=2)
  T9: CLI 端到端 — --compare-with 无效格式 (exit=2)
"""
import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SKILL_DIR))

from scripts.lib.baseline_local import LocalBackend


def _load_bm_module():
    """动态加载 baseline-manager.py (文件名含连字符, 不能直接 import)."""
    spec = importlib.util.spec_from_file_location(
        "baseline_manager", SCRIPTS_DIR / "baseline-manager.py"
    )
    bm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bm)
    return bm


# ── T1: get_by_date 正常 ──
def test_get_by_date_returns_existing_dir(tmp_path):
    """get_by_date 返回存在的 baseline 目录."""
    backend = LocalBackend(root_dir=tmp_path)
    target = "2026-05-15"
    target_dir = tmp_path / target
    target_dir.mkdir(parents=True)
    (target_dir / "manifest.json").write_text('{"test": true}')

    result = backend.get_by_date(target)
    assert result is not None
    assert result.name == target
    assert (result / "manifest.json").exists()


# ── T2: get_by_date 不存在 ──
def test_get_by_date_returns_none_for_missing(tmp_path):
    """get_by_date 对不存在的日期返回 None (不抛异常)."""
    backend = LocalBackend(root_dir=tmp_path)
    assert backend.get_by_date("2026-05-15") is None


# ── T3: get_by_date 无效格式 ──
def test_get_by_date_returns_none_for_invalid_format(tmp_path):
    """get_by_date 对无效日期格式返回 None (不抛异常)."""
    backend = LocalBackend(root_dir=tmp_path)
    for invalid in ["2026/05/15", "15-05-2026", "abc", "", "2026-13-99", None]:
        assert backend.get_by_date(invalid) is None, f"Expected None for {invalid!r}"


# ── T4: parse_args 接受 --compare-with ──
def test_parse_args_accepts_compare_with():
    """parse_args 接受 --compare-with 参数."""
    bm = _load_bm_module()
    args = bm.parse_args([
        "--output-dir", "/tmp/foo",
        "--diff",
        "--compare-with", "2026-05-15",
    ])
    assert args.compare_with == "2026-05-15"
    assert args.diff is True


# ── T5: parse_args 缺省值 (向后兼容) ──
def test_parse_args_compare_with_defaults_to_none():
    """--compare-with 缺省 = None (向后兼容, 等同于 vs latest)."""
    bm = _load_bm_module()
    args = bm.parse_args(["--output-dir", "/tmp/foo", "--diff"])
    assert args.compare_with is None


# ── T6: _compute_diff 检测 ADDED ──
def test_compute_diff_detects_added_resources():
    """_compute_diff 正确识别新增资源 (数量 delta + 具体 ID)."""
    bm = _load_bm_module()
    old = _make_manifest({"EIP": 2, "VPC": 1}, {"EIP": ["eip-1", "eip-2"], "VPC": ["vpc-1"]})
    new = _make_manifest({"EIP": 3, "VPC": 1}, {"EIP": ["eip-1", "eip-2", "eip-3"], "VPC": ["vpc-1"]})

    changes = bm._compute_diff(new, old)
    added = [c for c in changes if c.startswith("[ADDED]")]

    assert any("EIP" in c and "+1" in c for c in added), \
        f"Expected EIP count delta, got {added}"
    assert any("eip-3" in c for c in added), \
        f"Expected new resource ID eip-3, got {added}"


# ── T7: _compute_diff 检测 REMOVED ──
def test_compute_diff_detects_removed_resources():
    """_compute_diff 正确识别删除资源."""
    bm = _load_bm_module()
    old = _make_manifest({"ECS": 2}, {"ECS": ["i-1", "i-2"]})
    new = _make_manifest({"ECS": 1}, {"ECS": ["i-1"]})

    changes = bm._compute_diff(new, old)
    removed = [c for c in changes if c.startswith("[REMOVED]")]

    assert any("ECS" in c and "-1" in c for c in removed), \
        f"Expected ECS count delta, got {removed}"
    assert any("i-2" in c for c in removed), \
        f"Expected removed resource ID i-2, got {removed}"


# ── T8: CLI 不存在日期 ──
def test_cli_compare_with_nonexistent_date(tmp_path):
    """CLI --compare-with 指定不存在的日期应返回 exit=2 + 明确错误信息."""
    output_dir = tmp_path / "infra-baseline"
    output_dir.mkdir()

    # 预放一个 baseline (latest), 但不预放 2025-01-01
    (output_dir / "2026-06-01").mkdir()
    (output_dir / "2026-06-01" / "manifest.json").write_text(
        json.dumps(_make_manifest({"EIP": 1}, {"EIP": ["eip-1"]}))
    )

    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS_DIR / "baseline-manager.py"),
            "--output-dir", str(output_dir),
            "--diff",
            "--compare-with", "2025-01-01",
        ],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 2, \
        f"Expected exit=2, got {result.returncode}. stdout={result.stdout}, stderr={result.stderr}"
    combined = result.stdout + result.stderr
    assert "No baseline found for date" in combined, \
        f"Expected error message, got: {combined}"


# ── T9: CLI 无效日期格式 ──
def test_cli_compare_with_invalid_format(tmp_path):
    """CLI --compare-with 无效格式应返回 exit=2 + Invalid date format 错误."""
    output_dir = tmp_path / "infra-baseline"
    output_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable, str(SCRIPTS_DIR / "baseline-manager.py"),
            "--output-dir", str(output_dir),
            "--diff",
            "--compare-with", "2026/05/15",  # 用 / 代替 -, 无效
        ],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "Invalid date format" in combined


# ── Helper ──
def _make_manifest(by_type: dict, resource_ids: dict) -> dict:
    """构造最小可用的 manifest dict (满足 _compute_diff 字段需求)."""
    return {
        "schema_version": "1.0",
        "generator": "test",
        "generator_version": "1.0.0",
        "generated_at": date.today().isoformat() + "T00:00:00Z",
        "account_id": "test-account",
        "region": "cn-hangzhou",
        "scope": "all",
        "resource_count": sum(by_type.values()),
        "by_type": by_type,
        "resource_ids": resource_ids,
        "execution_time_ms": 0,
    }
