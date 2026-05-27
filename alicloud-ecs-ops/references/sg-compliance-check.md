# 安全组合规检查

## 高危模式

| 模式 | 检测规则 | 严重度 | 修复 |
|------|----------|--------|------|
| `0.0.0.0/0` 开放高危端口 | `SourceCidrIp="0.0.0.0/0"` + 端口∈{22,3389,3306,1433,6379,27017} | Critical | 限制源IP或删除规则 |
| 全通配规则 | `SourceCidrIp="0.0.0.0/0"` + `PortRange="-1/-1"` | Critical | 立即删除或收紧 |
| 数据库端口全网开放 | 3306/1433/6379/27017 对 `0.0.0.0/0` | Critical | 仅允许应用服务器 |

## 检测脚本

```bash
REGION="{{user.region}}"
RISK_PORTS="22|3389|3306|1433|6379|27017"

for sg_id in $(aliyun ecs DescribeSecurityGroups --RegionId "$REGION" --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[].SecurityGroupId | tail -n +2); do
  aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId "$sg_id" --RegionId "$REGION" | \
  jq -r '.Permissions.Permission[] | select(.SourceCidrIp == "0.0.0.0/0") | select(.PortRange | test("^(22|3389|3306|1433|6379|27017|-1)/")) | "HIGH RISK: \(.IpProtocol) \(.PortRange)"'
done
```

## 自动修复

```bash
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId "{{sg_id}}" \
  --SecurityGroupRuleId "{{rule_id}}"
```

> **注意：** 自动修复前必须人工审查，某些规则可能是业务需要的开放策略。