# Sprint 17 — Baseline 重采样能力

> **状态**: ✅ 4/4
> **优先级**: P2 (运维效率 + 历史回溯补全)
> **业务价值**: 季度审计前批量补全缺失 baseline; 故障复盘时快速补建"那时的状态"
> **依赖**: Sprint 16 (--compare-with) + LocalBackend.get_latest/get_by_date
> **开始日期**: 2026-06-07
> **完成日期**: 2026-06-07
> **需求来源**: 2026-06-07 19:44 用户决策 — "提供 baseline 重采样的能力, 允许指定日期生成采样数据"
> **关联文件**:
> - `alicloud-topo-discovery/scripts/baseline-manager.py` (新增 --resample 模式)
> - `alicloud-topo-discovery/scripts/lib/baseline_local.py` (新增 copy_baseline / list_gaps 工具)
> - `alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh` (--resample 透传)
> - `alicloud-topo-discovery/tests/test_sprint17_resample.py` (新增测试)

---

## 背景

Sprint 16 实现了 `--compare-with <date>` 让 configdrift 能与任意历史 baseline 对比。
但实际生产中, baseline 目录往往**不连续**:
- 周末/节假日 cron 未跑, 缺失 5-7 天 baseline
- 账号切换/权限问题导致 1-2 周空窗
- 季度审计前需要 90 天完整数据

> **重采样 (resample) 语义**: 用某个已知 baseline (源) 生成目标日期的 baseline 数据, **不真正扫描云上资源**。
> 这是"补建"而非"采集", 适用于**演示/审计/复盘**场景, 真实生产应依赖实际扫描。

---

## 重采样 4 种模式

### 模式 1: 复制式重采样 (核心)

```bash
python3 baseline-manager.py \
    --output-dir <DIR> \
    --resample \
    --from-baseline 2026-06-07 \
    --as-of 2026-05-15
```

**语义**: 把 `2026-06-07` 的 baseline 复制为 `2026-05-15`, 资源数据完全相同, 仅 `generated_at` 时间戳改为 `2026-05-15T00:00:00Z`。

**适用场景**:
- 故障复盘: 5/15 出了事故, 但当天没跑 baseline → 用 5/20 (或更近的) 复制补建, 然后 `configdrift --compare-with 2026-05-15` 复现当时差异
- 季度审计: 补全缺失日期, 让 `--compare-with` 任意日期都能跑

### 模式 2: 触发式重采样 (可选, V2)

```bash
python3 baseline-manager.py \
    --output-dir <DIR> \
    --region <REGION> \
    --resample \
    --as-of 2026-05-15 \
    --trigger-scan
```

**语义**: 真正调 `topo-scan.sh` 扫描一次云上资源, 但 `generated_at` 写 `2026-05-15T00:00:00Z`。

**风险**: 资源当前状态 ≠ 历史状态, "伪造"了过去某天的真实数据。**仅限审计演示**, 不应用于故障复盘。

**优先级**: P3 (本期可不做, 留待 Sprint 18+)

### 模式 3: 区间批量重采样

```bash
python3 baseline-manager.py \
    --output-dir <DIR> \
    --resample \
    --from-baseline 2026-06-07 \
    --as-of-range 2026-05-01:2026-05-31
```

**语义**: 在 `2026-05-01` 到 `2026-05-31` 之间的**每一天**都生成一份复制 (源 = 2026-06-07)。

**适用场景**: 一键补全整月缺失 baseline。

### 模式 4: 智能补全 (--fill-gaps)

```bash
python3 baseline-manager.py \
    --output-dir <DIR> \
    --resample \
    --from-baseline latest \
    --as-of-range 2026-05-01:2026-06-07 \
    --fill-gaps
```

**语义**: 在区间内**只为已存在目录外的缺失日期**生成, 不覆盖已有 baseline。

**适用场景**: 日常运维, 定期跑一次, 自动把零星缺失补齐。

---

## 任务清单

### ✅ T1: baseline_local.py 工具方法

