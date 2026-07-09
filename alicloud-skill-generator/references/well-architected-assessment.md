# Well-Architected Assessment — Alibaba Cloud Skill Generator

> **Purpose:** Defines how every generated `alicloud-[product]-ops` skill MUST incorporate Alibaba Cloud's Well-Architected Framework (卓越架构) five pillars into its generated content. This ensures that operational skills don't just execute APIs — they guide users toward excellent cloud architecture practices.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-16
> **Status:** MANDATORY — all generated skills MUST include well-architected assessment patterns
> **Reference:** [阿里云卓越架构](https://help.aliyun.com/zh/product/2362200.html)

---

## Table of Contents

1. [Framework Overview](#1-framework-overview)
2. [五支柱 Skill 集成规范](#2-五支柱-skill-集成规范)
   - [安全支柱 Security](#21-安全支柱-security)
   - [稳定支柱 Stability](#22-稳定支柱-stability)
   - [成本支柱 Cost](#23-成本支柱-cost)
   - [效率支柱 Efficiency](#24-效率支柱-efficiency)
   - [性能支柱 Performance](#25-性能支柱-performance)
3. [Skill 生成集成点](#3-skill-生成集成点)
4. [评估成熟度模型](#4-评估成熟度模型)
5. [合规性检查清单](#5-合规性检查清单)

---

## 1. Framework Overview

Alibaba Cloud Well-Architected Framework defines five pillars for cloud architecture excellence:

| Pillar | Core Focus | Official Doc |
|--------|-----------|--------------|
| **安全 (Security)** | Identity, network, host, data security; threat detection and response | [安全支柱](https://help.aliyun.com/document_detail/2362205.html) |
| **稳定 (Stability)** | High availability, failure-oriented design, change management, disaster recovery | [稳定支柱](https://help.aliyun.com/document_detail/2573818.html) |
| **成本 (Cost)** | Cost visibility, resource optimization, billing model selection, waste elimination | [成本支柱](https://help.aliyun.com/document_detail/2536197.html) |
| **效率 (Efficiency)** | DevOps toolchains, operational models, automation, incident response | [效率支柱](https://help.aliyun.com/document_detail/2536123.html) |
| **性能 (Performance)** | Auto-scaling, observability, performance baselines, bottleneck identification | [性能支柱](https://help.aliyun.com/document_detail/2531100.html) |

The framework follows a **Learn → Measure → Optimize** lifecycle. Generated skills MUST embed assessment guidance at the **Learn** level and operational hooks at the **Optimize** level.

### Three Design Principles (Stability Pillar)

The stability pillar defines three principles that ALL operational skills MUST follow:

1. **面向失败的架构设计** — Design for failure: redundancy, isolation, degradation, elasticity
2. **面向精细的运维管控** — Refined operations: version control, canary releases, monitoring, automated inspection
3. **面向风险的应急快恢** — Emergency recovery: real-time risk detection, coordinated response, rapid restoration, post-incident review

---

## 2. 五支柱 Skill 集成规范

Each generated skill MUST integrate the five pillars through structured assessment patterns. The integration depth depends on the skill's primary purpose:

| Skill Type | Security | Stability | Cost | Efficiency | Performance |
|-----------|----------|-----------|------|------------|-------------|
| **CRUD/Lifecycle** (ECS, RDS, etc.) | Required | Required | Required | Recommended | Required |
| **Monitoring/Diagnosis** (CMS, DAS) | Recommended | Required | Recommended | Required | Required |
| **Security/Access** (RAM, KMS) | Required | Recommended | Optional | Recommended | Optional |
| **Discovery/Read-Only** (topo) | Optional | Optional | Optional | Optional | Optional |

### 2.1 安全支柱 Security

Every generated skill MUST address security in at least these areas:

#### 2.1.1 Identity & Access Management

```markdown
## Security Assessment — IAM

### RAM Policy Requirements
For safe operation of this skill's APIs, the following minimum RAM permissions are required:

| API Operation | Required RAM Action | Resource Scope |
|---------------|--------------------|----------------|
| [Operation] | [product]:[Action] | acs:[product]:*:*:[resource-type]/* |

### Principle of Least Privilege
- **Do NOT** use `AdministratorAccess` for skill execution
- **Do** create a dedicated RAM user/role with product-scoped policies
- **Do** use STS temporary credentials for delegated operations

### Credential Management
- Credentials MUST use `{{env.*}}` placeholders — NEVER ask user for secrets
- AccessKey rotation: recommend 90-day cycle
- Prefer MFA-enabled RAM users for interactive operations
```

#### 2.1.2 Network Security

```markdown
## Security Assessment — Network

### Network Isolation
- Prefer VPC endpoints over public endpoints for API calls
- When using JIT Go SDK: ensure VPC NAT or egress rules allow outbound HTTPS (443)
- For `cli-only` skills: verify network access to `*.aliyuncs.com` endpoints

### Data in Transit
- All API calls use HTTPS — verify endpoint scheme is `https://`
- For sensitive operations (Delete, Modify credentials): recommend IP whitelist via `{{user.white_list_ip}}`
```

#### 2.1.3 Data Security

```markdown
## Security Assessment — Data Protection

### Sensitive Data Handling
- API responses may contain sensitive data — mask in user-facing output
- Backup/snapshot data: ensure encryption at rest is enabled
- Log output: NEVER include credential values, use `***` masking
```

### 2.2 稳定支柱 Stability

Every generated skill MUST embed stability patterns aligned with the three design principles:

#### 2.2.1 面向失败的架构设计 (Failure-Oriented Design)

```markdown
## Stability Assessment — Failure Orientation

### Built-in Resilience
- Every operation follows Pre-flight → Execute → Validate → Recover
- Non-retryable errors (QuotaExceeded, InsufficientBalance) trigger HALT, not blind retry
- Idempotent operations document duplicate behavior (client token / ResourceAlreadyExists)

### Cross-AZ/Region Considerations
- Multi-AZ deployment: when applicable, recommend distributing resources across zones
- Region dependency: document single-region risks in `core-concepts.md`
- Failure domain: identify the smallest blast radius for each operation
```

#### 2.2.2 面向精细的运维管控 (Refined Operations)

```markdown
## Stability Assessment — Operational Control

### Change Management
- Destructive operations require explicit confirmation with resource identifier
- Configuration changes: recommend staging → production promotion
- Version pinning: document API version in `metadata.api_profile`

### Monitoring Coverage
- Key operational metrics: document in `references/monitoring.md`
- Alert thresholds: provide recommended values in template
- Anomaly detection: integrate with CMS for automated alerting
```

#### 2.2.3 面向风险的应急快恢 (Emergency Recovery)

```markdown
## Stability Assessment — Emergency Recovery

### Backup & Recovery Strategy
- **Backup operations:** document backup API operations (CreateSnapshot, CreateBackup, etc.)
- **Recovery operations:** document recovery/restore APIs with pre-requisites
- **Recovery verification:** after restore, validate data integrity and service health
- **Recovery Time Objective (RTO):** document expected recovery time per operation
- **Recovery Point Objective (RPO):** document data loss window per backup strategy

### Disaster Recovery Patterns
| Pattern | CLI Example | SDK Example | Applicable Scope |
|---------|-------------|-------------|------------------|
| Backup to different region | `aliyun [product] CopySnapshot --DestRegionId` | `CopySnapshotRequest` with DestRegionId | Snapshots, images |
| Cross-region replication | `aliyun [product] CreateDtsJob` | DAS/replication API | Databases, storage |
| Failover promotion | `aliyun [product] SwitchOver` | Failover API | HA instances |

### Runbook Checklist

#### Phase 1: Backup Verification
1. Confirm backup exists: `aliyun [product] DescribeBackups --InstanceId <id>`
2. Verify backup integrity: check backup size, status = `Success`
3. Confirm backup age is within RPO window

#### Phase 2: Recovery Execution
1. Execute restore: `aliyun [product] RestoreInstance --BackupId <id>`
2. Monitor recovery progress: poll status until `Running`/`Available`
3. Validate post-recovery: connectivity check, data integrity, application health

#### Phase 3: Post-Recovery Validation
1. Verify all dependent resources are healthy
2. Run smoke tests against restored service
3. Document recovery duration vs RTO target
```

### 2.3 成本支柱 Cost

Every generated skill MUST include cost optimization guidance:

#### 2.3.1 Cost Visibility

```markdown
## Cost Assessment — Visibility

### Resource Cost Attribution
- Tag newly created resources: recommend `{{user.cost_center}}` tag
- Use Alibaba Cloud Cost Center API for budget tracking
- Document instance type pricing implications in `core-concepts.md`

### Billing Model Selection
| Billing Type | Best Use Case | Cost Savings |
|-------------|---------------|-------------|
| Pay-As-You-Go | Dev/test, short-term workloads | N/A |
| Subscription (包年包月) | Production, stable workloads | Up to 85% vs pay-as-you-go |
| Reserved Instances | Predictable 24/7 workloads | Up to 74% vs subscription |
| Spot Instances | Fault-tolerant, batch processing | Up to 90% vs pay-as-you-go |

### Waste Detection
- Idle resources: instances with CPU < 10% for 7+ consecutive days
- Unattached volumes: disks without `InstanceId` association
- Unused snapshots: snapshots with no active images/instances referencing them
- Orphaned snapshots: auto-cleanup after instance deletion
```

#### 2.3.2 Cost Optimization Actions

```markdown
## Cost Assessment — Optimization Actions

### Right-Sizing
- After creation: monitor actual resource utilization for 7 days
- Compare requested vs actual CPU/memory: recommend downgrade if utilization < 30%
- Compare vs burst: recommend upgrade if utilization > 80% sustained

### Lifecycle Cost Management
- Auto-decommission: tag resources with expiry date, automate cleanup
- Scheduled scaling: scale down during off-peak hours
- Storage tiering: move cold data to lower-cost storage classes
```

### 2.4 效率支柱 Efficiency

#### 2.4.1 Automation

```markdown
## Efficiency Assessment — Automation

### Batch Operations
- When operating on ≥ 3 resources: use batch APIs (RunInstances, BatchAttachDisk, etc.)
- Document concurrency limits per API
- Provide parallel execution patterns with error aggregation

### CI/CD Integration
- Skills can be invoked from CI/CD pipelines for infrastructure-as-code operations
- Output format is JSON by default — compatible with jq/yq for pipeline parsing
- Recommend storing skill output in CI artifact storage for audit trail
```

#### 2.4.2 Operational Model

```markdown
## Efficiency Assessment — Operations

### Incident Response Integration
- Error codes from this skill can trigger alert rules in CMS
- Document mapping: skill error → CMS alarm → runbook execution
- Recommend escalation path: automated → skill-assisted → human

### Knowledge Retention
- After each operation, document what changed in `assets/example-config.yaml`
- Maintain `references/knowledge-base.md` with observed patterns
- Cross-reference with ActionTrail for change history
```

### 2.5 性能支柱 Performance

#### 2.5.1 Auto-Scaling

```markdown
## Performance Assessment — Scaling

### Scaling Triggers
| Metric | Scale Up Threshold | Scale Down Threshold | Window |
|--------|-------------------|---------------------|--------|
| CPUUtilization | > 80% for 5min | < 30% for 15min | 300s |
| MemoryUsage | > 85% for 5min | < 50% for 15min | 300s |
| ConnectionUsage | > 70% for 5min | < 40% for 15min | 300s |
| IOPSUtilization | > 80% for 5min | < 50% for 15min | 300s |

### Elastic Response Patterns
- Horizontal scaling: add/remove instances (document max-min bounds)
- Vertical scaling: modify instance spec (document downtime implications)
- Pre-warming: provision capacity before expected traffic spikes

### Performance Baseline
- Document expected performance characteristics per instance type
- Recommend establishing baseline with `aliyun cms DescribeMetricList`
- Set alert rules for deviation from baseline (> 2σ)
```

#### 2.5.2 Observability Integration

```markdown
## Performance Assessment — Observability

### Metrics → Logs → Traces Pipeline
- CMS metrics: document relevant namespaces and metric names
- SLS logs: recommend log queries for error investigation
- ARMS traces: identify hot methods and slow SQL when applicable
```

---

## 3. Skill 生成集成点

The Well-Architected assessment MUST be integrated into generated skills at these precise locations:

### 3.1 In SKILL.md

Add after the **Operational Best Practices** section:

```markdown
## Well-Architected Assessment

This skill's operations are evaluated against Alibaba Cloud's Well-Architected Framework (卓越架构). For detailed assessment patterns per pillar:
- [Security Assessment](references/well-architected-assessment.md#21-安全支柱-security)
- [Stability Assessment](references/well-architected-assessment.md#22-稳定支柱-stability)
- [Cost Assessment](references/well-architected-assessment.md#23-成本支柱-cost)
- [Efficiency Assessment](references/well-architected-assessment.md#24-效率支柱-efficiency)
- [Performance Assessment](references/well-architected-assessment.md#25-性能支柱-performance)
```

### 3.2 In references/core-concepts.md

Add a **Resource Health & Architecture** section:

```markdown
## Resource Architecture & Well-Architected Alignment

### Dependency Graph
[Mermaid diagram or text description of resource dependencies]

### Single Point of Failure Analysis
- [Identify SPOFs for this resource type]
- Mitigation: [recommend HA pattern]
```

### 3.3 In references/monitoring.md

Add cost and performance metrics alongside operational metrics:

```markdown
## Cost & Performance Metrics

| Metric | CMS Namespace | Optimization Action |
|--------|--------------|--------------------|
| [Product]-Cost | acs_[product]_dashboard | Right-size, reserve, or decommission |
| [Product]-Utilization | acs_[product]_dashboard | Scale up/down based on actual usage |
```

---

## 4. 评估成熟度模型

| Level | Name | Characteristics | Target |
|-------|------|-----------------|--------|
| L1 | **Compliant** | Skill includes all five pillar checklists | All generated skills (mandatory) |
| L2 | **Actionable** | Skills include CLI commands for each pillar assessment | P0 product skills |
| L3 | **Automated** | Skills auto-detect and report pillar violations | Core P0 skills (ECS, RDS, ACK) |
| L4 | **Predictive** | Skills forecast pillar risks before they manifest | Future target |
| L5 | **Self-Optimizing** | Skills auto-remediate pillar gaps with user approval | Future target |

**Target:** All generated skills MUST achieve **L1 (Compliant)** minimum. P0 product skills (ECS, RDS, ACK, SLB, Redis) SHOULD achieve **L2 (Actionable)**.

---

## 5. 合规性检查清单

### 5.1 P0 — 必须通过

Generated skills MUST include in SKILL.md or references/:

- [ ] **Security — IAM:** Minimum RAM permissions documented for all skill operations
- [ ] **Security — Credential:** `{{env.*}}` placeholders used exclusively; masking rules present
- [ ] **Stability — Recovery:** Backup and recovery operations documented with RTO/RPO targets
- [ ] **Stability — Confirmation:** All destructive operations require explicit user confirmation
- [ ] **Cost — Billing:** At least one billing model comparison table relevant to the product
- [ ] **Cost — Waste:** Idle resource detection pattern documented
- [ ] **Performance — Metrics:** Key performance metrics identified with thresholds
- [ ] **Well-Architected Reference:** Link to `well-architected-assessment.md` in SKILL.md

### 5.2 P1 — 应该通过

- [ ] **Security — Network:** VPC endpoint recommendation present
- [ ] **Security — Data:** Encryption at rest documented for storage/backup operations
- [ ] **Stability — Multi-AZ:** Cross-AZ deployment recommendation present
- [ ] **Stability — Runbook:** DR runbook with Phase 1/2/3 structure
- [ ] **Cost — Right-Sizing:** Resource utilization → recommendation mapping documented
- [ ] **Efficiency — Batch:** Batch operation pattern documented (≥ 3 resources)
- [ ] **Performance — Baseline:** Performance baseline establishment procedure documented
- [ ] **Performance — Scaling:** Auto-scaling trigger thresholds documented

### 5.3 P2 — 建议通过

- [ ] **云治理中心:** Integration with Alibaba Cloud Governance Center (云治理中心) detection items
- [ ] **Well-Architected Tool:** Mapping to Well-Architected Tool questionnaire items
- [ ] **等保合规:** RAM policy templates aligned with 等保2.0 requirements
- [ ] **FinOps:** Cost Explorer API integration for continuous cost optimization
- [ ] **Auto-Remediation:** Skills auto-suggest fixes for common well-architected violations

---

*This well-architected assessment specification is mandatory for all skills generated by `alicloud-skill-generator`. It aligns generated operational runbooks with Alibaba Cloud's official Well-Architected Framework methodology.*
