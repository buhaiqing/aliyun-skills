# SecOps 安全组巡检与分析

## 概述

本模块从安全运营（SecOps）视角，提供安全组的**全面巡检、变更追踪、暴露面分析和合规评估**能力，补充 `sg-compliance-check.md` 的基础检测。

## 能力矩阵

| 能力 | 触发关键词 | 复杂度 | 风险 |
|------|-----------|--------|------|
| 安全组资产盘点 | "安全组资产", "SG盘点" | Low | None |
| 暴露面分析 | "暴露面", "互联网暴露" | Medium | None |
| 规则变更追踪 | "谁改了安全组", "变更历史" | Medium | None |
| 安全组与ECS关联分析 | "安全组关联", "规则覆盖率" | Medium | None |
| 出入站规则统计 | "规则统计", "流量分析" | Low | None |
| 规则冲突检测 | "规则冲突", "冗余规则" | Medium | None |
| 安全组基线合规评估 | "安全组合规", "SOC审计" | Medium | None |

---

## 1. 安全组资产盘点

### 触发条件
- "盘点所有安全组"
- "安全组资产清单"
- "SG inventory"

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 凭证有效 | Env vars | Non-empty AK/SK | HALT |
| 区域有效 | `aliyun ecs DescribeRegions` | Region supported | Suggest valid region |

### Execution — CLI

```bash
REGION="{{user.region}}"

# 获取所有安全组
aliyun ecs DescribeSecurityGroups \
  --RegionId "$REGION" \
  --output cols=SecurityGroupId,SecurityGroupName,VpcId,Description,CreationTime \
  rows=SecurityGroups.SecurityGroup[].{SecurityGroupId,SecurityGroupName,VpcId,Description,CreationTime}

# 统计安全组总数
aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=TotalCount rows=TotalCount
```

### 巡检输出格式

| 字段 | 说明 |
|------|------|
| SecurityGroupId | 安全组ID |
| SecurityGroupName | 安全组名称 |
| VpcId | 所属VPC |
| Description | 描述/用途 |
| CreationTime | 创建时间 |
| RuleCount | 规则数量（入站+出站） |

### 关联数据收集

```bash
# 获取每个安全组的规则数量
for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  IN_COUNT=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
  OUT_COUNT=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction egress \
    --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
  echo "$sg_id: Ingress=$IN_COUNT, Egress=$OUT_COUNT"
done
```

---

## 2. 暴露面分析（互联网暴露检测）

### 触发条件
- "暴露面分析"
- "互联网暴露"
- "公网暴露检测"

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 凭证有效 | Env vars | Non-empty | HALT |
| 区域有效 | `aliyun ecs DescribeRegions` | Region supported | HALT |

### Execution — CLI

```bash
REGION="{{user.region}}"
HIGH_RISK_PORTS="22|23|25|3389|3306|1433|5432|6379|27017|11211|9200|11210"

# 遍历所有安全组，检测入站规则
for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  SG_NAME=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
    --SecurityGroupId "$sg_id" \
    --output cols=SecurityGroupName rows=SecurityGroups.SecurityGroup[0].SecurityGroupName)
  
  # 检测0.0.0.0/0入站规则
  EXPOSURES=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --NicType internet 2>/dev/null | \
    jq -r --arg ports "$HIGH_RISK_PORTS" '
      .Permissions.Permission[] | 
      select(.SourceCidrIp == "0.0.0.0/0") | 
      select(.Policy == "accept") |
      "\(.IpProtocol) \(.PortRange) (\(.Description // "N/A"))"
    ' 2>/dev/null)
  
  if [ -n "$EXPOSURES" ]; then
    echo "=== $SG_NAME ($sg_id) ==="
    echo "$EXPOSURES"
    echo ""
  fi
done
```

### 暴露面风险等级

| 风险等级 | 条件 | 说明 |
|----------|------|------|
| **Critical** | 0.0.0.0/0 + 高危端口(22/3389/数据库) | 立即修复 |
| **High** | 0.0.0.0/0 + 中危端口(80/443) | 建议收紧 |
| **Medium** | 大范围CIDR + 敏感端口 | 评估必要性 |
| **Low** | 特定IP + 业务端口 | 可接受 |

### 高危端口定义

