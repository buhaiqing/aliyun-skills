# GCL 智能告警闭环 (Smart Alert Loop) — 使用指南

## 概述

智能告警闭环（Phase 7）是 GCL 架构的增强组件，实现**模式驱动的动态告警**替代传统的**阈值告警**。

### 核心改进

| 维度 | 传统告警 (Phase 3-B/4) | 智能告警 (Phase 7) |
|-----|---------------------|------------------|
| 触发条件 | Safety-Fail-Rate > 5% | 同一资源30分钟内Safety失败2次 |
| 告警精度 | 高误报（单点波动） | 低误报（模式确认） |
| 响应动作 | 仅告警，人工处理 | **自动降级** + 告警 |
| 恢复机制 | 人工恢复 | **自动恢复**（1小时后） |

## 组件架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GCL Smart Alert Loop                             │
│                                                                          │
│  ┌─────────────────────┐        ┌─────────────────────────────────────┐ │
│  │  gcl_runner.py      │        │  gcl_smart_alarm_engine.py          │ │
│  │  ─────────────────  │        │  ─────────────────────────          │ │
│  │  --adaptive mode    │◄──────►│  • Pattern Detector (模式识别)      │ │
│  │  • Generate traces  │  reads │  • Dynamic Threshold (动态阈值)     │ │
│  │  • Check degr state │  state │  • Auto-Degradation (自动降级)      │ │
│  └─────────────────────┘        └─────────────────────────────────────┘ │
│           │                                    │                         │
│           ▼                                    ▼                         │
│    ┌──────────────┐                    ┌──────────────┐                 │
│    │ Trace Store  │                    │ Degradation  │                 │
│    │ (JSON files) │                    │ State (JSON) │                 │
│    └──────────────┘                    └──────────────┘                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 联动流程

```
Step 1: gcl_runner 执行操作
    ├─ 生成 trace 文件 (gcl-trace-*.json)
    └─ 如启用 --adaptive，读取降级状态调整 max_iter

Step 2: Smart Alarm Engine 定期分析
    ├─ 扫描 trace 目录
    ├─ 检测风险模式 (resource_safety_repeated, region_safety_burst...)
    ├─ 应用自动降级 (写入 degradation state)
    └─ 恢复过期降级

Step 3: 后续 gcl_runner 操作
    └─ 自动感知降级，使用降低后的 max_iter
```

## 快速开始

### 1. 检测风险模式（dry-run）

```bash
# 分析最近30分钟的trace，仅检测不降级
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --window-minutes 30 \
  --dry-run
```

### 2. 启用自动降级

```bash
# 检测风险模式并执行自动降级
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --window-minutes 30 \
  --apply-degradation
```

### 3. 使用自适应模式的GCL Runner

```bash
# 运行GCL时启用自适应max_iter
python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
  --skill alicloud-ecs-ops \
  --op DeleteInstance \
  --command "aliyun ecs DeleteInstance --InstanceId i-bp1..." \
  --adaptive
```

### 4. 检查降级状态

```bash
# 查看当前降级资源并恢复过期降级
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --check-degradation \
  --restore-expired
```

### 5. 设置CMS智能告警

```bash
# 创建CMS告警规则监控智能引擎输出
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_cms_setup.py \
  --contact-group gcl-oncall \
  --region cn-hangzhou
```

## 与 gcl_runner 的联动使用

### 完整联动示例

```bash
#!/bin/bash
# smart-alert-demo.sh — 演示 Smart Alert 与 Runner 的联动

RESOURCE_ID="i-bp1xxxxxxxxxxxxxx"
TRACE_DIR=".runtime/audit/gcl-runner-ops"

# Step 1: 正常执行（max_iter=2）
echo "=== Step 1: Normal execution ==="
python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
  --skill alicloud-ecs-ops \
  --op DescribeInstanceAttribute \
  --command "aliyun ecs DescribeInstanceAttribute --InstanceId $RESOURCE_ID --RegionId cn-hangzhou" \
  --adaptive \
  --output-dir "$TRACE_DIR"

# Step 2: 模拟多次失败（生成SAFETY_FAIL traces）
echo "=== Step 2: Simulate failures ==="
for i in 1 2; do
  # 这里模拟 SAFETY_FAIL 的 trace
  # 实际场景中可能是真实的API失败
  echo "Failure $i"
done

# Step 3: 运行智能告警引擎检测并降级
echo "=== Step 3: Detect and degrade ==="
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --trace-dir "$TRACE_DIR" \
  --window-minutes 30 \
  --apply-degradation \
  --restore-expired

# Step 4: 再次执行（此时max_iter可能被降级为1）
echo "=== Step 4: Adaptive execution (degraded) ==="
python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
  --skill alicloud-ecs-ops \
  --op DescribeInstanceAttribute \
  --command "aliyun ecs DescribeInstanceAttribute --InstanceId $RESOURCE_ID --RegionId cn-hangzhou" \
  --adaptive \
  --output-dir "$TRACE_DIR"
```

