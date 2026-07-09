---
runbook_id: "10"
scenario: "主机 IO 巡检与根因分析"
version: "1.0.0"
last_updated: "2026-06-14"
trigger: "告警触发（DiskReadIOPS/DiskWriteIOPS/IO wait 异常）/ 人工触发 / 日常巡检 Step 2.8 内检测发现 IO 异常"
risk_level: "低"
execution_time_estimate: "10-20 分钟（单台 ECS）"
---

# 主机 IO 巡检与根因分析

## 1. 场景描述

当 ECS 实例出现磁盘 IO 相关异常时，从云监控层→OS 层→进程级→文件系统层逐层下钻，定位 IO 根因并给出修复建议。聚焦**普通应用服务器**和 **Nginx 服务器**场景。

### [ALERT] 安全铁律

| 红线 | 要求 |
|---|---|
| **任何资源的删除/停止/规格变更** | FAIL 不允许自动执行，报告只出建议 |
| **输出 AK/SK** | FAIL 必须掩码为 `AKID****SKRET` |
| **文件系统修改（mount/tune2fs）** | FAIL 需用户确认后执行 |

**底线**：本 runbook 是纯读（Read-Only）巡检，不执行任何写操作。所有建议需用户确认后执行。

### 适用条件

- ECS 实例处于 Running 状态
- Cloud Assistant Agent 已安装
- 实例为 Linux 操作系统
- 用户通过 `aliyun ecs RunCommand` 执行诊断命令

### 不适用条件

- Windows ECS → 使用不同的诊断工具链
- 容器化应用（ACK/ASK）→ 委托至容器层诊断
- 块存储（NAS/OSS）→ 委托至对应产品诊断

---

## 2. 执行流程

### Phase 0: 前置安全门

```bash
# 1. 凭证预检
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" || { echo "[ERROR] AK_ID 未设置"; exit 1; }
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "[ERROR] AK_SK 未设置"; exit 1; }

# 2. CLI 可用性检查
command -v aliyun >/dev/null 2>&1 || { echo "[ERROR] aliyun CLI 未安装"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq 未安装"; exit 1; }

# 3. API 连通性检查（只读）
aliyun ecs DescribeRegions --RegionId "$ALIBABA_CLOUD_REGION_ID" >/dev/null 2>&1 \
  || { echo "[ERROR] API 连通性检查失败"; exit 1; }

# 4. 确认巡检目标
INSTANCE_ID="{{user.instance_id}}"
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
echo "[INFO] 巡检目标: $INSTANCE_ID | 区域: $REGION"
```

### Phase 1: 云监控确认 IO 异常

#### Step 1.1: 采集 IO 云监控指标

```bash
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)

# 读 IOPS
DISK_READ_IOPS=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskReadIOPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add')

# 写 IOPS
DISK_WRITE_IOPS=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskWriteIOPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add')

# 读吞吐 (MB/s)
DISK_READ_BPS=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskReadBPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add / 1048576')

# 写吞吐 (MB/s)
DISK_WRITE_BPS=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName DiskWriteBPS \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Maximum] | max // 0] | add / 1048576')

# CPU（关联分析）
CPU_UTIL=$(aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 300 \
  --StartTime "$START_TIME" --EndTime "$END_TIME" \
  | jq '[.Datapoints | fromjson | [.[].Average] | add / length // 0]')

echo "[DIAG] 云监控 IO 指标: 读IOPS=$DISK_READ_IOPS 写IOPS=$DISK_WRITE_IOPS 读吞吐=${DISK_READ_BPS}MB/s 写吞吐=${DISK_WRITE_BPS}MB/s CPU=${CPU_UTIL}%"
```

#### Step 1.2: 获取实例信息