| 端口 | 服务 | 风险描述 |
|------|------|----------|
| 22 | SSH | 暴力破解风险 |
| 23 | Telnet | 明文传输，已废弃 |
| 25 | SMTP | 邮件中继滥用 |
| 3389 | RDP | Windows暴力破解 |
| 3306 | MySQL | 数据库直接暴露 |
| 1433 | SQL Server | 数据库直接暴露 |
| 5432 | PostgreSQL | 数据库直接暴露 |
| 6379 | Redis | 未授权访问风险 |
| 27017 | MongoDB | 未授权访问风险 |
| 11211 | Memcached | 未授权访问风险 |
| 9200 | Elasticsearch | 未授权访问风险 |

---

## 3. 规则变更追踪（需要ActionTrail）

### 触发条件
- "谁改了安全组"
- "安全组变更历史"
- "安全组审计"

### 依赖能力
- `alicloud-actiontrail-ops` 用于查询API操作历史

### Execution — CLI

```bash
REGION="{{user.region}}"
START_TIME="{{user.start_time}}"  # ISO格式: 2026-01-01T00:00:00Z
END_TIME="{{user.end_time}}"      # ISO格式: 2026-06-01T00:00:00Z

# 查询安全组相关API操作
aliyun actiontrail DescribeTrails --RegionId "$REGION"

# 查询审计事件（需要先配置ActionTrail）
aliyun actiontrail LookupEvents \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --RegionId "$REGION" \
  --ServiceName Ecs \
  --EventType ApiCall \
  --Output cols=EventTime,EventSource,EventName,UserIdentity.UserName,RequestParameters.SecurityGroupId \
  rows=Events.Event[].{EventTime,EventSource,EventName,UserName:UserIdentity.UserName,SecurityGroupId:RequestParameters.SecurityGroupId}
```

### 变更事件类型

| EventName | 说明 |
|-----------|------|
| AuthorizeSecurityGroup | 添加入站规则 |
| RevokeSecurityGroup | 删除入站规则 |
| AuthorizeSecurityGroupEgress | 添加出站规则 |
| RevokeSecurityGroupEgress | 删除出站规则 |
| CreateSecurityGroup | 创建安全组 |
| DeleteSecurityGroup | 删除安全组 |

### 安全组变更报告格式

| 字段 | 说明 |
|------|------|
| EventTime | 变更时间 |
| EventName | 变更操作 |
| UserName | 操作者 |
| SecurityGroupId | 目标安全组 |
| SourceCidrIp | 源IP（规则变更时） |
| PortRange | 端口范围（规则变更时） |

---

## 4. 安全组与ECS关联分析

### 触发条件
- "安全组关联分析"
- "规则覆盖率"
- "哪些实例用这个安全组"

### Execution — CLI

```bash
REGION="{{user.region}}"

# 方法1：按安全组查询关联的ECS实例
SECURITY_GROUP_ID="{{user.security_group_id}}"

aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --SecurityGroupId "$SECURITY_GROUP_ID" \
  --output cols=InstanceId,InstanceName,Status,VpcId,ZoneId \
  rows=Instances.Instance[].{InstanceId,InstanceName,Status,VpcId,ZoneId}

# 方法2：统计每个VPC的安全组使用情况
echo "=== VPC安全组使用统计 ==="
for vpc_id in $(aliyun vpc DescribeVpcs --RegionId "$REGION" \
  --output cols=VpcId rows=Vpcs.Vpc[].VpcId 2>/dev/null | tail -n +2); do
  SG_COUNT=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
    --VpcId "$vpc_id" \
    --output cols=TotalCount rows=TotalCount 2>/dev/null)
  INSTANCE_COUNT=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
    --VpcId "$vpc_id" \
    --output cols=TotalCount rows=TotalCount 2>/dev/null)
  echo "VPC: $vpc_id | 安全组: $SG_COUNT | 实例: $INSTANCE_COUNT"
done
```

### 关联分析输出

| 字段 | 说明 |
|------|------|
| SecurityGroupId | 安全组ID |
| InstanceId | 关联的ECS实例ID |
| InstanceName | 实例名称 |
| InstanceStatus | 实例状态 |
| VpcId | 所属VPC |
| ZoneId | 可用区 |

### 覆盖率计算

```bash
# 计算安全组规则覆盖率（假设每台服务器需要SSH+RDP+业务端口）
TOTAL_INSTANCES=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
  --output cols=TotalCount rows=TotalCount)
SG_MANAGED_INSTANCES=$(aliyun ecs DescribeInstances --RegionId "$REGION" \
  --SecurityGroupId "$SECURITY_GROUP_ID" \
  --output cols=TotalCount rows=TotalCount)

echo "安全组管理覆盖率: $SG_MANAGED_INSTANCES / $TOTAL_INSTANCES"
```

