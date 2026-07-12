---
name: ticket-integration
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# Ticket Integration — 工单集成指南

> 目的: 定义 `ticket_generator.sh` 产出的工单 JSON 格式, 并提供将工单转换为
> Jira 问题或其他 ITSM 系统的集成方案。

---

## 一、工单 JSON 格式

`ticket_generator.sh` 输出每个工单为独立的 JSON 文件, 命名格式为
`ticket-{timestamp}-{seq}.json`, 置于 `.runtime/tickets/` 目录下。

### 1.1 字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ticket_id` | string | 是 | 工单唯一 ID, 格式: `ticket-{YYYYMMDDTHHMMSS}-{NNN}` |
| `severity` | enum | 是 | 严重级别: `CRITICAL` / `HIGH` |
| `skill` | string | 是 | 归属产品 skill, 如 `alicloud-ecs-ops` |
| `finding` | object | 是 | 发现详情 (见 §1.2) |
| `suggested_action` | string | 是 | 建议操作描述 (中文) |
| `timestamp` | string | 是 | 工单生成时间, ISO-8601 格式 |
| `git_commit` | string | 是 | 生成时 SKILLS_DIR 的 HEAD commit |

### 1.2 `finding` 子结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `domain` | string | 分析域: `infra` / `cost` / `security` / `advisor` |
| `description` | string | 问题描述 (发现详情) |
| `resource_id` | string | 阿里云资源 ID (实例 ID / 安全组 ID 等) |
| `resource_type` | string | 资源类型: `ECS` / `RDS` / `SLB` / `Redis` / `SG` 等 |

### 1.3 完整示例

```json
{
  "ticket_id": "ticket-20260712T103000Z-001",
  "severity": "CRITICAL",
  "skill": "alicloud-ecs-ops",
  "finding": {
    "domain": "infra",
    "description": "ECS 实例 i-bp1xxxx CPU 使用率连续 15 分钟超过 95%",
    "resource_id": "i-bp1xxxx",
    "resource_type": "ECS"
  },
  "suggested_action": "请检查 infra 域: ECS 实例 CPU 使用率连续 15 分钟超过 95%",
  "timestamp": "2026-07-10T10:30:00Z",
  "git_commit": "a67aa1cd362204ba0ad3305589de3c563ff5b145"
}
```

---

## 二、技能 (skill) 字段映射优先级

`ticket_generator.sh` 按以下优先级确定 `skill` 字段:

1. **source_agent 精确匹配**: 如果 fusion report 的 finding 包含 `source_agent`
   字段, 优先查表匹配:

   | source_agent | 映射 skill |
   |-------------|------------|
   | healthcruise | `alicloud-ecs-ops` |
   | toposcan | `alicloud-vpc-ops` |
   | configdrift | `alicloud-ecs-ops` |
   | costwatch | `alicloud-bss-ops` |
   | securityscan | `alicloud-sas-ops` |
   | audittrail | `alicloud-actiontrail-ops` |
   | advisorscan | `alicloud-advisor-ops` |

2. **domain 模糊匹配**: 若 `source_agent` 不在映射表中, 按 `domain` 域匹配:

   | domain | 映射 skill |
   |--------|-----------|
   | infra | `alicloud-ecs-ops` |
   | cost | `alicloud-bss-ops` |
   | security | `alicloud-sas-ops` |
   | advisor | `alicloud-advisor-ops` |

3. **默认**: 以上均不匹配时, 默认使用 `alicloud-ecs-ops`。

---

## 三、Jira 集成

### 3.1 字段映射

| 工单 JSON 字段 | Jira 字段 | 说明 |
|----------------|-----------|------|
| `severity` | `priority` | CRITICAL -> Blocker; HIGH -> Critical |
| `skill` | `components` | 映射为 Jira 组件名 |
| `finding.description` | `description` | 问题描述 |
| `suggested_action` | `customfield` (建议操作) | 可选自定义字段 |
| `finding.resource_id` | `labels` 或 `customfield` | 添加 `resource-{id}` 标签 |
| `timestamp` | `created` | 自动填充 (由 API 侧维护) |
| `git_commit` | `customfield` (版本追溯) | 可选自定义字段 |
| `ticket_id` | `summary` prefix | 作为标题前缀 |

### 3.2 Severity -> Priority 映射

| 工单 `severity` | Jira Priority | 响应要求 |
|-----------------|---------------|---------|
| CRITICAL | Blocker | 1 小时内响应, 4 小时内修复 |
| HIGH | Critical | 4 小时内响应, 24 小时内修复 |

### 3.3 使用 Jira REST API 创建问题

