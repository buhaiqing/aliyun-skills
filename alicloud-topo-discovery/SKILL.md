---
name: alicloud-topo-discovery
description: >-
  Automatically discover and generate Alibaba Cloud network topology and resource
  inventory reports, and export cloud resources as Terraform HCL to establish
  declarative infrastructure baselines.
  Use when the user asks to "scan network resources", "generate topology diagram",
  "inventory VPC resources", "audit cloud resources", or "audit network structure",
  or to "export as Terraform", "create baseline snapshot", "generate HCL", or
  "audit infrastructure drift" for a specified Alibaba Cloud account.
  Supports brief and detailed inventory modes, on-demand HCL export, and periodic
  baseline management.
  Keywords: network topology, resource inventory, VPC scan, cloud resource audit,
  Terraform HCL export, infrastructure baseline, drift detection,
  网络拓扑, 资源清单, VPC 探测, 云资源扫描, 网络审计.
  NOT for resource create/modify/delete or troubleshooting — read-only discovery only.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime dependencies), valid
  API credentials, network access to Alibaba Cloud endpoints. Strictly limited to
  read-only operations (Describe/List/Get).
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  type: cross-product-discovery
  cli_applicability: cli-only
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Network Topology Discovery Skill

## 🔒 Read-Only Principle (Non-Negotiable)

The core design principle of this skill is **Absolute Read-Only**. Before executing
any operation, the Agent MUST observe the following red lines:

| Rule | Description |
|------|-------------|
| **No write operations** | Never execute any `Create`, `Update`, `Modify`, `Delete`, `Associate`, `Unassociate`, `Authorize`, or `Revoke` operations |
| **No state changes** | Never change the state of any cloud resource, including but not limited to instance start/stop, security group rule changes, or EIP binding |
| **No credential leakage** | Never output full AK/Secret; mask in output as `AKID******SKRET` or `***` |
| **Read-only APIs only** | Only call `Describe*`, `List*`, and `Get*` APIs (see [Safety Gate Spec](references/safety-gate.md)) |

**Violating this principle = critical security violation — HALT immediately and report to the user.**

## Overview

`alicloud-topo-discovery` is a **cross-product network discovery tool** that automates
scanning of VPC network structure under an Alibaba Cloud account, associated resources
(ECS/RDS/SLB/NAT/EIP/ACK/security groups), and generation of structured network
topology diagrams and resource inventory reports.

### Core Features

| Feature | Description |
|---------|-------------|
| **Interactive mode selection** | User chooses "Brief" (VPC/SLB/EIP summary) or "Detailed report" (full resource inventory) |
| **Tree topology view** | Output VPC → VSwitch → resource tree per reference template format |
| **Multi-format output** | ASCII tree + Mermaid diagram + Markdown report |
| **Multi-document generation** | Optional single file or split files (topology / inventory / summary) |
| **Standalone template engine** | Based on `.md` templates under `templates/` with variable substitution and customization |
| **Declarative safety gate** | Mandatory command pre-check before execution to ensure no destructive operations |

### Relationship to Existing Skills

| Relationship | Description |
|--------------|---------------|
| **Does not replace** | This skill does not replace any product-level skill (e.g. `alicloud-ecs-ops`, `alicloud-vpc-ops`) |
| **Composition** | This skill aggregates cross-product topology by calling read-only APIs of each product |
| **Discovery vs operations** | This skill handles "discovery"; product skills handle "operations". If the user needs to modify resources after discovery, route to the corresponding product skill |
| **AIOps integration** | `alicloud-aiops-cruise` calls this skill's `topo-render.py` during patrol to render topology and overlay health status |

## Trigger & Scope

### SHOULD Use This Skill When

- User needs to view/scan/probe/audit Alibaba Cloud network topology
- User needs a resource inventory/asset list under a VPC
- User needs to know which VPCs/EIPs/SLBs/ECSs exist in the account
- User needs a network architecture diagram or resource report
- User needs to export cloud resources as Terraform HCL (`export-hcl`)
- User needs to create an infrastructure baseline snapshot (`baseline`)
- User needs to compare configuration changes between two baselines (`baseline-diff`)
- User needs cross-account resource scanning (via `--assume-role`)
- Keywords: network topology, VPC structure, resource inventory, cloud resource scan, Terraform HCL export, infrastructure baseline
- User says "scan the network", "see what resources we have", "generate topology", "export HCL", "create baseline"