### Adaptive 模式输出示例

当 `--adaptive` 检测到资源被降级时，输出会显示：

```
[ADAPTIVE] max_iter adjusted: 2 → 1
[ADAPTIVE] Reason: Resource i-bp1xxxxxxxxxxxxxx downgraded due to 资源级Safety反复失败 (restore at 2026-06-13T10:30:00Z)
[GCL] skill=alicloud-ecs-ops op=DescribeInstanceAttribute status=PASS iter=1 [ADAPTIVE]
[GCL] trace: .runtime/audit/gcl-runner-ops/gcl-trace-20260613-083000-abc123.json
```

## 风险模式定义

当前支持4种风险模式：

| 模式ID | 名称 | 条件 | 动作 | 恢复时间 |
|-------|-----|------|-----|---------|
| `resource_safety_repeated` | 资源级Safety反复失败 | 同一资源30分钟内≥2次Safety失败 | max_iter降至1 | 60分钟 |
| `resource_hallucination_repeated` | 资源级Hallucination持续 | 同一资源60分钟内≥2次Hallucination失败 | max_iter降至1 | 30分钟 |
| `region_safety_burst` | Region级Safety集中爆发 | 同一Region15分钟内≥5次Safety失败 | 触发巡检 | 手动 |
| `skill_wide_failure` | Skill级全面失败 | 同一Skill20分钟内≥10次失败 | 告警维护者 | 手动 |

## 状态文件

降级状态存储在：
- 默认路径: `${ALIYUN_SKILLS_RUNTIME_ROOT}/gcl-degradation-state.json`
- Fallback: `.runtime/metrics/alicloud-gcl-runner-ops/gcl-degradation-state.json` (legacy: `alicloud-gcl-runner-ops/.runtime/`)

状态文件示例：

```json
{
  "downgraded_resources": {
    "i-bp1xxxxxxxxxx": {
      "resource_id": "i-bp1xxxxxxxxxx",
      "skill": "alicloud-ecs-ops",
      "original_max_iter": 2,
      "current_max_iter": 1,
      "downgraded_at": "2026-06-13T08:30:00Z",
      "auto_restore_at": "2026-06-13T09:30:00Z",
      "reason": "资源级Safety反复失败",
      "triggered_by": "resource_safety_repeated"
    }
  },
  "hot_regions": {
    "cn-hangzhou": {
      "region": "cn-hangzhou",
      "detected_at": "2026-06-13T08:25:00Z",
      "occurrence_count": 5,
      "affected_skills": ["alicloud-ecs-ops"]
    }
  }
}
```

## 集成到CI/CD

### Cron Pipeline 建议

```bash
#!/bin/bash
# gcl-smart-pipeline.sh

TRACE_DIR=".runtime/audit/gcl-runner-ops"

# Step 1: 运行智能告警引擎（检测+降级）
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --trace-dir "$TRACE_DIR" \
  --window-minutes 30 \
  --apply-degradation \
  --restore-expired \
  --output-json .runtime/smart-alert-report.json

# Step 2: 推送自定义指标到CMS（用于告警）
# 注意：这里需要扩展gcl_passrate_reporter.py来推送智能引擎指标

# Step 3: 更新CMS告警规则
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_cms_setup.py \
  --region cn-hangzhou
```

## 与现有GCL组件的关系

```
Phase 1 (GCL Spec) → Phase 2 (Runner) → Phase 3-B (Phantom Alarm)
                                           ↓
Phase 6 (Hallucination Detection) → Phase 7 (Smart Alert Loop) ← 你在这里
                                           ↓
                              Phase 4 (Pass-rate Metrics)
```

