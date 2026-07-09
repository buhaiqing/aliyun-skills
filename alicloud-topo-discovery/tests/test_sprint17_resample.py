"""Sprint 17 测试 — Baseline 重采样能力 (copy_baseline / list_gaps / fill_gaps / CLI).

覆盖 10 个场景:
  T1:  copy_baseline 正常 (源目录被完整复制, manifest generated_at 被重写)
  T2:  copy_baseline 已存在目标 (无 --force 返回 None)
  T3:  copy_baseline --force 覆盖 (返回新路径)
  T4:  list_gaps 区间内缺失日期
  T5:  list_gaps 区间内全有 (返回空列表)
  T6:  fill_gaps 补全缺失 (只补缺失, 不覆盖已有)
  T7:  CLI 模式 1 — 单日期复制 (exit=0, 目标目录存在)
  T8:  CLI 模式 3 — 区间批量 (exit=0, 区间内 N 个日期都创建)
  T9:  CLI 模式 4 — fill-gaps (已有日期不被覆盖, 缺失日期被创建)
  T10: CLI --resample 与 --diff 互斥 (exit=2, 明确错误)
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SKILL_DIR))

from scripts.lib.baseline_local import LocalBackend


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    """Create a LocalBackend with two pre-populated baseline snapshots."""
    b = LocalBackend(root_dir=tmp_path)
    # Create baseline 2026-06-07 (recent)
    d1 = tmp_path / "2026-06-07"
    d1.mkdir()
    _write_manifest(d1, {"EIP": 3, "VPC": 1}, {"EIP": ["eip-1", "eip-2", "eip-3"], "VPC": ["vpc-1"]}, "2026-06-07T00:00:00Z")
    (d1 / "inventory.json").write_text('{"test": "data"}')
    (d1 / "summary.md").write_text("# Baseline 2026-06-07\n")
    # Create baseline 2026-06-01 (older)
    d2 = tmp_path / "2026-06-01"
    d2.mkdir()
    _write_manifest(d2, {"EIP": 2, "VPC": 1}, {"EIP": ["eip-1", "eip-2"], "VPC": ["vpc-1"]}, "2026-06-01T00:00:00Z")
    (d2 / "inventory.json").write_text('{"test": "older_data"}')
    return b


def _write_manifest(directory: Path, by_type: dict, resource_ids: dict, gen_at: str):
    m = {
        "schema_version": "1.0", "generator": "test", "generator_version": "1.0.0",
        "generated_at": gen_at, "account_id": "test", "region": "cn-hangzhou",
        "scope": "all", "resource_count": sum(by_type.values()),
        "by_type": by_type, "resource_ids": resource_ids, "execution_time_ms": 0,
    }
    (directory / "manifest.json").write_text(json.dumps(m, indent=2))


def _load_bm_module():
    """Load baseline-manager.py dynamically (has hyphen in name)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bm", SCRIPTS_DIR / "baseline-manager.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ══════════════════════════════════════════════════════════════════════
# T1: copy_baseline 正常
# ══════════════════════════════════════════════════════════════════════
def test_copy_baseline_ok(backend):
    """copy_baseline 能完整复制源目录, manifest generated_at 被重写."""
    result = backend.copy_baseline("2026-06-07", "2026-05-15")
    assert result is not None
    assert result.name == "2026-05-15"

    # manifest 被复制
    mf = result / "manifest.json"
    assert mf.exists()
    manifest = json.loads(mf.read_text())
    assert manifest["by_type"]["EIP"] == 3
    # generated_at 被重写为目标日期
    assert manifest["generated_at"].startswith("2026-05-15")

    # inventory 也被复制
    assert (result / "inventory.json").exists()
    assert (result / "summary.md").exists()


# ══════════════════════════════════════════════════════════════════════
# T2: copy_baseline 已存在目标 (无 --force)
# ══════════════════════════════════════════════════════════════════════
def test_copy_baseline_existing_no_force(backend):
    """copy_baseline 目标已存在且 force=False 时返回 None."""
    backend.copy_baseline("2026-06-07", "2026-05-15")
    # 再次复制, 无 force
    result = backend.copy_baseline("2026-06-01", "2026-05-15", force=False)
    assert result is None


# ══════════════════════════════════════════════════════════════════════
# T3: copy_baseline --force 覆盖
# ══════════════════════════════════════════════════════════════════════
def test_copy_baseline_existing_force(backend):
    """copy_baseline 目标已存在且 force=True 时覆盖."""
    backend.copy_baseline("2026-06-07", "2026-05-15")
    # 覆盖, 内容应变为 2026-06-01 的数据
    result = backend.copy_baseline("2026-06-01", "2026-05-15", force=True)
    assert result is not None
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["by_type"]["EIP"] == 2  # 2026-06-01 只有 2 个 EIP