### SHOULD NOT Use This Skill When

- User needs to create/modify/delete resources → route to the corresponding product skill
- User needs to troubleshoot resource faults/performance → route to monitoring/diagnostic skills
- User needs billing/cost queries → route to billing skill
- User needs to configure security policies → route to security-related skills
- User needs to create cloud resources via `terraform apply` → route to `alicloud-terraform-ops` (planned)

## Delegation Rules

| Capability | Delegate To | Notes |
|------------|-------------|-------|
| GCL quality gate | N/A | Read-only operations; GCL quality gate not triggered |

## Quality Gate (GCL)

This skill follows the Generator-Critic-Loop quality gate in AGENTS.md §12.

### Scoring Dimensions

See [references/gcl-rubric.md](references/gcl-rubric.md).

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Correctness** | 25% | Topology relationships and resource inventory match actual state |
| **Safety** | 30% | Read-only operations; any write operation scores 0 |
| **Idempotency** | 15% | Repeated scans with the same input produce consistent results |
| **Traceability** | 20% | Report includes full execution context (commands, parameters, output paths) |
| **Spec Compliance** | 10% | Follows manifest-schema and field mapping conventions |

### Sub-Mode Scoring Focus

| Sub-mode | Correctness Focus | Safety Checkpoint |
|----------|-------------------|-------------------|
| scan-topo | Complete output format, accurate topology relationships | Read-only gate |
| export-hcl | Field mapping accuracy | No sensitive data leakage |
| baseline | Complete directory structure | No data deletion |
| baseline-diff | Diff accuracy | Read-only diff |

### GCL Prompts

Generator → Critic loop details are in [references/gcl-rubric.md](references/gcl-rubric.md), following the standard flow in AGENTS.md §12.

## Pre-Execution Interaction (User Decisions)

Before running a scan, **MUST** confirm the following options with the user:

```
📋 Topology Scan Configuration:

1. Report mode (required):
   [1] Brief — VPC + VSwitch + SLB/EIP + resource count summary (default)
   [2] Detailed — Brief + full attributes and inventory for all ECS/RDS/ACK/security groups

2. Topology format:
   [1] ASCII tree — terminal-friendly, directly readable (default)
   [2] Mermaid diagram — flow/render support, suitable for document embedding
   [3] Both

3. Output structure:
   [1] Single file — all content written to report.md (default)
   [2] Multi-file — split into topology.md + inventory.md + summary.md

4. Project name/identifier (optional):
   [input]: Custom report title prefix (default: auto-extracted from VPC name)

5. Output format (optional):
   [a] ASCII tree — terminal-friendly (default)
   [b] Mermaid diagram — visual topology
   [c] Both (recommended)

6. Health status overlay (optional, integrates with `alicloud-aiops-cruise`):
   [input]: Patrol JSON report path (auto-overlay health status onto topology)

Reply with option numbers or descriptions to confirm before scanning begins.
```

## Variable Convention

| Placeholder | Meaning | Source |
|-------------|---------|--------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | AK ID | From runtime environment; never ask the user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | AK Secret | From runtime environment; never expose |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Region | From runtime environment |
| `{{user.report_mode}}` | Brief/detailed | User decision (step 1) |
| `{{user.topology_format}}` | ASCII/Mermaid | User decision (step 2) |
| `{{user.output_structure}}` | Single/multi-file | User decision (step 3) |
| `{{user.project_name}}` | Project name | User input or extracted from VPC name |
| `{{output.topology_data}}` | Scan results | From CLI execution |
| `{{output.vpc_name}}` | VPC name | From DescribeVpcs response |

## Execution Flow

### Phase 1: Pre-Execution Safety Checks

**Must complete before any CLI execution:**

1. Verify credentials exist:
   ```bash
   test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || { echo "ERROR: Credentials not set"; exit 1; }
   ```

