# Sprint 19 — Runtime 清理 + 路径迁移收尾

> **状态**: PASS 6/6 + P0-2 补漏 6 文件
> **优先级**: P1 (架构收尾 + 工具完善)
> **业务价值**: 消除所有硬编码 audit-results 路径; 提供 cleanup 工具; 防止 .runtime/ 膨胀
> **依赖**: Sprint 18 (RUNTIME_ROOT 共享 lib)
> **开始日期**: 2026-06-07
> **需求来源**: 2026-06-07 20:30 用户决策 — "接着完成清理"

---

## 背景

Sprint 18 实现了 `.runtime/` 统一根目录 + 共享 lib, 并迁移了核心脚本 (configdrift.sh / __init__.sh / baseline-manager.py)。
但仍有大量硬编码 `audit-results` 路径散落在其他 skill:
- alicloud-gcl-runner-ops/scripts/*.py (5 个)
- alicloud-aiops-cruise/runbooks/scripts/_shared.py (CACHE_DIR)
- alicloud-aiops-cruise/runbooks/scripts/*.py (7 个 runbook 脚本的 --output-dir 默认值)

此外, `.runtime/` 缺少:
- 过期数据清理工具
- 大小监控 + 报警

---

## 任务清单

### PASS T1: 调研所有硬编码路径 (已完成)

- PASS alicloud-gcl-runner-ops/scripts/ (5 文件): gcl_runner, gcl_actiontrail_crosscheck, gcl_cms_alarm_setup, gcl_passrate_reporter, gcl_runner_test
- PASS alicloud-aiops-cruise/runbooks/scripts/_shared.py: CACHE_DIR = `audit-results/cache` (280 行)
- PASS alicloud-aiops-cruise/runbooks/scripts/*.py (7 文件): --output-dir default = `"audit-results"`
- PASS alicloud-topo-discovery/scripts/lib/baseline_git.py: 无硬编码 (接受参数, 不需改)

### PASS T2: 迁移 alicloud-gcl-runner-ops 路径

- PASS gcl_runner.py: trace 输出默认 -> `${RUNTIME_ROOT}/audit/gcl-runner/`
- PASS gcl_actiontrail_crosscheck.py: trace-dir / report 默认 -> 同上
- PASS gcl_cms_alarm_setup.py: --report-dir 默认 -> 同上
- PASS gcl_passrate_reporter.py: trace 扫描 -> 同上
- PASS gcl_runner_test.py: 测试目录 -> 用 tmp_path

**新默认路径**:
```python
from runtime_root import RuntimeRoot  # 在 aiops-cruise/scripts/lib/
GCL_AUDIT_DIR = str(RuntimeRoot("gcl-runner-ops").audit_dir)
# 实际: ${ALIYUN_SKILLS_RUNTIME_ROOT}/audit/gcl-runner-ops/
```

### PASS T3: 迁移 _shared.py 的 CACHE_DIR

**新代码** (行 280):
```python
# Sprint 19: 改用 RUNTIME_ROOT 共享路径
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from runtime_root import get_runtime_root
CACHE_DIR = get_runtime_root() / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)  # 立即创建
```

### PASS T4: 迁移 runbooks 7 个脚本的 --output-dir

**新默认值** (从 RUNTIME_ROOT 解析):
```python
def default_output_dir():
    """Sprint 19: 改用 RUNTIME_ROOT/audit/aiops-cruise/runbooks/"""
    from runtime_root import audit_path
    return str(audit_path("alicloud-aiops-cruise", "runbooks"))

# 7 个脚本的 --output-dir 改为 default=default_output_dir()
```

涉及脚本: agent-fallback, capacity-planning, cost-watch, cruise-orchestrator, daily-health-check, emergency-troubleshoot, pre-launch-check, workflow-runner

### PASS T5: 创建 aliyun-skills-cleanup 命令

**目标**: 提供一键清理 `.runtime/` 中过期数据的工具。

**接口**:
```bash
# 默认: 清理 > 90 天的 baseline + 清理 > 7 天的 audit + 清理 > 30 天的 logs
python3 -m alicloud_aiops_cruise.scripts.lib.runtime_cleanup

# 自定义阈值
python3 -m alicloud_aiops_cruise.scripts.lib.runtime_cleanup \
    --baseline-keep-days 90 \
    --audit-keep-days 30 \
    --logs-keep-days 7 \
    --max-total-size-mb 1024 \
    --dry-run
```

**实现**: `alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py` (200 行)
- baseline: 标记过期 (复用 baseline-manager 的 retention 逻辑)
- audit/logs: 直接删除 `*.expired` 重命名模式
- max-total-size: 报警 + 二次清理 (从最旧开始删)

### PASS T6: 单元测试 + 端到端验证 + F8 同步

- PASS 测试: `test_sprint19_runtime_cleanup.py` (cleanup dry-run + size limit)
- PASS 测试: `test_sprint19_path_migration.py` (验证所有新默认值正确)
- PASS 端到端: 跑一次 `gcl_runner` + `daily-health-check` 验证写到 .runtime/
- PASS F8 同步: SKILL.md Changelog (v1.2.1) + TODO.md 索引

---

## 风险

| 风险 | 缓解 |
|------|------|
| 修改 runbook --output-dir 默认值破坏现有 CI/CD | 默认值仍可被 --output-dir 显式覆盖; 旧路径软链接兜底 |
| gcl-runner 测试用例依赖固定路径 | 改用 `tmp_path` fixture (pytest) |
| cleanup 误删重要数据 | dry-run 模式默认开启; 生产执行需显式 --no-dry-run |
| RUNTIME_ROOT 不可用时 fallback | 软链接 `audit-results/` -> `.runtime/audit/...` 兜底 |

---

## Self-Review (F1-F8)

- [x] F1: CLI command validation — gcl-runner 的 --trace-dir / --report-dir 仍接受任意路径
- [x] F2: OpenAPI accuracy — N/A
- [x] F3: Error handling — cleanup 增加 dry-run + 明确确认
- [x] F4: Safety gates — 默认不删数据, --no-dry-run 显式 opt-in
- [x] F5: Link integrity — 软链接 fallback 保持
- [x] F6: Content deduplication — 共享 runtime_root lib
- [x] F7: Cross-skill delegation — runtime_cleanup lib 在 aiops-cruise, 其他 skill 可调用
- [x] F8: TODO.md 同步 — PASS (本文件 + 索引 + Changelog)

---

## 验证

```bash
# 1. 单元测试
cd alicloud-topo-discovery && python3 -m pytest tests/test_sprint19_*.py -v
# 预期: 全部通过

# 2. 端到端
ALIYUN_SKILLS_RUNTIME_ROOT=/tmp/test-cleanup python3 -m runtime_cleanup --dry-run
# 预期: 列出将清理的文件, 不实际删除

# 3. 旧路径仍能工作 (软链接)
ls audit-results/  # 应仍能列出
```
