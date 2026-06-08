# Terraform IaC Skill — GCL Rubric

> GCL Level: **required** | max_iter: **2** | Skill Version: 1.0.0

## 1. Scoring Dimensions

| Dimension | Weight | Scale | Threshold | Critical Op Override |
|-----------|--------|-------|-----------|---------------------|
| **Correctness** | 25% | 0 / 0.5 / 1 | ≥ 0.5 | = 1 for `destroy` |
| **Safety** | 30% | 0 / 1 | = 1 | — |
| **Idempotency** | 15% | 0 / 0.5 / 1 | ≥ 0.5 | — |
| **Traceability** | 15% | 0 / 0.5 / 1 | ≥ 0.5 | — |
| **Spec Compliance** | 15% | 0 / 0.5 / 1 | ≥ 0.5 | — |

**Abort Conditions:**
- Safety = 0 → Immediate ABORT, no partial result
- Correctness = 0 on destructive op → ABORT

## 2. Per-Operation Safety Rules

### 2.1 terraform destroy (CRITICAL)

| Check | Rule | Enforcement |
|-------|------|-------------|
| DESTROY-001 | Must have explicit environment confirmation | `{{user.environment}}` must be explicitly provided |
| DESTROY-002 | Production environment requires double confirmation | Must confirm with "yes-prod-destroy" literal |
| DESTROY-003 | `prevent_destroy` lifecycle check | HALT if any resource has `prevent_destroy = true` |
| DESTROY-004 | State backup before destroy | Must execute `terraform state pull` to backup |
| DESTROY-005 | No auto-approve in production | `--auto-approve` is banned for prod environment |

**Scoring:**
- Pass all checks → Safety = 1
- Fail any DESTROY-001/002/005 → Safety = 0 (ABORT)
- Fail DESTROY-003/004 → Safety = 0.5 (WARN, requires override)

### 2.2 terraform apply (HIGH)

| Check | Rule | Enforcement |
|-------|------|-------------|
| APPLY-001 | Must run plan first | Plan file must exist and be newer than 5 minutes |
| APPLY-002 | No auto-approve without explicit flag | `{{user.auto_approve}}` must be explicitly set |
| APPLY-003 | Production requires plan review | Plan summary must be shown before apply |
| APPLY-004 | Detect destructive changes | Plan must be parsed for `-/destroy` markers |

**Scoring:**
- Pass all → Safety = 1
- Fail APPLY-001/004 → Safety = 0.5
- Fail APPLY-002/003 with prod → Safety = 0 (ABORT)

### 2.3 terraform plan (MEDIUM)

| Check | Rule | Enforcement |
|-------|------|-------------|
| PLAN-001 | Valid backend configuration | Backend must be initialized |
| PLAN-002 | Variables must be resolved | No `{{user.*}}` placeholders in final command |

### 2.4 nl2hcl_generation (HIGH)

| Check | Rule | Enforcement |
|-------|------|-------------|
| NL2HCL-001 | No hardcoded secrets in generated HCL | Check for password patterns, AK patterns |
| NL2HCL-002 | Valid resource type names | All `alicloud_*` resources must exist in provider |
| NL2HCL-003 | Required fields present | Check `region`, `zone_id` for compute resources |

### 2.5 reverse_engineering (HIGH)

| Check | Rule | Enforcement |
|-------|------|-------------|
| REV-001 | Resource ID format validation | IDs must match Aliyun patterns (e.g., `i-bp1.*`) |
| REV-002 | Import script must be executable | Generated `import.sh` must pass shellcheck |
| REV-003 | State modification warning | User must acknowledge state will be modified |

## 3. Idempotency Rules

| Operation | Idempotency Pattern | Verification |
|-----------|---------------------|--------------|
| `terraform apply` | TF state tracks applied changes | Re-run plan shows no changes |
| `terraform destroy` | N/A (destructive) | Requires explicit confirmation every time |
| `nl2hcl` | File-based idempotency | Overwrite protection with checksum |
| `import` | State-based | `terraform plan` shows no drift post-import |

**Scoring:**
- Idempotent pattern implemented → 1
- Partial / requires manual verification → 0.5
- No idempotency guarantee → 0

## 4. Traceability Requirements

### 4.1 Execution Trace Schema