```bash
# 获取实例规格和云盘类型
INSTANCE_INFO=$(aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --InstanceIds "[\"$INSTANCE_ID\"]" \
  | jq '.Instances.Instance[0]')
INSTANCE_TYPE=$(echo "$INSTANCE_INFO" | jq -r '.InstanceType')
STATUS=$(echo "$INSTANCE_INFO" | jq -r '.Status')

# 获取云盘列表
DISK_LIST=$(aliyun ecs DescribeDisks \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  | jq '.Disks.Disk[] | {DiskId, DiskName, Size, Status, Category}')

echo "[DIAG] 实例: $INSTANCE_ID ($INSTANCE_TYPE) 状态: $STATUS"
echo "[DIAG] 云盘:"
echo "$DISK_LIST" | jq -r '.[] | "  \(.DiskId) [\(.Category)] \(.Size)GB \(.Status)"'
```

#### Step 1.3: 判定是否需要 OS 层下钻

```bash
# 简单判定：如果 IOPS 或吞吐有异常值，或用户主动要求，进入 OS 层
NEED_OS_INSPECTION=false

# IOPS 阈值参考（根据云盘类型调整）
# cloud_essd PL1: IOPS 上限 50000, 吞吐 350 MB/s
# cloud_efficiency: IOPS 上限 10000, 吞吐 180 MB/s
# 如果云盘类型是 cloud_essd，IOPS > 30000 关注，> 45000 严重
# 如果云盘类型是 cloud_efficiency，IOPS > 7000 关注，> 9000 严重

echo "[DIAG] 云监控 IO 指标采集完成"
echo "[DIAG] 如需 OS 层深度分析，请执行 Phase 2"
```

---

### Phase 2: OS 层诊断（Cloud Assistant 远程执行）

> 通过 `aliyun ecs RunCommand` 在 ECS 内部执行诊断命令。

#### Step 2.1: 一键 IO 诊断

```bash
IO_SCRIPT='#!/bin/bash
echo "=== DISK INFO ==="
lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL 2>/dev/null || fdisk -l 2>/dev/null | head -20

echo ""
echo "=== FILESYSTEM ==="
df -hT / 2>/dev/null

echo ""
echo "=== MOUNT OPTIONS ==="
mount | grep " / " 2>/dev/null

echo ""
echo "=== IOSTAT (5x2s) ==="
iostat -xmd 2 5 2>/dev/null || echo "[WARN] sysstat not installed"

echo ""
echo "=== TOP IO PROCESSES ==="
iotop -b -o -n 1 -d 1 2>/dev/null || echo "[WARN] iotop not installed"

echo ""
echo "=== MEMORY/SWAP ==="
free -h 2>/dev/null
cat /proc/meminfo 2>/dev/null | grep -E "SwapTotal|SwapFree|Dirty|Writeback"

echo ""
echo "=== INODE ==="
df -i / 2>/dev/null

echo ""
echo "=== DMESG OOM ==="
dmesg -T 2>/dev/null | grep -i "oom\|out of memory" | tail -3

echo ""
echo "=== IO SCHEDULER ==="
cat /sys/block/*/queue/scheduler 2>/dev/null
'

ENCODED_SCRIPT=$(echo "$IO_SCRIPT" | base64)

CMD_ID=$(aliyun ecs RunCommand \
  --RegionId "$REGION" \
  --Name "io-inspection" \
  --CommandContent "$ENCODED_SCRIPT" \
  --Type RunShellScript \
  --InstanceId "[\"$INSTANCE_ID\"]" \
  --Timeout 60 | jq -r '.CommandId')

echo "[INFO] 诊断命令已发送: $CMD_ID"

# 等待执行完成
for i in $(seq 1 12); do
  STATUS=$(aliyun ecs DescribeInvocationResults \
    --RegionId "$REGION" \
    --InstanceId "$INSTANCE_ID" \
    --CommandId "$CMD_ID" \
    | jq -r '.Invocation.InvocationResults.InvocationResult[0].InvocationStatus')
  case "$STATUS" in
    Success) echo "[INFO] 诊断命令执行成功"; break ;;
    Failed|Timeout|Cancelled) echo "[ERROR] 诊断命令执行失败: $STATUS"; break ;;
  esac
  sleep 5
done

# 获取输出
IO_OUTPUT=$(aliyun ecs DescribeInvocationResults \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  --CommandId "$CMD_ID" \
  | jq -r '.Invocation.InvocationResults.InvocationResult[0].Output // ""' | base64 -d 2>/dev/null)

echo "$IO_OUTPUT"
```

