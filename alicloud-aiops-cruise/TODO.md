# TODO — alicloud-aiops-cruise 行动追踪清单（主索引）

> [WARN] **强制规则**：
> 1. 每次新增/修改功能后，必须同步更新对应的 Sprint 文件中的状态标记
> 2. 每个 Sprint 的任务细节存放在 `TODO/sprint-{编号}-{名称}.md`，不在本文档展开
> 3. 违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交
>
> **阶段自评**：详见 `references/self-assessment-framework.md`

---

## Phase 0: 基础设施（已完成 10 项）

- [x] **P0-01** 技能重命名（v0.x 旧名 -> 当前正式名，详见 Hotfix 历史）
- [x] **P0-02** 动态基线规范文档 `references/dynamic-baseline.md`
- [x] **P0-03** 架构蓝图文档 `references/architecture-roadmap.md` + Sprint 状态真值表脚本 `scripts/sprint-status-truth-table.py`
- [x] **P0-04** 阈值文档更新 `references/threshold-definitions.md`
- [x] **P0-4** .gitignore 完整性补齐 — 凭证/缓存/报告三类缺口修复; 36项跨 skill 验证 [Sprint 20](TODO/sprint-20-gitignore-complete.md)
- [x] **P0-05** topo-discovery 联动改造
- [x] **P0-06** 交付产物标准 `references/delivery-standards.md`
- [x] **P0-07** 自评估框架 + 阶段追踪文件 + 质量评审流程
- [x] **P0-08** MR-6 代码审查规范（每次脚本变更自动触发 code-reviewer 评审 P0/P1）
- [x] **P0-09** MR-7 Lint 检测规范 + Ruff 配置 + 首次全量扫描修复（从 385 错误降至零）

---

## 当前阶段进度

| 验收项 | 状态 | 关联 Sprint | 优先级 |
|--------|------|------------|--------|
| **S1-D1** Runbook 脚本化 | 完成 | [Sprint 1](TODO/sprint-01-core-scripts.md) | P0 |
| **S1-D2** 动态基线嵌入 | 完成 | [Sprint 3](TODO/sprint-03-baseline.md) | P0 |
| **S1-D3** 预授权白名单 | PASS **完成** | [Sprint 6](TODO/sprint-06-pre-approved-whitelist.md) | P2 |
| **S1-D4** 拓扑渲染联动 | PASS **完成** | [Sprint 4](TODO/sprint-04-topology.md) | P1 |
| **S1-D5** Incident Schema | PASS **完成** | [Sprint 7](TODO/sprint-07-incident-schema.md) | P1 |
| **S1-D6** 交付物标准 | 完成 | Phase 0 | P0 |
| **S1-D7** ACK节点超分检测 | PASS **完成** | [Sprint 5](TODO/sprint-05-limits-overcommit.md) | **P0** |

**进度: 7/7 (100%) | Stage 1: 100% PASS 全部闭环 | Sprint 3 PASS Sprint 4 PASS Sprint 5 PASS Sprint 6 PASS Sprint 7 PASS Sprint 8 PASS Sprint 9 PASS (MVP) | Stage 1 验收通过, 可进入 Stage 2**

### [TEST] 集成测试验证结果（2026-06-06）

**环境**: `cn-hangzhou` / 资源组 `rg-acfmvyfsd4znnoi` (default)

| 脚本 | 耗时 | 发现 | 结果 |
|------|------|------|------|
| daily-health-check | ~3s | **55 个资源** (ECS=5, RDS=10, Redis=9, SLB=11, EIP=6, NAT=1, VPC=2, SG=10, NAS=1) | PASS 发现 3 Critical (RDS磁盘97%+, SLB连接82%) |
| emergency-troubleshoot | ~20s | SLB 健康检查大面积失败 (10个SLB有异常后端) | PASS 根因定位正确 |
| capacity-planning | ~40s | 10 ECS + 26 RDS 趋势采集 | PASS 发现高磁盘率趋势 |
| pre-launch-check | ~40s | 3x 压力模拟 | PASS 大量升配建议 |

**代码质量**: Ruff Lint 零错误 (385->0) | 限速器 Semaphore 5 正常 | 退出码规范通过

---

## Sprint 索引