智能告警闭环**增强但不替代**现有组件：
- 保留所有Phase 1-6功能
- 新增模式检测层
- 动态调整max_iter
- 自动恢复降级

## 测试

### 运行单元测试

```bash
# 运行 Smart Alarm Engine 的单元测试 (79 tests)
python -m unittest alicloud-gcl-runner-ops.scripts.gcl_smart_alarm_test -v

# 运行集成测试 (12 tests)
python -m unittest alicloud-gcl-runner-ops.scripts.gcl_smart_alarm_integration_test -v

# 运行所有测试
python -m unittest discover -s alicloud-gcl-runner-ops/scripts -p "*_test.py" -v
```

### 集成测试覆盖

| 测试类别 | 测试数量 | 说明 |
|---------|---------|------|
| **I1: End-to-End Workflow** | 3 | 完整流程测试（检测→降级→恢复） |
| **I2: Adaptive Mode** | 3 | Runner adaptive 模式集成 |
| **I3: Trace Format** | 2 | Trace 格式兼容性测试 |
| **I4: State File** | 2 | 状态文件兼容性测试 |
| **I5: Multi-Resource** | 2 | 多资源场景测试 |

### 手动验证联动

```bash
# 1. 创建测试 trace 目录
mkdir -p .runtime/audit/gcl-runner-ops

# 2. 创建一个模拟的 SAFETY_FAIL trace
cat > .runtime/audit/gcl-runner-ops/gcl-trace-test-fail.json << 'EOF'
{
  "skill": "alicloud-ecs-ops",
  "request": "test",
  "rubric_version": "1.0.0",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "iterations": [{
    "iter": 1,
    "generator": {
      "command": "aliyun ecs TestOp --InstanceId i-bp1testxxxxxxxxx --RegionId cn-hangzhou",
      "exit_code": 1,
      "stdout": "",
      "stderr": "Error"
    },
    "critic": {
      "scores": {"safety": 0.0},
      "blocking": true
    },
    "decision": "SAFETY_FAIL"
  }],
  "final": {"status": "SAFETY_FAIL", "iter": 1}
}
EOF

# 3. 运行引擎（dry-run 模式）
python3 alicloud-gcl-runner-ops/scripts/gcl_smart_alarm_engine.py \
  --trace-dir .runtime/audit/gcl-runner-ops \
  --window-minutes 60 \
  --dry-run

# 4. 检查 Runner 是否能读取状态
python3 -c "
import sys
sys.path.insert(0, 'alicloud-gcl-runner-ops/scripts')
import gcl_runner as runner

# 模拟降级状态
import json
from pathlib import Path
state_path = Path('.runtime/gcl-degradation-state.json')
state_path.parent.mkdir(exist_ok=True)
state_path.write_text(json.dumps({
    'downgraded_resources': {
        'i-bp1testxxxxxxxxx': {
            'resource_id': 'i-bp1testxxxxxxxxx',
            'current_max_iter': 1,
            'auto_restore_at': '2099-01-01T00:00:00Z'
        }
    }
}))

# 测试 adaptive 模式
import os
os.environ['ALIYUN_SKILLS_RUNTIME_ROOT'] = '.runtime'
max_iter, reason = runner.get_adaptive_max_iter(
    'alicloud-ecs-ops',
    'aliyun ecs TestOp --InstanceId i-bp1testxxxxxxxxx --RegionId cn-hangzhou',
    2
)
print(f'Adaptive max_iter: {max_iter}')
print(f'Reason: {reason}')
"
```

## 故障排查

### 问题：降级未生效