```json
{
  "trace_version": "1.0.0",
  "timestamp": "2026-06-08T12:00:00Z",
  "skill": "alicloud-terraform-ops",
  "operation": "apply|destroy|plan|nl2hcl|import",
  "environment": "dev|staging|prod",
  "generator": {
    "command": "terraform plan -out=tfplan",
    "working_directory": "environments/dev",
    "exit_code": 0,
    "stdout_excerpt": "...",
    "stderr_excerpt": "...",
    "duration_ms": 12500
  },
  "critic": {
    "scores": {
      "correctness": 1,
      "safety": 1,
      "idempotency": 1,
      "traceability": 1,
      "spec_compliance": 1
    },
    "suggestions": [],
    "blocking": false
  }
}
```

### 4.2 Required Trace Fields

| Field | Source | Diagnostic Use |
|-------|--------|----------------|
| `command` | Generator output | Replay/audit exact command |
| `working_directory` | Context | Isolate multi-env issues |
| `exit_code` | Process result | Quick failure classification |
| `stdout_excerpt` | Command output | Success verification |
| `stderr_excerpt` | Error stream | Root cause analysis |
| `duration_ms` | Timing | Performance regression detection |

### 4.3 Trace Storage

- Path: `./audit-results/gcl-trace-terraform-YYYYMMDD-HHMMSS.json`
- Retention: 30 days (configurable via `{{env.GCL_TRACE_RETENTION_DAYS}}`)
- Rotation: Automatic gzip after 7 days

## 5. Spec Compliance Checklist

### 5.1 Backend Configuration (Spec: core-concepts.md §3)

| Requirement | Check | Weight |
|-------------|-------|--------|
| OSS bucket exists | `aliyun oss head-object` | Required |
| OTS table for locking | Table exists and accessible | Required |
| Region matches | Backend region = operation region | Required |
| Encryption enabled | OSS bucket has server-side encryption | Recommended |

### 5.2 Module Standards (Spec: modules-catalog.md)

| Requirement | Check | Weight |
|-------------|-------|--------|
| Source path valid | Relative path resolves | Required |
| Required variables documented | README.md or variables.tf comments | Recommended |
| Output values defined | At least one meaningful output | Required |

### 5.3 HITL Compliance (Spec: hitl-workflow.md)

| Checkpoint | Required For | Verification |
|------------|--------------|--------------|
| CP1 Intent Confirmation | NL2HCL | User confirmed resource list |
| CP2 Config Review | uat+ environments | Code review completed |
| CP3 Plan Confirmation | apply/destroy operations | Plan reviewed and approved |
| CP4 Import Confirmation | reverse engineering | Import scope selected |
| CP5 Destroy Confirmation | destroy operations | Double confirmation recorded |

## 6. WAF Compliance (Offline Check)

### 6.1 Security Pillar

| Pattern | Risk | Detection |
|---------|------|-----------|
| `password` in plain text | Secret exposure | Regex: `password\s*=\s*"[^"]+"` |
| `access_key` in HCL | Credential leak | Regex: `access_key` |
| `0.0.0.0/0` in security group | Overly permissive | Regex: `0\.0\.0\.0/0` |

### 6.2 Stability Pillar

| Pattern | Risk | Detection |
|---------|------|-----------|
| `prevent_destroy = false` in prod | Accidental deletion | Resource with env=prod and prevent_destroy=false |
| No `lifecycle` block for critical resources | Missing protection | Check for DB, EIP, OSS bucket resources |

### 6.3 Cost Pillar

| Pattern | Risk | Detection |
|---------|------|-----------|
| `PostPaid` without `spot_strategy` | Unexpected billing | Flag PayType=PostPaid without spot |
| High-spec instances default | Cost overrun | `instance_type` in [ecs.g7.8xlarge, ...] |

## 7. Scoring Examples

### Example 1: Safe Apply (PASS)

```json
{
  "scores": {
    "correctness": 1,
    "safety": 1,
    "idempotency": 1,
    "traceability": 1,
    "spec_compliance": 1
  },
  "decision": "PASS"
}
```

### Example 2: Destroy Without Backup (FAIL → ABORT)

```json
{
  "scores": {
    "correctness": 1,
    "safety": 0,
    "idempotency": 0,
    "traceability": 1,
    "spec_compliance": 0.5
  },
  "decision": "ABORT",
  "reason": "Safety=0: DESTROY-004 state backup not performed"
}
```