**目标**: 在 `LocalBackend` 类上增加 3 个工具方法。

**接口设计**:
```python
class LocalBackend:
    def copy_baseline(self, src_date: str, dst_date: str) -> Optional[Path]:
        """复制 src_date 目录为 dst_date, 返回新路径或 None."""

    def list_gaps(self, start: str, end: str) -> List[str]:
        """返回区间内缺失的日期列表 (ISO 格式)."""

    def fill_gaps(self, src_date: str, start: str, end: str) -> List[str]:
        """用 src_date 复制填充区间内所有缺失日期, 返回实际创建的日期列表."""
```

**实现要点**:
- `copy_baseline`: `shutil.copytree(src, dst)`, 复制 manifest.json + inventory.json
- 校验 `dst_date` 不与已有目录冲突 (除非加 `--force` 标志)
- `list_gaps`: 在 `[start, end]` 区间枚举日期, 过滤 `self.list_baselines()`
- `fill_gaps`: 复用 `copy_baseline`, 遍历 `list_gaps` 结果

### ✅ T2: baseline-manager.py 集成 `--resample` 模式

**目标**: 在主 CLI 暴露 `--resample` 子命令。

**接口设计**:
```bash
# 模式 1: 复制
python3 baseline-manager.py --output-dir <DIR> --resample \
    --from-baseline 2026-06-07 --as-of 2026-05-15

# 模式 3: 区间批量
python3 baseline-manager.py --output-dir <DIR> --resample \
    --from-baseline 2026-06-07 --as-of-range 2026-05-01:2026-05-31

# 模式 4: 智能补全
python3 baseline-manager.py --output-dir <DIR> --resample \
    --from-baseline latest --as-of-range 2026-05-01:2026-06-07 --fill-gaps
```

**实现要点**:
- 互斥检查: `--resample` 与 `--diff` 互斥 (重采样和漂移检测是不同阶段)
- 必填参数: `--resample` 模式下, `--from-baseline` + (`--as-of` 或 `--as-of-range`) 至少一组
- 校验: `--from-baseline=latest` 时用 `backend.get_latest()` 解析
- 输出: 列出创建/跳过的日期
- `--force` 标志: 允许覆盖已存在目录 (默认保护)

### ✅ T3: configdrift.sh 透传 `--resample` 链路

**目标**: 让 ConfigDrift Agent 支持"重采样 + 对比"一键完成。

**接口设计**:
```bash
# 重采样到 5/15, 立即与 5/15 对比
bash configdrift.sh --resample --from-baseline latest --as-of 2026-05-15 \
    --compare-with 2026-05-15

# 实际场景: 不带 --compare-with 时, 重采样完成后不立即对比
bash configdrift.sh --resample --from-baseline latest \
    --as-of-range 2026-05-01:2026-05-31 --fill-gaps
```

**实现要点**:
- 新增 `--resample` / `--from-baseline` / `--as-of` / `--as-of-range` / `--fill-gaps` / `--force` 参数
- 互斥: `--resample` 模式下, `--compare-with` 可选 (默认不对比)
- JSON 报告 `mode` 字段: `"resample"` 或 `"diff"` (替代隐式推断)

### ✅ T4: 测试用例

**目标**: 覆盖 4 个模式 + 边界场景。

**测试文件**: `alicloud-topo-discovery/tests/test_sprint17_resample.py`

**测试场景** (预计 8-10 个):
| ID | 场景 | 验证 |
|----|------|------|
| T1 | `copy_baseline` 正常 | 源目录被完整复制, manifest.json 内容一致 |
| T2 | `copy_baseline` 已存在目标 (无 --force) | 返回 None, 不覆盖 |
| T3 | `copy_baseline` --force 覆盖 | 返回新路径, 内容更新 |
| T4 | `list_gaps` 区间内缺失日期 | 返回缺失日期列表 |
| T5 | `list_gaps` 区间内全有 | 返回空列表 |
| T6 | `fill_gaps` 补全缺失 | 返回创建列表, 文件存在 |
| T7 | CLI 模式 1 复制 | exit=0, 目标日期 baseline 存在 |
| T8 | CLI 模式 3 区间 | exit=0, 区间内 N 个日期都创建 |
| T9 | CLI 模式 4 fill-gaps | 已有日期不被覆盖, 缺失日期被创建 |
| T10 | CLI --resample 与 --diff 互斥 | exit=2, 明确错误信息 |