```bash
#!/usr/bin/env bash
# 示例: 将工单 JSON 转换为 Jira 问题
# 依赖: curl, jq, 环境变量 JIRA_URL / JIRA_TOKEN

JIRA_URL="${JIRA_URL:?必填}"
JIRA_TOKEN="${JIRA_TOKEN:?必填}"
TICKET_FILE="$1"

[[ -f "$TICKET_FILE" ]] || { echo "文件不存在: $TICKET_FILE"; exit 1; }

# 读取工单
ticket_json=$(cat "$TICKET_FILE")
severity=$(echo "$ticket_json" | jq -r '.severity')
description=$(echo "$ticket_json" | jq -r '.finding.description')
skill=$(echo "$ticket_json" | jq -r '.skill')
action=$(echo "$ticket_json" | jq -r '.suggested_action')
resource_id=$(echo "$ticket_json" | jq -r '.finding.resource_id')
ticket_id=$(echo "$ticket_json" | jq -r '.ticket_id')

# Severity -> Priority
case "$severity" in
    CRITICAL) priority="Blocker" ;;
    HIGH)     priority="Critical" ;;
    *)        priority="Major" ;;
esac

# 构造 Jira issue payload
jira_payload=$(jq -n \
    --arg summary "[${ticket_id}] ${description:0:80}" \
    --arg priority "$priority" \
    --arg description "## 问题描述\n\n${description}\n\n## 建议操作\n\n${action}\n\n## 资源\n\n- 资源 ID: ${resource_id}\n- Skill: ${skill}\n- 工单 ID: ${ticket_id}" \
    --arg component "$skill" \
    '{
        "fields": {
            "project": {"key": "DOPS"},
            "issuetype": {"name": "Task"},
            "summary": $summary,
            "description": $description,
            "priority": {"name": $priority},
            "components": [{"name": $component}]
        }
    }'
)

# 创建 issue
curl -s -X POST "${JIRA_URL}/rest/api/2/issue" \
    -H "Authorization: Basic ${JIRA_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$jira_payload" | jq .
```

### 3.4 使用 MCP 创建问题

若已集成 Jira MCP Server, 可使用以下工具创建:

```json
{
  "tool": "create_dops_issue",
  "params": {
    "summary": "[ticket-20260712T103000Z-001] ECS CPU 使用率超标",
    "description": "ECS 实例 i-bp1xxxx CPU 使用率连续 15 分钟超过 95%\n\n建议操作: 请检查 infra 域: ECS 实例 CPU 使用率",
    "operator": "aiops-agent",
    "labels": "主动巡检,CRITICAL"
  }
}
```

对应 MCP 工具: `create_dops_issue` (在 aliyun-skills 生态中使用时, 需对接
DOPS Jira 项目)。

---

## 四、批量处理

### 4.1 批量创建 Jira 问题

```bash
# 将 .runtime/tickets/ 下所有工单批量创建为 Jira 问题
for ticket in .runtime/tickets/ticket-*.json; do
    [[ -f "$ticket" ]] || continue
    echo "处理: $(basename "$ticket")"
    bash create_jira_issue.sh "$ticket" || echo "[WARN] 创建失败: $ticket"
done
```

### 4.2 统计摘要

```bash
# 统计工单分布
echo "=== 工单统计 ==="
echo "CRITICAL: $(jq -r 'select(.severity=="CRITICAL") | .ticket_id' .runtime/tickets/ticket-*.json | wc -l)"
echo "HIGH:     $(jq -r 'select(.severity=="HIGH") | .ticket_id' .runtime/tickets/ticket-*.json | wc -l)"
echo ""
echo "按 Skill:"
jq -r '.skill' .runtime/tickets/ticket-*.json | sort | uniq -c | sort -rn
```

---

## 五、与 AIOps Cruise 流水线集成

```text
Perceive Agents ──→ Fusion Report ──→ Ticket Generator ──→ Jira / ITSM
      (C0)               (C1)               (D3)
```

典型调用顺序:

```bash
# 1. 感知层巡检
bash perceive/__init__.sh --fusion

# 2. 根因分析 (可选)
bash fusion/root_cause_engine.sh --report audit/aiops-cruise/fusion-report-*.json

# 3. 生成工单
bash fusion/ticket_generator.sh \
    --fusion-report  audit/aiops-cruise/fusion-report-*.json \
    --anomaly-report audit/aiops-cruise/root-cause-*.json
```

---

## 六、.gitignore

`.runtime/tickets/` 目录已由 `runtime_root.sh` 机制自动排除 (所有 `.runtime/`
子目录在 `.gitignore` 中忽略)。无需手动添加。

---

## 七、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-07-12 | 初始版本 |