### Example 3: NL2HCL With Minor Issues (RETRY)

```json
{
  "scores": {
    "correctness": 0.5,
    "safety": 1,
    "idempotency": 1,
    "traceability": 1,
    "spec_compliance": 0.5
  },
  "decision": "RETRY",
  "suggestions": [
    "Add 'region' variable to generated configuration",
    "Include tags block for cost allocation"
  ]
}
```

## 8. Diagnostic Quick Reference

| Symptom | Check | Resolution |
|---------|-------|------------|
| Safety=0 on destroy | DESTROY-001~005 | Verify environment confirmation, check prevent_destroy |
| Correctness=0.5 | Command validation | Check resource IDs, parameter names |
| Idempotency=0.5 | State tracking | Verify tfplan file exists, check state lock |
| Traceability=0 | Log capture | Check write permissions to audit-results/ |
| Spec Compliance=0.5 | Backend config | Verify OSS bucket, OTS table accessibility |

## 9. Dry-Run 输出标识规范 (强制)

### 9.1 输出格式标准

所有 dry-run 执行必须在输出中包含以下标识元素：

#### 视觉标识 (控制台输出)

```
╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，不会创建或修改任何资源            ║
╚════════════════════════════════════════════════════════════════╝
```

#### 每个执行步骤的标识

```
[DRY-RUN] [11:23:45] [INIT] 执行 terraform init -backend=false
[DRY-RUN] [11:23:46] [VALIDATE] 执行 terraform validate
[DRY-RUN] [11:23:48] [PLAN] 执行 terraform plan
```

#### 结果摘要标识

```
┌─────────────────────────────────────────────────────────────────┐
│                     DRY-RUN 结果摘要                             │
├─────────────────────────────────────────────────────────────────┤
│  状态: ✅ 成功 (仅验证，未实际执行)                               │
│  资源变更预览:                                                   │
│    🟢 创建: 5 个资源                                            │
│    🟡 修改: 0 个资源                                            │
│    🔴 删除: 0 个资源                                            │
│  注意: 以上仅为预览，实际执行请在确认后操作                        │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 与正式执行的区分

| 特征 | Dry-Run | 正式执行 |
|------|---------|----------|
| 标题栏 | `🔍 DRY-RUN MODE` | `⚡ EXECUTION MODE` |
| 时间戳前缀 | `[DRY-RUN]` | `[EXEC]` |
| 结果状态 | `预览/验证` | `已执行/已应用` |
| 资源状态 | `将创建` | `已创建` |
| 确认要求 | 无需确认 | 必须确认 |

### 9.3 JSON 输出标识

```json
{
  "execution_mode": "DRY-RUN",
  "warnings": [
    "此输出仅为预览，未实际修改任何资源"
  ],
  "dry_run_indicators": {
    "backend_initialized": false,
    "state_modified": false,
    "resources_created": 0,
    "resources_previewed": 5
  }
}
```

### 9.4 环境变量标识

```bash
# 在 dry-run 模式下自动设置
export TF_DRY_RUN="true"
export TF_BACKEND_CONFIG="false"
export TF_EXECUTION_MODE="preview"
```

### 9.5 错误处理标识

即使 dry-run 失败，也必须明确标识：

```
╔════════════════════════════════════════════════════════════════╗
║              ❌ DRY-RUN FAILED (验证失败)                        ║
║         配置存在问题，请在修复后重试                              ║
║         注意: 由于处于 dry-run 模式，未对任何资源造成影响         ║
╚════════════════════════════════════════════════════════════════╝

错误详情:
  [DRY-RUN] Error: Invalid CIDR block format
  [DRY-RUN] Resource: alicloud_vpc.main
  [DRY-RUN] Fix: Use format like "10.0.0.0/16"
```

## 10. Integration with GCL Runner

```yaml
# Delegation from SKILL.md
dry_run_mode:
  enabled: true
  phases:
    - init
    - validate
    - plan
  trace_output: "./audit-results/gcl-trace-{timestamp}.json"
  rubric_reference: "references/rubric.md"
  output_format:
    header: "DRY-RUN MODE"
    prefix: "[DRY-RUN]"
    visual_indicator: "🔍"
```

---

**Version History:**
- v1.0.0 (2026-06-08): Initial rubric for Terraform IaC skill with NL2HCL and Reverse Engineering support