2. Check CLI availability:
   ```bash
   command -v aliyun >/dev/null || { echo "ERROR: aliyun CLI not found"; exit 1; }
   ```

3. Verify read-only mode:
   - Review the list of commands planned for execution
   - Reject any command matching `(Create|Update|Modify|Delete|Associate|Unassociate|Authorize|Revoke|Stop|Start|Reboot|Run|Invoke)`
   - If found → HALT and report to the user

4. Test API connectivity (read-only):
   ```bash
   aliyun vpc DescribeRegions --RegionId "$ALIBABA_CLOUD_REGION_ID" >/dev/null 2>&1 || { echo "ERROR: API check failed"; exit 1; }
   ```

#### 📊 Output Format (Token Efficiency)

All CLI JSON output MUST be filtered with `jq` to the minimum necessary fields to avoid token waste from full JSON dumps:

```bash
# Before: full JSON output (may be 100+ lines)
aliyun ecs DescribeInstances --RegionId $REGION_ID

# After: ID + Name + Type + Status only
aliyun ecs DescribeInstances --RegionId $REGION_ID \
  | jq '.Instances.Instance[] | {InstanceId, InstanceName, InstanceType, Status}'
```

Field filtering rules per API are in the JSON output path mapping in `references/execution-commands.md`.

### Phase 2: Parallel Data Collection

For speed, run CLI commands in parallel (background).

> **Note**: `topo-scan.sh` implements multi-VPC scanning, health status overlay, and Mermaid diagram generation.
> The flow below is illustrative; full implementation is in `scripts/topo-scan.sh`.

```bash
# VPC & VSwitch (base layer) — wait for VPC before querying VSwitch
aliyun vpc DescribeVpcs --RegionId "$ALIBABA_CLOUD_REGION_ID" > /tmp/topo_vpcs.json &
PID_VPC=$!

# Parallel SLB/NAT/EIP queries
aliyun slb DescribeLoadBalancers --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_slbs.json &
aliyun vpc DescribeNatGateways --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 50 > /tmp/topo_nats.json &
aliyun vpc DescribeEipAddresses --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 50 > /tmp/topo_eips.json &

# Query VSwitch after VPC returns
wait $PID_VPC
FIRST_VPC_ID=$(python3 -c "import json;d=json.load(open('/tmp/topo_vpcs.json'));print(d.get('Vpcs',{}).get('Vpc',[{}])[0].get('VpcId',''))" 2>/dev/null)
if [ -n "$FIRST_VPC_ID" ]; then
  aliyun vpc DescribeVSwitches --RegionId "$ALIBABA_CLOUD_REGION_ID" --VpcId "$FIRST_VPC_ID" --PageSize 50 > /tmp/topo_vswitches.json &
fi

# ECS instances (optional in detailed mode)
if [ "$REPORT_MODE" = "detailed" ]; then
  aliyun ecs DescribeInstances --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_ecs.json &
  aliyun ecs DescribeSecurityGroups --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_sgs.json &
  aliyun cs DescribeClustersV1 --page_size 50 > /tmp/topo_ack.json &
  aliyun rds DescribeDBInstances --RegionId "$ALIBABA_CLOUD_REGION_ID" --PageSize 100 > /tmp/topo_rds.json &
fi

# Wait for remaining background jobs
wait
```

### Phase 3: Topology Generation (Template Rendering)

`topo-render.py` automatically:

1. Loads `/tmp/topo_*.json` data
2. Builds VSwitch → resource mapping (ECS/SLB/RDS grouped by attached VSwitch)
3. Loads health status overlay (if `--health-json` is passed)
4. Generates output:
   - **ASCII tree**: terminal-friendly, written to `report.md`
   - **Mermaid diagram**: visual topology with render support, written to `topology.mermaid.md`
5. Writes files to the output directory

> Legacy template `templates/vpc-topology.md` is retained for reference. Full rendering logic is implemented in `topo-render.py`.

### Phase 4: Report Compilation

Supports **ASCII tree + Mermaid diagram** formats; selectable via pre-execution interaction options.

- ASCII tree: terminal-friendly, directly readable
- Mermaid diagram: renderable visual chart, suitable for document embedding

**Single-file mode:**