---

## 5. 出入站规则统计

### 触发条件
- "规则统计"
- "出入站分析"
- "安全组规则分布"

### Execution — CLI

```bash
REGION="{{user.region}}"

echo "=== 安全组规则统计 ==="
echo "安全组ID | 入站规则数 | 出站规则数 | 0.0.0.0/0入站 | 0.0.0.0/0出站"

for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  
  # 入站规则统计
  IN_TOTAL=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
  IN_PUBLIC=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --NicType internet 2>/dev/null | \
    jq -r '.Permissions.Permission[] | select(.SourceCidrIp == "0.0.0.0/0") | select(.Policy == "accept")' 2>/dev/null | wc -l)
  
  # 出站规则统计
  OUT_TOTAL=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction egress \
    --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
  OUT_PUBLIC=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction egress \
    --NicType internet 2>/dev/null | \
    jq -r '.Permissions.Permission[] | select(.DestCidrIp == "0.0.0.0/0") | select(.Policy == "accept")' 2>/dev/null | wc -l)
  
  echo "$sg_id | $IN_TOTAL | $OUT_TOTAL | $IN_PUBLIC | $OUT_PUBLIC"
done
```

### 统计维度

| 维度 | 说明 |
|------|------|
| 入站规则数 | ingress方向规则总数 |
| 出站规则数 | egress方向规则总数 |
| 0.0.0.0/0入站 | 公网入站允许规则数 |
| 0.0.0.0/0出站 | 公网出站允许规则数 |
| 内网互通规则 | 同VPC内安全组互通规则 |

---

## 6. 规则冲突与冗余检测

### 触发条件
- "规则冲突"
- "冗余规则"
- "规则优化"

### Execution — CLI

```bash
REGION="{{user.region}}"

# 检测完全重复的规则
echo "=== 重复规则检测 ==="
for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  
  # 获取入站规则
  INGRESS_RULES=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --NicType internet 2>/dev/null | \
    jq -r '.Permissions.Permission[] | "\(.IpProtocol)|\(.PortRange)|\(.SourceCidrIp)"' 2>/dev/null)
  
  # 统计重复
  echo "$INGRESS_RULES" | sort | uniq -c | awk '$1 > 1 {print "Duplicate: " $0}'
done
```

### 冲突类型

| 冲突类型 | 检测规则 | 影响 |
|----------|----------|------|
| 完全重复 | 相同协议+端口+源IP | 浪费规则额度 |
| 包含冲突 | 宽范围包含窄范围 | 优先级问题 |
| 过度宽松 | 0.0.0.0/0 + 全端口 | 安全风险 |
| 矛盾规则 | allow + deny同源 | 取决于优先级 |

### 规则优化建议

```bash
# 生成优化建议报告
echo "=== 安全组规则优化建议 ==="
for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  
  SG_NAME=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
    --SecurityGroupId "$sg_id" \
    --output cols=SecurityGroupName rows=SecurityGroups.SecurityGroup[0].SecurityGroupName)
  
  # 检测可优化的规则
  OVERLY_PERMISSIVE=$(aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --NicType internet 2>/dev/null | \
    jq -r '.Permissions.Permission[] | 
      select(.SourceCidrIp == "0.0.0.0/0") | 
      select(.Policy == "accept") |
      select(.PortRange == "-1/-1") |
      "\(.SecurityGroupRuleId) 全端口开放"
    ' 2>/dev/null)
  
  if [ -n "$OVERLY_PERMISSIVE" ]; then
    echo "[$SG_NAME] 建议优化:"
    echo "$OVERLY_PERMISSIVE"
    echo ""
  fi
done
```

---

## 7. 安全组基线合规评估

### 触发条件
- "安全组合规"
- "SOC审计"
- "等保合规"

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 凭证有效 | Env vars | Non-empty | HALT |
| 区域有效 | `aliyun ecs DescribeRegions` | Region supported | HALT |

### 合规检查项

| 检查项 | 合规要求 | 不合规条件 | 风险等级 |
|--------|----------|------------|----------|
| SSH访问控制 | 仅特定IP可访问22端口 | 0.0.0.0/0 开放22端口 | Critical |
| RDP访问控制 | 仅特定IP可访问3389端口 | 0.0.0.0/0 开放3389端口 | Critical |
| 数据库访问控制 | 仅应用服务器可访问DB端口 | 0.0.0.0/0 开放DB端口 | Critical |
| 管理端口收紧 | 22/3389不对公网开放 | 0.0.0.0/0 开放管理端口 | Critical |
| 出站控制 | 建议限制出站目的地 | 完全放行出站0.0.0.0/0 | Medium |
| 最小权限 | 按需开放端口和IP | 开放不必要端口 | Medium |
| 规则审计 | 定期审查规则必要性 | 存在长期未使用规则 | Low |

