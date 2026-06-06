# Advisor — Integration

## Execution Environment

This skill uses the standard Alibaba Cloud execution environment.
Reference: [Execution Environment](../../alicloud-skill-generator/references/execution-environment.md).

### Required Setup

```bash
# 1. Install the official aliyun CLI (if not present)
# See: https://github.com/aliyun/aliyun-cli
which aliyun || echo "install aliyun CLI"

# 2. Install the Advisor plugin
aliyun plugin install --names aliyun-cli-advisor

# 3. Verify
aliyun advisor version

# 4. Set credentials
export ALIBABA_CLOUD_ACCESS_KEY_ID="<your-ak-id>"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="<your-ak-secret>"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"   # default region; Advisor is global

# 5. Test
aliyun advisor GetProductList
```

### Go Runtime (for SDK Fallback)

```bash
# Install Go 1.21+ (Ubuntu/Debian)
sudo apt-get install -y golang-1.21

# Or use the JIT bootstrap script in this repo
# ./alicloud-jit-setup.sh
go version
```

The Go SDK is `github.com/alibabacloud-go/advisor-20180120/v3`.
See [api-sdk-usage.md](api-sdk-usage.md) for usage.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | — | RAM user AccessKey ID. NEVER ask the user; HALT if unset. |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | — | RAM user AccessKey Secret. NEVER ask the user; HALT if unset. |
| `ALIBABA_CLOUD_REGION_ID` | No | `cn-hangzhou` | Default region. Advisor is a global service; the region parameter is mostly ignored. |
| `ALIBABA_CLOUD_STS_TOKEN` | No | — | Required only when using `--assume-aliyun-id` for cross-account access. |

## Cross-Skill Delegation

Advisor is an **aggregation** skill — it produces cross-product advice
but does not perform remediation. For each advice, delegate to the
relevant per-product skill:

| Advice Topic | Delegate To | Delegation Action |
|--------------|-------------|-------------------|
| ECS security group risk | `alicloud-ecs-ops` | RevokeSecurityGroup, ModifySecurityGroupRule |
| RDS oversized / idle | `alicloud-rds-ops` | ModifyDBInstanceSpec, DeleteDBInstance |
| SLB health check failure | `alicloud-slb-ops` | DescribeLoadBalancers, ModifyLoadBalancer |
| ACK cluster overcommit | `alicloud-ack-ops` | ScaleCluster, DeleteClusterNodes |
| Cost optimization on a product | `alicloud-billing-ops` | Cost analysis, subscription/plan optimization |
| Underlying metric behind an advice | `alicloud-cms-ops` | DescribeMetricList with metric from advice |
| ActionTrail event behind a config change | `alicloud-actiontrail-ops` | LookupEvents for the resource + time range |
| Cross-product health sweep | `alicloud-aiops-cruise` | End-to-end cruise inspection with Advisor results as one input |

### Delegation Pattern

```markdown
1. User asks: "Why is my account flagged for security risk?"
2. Advisor reports: [Critical] Ecs.SecurityGroup.OpenPort22 on sg-xxx
3. Delegate to alicloud-ecs-ops:
   - Verify the SG exists: aliyun ecs DescribeSecurityGroups
   - Get the offending rule: aliyun ecs DescribeSecurityGroupAttribute
   - Revoke the rule: aliyun ecs RevokeSecurityGroup
4. After fix, re-trigger Advisor scan:
   - aliyun advisor RefreshAdvisorResource --product Ecs --resource-id sg-xxx
   - Confirm advice gone: aliyun advisor DescribeAdvices --check-id ...
```

## Multi-Account Scenarios

Advisor supports inspecting sub-accounts from a master account using
`--assume-aliyun-id`:

```bash
# Master account inspects sub-account
aliyun advisor DescribeAdvices --assume-aliyun-id 12345
```

**Pre-conditions:**

- The master account's RAM role has `AssumeRole` permission on the
  sub-account.
