# Alibaba Cloud CLI 参数格式规范

> **Purpose**: Reference document for common `aliyun` CLI parameter patterns that are non-obvious or error-prone.

---

## 1. Parameter Type Taxonomy

| Type | Format | Example |
|------|--------|---------|
| **String** | `--ParamName value` | `--RegionId cn-hangzhou` |
| **RepeatList** | `--ParamName.N value` | `--InstanceId.1 i-xxx` |
| **JSON Array** | `--ParamName '["val1","val2"]'` | `--InstanceIds '["i-xxx","i-yyy"]'` |
| **Nested Object** | `--ParamName.N.Key=K --ParamName.N.Value=V` | `--Tag.1.Key=env --Tag.1.Value=prod` |
| **Boolean** | `--ParamName true/false` | `--ForceStop false` |
| **Integer** | `--ParamName N` | `--PageSize 100` |

---

## 2. RepeatList Parameters (Most Common Error Source)

### Definition
Parameters that accept **multiple values** via indexed suffix `.N`.

### Correct Pattern
```bash
# Single value
--InstanceId.1 i-bp1234567890abcdef

# Multiple values
--InstanceId.1 i-xxx
--InstanceId.2 i-yyy
--InstanceId.3 i-zzz
```

### Wrong Pattern (Causes MissingParam Error)
```bash
# ❌ This does NOT work
--InstanceId i-xxx

# ❌ This also does NOT work
--InstanceIds i-xxx,i-yyy
```

### Products Using RepeatList

| Product | Common RepeatList Parameters |
|---------|------------------------------|
| **ECS** | `InstanceId`, `SecurityGroupId`, `VSwitchId`, `ImageId` |
| **RDS** | `DBInstanceId`, `SecurityGroupId` |
| **Redis** | `InstanceId` |
| **SLB** | `LoadBalancerId`, `ListenerPort` |
| **VPC** | `VpcId`, `VSwitchId`, `SecurityGroupId` |

---

## 3. JSON Array Parameters

### Definition
Parameters that accept **JSON-formatted arrays**.

### Correct Pattern
```bash
# Single value
--InstanceIds '["i-xxx"]'

# Multiple values
--InstanceIds '["i-xxx","i-yyy","i-zzz"]'

# Nested objects in array
--Tag.1.Key=env --Tag.1.Value=prod
--Tag.2.Key=project --Tag.2.Value=test
```

### Wrong Pattern
```bash
# ❌ Comma-separated does NOT work
--InstanceIds i-xxx,i-yyy

# ❌ Without JSON quotes does NOT work
--InstanceIds [i-xxx,i-yyy]
```

---

## 4. Nested Object Parameters

### Definition
Parameters that accept **key-value pairs** as nested objects.

### Correct Pattern
```bash
# Tags (most common)
--Tag.1.Key=Environment --Tag.1.Value=Production
--Tag.2.Key=Team --Tag.2.Value=SRE

# SecurityGroup rules
--SecurityGroupRule.1.IpProtocol=tcp
--SecurityGroupRule.1.PortRange=80/80
--SecurityGroupRule.1.SourceCidrIp=0.0.0.0/0
```

### Wrong Pattern
```bash
# ❌ Flat key-value does NOT work
--Tag.Key=env --Tag.Value=prod

# ❌ Without index does NOT work
--Tag.Key=env --Tag.Value=prod
```

---

## 5. Product-Specific Examples

### ECS (Elastic Compute Service)

```bash
# ✅ Correct: DescribeInstances with RepeatList
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceId.1 i-bp1234567890abcdef

# ✅ Correct: RunCommand with RepeatList
aliyun ecs RunCommand \
  --RegionId cn-hangzhou \
  --InstanceId.1 i-bp1234567890abcdef \
  --Type RunShellScript \
  --CommandContent "echo hello"

# ✅ Correct: Multiple security groups
aliyun ecs CreateInstance \
  --SecurityGroupId.1 sg-xxx \
  --SecurityGroupId.2 sg-yyy
```

### RDS (Relational Database Service)

```bash
# ✅ Correct: DescribeDBInstances
aliyun rds DescribeDBInstances \
  --RegionId cn-hangzhou \
  --ResourceGroupId rg-xxx

# ✅ Correct: CreateDBInstance with security groups
aliyun rds CreateDBInstance \
  --SecurityGroupId.1 sg-xxx
```

### Redis (ApsaraDB for Redis)

```bash
# ✅ Correct: DescribeInstances
aliyun r-kvstore DescribeInstances \
  --RegionId cn-hangzhou \
  --ResourceGroupId rg-xxx

# ✅ Correct: CreateInstance
aliyun r-kvstore CreateInstance \
  --RegionId cn-hangzhou \
  --InstanceClass redis.master.small.default \
  --InstanceName my-redis
```

---

## 6. Error Diagnosis

### Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `MissingParam.InstanceId` | Used `--InstanceId` instead of `--InstanceId.1` | Use RepeatList format: `--InstanceId.1 i-xxx` |
| `InvalidParameter.InstanceIds` | Used comma-separated instead of JSON array | Use JSON format: `--InstanceIds '["i-xxx"]'` |
| `InvalidParameter.Tag` | Used flat key-value instead of indexed format | Use indexed format: `--Tag.1.Key=K --Tag.1.Value=V` |
| `MissingParam.RegionId` | Forgot to specify region | Add `--RegionId cn-hangzhou` |

### Debugging Steps

```bash
# Step 1: Check parameter format
aliyun <product> <action> --help

# Step 2: Look for "RepeatList" or "Array" in parameter description

# Step 3: Test with dry-run (if available)
aliyun <product> <action> --dry-run ...

# Step 4: Use Describe/List operations first (read-only, safe)
aliyun <product> Describe<Resources> --RegionId cn-hangzhou
```

---

## 7. Pre-Flight Checklist

Before executing ANY `aliyun` CLI command:

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI PRE-FLIGHT CHECKLIST                                       │
├─────────────────────────────────────────────────────────────────┤
│  □ Is this command documented in a loaded Skill?                │
│    → YES: Use documented command directly                       │
│    → NO: Proceed to step 2                                      │
│                                                                 │
│  □ Run `aliyun <product> <action> --help`                       │
│    → Check Required parameters                                  │
│    → Check parameter types (RepeatList, JSON array, etc.)      │
│    → Look for example commands                                  │
│                                                                 │
│  □ Verify parameter format                                      │
│    → RepeatList: Use .N suffix                                  │
│    → JSON Array: Use '["val1","val2"]' format                   │
│    → Nested Objects: Use .N.Key=K --.N.Value=V format           │
│                                                                 │
│  □ Execute command                                              │
│    → Check InvocationStatus for CloudShell commands              │
│    → Decode Base64 Output if needed                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. References

- [Alibaba Cloud CLI GitHub](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud CLI Documentation](https://www.alibabacloud.com/help/en/cli/)
- [AGENTS.md §14 CLI Usage Protocol](../AGENTS.md#14-cli-usage-protocol-mandatory)

---

> **Last Updated**: 2026-06-13
> **Maintainer**: Sisyphus (AI Agent)