### 执行 — CLI

```bash
REGION="{{user.region}}"
SCORE=100
CRITICAL_ISSUES=()
HIGH_ISSUES=()
MEDIUM_ISSUES=()

echo "=== 安全组合规评估报告 ==="
echo "评估时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Region: $REGION"
echo ""

for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
  --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  
  SG_NAME=$(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" \
    --SecurityGroupId "$sg_id" \
    --output cols=SecurityGroupName rows=SecurityGroups.SecurityGroup[0].SecurityGroupName)
  
  # 检查入站规则
  aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId "$sg_id" --RegionId "$REGION" --Direction ingress \
    --NicType internet 2>/dev/null | \
    jq -r '.Permissions.Permission[] | 
      select(.Policy == "accept") |
      "\(.IpProtocol)|\(.PortRange)|\(.SourceCidrIp)"
    ' 2>/dev/null | while read rule; do
    
    IP_PROTOCOL=$(echo "$rule" | cut -d'|' -f1)
    PORT_RANGE=$(echo "$rule" | cut -d'|' -f2)
    SOURCE_CIDR=$(echo "$rule" | cut -d'|' -f3)
    
    # 检查SSH公网开放
    if [ "$SOURCE_CIDR" = "0.0.0.0/0" ] && echo "$PORT_RANGE" | grep -qE "^(22|22/22)"; then
      echo "[CRITICAL] $SG_NAME: SSH(22) 对公网开放"
      SCORE=$((SCORE - 20))
      CRITICAL_ISSUES+=("$SG_NAME: SSH公网开放")
    fi
    
    # 检查RDP公网开放
    if [ "$SOURCE_CIDR" = "0.0.0.0/0" ] && echo "$PORT_RANGE" | grep -qE "^(3389|3389/3389)"; then
      echo "[CRITICAL] $SG_NAME: RDP(3389) 对公网开放"
      SCORE=$((SCORE - 20))
      CRITICAL_ISSUES+=("$SG_NAME: RDP公网开放")
    fi
    
    # 检查数据库端口公网开放
    if [ "$SOURCE_CIDR" = "0.0.0.0/0" ] && echo "$PORT_RANGE" | grep -qE "^(3306|3306/3306|1433|1433/1433|5432|5432/5432|6379|6379/6379|27017|27017/27017)"; then
      echo "[CRITICAL] $SG_NAME: 数据库端口($PORT_RANGE) 对公网开放"
      SCORE=$((SCORE - 15))
      CRITICAL_ISSUES+=("$SG_NAME: 数据库端口公网开放")
    fi
    
    # 检查全端口开放
    if [ "$SOURCE_CIDR" = "0.0.0.0/0" ] && [ "$PORT_RANGE" = "-1/-1" ]; then
      echo "[HIGH] $SG_NAME: 全端口(-1/-1) 对公网开放"
      SCORE=$((SCORE - 10))
      HIGH_ISSUES+=("$SG_NAME: 全端口开放")
    fi
  done
done

echo ""
echo "=== 合规评分 ==="
echo "总分: $SCORE / 100"

if [ $SCORE -ge 90 ]; then
  echo "等级: 优秀"
elif [ $SCORE -ge 70 ]; then
  echo "等级: 良好"
elif [ $SCORE -ge 50 ]; then
  echo "等级: 需改进"
else
  echo "等级: 不合格"
fi

echo ""
if [ ${#CRITICAL_ISSUES[@]} -gt 0 ]; then
  echo "=== Critical 问题 (立即修复) ==="
  printf '%s\n' "${CRITICAL_ISSUES[@]}"
fi

if [ ${#HIGH_ISSUES[@]} -gt 0 ]; then
  echo ""
  echo "=== High 问题 (尽快修复) ==="
  printf '%s\n' "${HIGH_ISSUES[@]}"
fi
```

### 合规报告输出格式

| 字段 | 说明 |
|------|------|
| 评估时间 | ISO 8601格式 |
| 评估Region | 区域信息 |
| 合规评分 | 0-100分 |
| 合规等级 | 优秀/良好/需改进/不合格 |
| Critical问题 | 立即修复项 |
| High问题 | 尽快修复项 |
| Medium问题 | 计划修复项 |