**端到端验证**:
```bash
# 1. 模式 1
python3 baseline-manager.py --output-dir <DIR> --resample \
    --from-baseline 2026-06-07 --as-of 2026-05-15
# 预期: <DIR>/2026-05-15/manifest.json 存在

# 2. configdrift 链路
bash configdrift.sh --resample --from-baseline latest \
    --as-of 2026-05-15 --compare-with 2026-05-15
# 预期: drift_count=0 (重采样自对比)
```

---

## 安全与风险

| 风险 | 缓解 |
|------|------|
| 误用重采样"伪造"生产审计数据 | 报告 JSON 增加 `mode: resample` + `source_baseline` 字段, 透明可追溯 |
| `--force` 误覆盖真实扫描数据 | 默认拒绝覆盖, 需显式 `--force`; force 时打印 WARN |
| 重采样消耗大量存储 (90 天 × 50KB = 4.5MB, 仍可接受) | 监控 `infra-baseline/` 目录大小, > 100MB 时报警 |
| 模式 2 (触发式) 误用 | **本期不实现**, 留待 Sprint 18+ 评估; 避免"伪造时间戳"陷阱 |

---

## 与 Sprint 16 的协同

```
Sprint 16: --compare-with <date>    ← 读: 历史 baseline
Sprint 17: --resample --as-of <date> ← 写: 补建历史 baseline
组合用法: 重采样补全 → 对比验证
```

**典型工作流**:
```bash
# 第 1 步: 智能补全 90 天区间
python3 baseline-manager.py --output-dir <DIR> --resample \
    --from-baseline latest --as-of-range $(date -v-90d '+%Y-%m-%d'):$(date '+%Y-%m-%d') \
    --fill-gaps

# 第 2 步: 对比 90 天前 vs 现在
bash configdrift.sh --compare-with $(date -v-90d '+%Y-%m-%d')
```

---

## Self-Review (F1-F8)

- [x] F1: CLI command validation — 4 个新参数, 互斥检查已规划
- [x] F2: OpenAPI accuracy — N/A (不调 OpenAPI, 纯本地文件操作)
- [x] F3: Error handling — T4 包含不存在源/已存在目标/无效日期 等错误场景
- [x] F4: Safety gates — 默认拒绝覆盖, --force 显式 opt-in; 重采样透明记录在报告中
- [x] F5: Link integrity — 关联文件清单已列
- [x] F6: Content deduplication — 复用 `LocalBackend.list_baselines()` 等已有方法
- [x] F7: Cross-skill delegation — baseline-manager.py 在 topo-discovery, configdrift.sh 在 aiops-cruise, 跨 skill 委托符合规范
- [x] F8: TODO.md 同步 — ✅ (本文件 + TODO.md 索引)

---

## 验证

```bash
# 单测
cd alicloud-topo-discovery && python3 -m pytest tests/test_sprint17_resample.py -v
# 预期: 10/10 PASS

# 端到端
bash alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh \
    --resample --from-baseline latest --as-of 2026-05-15 \
    --compare-with 2026-05-15
# 预期: 补建 + 0 漂移 (与自身对比)
```

---

## 后续候选 (Sprint 18+)

- [ ] **模式 2 触发式重采样**: 真正扫描 + 伪造时间戳, 评估审计价值与误用风险
- [ ] **重采样策略配置化**: 支持 `--strategy=copy|interpolate|extrapolate` 三种策略
- [ ] **跨账号 baseline 同步**: 多个账号的 baseline 汇总到统一目录
- [ ] **baseline 健康度指标**: 检测 baseline 是否过期 (资源定义过时) / 损坏 (manifest 解析失败)