| 编号 | 名称 | 优先级 | 业务价值 | 依赖 | 状态 |
|------|------|--------|---------|------|------|
| [**1**](TODO/sprint-01-core-scripts.md) | 核心脚本化 | P0 | 巡检速度 50%+ | 无 | PASS 9/9 |
| [**2**](TODO/sprint-02-parallel-cleanup.md) | 并行加速+代码修缮 | P1 | 5min -> 1min | Sprint 1 | PASS 5/6 |
| [**3**](TODO/sprint-03-baseline.md) | 基线完善 | P0 | 双判定降误报 | 无 | PASS **4/4** |
| [**4**](TODO/sprint-04-topology.md) | 拓扑渲染 | P1 | 图+健康叠加 | 无 | PASS **3/3** |
| [**5**](TODO/sprint-05-limits-overcommit.md) | **ACK Limits超分检测+回溯** | **P0** | ACK 作为一等资源巡检 | 无 | PASS **12/12** |
| **6** | 预授权白名单 | P2 | 半自动修复 | Sprint 1 | PASS **8/8** |
| **7** | Incident Schema | P1 | 数据标准化 | 无 | PASS **1/1** |
| **8** | 结果缓存 | P2 | API 减 60% | Sprint 1+2 | PASS **5/5** |
| [**9**](TODO/sprint-09-incident-deploy.md) | Incident 落地 | P3 | 故障可检索 | Sprint 7 | PASS **6/6** (MVP) |
| [**10**](TODO/sprint-10-sls-arms.md) | SLS/ARMS | P2 | 应用层可观测 | 权限 | [ ] 0/3 |
| **11** | ML 升级 | P3 | 精度升 30% | Sprint 3 | PASS **20/20** (STL+Prophet MVP) |
| **12** | 双引擎 | Future | 自治运维 | Sprint 1+6+9 | PASS **5/5** (Stage 2 D1 幂等加固) |
| [**14**](TODO/sprint-14-perf-batch.md) | **性能优化 (batch+缓存+并发)** | **P1** | **总耗时 -50%~85%** | Sprint 1+2+8 | PASS **5/5** (mock 9x 加速) |
| [**15**](TODO/sprint-15-batch-by-dim.md) | **CMS 按 dimension 批量拉取** | **P1** | **API 调用 -98%** | Sprint 14 | PASS **4/4** (mock 50x 加速) |
| [**16**](TODO/sprint-16-baseline-retention.md) | **Baseline Retention + 3 月回溯** | **P2** | **季度审计可回溯 90 天** | BUG-001/002 修复 | PASS **4/4** (9 个单测通过) |
| [**17**](TODO/sprint-17-baseline-resample.md) | **Baseline 重采样能力** | **P2** | **补建/批量补全缺失 baseline** | Sprint 16 | PASS **4/4** (10 个单测通过, 端到端验证通过) |
| [**18**](TODO/sprint-18-runtime-root.md) | **运行时数据统一根目录 (.runtime/)** | **P0** | **集中管理; 软链接兼容; .gitignore 完整** | 无 | PASS **6/6** (含 5 软链接 + .gitignore 增强 + 共享 lib + 端到端验证) |
| [**19**](TODO/sprint-19-runtime-cleanup.md) | **Runtime 清理 + 路径迁移收尾** | **P1** | **消除所有硬编码 audit-results; 提供 cleanup 工具; 防止 .runtime/ 膨胀** | Sprint 18 | PASS **6/6** + P0-2 补漏 6 shell agent |
| [**20**](TODO/sprint-20-gitignore-complete.md) | **.gitignore 完整性补齐 (P0-4)** | **P0** | **凭证/缓存/报告 三类缺口修复; 36 项跨 skill 验证** | 无 | PASS **4/4** |

---

## 依赖关系总图

```
P0 (基座工程)
├── Sprint 1 (4个脚本) ──────-> Sprint 6 (预授权) ──-> Sprint 12 (双引擎)
│                                                            UP
├── Sprint 3 (基线完善) ────-> Sprint 11 (ML升级)              UP
│                                                            UP
├── Sprint 5 (ACK超分) ───── 无依赖，独立推进                  UP
│                                                            UP
├── Sprint 7 (Schema) ───────-> Sprint 9 (Incident) ───────────┘
└── Sprint 20 (.gitignore 补齐) 无依赖，独立推进 (跨 Sprint 18/19 路径迁移)

P1 (独立推进)    Sprint 4 (拓扑)        Sprint 2 (并行) -> Sprint 8 (缓存)
```

---

## Stage 评估速查

| 阶段 | 状态 | 完成项 | 总项 | 进度 |
|------|------|--------|------|------|
| Stage 1 验收项 | 进行中 | 5 | 6 | 83% |
| Stage 2 验收项 | 未开始 | 0 | 6 | 0% |
| Stage 3 验收项 | 未开始 | 0 | 6 | 0% |

> 完整阶段定义见 `references/self-assessment-framework.md`。
> 交付产物标准见 `references/delivery-standards.md`。
> 质量评审流程见 `references/quality-review-process.md`。

---

## Hotfix 记录

### PASS HF-2026-06-07-01 — ConfigDrift Agent 修复 (BUG-001 + BUG-002)

> **发现时间**: 2026-06-07 19:25
> **修复时间**: 2026-06-07 19:32
> **优先级**: P0 (Agent 实际不工作)
> **触发场景**: 第一次跑 `configdrift.sh` 巡检时发现
> **关联文件**: `alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh`

| Bug | 严重度 | 描述 | 修复 |
|-----|:-----:|------|------|
| **BUG-001** | High | `SKILLS_DIR`/`BASELINE_DIR`/`AUDIT_DIR` 路径多走一层 `../` — Agent 永远找不到 baseline，输出 `status: skipped` | `SKILLS_DIR` 改为 `${AIOPS_DIR}/../`，`BASELINE_DIR` 改为 `${SKILLS_DIR}/infra-baseline`，`AUDIT_DIR` 改为 `${SKILLS_DIR}/audit-results` |
| **BUG-002** | Medium | 调 `baseline-manager.py` 时传 `--baseline/--current/--output` 与脚本真实接受的 `--output-dir/--region/--diff` 不匹配，参数传递错位 | 重写调用为 `python3 baseline-manager.py --output-dir <DIR> --region <REGION> --diff` |

**修复后验证**（`bash alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh`）：

```json
{
  "agent": "configdrift",
  "status": "completed",
  "region": "cn-hangzhou",
  "drift_count": 0,
  "drift_items": [],
  "note": "no drift detected"
}
```

**回归风险**:
- `__init__.sh` 仍存在类似路径 bug（`REPORTS_DIR="${SCRIPT_DIR}/../../../audit-results"` 多走一层）— **未在本次修复范围**，下次巡检时单独处理
- `__init__.sh --mode configdrift` 调用入口已可正常工作（configdrift.sh 自身接受 `--output-file` 参数）