---

### Phase 3: 根因推理 + 报告

> Agent 对照 `references/inference-rules.md` 中的 ECS-IO-01~06 规则进行根因推理。

#### Step 3.1: IO 根因推理

```markdown
## [IO] 主机 IO 根因推理

| 现象 | 匹配规则 | 推理结论 | 建议 |
|------|----------|----------|------|
| %util>80% + await>10ms | ECS-IO-01 | 云盘 IOPS/吞吐达上限 | 升级云盘类型 |
| kswapd0 IO 高 | ECS-IO-02 | 内存不足导致 swap | 升级内存或优化应用 |
| jbd2/kjournald IO 高 | ECS-IO-03 | 文件系统 journal 延迟 | 切换 xfs 或调整 journal |
| nginx/writer 进程 IO 高 | ECS-IO-04 | 应用日志写入过多 | 优化日志缓冲策略 |
| await 高但 %util 正常 | ECS-IO-05 | IO 调度/文件系统层问题 | 检查调度器和挂载选项 |
| inode 使用率>95% | ECS-IO-06 | inode 耗尽 | 清理小文件或重建文件系统 |
```

#### Step 3.2: 双格式报告输出

**Markdown（给人读）：**

```markdown
══════════════════════════════════════════════════════
  [IO] 主机 IO 巡检报告
══════════════════════════════════════════════════════
  实例: {{user.instance_id}} ({{instance_type}})
  区域: $REGION | 时间: $(date) | 窗口: $START_TIME -> $END_TIME
══════════════════════════════════════════════════════

[STATS] IO 概览
  云盘类型: {{disk_category}} ({{disk_size}}GB)
  读 IOPS: {{disk_read_iops}} / 上限 {{iops_limit}}
  写 IOPS: {{disk_write_iops}} / 上限 {{iops_limit}}
  读吞吐: {{disk_read_bps}} MB/s / 上限 {{throughput_limit}} MB/s
  写吞吐: {{disk_write_bps}} MB/s / 上限 {{throughput_limit}} MB/s
  %util: {{iostat_util}}%
  await: {{iostat_await}}ms

[RESULT] IO 健康度: {{PASS/WARNING/CRITICAL}}

[LINK] 根因推理
  规则: ECS-IO-{{XX}}
  结论: {{根因描述}}
  修复: {{修复建议}}
```

**JSON（持久化到 `audit-results/`）：**

```bash
mkdir -p audit-results/
cat > "audit-results/io-inspection-${INSTANCE_ID}-$(date +%Y%m%dT%H%M%SZ).json" << IO_JSON
{
  "report_id": "io-inspection-${INSTANCE_ID}-$(date +%Y%m%dT%H%M%SZ)",
  "instance_id": "${INSTANCE_ID}",
  "instance_type": "${INSTANCE_TYPE}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenario": "host_io_inspection",
  "runbook_version": "1.0.0",
  "cloud_monitor": {
    "disk_read_iops": ${DISK_READ_IOPS:-0},
    "disk_write_iops": ${DISK_WRITE_IOPS:-0},
    "disk_read_bps": ${DISK_READ_BPS:-0},
    "disk_write_bps": ${DISK_WRITE_BPS:-0}
  },
  "host_inspection": {},
  "findings": []
}
IO_JSON
echo "[RESULT] JSON 报告已持久化到 audit-results/"
```

---

## 3. 阈值速查

| 指标 | Warning | Critical | 来源 |
|------|---------|----------|------|
| %util | > 60% | > 80% | iostat |
| await | > 10ms | > 50ms | iostat |
| SwapUsed | > 0 | > 100MB | free |
| Dirty | > 100MB | > 500MB | /proc/meminfo |
| inode 使用率 | > 80% | > 95% | df -i |
| IOPS (vs 云盘上限) | > 70% | > 85% | CloudMonitor |

---

## 4. Changelog

| 版本 | 日期 | 变更内容 |
|---|---|---|
| 1.0.0 | 2026-06-14 | 初始版本，主机 IO 巡检与根因分析完整流程 |