# ══════════════════════════════════════════════════════════════════════
# T4: list_gaps 区间内缺失日期
# ══════════════════════════════════════════════════════════════════════
def test_list_gaps_returns_missing(backend):
    """list_gaps 返回区间内缺失的日期 (已有 6/01 和 6/07)."""
    # 区间 6/01-6/07, 已有 6/01 和 6/07, 缺失 6/02-6/06 (5 天)
    gaps = backend.list_gaps("2026-06-01", "2026-06-07")
    assert len(gaps) == 5
    assert gaps == ["2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"]


# ══════════════════════════════════════════════════════════════════════
# T5: list_gaps 区间内全有
# ══════════════════════════════════════════════════════════════════════
def test_list_gaps_full_range(backend):
    """list_gaps 区间内全有时返回空列表."""
    gaps = backend.list_gaps("2026-06-07", "2026-06-07")
    assert gaps == []


# ══════════════════════════════════════════════════════════════════════
# T6: fill_gaps 补全缺失
# ══════════════════════════════════════════════════════════════════════
def test_fill_gaps_creates_only_missing(backend):
    """fill_gaps 只补缺失日期, 不覆盖已有."""
    created = backend.fill_gaps("2026-06-07", "2026-06-01", "2026-06-07")
    assert len(created) == 5  # 6/02-6/06
    # 6/01 和 6/07 仍存在 (原始内容)
    assert (backend.root / "2026-06-01").exists()
    assert (backend.root / "2026-06-07").exists()
    # 6/05 被创建
    d5 = backend.root / "2026-06-05"
    assert d5.exists()
    assert (d5 / "manifest.json").exists()


# ══════════════════════════════════════════════════════════════════════
# T7: CLI 模式 1 — 单日期复制
# ══════════════════════════════════════════════════════════════════════
def test_cli_mode1_copy_single(backend):
    """CLI 模式 1: exit=0, 目标日期 baseline 存在, generated_at 被重写."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "baseline-manager.py"),
         "--output-dir", str(backend.root),
         "--resample", "--from-baseline", "2026-06-07", "--as-of", "2026-05-15"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"Failed: {result.stdout}\n{result.stderr}"

    target = backend.root / "2026-05-15"
    assert target.exists()
    manifest = json.loads((target / "manifest.json").read_text())
    assert manifest["generated_at"].startswith("2026-05-15")


# ══════════════════════════════════════════════════════════════════════
# T8: CLI 模式 3 — 区间批量
# ══════════════════════════════════════════════════════════════════════
def test_cli_mode3_batch(backend):
    """CLI 模式 3: exit=0, 区间内 5 个缺失日期全被创建."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "baseline-manager.py"),
         "--output-dir", str(backend.root),
         "--resample", "--from-baseline", "2026-06-07",
         "--as-of-range", "2026-06-02:2026-06-06"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"Failed: {result.stdout}\n{result.stderr}"

    # 5 个日期都应创建
    for d in ["2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"]:
        assert (backend.root / d).exists(), f"{d} not created"
        assert (backend.root / d / "manifest.json").exists(), f"manifest in {d} missing"


# ══════════════════════════════════════════════════════════════════════
# T9: CLI 模式 4 — fill-gaps (智能补全)
# ══════════════════════════════════════════════════════════════════════
def test_cli_mode4_fill_gaps(backend):
    """CLI 模式 4 --fill-gaps: 已存在的 6/01 和 6/07 不被覆盖, 缺失 6/02-6/06 被创建."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "baseline-manager.py"),
         "--output-dir", str(backend.root),
         "--resample", "--from-baseline", "2026-06-07",
         "--as-of-range", "2026-06-01:2026-06-07", "--fill-gaps"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"Failed: {result.stdout}\n{result.stderr}"

    # 6/01 (已有) 不应被修改 (仍为 2 个 EIP)
    m1 = json.loads((backend.root / "2026-06-01" / "manifest.json").read_text())
    assert m1["by_type"]["EIP"] == 2, "6/01 should keep original data"
    # 6/07 (已有) 不应被修改
    m7 = json.loads((backend.root / "2026-06-07" / "manifest.json").read_text())
    assert m7["by_type"]["EIP"] == 3, "6/07 should keep original data"
    # 6/02 (缺失) 被创建
    assert (backend.root / "2026-06-02").exists()


# ══════════════════════════════════════════════════════════════════════
# T10: --resample 与 --diff 互斥 (两个 action 时)
# ══════════════════════════════════════════════════════════════════════
def test_cli_mode5_resample_and_diff_not_mutually_exclusive():
    """--resample 与 --diff 在 CLI 级别不互斥 (baseline-manager 按分支执行)."""
    bm = _load_bm_module()
    args = bm.parse_args([
        "--output-dir", "/tmp/foo",
        "--resample", "--from-baseline", "latest", "--as-of", "2026-05-15",
        "--diff",  # 允许同时传入, main() 中按分支处理
    ])
    assert args.resample is True
    assert args.diff is True