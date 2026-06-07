# Sprint 16 — Baseline Retention 与 3 个月回溯能力

> **状态**: ✅ 4/4
> **优先级**: P2 (运维合规 + 历史回溯)
> **业务价值**: 季度审计/复盘可回溯 90 天内任意时间点的拓扑状态
> **依赖**: Sprint 5 (topo 联动) + BUG-001/002 修复完成 (HF-2026-06-07-01)
> **开始日期**: 2026-06-07
> **完成日期**: 2026-06-07
> **关联文件**:
> - `alicloud-aiops-cruise/SKILL.md` (Baseline Retention 策略小节)
> - `alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh` (头部注释 + --compare-with 透传)
> - `alicloud-aiops-cruise/references/perceive-design.md` (§4.3 cron 模板)
> - `alicloud-topo-discovery/scripts/baseline-manager.py` (--compare-with 参数 + main() 处理)
> - `alicloud-topo-discovery/scripts/lib/baseline_local.py` (LocalBackend.get_by_date)
> - `alicloud-topo-discovery/tests/test_sprint16_compare_with.py` (9 个测试场景)

---

## 背景

ConfigDrift Agent 在 2026-06-07 完成 BUG-001/002 修复后已可正常工作。
但实际生产环境需要：
1. 持续累积每日 baseline（否则永远只有"今天"可对比）
2. 90 天保留窗口（满足季度审计）
3. **任意历史时间点 vs 当前**的对比能力（baseline-manager.py 当前只支持 vs 最新）

> 决策（2026-06-07 19:33 用户确认）：保留 `retention_days=90` 默认值，便于 3 个月拓扑演进回溯

---

## 任务清单

### ✅ T1: baseline-manager.py 增强 `--compare-with <date>`

**目标**: 支持对比指定历史 baseline，而不仅是"最新"。

**接口设计**:
```bash
python3 baseline-manager.py \
    --output-dir <DIR> \
    --region <REGION> \
    --diff \
    --compare-with 2026-05-15    # 新增：与 5/15 的 baseline 对比
```

**实现要点**:
- ✅ 默认行为不变（`--compare-with` 缺省 = `latest`）
- ✅ 校验 date 目录存在（`infra-baseline/<date>/manifest.json`）
- ✅ 复用现有 `_compute_diff` 逻辑
- ✅ 新增 `LocalBackend.get_by_date(date_str)` 方法
- ✅ 不存在日期 → exit=2 + 明确错误 + 列出可用 baselines
- ✅ 无效格式 → exit=2 + Invalid date format 错误

### ✅ T2: configdrift.sh 透传 `--compare-with`

**目标**: Agent 层暴露参数。

**实现**:
- ✅ 参数解析 `--compare-with <YYYY-MM-DD>`
- ✅ 透传到 `baseline-manager.py`
- ✅ JSON 报告增加 `compared_with` 字段（自动从 stdout 提取 `(vs <label>)` 或透传参数）
- ✅ 日志开头打印 `COMPARE_WITH: <date> (历史 baseline)` 或 `COMPARE_WITH: latest (默认)`

**目标**: Agent 层暴露参数。

**接口**:
```bash
bash configdrift.sh --compare-with 2026-05-15 --output-file ./out.json
```

**实现要点**:
- 解析 `--compare-with` 参数
- 透传到 `baseline-manager.py`
- JSON 报告增加 `compared_with` 字段

### ✅ T3: Cron 配置模板

**目标**: 把"每日 toposcan + 每周 retention 清理"沉淀为可直接复制的配置。

**落地**:
- ✅ `references/perceive-design.md` §4.3 新增 Baseline Retention 调度小节
- ✅ 包含 3 条 cron 规则:
  1. 每日 02:00 — `baseline-manager.py` 累积新 baseline
  2. 每周日 03:00 — `--apply-retention --retention-days 90` 清理
  3. 每周一 09:00 — `configdrift.sh --compare-with <7天前>` 跑周对比
- ✅ macOS/Linux `date` 命令差异已加 fallback 注释

