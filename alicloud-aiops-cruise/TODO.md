# TODO — alicloud-aiops-cruise 行动追踪清单（主索引）

> ⚠️ **强制规则**：
> 1. 每次新增/修改功能后，必须同步更新对应的 Sprint 文件中的状态标记
> 2. 每个 Sprint 的任务细节存放在 `TODO/sprint-{编号}-{名称}.md`，不在本文档展开
> 3. 违反后果：Post-Update Self-Review 的 F8 检查不通过，不得提交
>
> **阶段自评**：详见 `references/self-assessment-framework.md`

---

## Phase 0: 基础设施（已完成 7 项）

- [x] **P0-01** 技能重命名: `alicloud-link-cruise` → `alicloud-aiops-cruise`
- [x] **P0-02** 动态基线规范文档 `references/dynamic-baseline.md`
- [x] **P0-03** 架构蓝图文档 `references/architecture-roadmap.md`
- [x] **P0-04** 阈值文档更新 `references/threshold-definitions.md`
- [x] **P0-05** topo-discovery 联动改造
- [x] **P0-06** 交付产物标准 `references/delivery-standards.md`
- [x] **P0-07** 自评估框架 + 阶段追踪文件 + 质量评审流程
- [x] **P0-08** MR-6 代码审查规范（每次脚本变更自动触发 code-reviewer 评审 P0/P1）
- [x] **P0-09** MR-7 Lint 检测规范 + Ruff 配置 + 首次全量扫描修复（从 385 错误降至零）

---

## 当前阶段进度

| 验收项 | 状态 | 关联 Sprint | 优先级 |
|--------|------|------------|--------|
| **S1-D1** Runbook 脚本化 | ✅ 完成 | [Sprint 1](TODO/sprint-01-core-scripts.md) | P0 |
| **S1-D2** 动态基线嵌入 | ✅ 完成 | [Sprint 3](TODO/sprint-03-baseline.md) | P0 |
| **S1-D3** 预授权白名单 | ⬜ 待做 | Sprint 5 → 依赖 Sprint 1 | P2 |
| **S1-D4** 拓扑渲染联动 | ⬜ 待做 | [Sprint 4](TODO/sprint-04-topology.md) | P1 |
| **S1-D5** Incident Schema | ⬜ 待做 | Sprint 6 | P1 |
| **S1-D6** 交付物标准 | ✅ 完成 | Phase 0 | P0 |

**进度: 4/6 (67%) | 可并行推进: Sprint 4 + Sprint 6**

### 🧪 集成测试验证结果（2026-06-06）

**环境**: `cn-hangzhou` / 资源组 `rg-acfmvyfsd4znnoi` (default)

| 脚本 | 耗时 | 发现 | 结果 |
|------|------|------|------|
| daily-health-check | ~3s | **55 个资源** (ECS=5, RDS=10, Redis=9, SLB=11, EIP=6, NAT=1, VPC=2, SG=10, NAS=1) | ✅ 发现 3 Critical (RDS磁盘97%+, SLB连接82%) |
| emergency-troubleshoot | ~20s | SLB 健康检查大面积失败 (10个SLB有异常后端) | ✅ 根因定位正确 |
| capacity-planning | ~40s | 10 ECS + 26 RDS 趋势采集 | ✅ 发现高磁盘率趋势 |
| pre-launch-check | ~40s | 3x 压力模拟 | ✅ 大量升配建议 |

**代码质量**: Ruff Lint 零错误 (385→0) | 限速器 Semaphore 5 正常 | 退出码规范通过

---

## Sprint 索引

| 编号 | 名称 | 优先级 | 业务价值 | 依赖 | 状态 |
|------|------|--------|---------|------|------|
| [**1**](TODO/sprint-01-core-scripts.md) | 核心脚本化 | P0 | 巡检速度 50%+ | 无 | ✅ 9/9 |
| [**2**](TODO/sprint-02-parallel-cleanup.md) | 并行加速+代码修缮 | P1 | 5min → 1min | Sprint 1 | ✅ 5/6 |
| [**3**](TODO/sprint-03-baseline.md) | 基线完善 | P0 | 双判定降误报 | 无 | ≈ 1/4 |
| [**4**](TODO/sprint-04-topology.md) | 拓扑渲染 | P1 | 图+健康叠加 | 无 | ≈ 1/3 |
| **5** | 预授权白名单 | P2 | 半自动修复 | Sprint 1 | ⬜ 0/5 |
| **6** | Incident Schema | P1 | 数据标准化 | 无 | ⬜ 0/1 |
| **7** | 结果缓存 | P2 | API 减 60% | Sprint 1+2 | ⬜ 0/3 |
| **8** | Incident 落地 | P3 | 故障可检索 | Sprint 6 | ⬜ 0/4 |
| **9** | SLS/ARMS | P2 | 应用层可观测 | 权限 | ⬜ 0/3 |
| **10** | ML 升级 | P3 | 精度升 30% | Sprint 3 | ⬜ 0/4 |
| **11** | 双引擎 | Future | 自治运维 | Sprint 1+5+8 | ⬜ 0/4 |

---

## 依赖关系总图

```
P0 (基座工程)
├── Sprint 1 (4个脚本) ──────→ Sprint 5 (预授权) ──→ Sprint 11 (双引擎)
│                                                            ↑
├── Sprint 3 (基线完善) ────→ Sprint 10 (ML升级)              ↑
│                                                            ↑
└── Sprint 6 (Schema) ────────→ Sprint 8 (Incident) ──────────┘

P1 (独立推进)    Sprint 4 (拓扑)        Sprint 2 (并行) → Sprint 7 (缓存)
P2 (按序启动)    Sprint 9 (SLS/ARMS)
```

---

## Stage 评估速查

| 阶段 | 状态 | 完成项 | 总项 | 进度 |
|------|------|--------|------|------|
| Stage 1 验收项 | 进行中 | 4 | 6 | 67% |
| Stage 2 验收项 | 未开始 | 0 | 6 | 0% |
| Stage 3 验收项 | 未开始 | 0 | 6 | 0% |

> 完整阶段定义见 `references/self-assessment-framework.md`。
> 交付产物标准见 `references/delivery-standards.md`。
> 质量评审流程见 `references/quality-review-process.md`。