- The sub-account's trust policy allows the master account.
- The assumed role on the sub-account has `advisor:Describe*` (or
  `advisor:Refresh*` for refresh operations) permissions.

**For partner / MSP scenarios:**

```bash
# Inspect multiple tenants in a single call (where supported)
aliyun advisor DescribeCostCheckAdvices \
  --assume-aliyun-id-list 12345 67890 54321
```

## CI/CD Integration Pattern

Common pattern: nightly Advisor cost report in CI.

```yaml
# .github/workflows/advisor-cost-report.yml
name: advisor-cost-report
on:
  schedule:
    - cron: '0 8 * * 1'  # Monday 08:00 UTC
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - name: Setup
        env:
          ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIYUN_AK }}
          ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIYUN_SK }}
        run: |
          pip install aliyun-cli
          aliyun plugin install --names aliyun-cli-advisor

      - name: Generate cost report
        run: |
          aliyun advisor DescribeCostOptimizationOverview > cost.json
          aliyun advisor DescribeCostCheckResults --group-by Check >> cost.json
          # Post-process and upload to internal dashboard
```

## Output Conventions for Downstream Skills

When this skill is part of a multi-skill chain, emit these outputs:

| Output Path | Type | Source |
|-------------|------|--------|
| `{{output.advice_summary}}` | Markdown table | `DescribeAdvices` results, formatted |
| `{{output.critical_count}}` | int | Count of `Critical` advices |
| `{{output.warning_count}}` | int | Count of `Warning` advices |
| `{{output.total_savings}}` | number | From `$.Overview.TotalSavings` |
| `{{output.cost_by_category}}` | dict | From `$.Overview.Items[]` |
| `{{output.task_id}}` | int | From `RefreshAdvisorCheck` response |

**Example chain output (JSON):**

```json
{
  "report_id": "advisor-20260606-cn-hangzhou",
  "timestamp": "2026-06-06T08:00:00Z",
  "summary": {
    "critical_count": 3,
    "warning_count": 12,
    "info_count": 7,
    "total_savings_cny": 4500.00
  },
  "advices": [
    {
      "advice_id": 12345,
      "check_id": "Ecs.SecurityGroup.OpenPort22",
      "severity": "Critical",
      "product": "Ecs",
      "resource_id": "sg-bp1xxxxxxxxxx",
      "fix_action": "Revoke inbound 0.0.0.0/0:22"
    }
  ]
}
```

## Verifying Integration

After setup, run:

```bash
# 1. CLI works
aliyun advisor version
aliyun advisor GetProductList

# 2. List advices (should return at least an empty array)
aliyun advisor DescribeAdvices

# 3. Trigger a refresh (small scope to keep cost low)
aliyun advisor RefreshAdvisorResource --product Ecs --resource-id i-test
```

If any step fails, see [Troubleshooting](troubleshooting.md).

## Self-Validation Checklist (per Skill Spec)

Before declaring the integration ready:

- [ ] `aliyun --version` returns >= 3.3.0
- [ ] `aliyun advisor version` returns plugin version
- [ ] `GetProductList` returns non-empty list
- [ ] `DescribeAdvices` returns JSON with `RequestId` field
- [ ] Environment variables are set (do NOT echo them in logs)
- [ ] RAM policy attached includes `advisor:DescribeAdvices`
- [ ] If using cross-account: STS token valid, assume-role works
- [ ] If using SDK fallback: `go version` returns >= 1.21, `go mod tidy` succeeds

## Reference

- [Advisor OpenAPI](https://help.aliyun.com/zh/advisor/developer-reference/api-advisor-2018-01-20-overview)
- [Aliyun CLI](https://github.com/aliyun/aliyun-cli)
- [Aliyun CLI plugins](https://github.com/aliyun/aliyun-cli)
- [Aliyun CLI advisor plugin](https://github.com/aliyun/aliyun-cli-advisor)
- [JIT Go setup script](../../alicloud-jit-setup.sh) (this repo)
- [Cross-skill router: aiops-cruise](../../alicloud-aiops-cruise) (consumes Advisor results)