**目标**: 把"每日 toposcan + 每周 retention 清理"沉淀为可直接复制的配置。

**示例**:
```cron
# 每日 02:00 — 累积 baseline
0 2 * * * cd /path/to/aliyun-skills/alicloud-aiops-cruise && \
  bash scripts/agents/perceive/infra/toposcan.sh 2>&1 | logger -t perceive-topo

# 每周日 03:00 — 清理过期 baseline（>90 天）
0 3 * * 0 cd /path/to/aliyun-skills/alicloud-topo-discovery/scripts && \
  python3 baseline-manager.py --output-dir /path/to/infra-baseline \
  --apply-retention --retention-days 90 2>&1 | logger -t baseline-cleanup
```

**落地**:
- 在 `references/perceive-design.md` §4.2 中补充
- 在 SKILL.md 引用

### ✅ T4: 测试用例 — `--compare-with` 行为

**目标**: 验证历史对比能力。

**测试文件**: `alicloud-topo-discovery/tests/test_sprint16_compare_with.py`

**9 个测试场景** (全部 PASSED):
| ID | 场景 | 验证 |
|----|------|------|
| T1 | `get_by_date` 正常返回 | 返回目录存在 manifest.json |
| T2 | `get_by_date` 不存在日期 | 返回 None (不抛异常) |
| T3 | `get_by_date` 无效格式 | 返回 None (不抛异常) |
| T4 | `parse_args` 接受 `--compare-with` | args.compare_with 正确填充 |
| T5 | `parse_args` 缺省值 | args.compare_with = None (向后兼容) |
| T6 | `_compute_diff` ADDED | 正确识别新增资源 (数量 + ID) |
| T7 | `_compute_diff` REMOVED | 正确识别删除资源 |
| T8 | CLI 不存在日期 | exit=2 + "No baseline found for date" |
| T9 | CLI 无效格式 | exit=2 + "Invalid date format" |

**测试运行**:
```bash
$ cd alicloud-topo-discovery && python3 -m pytest tests/test_sprint16_compare_with.py -v
============================== 9 passed in 4.70s ==============================
```

**端到端验证** (实跑 configdrift.sh):
- ✅ 默认 (vs latest) → 显示 `(vs 2026-06-07)`，无漂移
- ✅ `--compare-with 2026-06-07` (与自身对比) → 0 漂移
- ✅ `--compare-with 2025-01-01` (不存在) → exit=2 + 列出可用 baseline
- ✅ `--compare-with 2026/06/07` (无效格式) → exit=2 + Invalid date format

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| `infra-baseline/` 目录膨胀（90 天 × 50KB = 4.5MB） | 影响可忽略；若 1000+ 资源账号考虑压缩存储 |
| apply-retention 误删仍在使用的 baseline | 启动前 7 天内 baseline 加保护标记（V2） |
| 跨账号 baseline 比对（多账号场景） | 不在 Sprint 16 范围；未来独立 Sprint |

---

## Self-Review

- [x] F1: CLI command validation — N/A（增强的是 Python 脚本 + 透传参数）
- [x] F2: OpenAPI accuracy — N/A
- [x] F3: Error handling — T4 明确测试 "不存在的日期" 错误路径
- [x] F4: Safety gates — N/A（纯读操作）
- [x] F5: Link integrity — 关联文件已声明
- [x] F6: Content deduplication — 复用 `_compute_diff` 现有逻辑
- [x] F7: Cross-skill delegation — baseline-manager.py 在 alicloud-topo-discovery，configdrift.sh 在 alicloud-aiops-cruise，跨 skill 委托符合规范
- [x] F8: TODO.md 同步 — ✅（本文件 + 索引 + Hotfix 记录）

---

## 验证

```bash
# T1 + T2 端到端验证
bash alicloud-aiops-cruise/scripts/agents/perceive/infra/configdrift.sh \
    --compare-with 2026-06-07 \
    --output-file /tmp/drift-test.json
# 预期: 返回与最新 baseline（自身）的 diff，应为 0 项
```