检查清单：
1. 确认`--adaptive`参数已传递给gcl_runner.py
2. 检查资源ID是否能从命令中正确提取
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'alicloud-gcl-runner-ops/scripts')
   import gcl_runner as runner
   print(runner._extract_resource_id('alicloud-ecs-ops', 'your-command'))
   "
   ```
3. 查看degradation-state.json是否存在且可写
   ```bash
   cat .runtime/gcl-degradation-state.json | python3 -m json.tool
   ```

### 问题：误报过多

调整策略：
1. 增加`window_minutes`（如30→60）
2. 增加`min_occurrences`阈值（如2→3）
3. 在gcl_smart_alarm_engine.py中修改RISK_PATTERNS

### 问题：恢复未发生

检查：
1. 确认`--restore-expired`参数已传递
2. 检查系统时间是否正确
3. 查看degradation-state.json中的`auto_restore_at`字段
   ```bash
   python3 -c "
   import json
   from datetime import datetime, timezone
   state = json.load(open('.runtime/gcl-degradation-state.json'))
   for rid, info in state.get('downgraded_resources', {}).items():
       restore_at = info.get('auto_restore_at', 'N/A')
       now = datetime.now(timezone.utc).isoformat()
       print(f'{rid}: restore_at={restore_at}, now={now}')
   "
   ```

### 问题：Runner 和 Engine 状态不一致

检查环境变量：
```bash
# 确保两者使用相同的 RUNTIME_ROOT
echo $ALIYUN_SKILLS_RUNTIME_ROOT

# 检查状态文件路径
python3 -c "
import sys; sys.path.insert(0, 'alicloud-gcl-runner-ops/scripts')
import gcl_runner as runner
import gcl_smart_alarm_engine as engine
print('Runner state path:', runner._get_degradation_state_path())
print('Engine state path:', engine.get_degradation_state_path())
"
```

## CLI 参考

### gcl_smart_alarm_engine.py

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `--trace-dir` | Path | `${RUNTIME_ROOT}/audit/gcl-runner-ops` | GCL trace 文件目录 |
| `--window-minutes` | int | 30 | 分析时间窗口（分钟） |
| `--apply-degradation` | flag | False | 检测到风险模式时执行自动降级 |
| `--check-degradation` | flag | False | 仅检查当前降级状态 |
| `--restore-expired` | flag | False | 恢复已过期的降级 |
| `--dry-run` | flag | False | 模拟执行，不实际修改状态 |
| `--output-json` | Path | None | 将结果保存为 JSON 文件 |

### gcl_runner.py（新增参数）

| 参数 | 说明 |
|-----|------|
| `--adaptive` | 启用自适应 max_iter，根据智能告警引擎的降级状态动态调整 |

## Python API 参考

### 在代码中使用 Engine

```python
from gcl_smart_alarm_engine import (
    load_traces,
    match_risk_pattern,
    apply_degradation,
    DEFAULT_RISK_PATTERNS
)

# 加载 traces
traces = load_traces(Path("./traces"), window_minutes=30)

# 检测风险模式
for pattern in DEFAULT_RISK_PATTERNS:
    matches = match_risk_pattern(traces, pattern)
    for match in matches:
        print(f"Detected: {match['pattern_name']} for {match['group_key']}")
```

### 在代码中使用 Runner Adaptive 模式

```python
from gcl_runner import get_adaptive_max_iter

# 获取自适应 max_iter
base_max_iter = 2
command = "aliyun ecs DescribeInstanceAttribute --InstanceId i-bp1..."
max_iter, reason = get_adaptive_max_iter(
    "alicloud-ecs-ops",
    command,
    base_max_iter
)

if reason:
    print(f"Resource degraded: {reason}")
```

## 扩展开发

### 添加新的风险模式

```python
# 在 gcl_smart_alarm_engine.py 的 DEFAULT_RISK_PATTERNS 中添加
{
    "id": "my_custom_pattern",
    "name": "自定义模式",
    "description": "描述",
    "min_occurrences": 3,
    "group_by": "resource_id",  # 或 "region", "skill"
    "decisions": {"SAFETY_FAIL"},
    "window_minutes": 45,
    "severity": "P1",
    "action": "downgrade_resource_max_iter",
    "action_params": {"target_max_iter": 1, "restore_after_minutes": 90},
}
```

### 添加新的资源 ID 提取模式

```python
# 在 gcl_smart_alarm_engine.py 和 gcl_runner.py 的 RESOURCE_PATTERNS 中添加
RESOURCE_PATTERNS = {
    # ... existing patterns ...
    "alicloud-new-product-ops": r"--NewResourceId\s+['"]?(nr-[a-z0-9]+)['"]?",
```

## 参考

- 架构设计: `docs/gcl-spec.md` §12
- 告警标准: `alicloud-cms-ops/references/gcl-cms-alarm-guide.md`
- Token效率: `docs/token-efficiency-strategy.md`
- GCL Runner: `alicloud-gcl-runner-ops/scripts/README.md`
