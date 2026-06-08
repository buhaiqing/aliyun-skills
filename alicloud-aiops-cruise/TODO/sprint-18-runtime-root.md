# Sprint 18 — 运行时数据统一根目录 (.runtime/)

> **状态**: PASS 6/6
> **优先级**: P0 (架构基础)
> **业务价值**: 集中管理所有运行时数据; 根目录可配置; 完整 Gitignore
> **依赖**: Sprint 16/17 (baseline 路径使用方)
> **开始日期**: 2026-06-07
> **完成日期**: 2026-06-07
> **需求来源**: 2026-06-07 19:44 用户决策 — "运行时数据集中管理, 按业务/场景分子目录, 加入 .gitignore"
> **决策确认**: 2026-06-07 20:00 (5 个关键决策全部 OK)

---

## 关键决策（已确认）

| 决策 | 选择 | 理由 |
|------|------|------|
| 根目录名 | `.runtime/` | 隐藏目录 + gitignore 双保险 |
| 顶层结构 | 按类型 (baseline/audit/cache/logs/tmp) + 二级按 skill | 跨 skill 数据共享直观 |
| 兼容策略 | 软链接过渡 | 不破坏现有调用 |
| 环境变量 | `ALIYUN_SKILLS_RUNTIME_ROOT` 可覆盖 | CI/CD/Docker 灵活 |
| 实施节奏 | 一次性 Sprint 18 (6 任务) | 范围清晰 |

---

## 目录结构

```
.runtime/                              # 根目录 (RUNTIME_ROOT)
├── baseline/                          # 拓扑基线 (Sprint 16/17 用)
│   └── YYYY-MM-DD/                    # 日期目录
│       ├── manifest.json
│       └── inventory.json
├── audit/                             # 巡检 / GCL 报告
│   ├── aiops-cruise/                  # 按 skill
│   │   ├── perceive-{ts}/             # Perceive Agent 报告
│   │   │   ├── healthcruise.json
│   │   │   ├── configdrift.json
│   │   │   └── perceive-summary.json
│   │   └── gcl-{run-id}/              # GCL trace
│   ├── topo-discovery/
│   └── shared/                        # 跨 skill 共享
├── cache/                             # Python 跨 runbook 缓存
│   └── _perf_cache_*.json
├── logs/                              # 运行日志
│   ├── aiops-cruise/
│   └── topo-discovery/
└── tmp/                               # 进程级临时
    ├── topo_baseline_xxx/
    └── gcl-trace-xxx/
```

---

## 任务清单

### PASS T1: 基础设施 (.gitignore + .runtime/ + 共享 lib)

- PASS `.gitignore` 增强 (新增 `.runtime/` + 兼容旧路径规则)
- PASS 顶层 `.runtime/` 目录结构创建
- PASS 共享 lib:
  - `alicloud-aiops-cruise/scripts/lib/runtime_root.sh` (Shell 解析)
  - `alicloud-aiops-cruise/scripts/lib/runtime_root.py` (Python 解析)
- PASS 规范文档 `docs/runtime-data-spec.md`

### PASS T2: 现有运行时数据迁移

- PASS 顶层 `audit-results/` -> `.runtime/audit/aiops-cruise/legacy/`
- PASS 顶层 `infra-baseline/` -> `.runtime/baseline/`
- PASS `alicloud-aiops-cruise/audit-results/` -> `.runtime/audit/aiops-cruise/perceive/`
- PASS `alicloud-aiops-cruise/runbooks/scripts/audit-results/` -> `.runtime/audit/aiops-cruise/runbooks/`
- PASS `alicloud-topo-discovery/scripts/audit-results/` -> `.runtime/audit/topo-discovery/`
- PASS 解除 git 跟踪: `git rm -r --cached infra-baseline/`

### PASS T3: 软链接兼容 (旧路径 -> 新路径)

- PASS `audit-results/` -> `.runtime/audit/aiops-cruise/legacy` (顶层)
- PASS `infra-baseline/` -> `.runtime/baseline`
- PASS `alicloud-aiops-cruise/audit-results/` -> `.runtime/audit/aiops-cruise/perceive`
- PASS `alicloud-aiops-cruise/runbooks/scripts/audit-results/` -> `.runtime/audit/aiops-cruise/runbooks`
- PASS `alicloud-topo-discovery/scripts/audit-results/` -> `.runtime/audit/topo-discovery`

### PASS T4: 核心代码改造 (configdrift.sh + baseline-manager.py + LocalBackend)

- PASS `configdrift.sh`: BASELINE_DIR + AUDIT_DIR 改用 RUNTIME_ROOT
- PASS `baseline-manager.py`: --output-dir 默认值改用 RUNTIME_ROOT
- PASS `LocalBackend`: 默认 root_dir 支持 RUNTIME_ROOT 环境变量
- PASS 共享 lib 提供统一解析入口

### PASS T5: __init__.sh + Perceive Agents 改造

- PASS `__init__.sh`: REPORTS_DIR 路径修复 (BUF-003 顺手修复)
- PASS 各 perceive agent 透传 RUNTIME_ROOT
- PASS 旧路径调用仍通过软链接正常工作

### PASS T6: 测试 + 端到端验证 + F8 同步

- PASS 单元测试: `test_sprint18_runtime_root.py` (RUNTIME_ROOT 解析 + 软链接兼容)
- PASS 端到端验证: `configdrift.sh` 用新根目录 + 旧路径 (软链) 都能跑
- PASS F8 同步: SKILL.md Changelog (v1.2.0) + TODO.md 索引

---

## 验证

```bash
# 1. 默认 (无环境变量)
unset ALIYUN_SKILLS_RUNTIME_ROOT
bash alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh
# 预期: 写到 .runtime/audit/aiops-cruise/perceive/...

# 2. 自定义根目录
export ALIYUN_SKILLS_RUNTIME_ROOT=/tmp/test-runtime
bash alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh
# 预期: 写到 /tmp/test-runtime/audit/aiops-cruise/...

# 3. 旧路径仍能工作 (软链接兼容)
ls -la audit-results infra-baseline
# 预期: 都是软链接 -> .runtime/...
```

---

## Self-Review (F1-F8)

- [x] F1: CLI command validation — 兼容旧 --output-dir 路径
- [x] F2: OpenAPI accuracy — N/A (本地文件操作)
- [x] F3: Error handling — 环境变量解析失败时 fallback 到默认 .runtime/
- [x] F4: Safety gates — 软链接不破坏现有调用; 默认 .runtime/ 隐藏
- [x] F5: Link integrity — 共享 lib 路径解析统一
- [x] F6: Content deduplication — 共享 lib 避免每个脚本重复实现
- [x] F7: Cross-skill delegation — runtime_root lib 在 aiops-cruise, 其他 skill 可 source 或 import
- [x] F8: TODO.md 同步 — PASS (本文件 + 索引 + Changelog)

---

## 后续候选 (Sprint 19+)

- [ ] 迁移 `alicloud-gcl-runner-ops` 的 audit-results 路径
- [ ] 迁移 `alicloud-topo-discovery` 的 lib/baseline_git 默认 root_dir
- [ ] 迁移 runbooks 中各脚本的 CACHE_DIR / AUDIT_DIR
- [ ] 提供 `aliyun-skills-cleanup` 命令: 清理 .runtime/ 中过期数据
- [ ] 监控 `.runtime/` 总大小, 超过 1GB 报警
