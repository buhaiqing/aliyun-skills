"""Sprint 19 测试 — runtime_cleanup 工具 + 路径迁移验证.

覆盖场景:
  T1: cleanup dry-run 默认行为 (不实际删除)
  T2: get_runtime_root 优先使用 ALIYUN_SKILLS_RUNTIME_ROOT
  T3: get_runtime_root 使用 SKILLS_DIR 环境变量 (Sprint 19 修复)
  T4: _resolve_runbooks_output_dir 指向 aliyun-skills 顶层 .runtime
  T5: gcl_runner.DEFAULT_AUDIT_DIR 指向 aliyun-skills 顶层 .runtime
  T6: cleanup --apply 标记超期 baseline 为 .expired
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SKILLS_DIR = Path("/Users/bohaiqing/opensource/git/aliyun-skills")


# ── T1: cleanup dry-run ──
def test_cleanup_dry_run_default():
    """cleanup dry-run 默认行为 (不实际删除)."""
    rt = SKILLS_DIR / ".runtime"
    result = subprocess.run(
        [sys.executable,
         str(SKILLS_DIR / "alicloud-aiops-cruise" / "scripts" / "lib" / "runtime_cleanup.py")],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "ALIYUN_SKILLS_RUNTIME_ROOT": str(rt)},
    )
    assert result.returncode == 0
    assert "DRY-RUN" in result.stdout
    assert "runtime_cleanup" in result.stdout.lower() or "Runtime Cleanup" in result.stdout


# ── T2: get_runtime_root 优先 ALIYUN_SKILLS_RUNTIME_ROOT ──
def test_get_runtime_root_respects_env():
    """get_runtime_root 优先使用 ALIYUN_SKILLS_RUNTIME_ROOT env."""
    os.environ["ALIYUN_SKILLS_RUNTIME_ROOT"] = "/tmp/test-rt-sprint19"
    try:
        sys.path.insert(0, str(SKILLS_DIR / "alicloud-aiops-cruise" / "scripts" / "lib"))
        if "runtime_root" in sys.modules:
            del sys.modules["runtime_root"]
        from runtime_root import get_runtime_root
        # macOS /tmp 自动 resolve 到 /private/tmp, 用 resolve() 对比
        assert get_runtime_root() == Path("/tmp/test-rt-sprint19").resolve()
    finally:
        del os.environ["ALIYUN_SKILLS_RUNTIME_ROOT"]


# ── T3: get_runtime_root 使用 SKILLS_DIR env (Sprint 19 修复) ──
def test_get_runtime_root_uses_skills_dir_env():
    """get_runtime_root 在 SKILLS_DIR 存在时优先使用 (Sprint 19 修复)."""
    os.environ["SKILLS_DIR"] = "/tmp/test-skills-sprint19"
    os.environ.pop("ALIYUN_SKILLS_RUNTIME_ROOT", None)
    try:
        sys.path.insert(0, str(SKILLS_DIR / "alicloud-aiops-cruise" / "scripts" / "lib"))
        if "runtime_root" in sys.modules:
            del sys.modules["runtime_root"]
        from runtime_root import get_runtime_root
        # macOS 自动 resolve /tmp -> /private/tmp, 用 resolve() 对比
        assert get_runtime_root() == Path("/tmp/test-skills-sprint19/.runtime").resolve()
    finally:
        del os.environ["SKILLS_DIR"]


# ── T4: _resolve_runbooks_output_dir 指向顶层 .runtime ──
def test_resolve_runbooks_output_dir():
    """_resolve_runbooks_output_dir 应指向 aliyun-skills 顶层 .runtime."""
    os.environ.pop("ALIYUN_SKILLS_RUNTIME_ROOT", None)
    sys.path.insert(0, str(SKILLS_DIR / "alicloud-aiops-cruise" / "runbooks" / "scripts"))
    if "_shared" in sys.modules:
        del sys.modules["_shared"]
    from _shared import _resolve_runbooks_output_dir
    result = _resolve_runbooks_output_dir()
    expected = str((SKILLS_DIR / ".runtime" / "audit" / "aiops-cruise" / "runbooks").resolve())
    assert result == expected, f"Expected {expected}, got {result}"


# ── T5: gcl_runner.DEFAULT_AUDIT_DIR 指向顶层 .runtime ──
def test_gcl_runner_default_audit_dir():
    """gcl_runner.DEFAULT_AUDIT_DIR 应指向 aliyun-skills 顶层 .runtime."""
    os.environ.pop("ALIYUN_SKILLS_RUNTIME_ROOT", None)
    sys.path.insert(0, str(SKILLS_DIR / "alicloud-gcl-runner-ops" / "scripts"))
    if "gcl_runner" in sys.modules:
        del sys.modules["gcl_runner"]
    import gcl_runner
    expected = (SKILLS_DIR / ".runtime" / "audit" / "gcl-runner-ops").resolve()
    assert Path(gcl_runner.DEFAULT_AUDIT_DIR).resolve() == expected, \
        f"Expected {expected}, got {gcl_runner.DEFAULT_AUDIT_DIR}"


# ── T6: cleanup --apply 标记超期 baseline ──
def test_cleanup_baseline_marks_expired():
    """cleanup --apply 将超过 90 天的 baseline 标记为 .expired."""
    with tempfile.TemporaryDirectory() as tmp:
        rt = Path(tmp)
        # 新 baseline: 2026-06-07
        (rt / "baseline" / "2026-06-07").mkdir(parents=True)
        (rt / "baseline" / "2026-06-07" / "manifest.json").write_text("{}")
        # 过期 baseline: 2025-01-01 (超过 90 天)
        (rt / "baseline" / "2025-01-01").mkdir(parents=True)
        (rt / "baseline" / "2025-01-01" / "manifest.json").write_text("{}")

        result = subprocess.run(
            [sys.executable,
             str(SKILLS_DIR / "alicloud-aiops-cruise" / "scripts" / "lib" / "runtime_cleanup.py"),
             "--apply", "--baseline-keep-days", "90"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "ALIYUN_SKILLS_RUNTIME_ROOT": str(rt)},
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        # 2025-01-01 应被标记
        assert (rt / "baseline" / "2025-01-01.expired").exists()
        # 2026-06-07 不应被标记
        assert (rt / "baseline" / "2026-06-07").exists()
        assert not (rt / "baseline" / "2026-06-07.expired").exists()


# ── T7: cleanup_traces 删除超期 trace ──
def test_cleanup_traces_removes_old_trace_files():
    """cleanup_traces --apply 删除超过 keep_days 的 trace-*.json."""
    import time

    with tempfile.TemporaryDirectory() as tmp:
        skills = Path(tmp)
        traces = skills / "alicloud-ecs-ops" / ".runtime" / "traces"
        traces.mkdir(parents=True)
        old_trace = traces / "trace-sess-old-1.json"
        old_trace.write_text('{"status":"success","start_time":"2025-01-01T00:00:00+0000"}')
        old_ts = time.time() - (30 * 86400)
        os.utime(old_trace, (old_ts, old_ts))
        new_trace = traces / "trace-sess-new-1.json"
        new_trace.write_text('{"status":"success"}')

        sys.path.insert(0, str(SKILLS_DIR / "alicloud-aiops-cruise" / "scripts" / "lib"))
        if "runtime_cleanup" in sys.modules:
            del sys.modules["runtime_cleanup"]
        from runtime_cleanup import cleanup_traces

        result = cleanup_traces(skills, skills / ".runtime", keep_days=7, apply=True)
        assert result["trace_deleted"] == 1
        assert not old_trace.exists()
        assert new_trace.exists()