### 修复建议生成

```bash
# 针对检测到的问题生成修复建议
generate_remediation() {
  local issue_type="$1"
  local sg_id="$2"
  local rule_id="$3"
  
  case "$issue_type" in
    "SSH_PUBLIC")
      echo "建议: 限制22端口访问源IP，例如:"
      echo "aliyun ecs RevokeSecurityGroup --SecurityGroupId $sg_id --SecurityGroupRuleId $rule_id"
      echo "aliyun ecs AuthorizeSecurityGroup --SecurityGroupId $sg_id --Permissions '[{\"IpProtocol\":\"tcp\",\"PortRange\":\"22/22\",\"SourceCidrIp\":\"<企业IP>/32\"}]'"
      ;;
    "RDP_PUBLIC")
      echo "建议: 限制3389端口访问源IP，例如:"
      echo "aliyun ecs RevokeSecurityGroup --SecurityGroupId $sg_id --SecurityGroupRuleId $rule_id"
      echo "aliyun ecs AuthorizeSecurityGroup --SecurityGroupId $sg_id --Permissions '[{\"IpProtocol\":\"tcp\",\"PortRange\":\"3389/3389\",\"SourceCidrIp\":\"<企业IP>/32\"}]'"
      ;;
    "DB_PUBLIC")
      echo "建议: 数据库端口仅允许应用服务器安全组访问，例如:"
      echo "aliyun ecs RevokeSecurityGroup --SecurityGroupId $sg_id --SecurityGroupRuleId $rule_id"
      echo "aliyun ecs AuthorizeSecurityGroup --SecurityGroupId $sg_id --Permissions '[{\"IpProtocol\":\"tcp\",\"PortRange\":\"3306/3306\",\"SourceCidrIp\":\"<应用服务器安全组ID>\"}]'"
      ;;
  esac
}
```

---

## 8. 定时巡检自动化建议

### Cron表达式示例

| 巡检频率 | Cron表达式 | 说明 |
|----------|-----------|------|
| 每日巡检 | `0 2 * * *` | 每天凌晨2点 |
| 每周巡检 | `0 2 * * 0` | 每周日凌晨2点 |
| 每月巡检 | `0 2 1 * *` | 每月1日凌晨2点 |

### 巡检报告自动化

```bash
#!/bin/bash
# 安全组巡检自动化脚本
REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
REPORT_DIR="/tmp/sg-audit-$(date +%Y%m%d)"
mkdir -p "$REPORT_DIR"

# 1. 资产盘点
echo "[$(date)] 生成资产盘点..."
aliyun ecs DescribeSecurityGroups --RegionId "$REGION" > "$REPORT_DIR/inventory.json"

# 2. 暴露面分析
echo "[$(date)] 执行暴露面分析..."
bash <<'EOF' > "$REPORT_DIR/exposure-analysis.json"
REGION="{{user.region}}"
# ... 暴露面分析脚本
EOF

# 3. 合规评估
echo "[$(date)] 执行合规评估..."
bash <<'EOF' > "$REPORT_DIR/compliance-report.txt"
REGION="{{user.region}}"
# ... 合规评估脚本
EOF

# 4. 生成汇总报告
cat > "$REPORT_DIR/summary.md" <<EOF
# 安全组巡检汇总报告
生成时间: $(date)
Region: $REGION

## 巡检结果
- 资产盘点: inventory.json
- 暴露面分析: exposure-analysis.json
- 合规评估: compliance-report.txt

## 下一步行动
请查看各报告详情，并根据建议修复发现的问题。
EOF

echo "[$(date)] 巡检完成，报告位于: $REPORT_DIR"
```

---

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| `InvalidRegionId` | 检查RegionID是否正确 |
| `Forbidden.NoPermission` | 需要ECS只读权限 |
| `Throttling` | API限流，减少请求频率 |
| `ResourceNotFound` | 安全组已被删除 |
| `NetworkInterfaceLimitExceeded` | 安全组规则数达到上限 |

## 安全注意事项

1. **凭证安全**: 永远不要在日志中输出完整的AK/SK
2. **变更管控**: 安全组变更应经过审批流程
3. **最小权限**: 巡检账号只需要 Describe* 权限
4. **审计追溯**: 保留至少6个月的巡检记录
5. **变更通知**: 安全组变更应触发告警通知

---

## 相关文档

- [安全组合规检查（基础版）](sg-compliance-check.md)
- [ECS故障诊断](troubleshooting.md)
- [云助手执行](integration.md)