```markdown
# {{user.project_name}} - Network Topology & Resource Inventory

> Generated: {{timestamp}}
> Region: {{env.ALIBABA_CLOUD_REGION_ID}}
> Mode: {{user.report_mode}}

{{topology_output}}

---

{{inventory_output}}

---

{{statistics_output}}
```

**Multi-file mode:**

- `topology.md`: VPC tree + Mermaid diagram
- `inventory.md`: full resource inventory table
- `summary.md`: summary + architecture analysis + risk notes

### Phase 5: Post-Execution Validation

1. Verify output file exists and size > 0:
   ```bash
   test -s report.md && echo "Report generated successfully"
   ```

2. Check for credential leakage:
   ```bash
   grep -E 'LTAI|AKIA|wJalr|SECRET|secret' report.md && { echo "WARNING: Possible credential leak"; exit 1; }
   ```

3. Verify read-only compliance (meta-check, no command execution):
   - Confirm execution log contains no write-operation commands

## Failure Recovery

| Error Pattern | Max Retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidAccessKeyId` / `InvalidAccessKey.Secret` | 0 | - | HALT. Invalid credentials; user must provide valid AK. |
| `SignatureDoesNotMatch` | 0 | - | HALT. AK/Secret mismatch or clock skew; check credentials. |
| `Forbidden.RAM` | 0 | - | HALT. Insufficient permissions; user needs `AliyunReadOnlyAccess` or custom read-only policy. |
| `Throttling` / 429 | 3 | Exponential | Retry after 2s, 4s, 8s backoff. |
| `InternalError` / 5xx | 3 | Fixed 2s | Retry; if persistent, continue with partial data. |
| `RegionId.NotExist` | 0 | - | HALT. Check `{{env.ALIBABA_CLOUD_REGION_ID}}`. |
| `InvalidVpcId.NotFound` | 0 | - | Skip that VPC and continue scanning. |
| Command timeout (>30s) | 1 | - | Kill process; log timeout; continue with other resources. |

---

## Well-Architected Assessment

Operations in this skill are evaluated against the Alibaba Cloud
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).
This section provides guidance on security, stability, cost, efficiency, and
performance for network topology discovery scenarios.

### Security

| Area | Guidance |
|------|----------|
| **IAM** | Require: `AliyunReadOnlyAccess` only. Principle: least privilege, read-only access |
| **Credentials** | Use `{{env.*}}` only. All AK/Secret in output must be masked (e.g. `LTAI***`) |
| **Data sensitivity** | VPC IDs, instance IDs, and IP ranges are sensitive infrastructure data; limit report distribution |

### Stability

| Area | Guidance |
|------|----------|
| **Failure-oriented design** | Skip individual VPC errors and continue scanning; partial results still have value |
| **Fine-grained operations** | Periodic topology discovery supports change tracking and drift detection |
| **Risk-oriented recovery** | N/A (read-only skill). Reports can serve as post-incident infrastructure comparison baselines |

### Cost

This skill uses read-only Describe APIs and incurs no API charges. Call volume is minimal:
- **Optimization**: Use batch APIs where possible; set `PageSize` to 50 to reduce call count
- **Waste**: Not applicable for read-only discovery

### Efficiency

- **Parallel collection**: ECS/RDS/SLB/VPC APIs can be queried concurrently
- **CI/CD integration**: Run periodically in CI pipelines to detect topology drift
- **JSON output**: jq-compatible for automated analysis

### Performance

| Operation | Expected API Calls | Time Estimate |
|-----------|-------------------|---------------|
| Full scan (all VPCs, multi-region) | ~10–20 Describe calls | < 30s |
| Brief mode | ~5 Describe calls | < 10s |
| + Health status overlay | +0 (reuses existing data) | +0s |
| + HCL export | ~10–30 API calls | < 60s |

## See Also — Meta-Skill Rules

This skill is governed by cross-cutting rules defined in the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rules](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI cannot cover full functionality and SDK/API
  is required), the skill MUST provide runnable Go SDK code under `assets/code-snippets/`.
  **Not applicable** — this skill is `cli-only`; CLI/SDK coverage is sufficient; no code snippets needed.
