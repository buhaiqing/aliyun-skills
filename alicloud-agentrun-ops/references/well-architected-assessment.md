# Well-Architected Assessment — AgentRun Sandbox

> **Purpose**: Five-pillar framework integration for AgentRun operations.

## 1. Framework Overview

Alibaba Cloud Well-Architected Framework evaluates systems across five pillars:
- **安全 (Security)**: Identity, access control, data protection
- **稳定 (Stability)**: Fault tolerance, disaster recovery, change management
- **成本 (Cost)**: Resource optimization, cost visibility, right-sizing
- **效率 (Efficiency)**: Development velocity, automation, operational efficiency
- **性能 (Performance)**: Responsiveness, scalability, resource efficiency

---

## 2. Pillar Integration

### 2.1 安全 (Security)

| Category | AgentRun-Specific Requirements | Assessment Criteria |
|---|---|---|
| **身份认证** | ACS3-HMAC-SHA256 signing | ✅ All API calls signed |
| **访问控制** | RAM policy management | ✅ Minimum required permissions |
| **数据保护** | Sandbox isolation, file encryption | ✅ PRIVATE network for sensitive data |
| **网络隔离** | VPC configuration | ✅ PRIVATE mode for internal services |
| **凭证管理** | AK/SK rotation, STS temporary credentials | ✅ Prefer STS over long-term AK |

**Security Checklist**:
- [ ] RAM policy grants minimum required actions (see [security-enhancement.md](security-enhancement.md) §1 for layered policies)
- [ ] AK/SK stored securely (KMS, environment variables)
- [ ] Credential format validated before signing (see [security-enhancement.md](security-enhancement.md) §2.1)
- [ ] Signing implementation verified (no timing attacks)
- [ ] PRIVATE network mode for sensitive workloads
- [ ] Sandbox lifecycle < 6 hours (auto-termination)
- [ ] Safety gates enforced for destructive operations (see [security-enhancement.md](security-enhancement.md) §4)
- [ ] Input validation before all API calls (see [security-enhancement.md](security-enhancement.md) §3)

**RAM Policy Template (Operator — Recommended)**:
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fc:CreateTemplate",
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:UpdateTemplate",
        "fc:CreateSandbox",
        "fc:GetSandbox",
        "fc:ListSandboxes",
        "fc:StopSandbox",
        "fc:ExecuteSandboxCode"
      ],
      "Resource": [
        "acs:agentrun:*:*:template/*",
        "acs:agentrun:*:*:sandbox/*"
      ]
    },
    {
      "Effect": "Deny",
      "Action": [
        "fc:DeleteTemplate",
        "fc:DeleteSandbox"
      ],
      "Resource": "*"
    }
  ]
}
```

> See [security-enhancement.md](security-enhancement.md) for full Read-Only / Operator / Admin / Data-Plane-Only policy templates.

### 2.2 稳定 (Stability)

| Category | AgentRun-Specific Requirements | Assessment Criteria |
|---|---|---|
| **故障隔离** | Sandbox instance isolation | ✅ Each sandbox independent |
| **状态管理** | Sandbox lifecycle tracking | ✅ Monitor CREATING → READY → TERMINATED |
| **变更管理** | Template versioning | ✅ UpdateTemplate for controlled changes |
| **恢复能力** | Sandbox recreation, file backup | ✅ StopSandbox before critical operations |
| **会话管理** | Idle timeout, deep hibernation | ✅ Configure appropriate timeout |

**Stability Checklist**:
- [ ] Poll sandbox status before operations
- [ ] Handle TERMINATED sandboxes gracefully (create new)
- [ ] Implement exponential backoff for 5xx errors
- [ ] Track sandbox creation time (approaching 6h limit)
- [ ] Stop sandbox after task completion

**State Monitoring**:
```yaml
states:
  CREATING: Wait (poll interval 5s, max 120s)
  READY: Proceed with operations
  TERMINATED: Create new sandbox
```

**Recovery Matrix**:
| Failure | Recovery Action |
|---|---|
| Sandbox TERMINATED unexpectedly | Create new sandbox, restore state |
| Template update fails | Rollback to previous config |
| API timeout | Retry with backoff (max 3) |
| Rate limit exceeded | Wait 60s, retry |

### 2.3 成本 (Cost)

| Category | AgentRun-Specific Requirements | Assessment Criteria |
|---|---|---|
| **资源配额** | Template CPU/memory right-sizing | ✅ Minimal sufficient resources |
| **生命周期管理** | Idle timeout optimization | ✅ Auto-terminate idle sandboxes |
| **计费透明** | Sandbox billing per execution time | ✅ Monitor usage via ActionTrail |
| **资源清理** | Delete TERMINATED sandboxes | ✅ Regular cleanup (> 6h old) |
| **模板复用** | Shared templates across workloads | ✅ Reduce template creation overhead |

**Cost Checklist**:
- [ ] CPU/memory sized for workload (avoid over-provisioning)
- [ ] Idle timeout set appropriately (1800-3600s recommended)
- [ ] Active sandbox count monitored
- [ ] TERMINATED sandboxes cleaned up daily
- [ ] Template reuse maximized

**Cost Optimization Matrix**:
| Resource | Optimization Strategy | Expected Savings |
|---|---|---|
| CPU | Use 2 cores for light workloads | 50% CPU cost |
| Memory | 2GB for simple scripts, 4GB for data processing | 40% memory cost |
| Idle Timeout | 1800s for burst workloads | 60% lifecycle cost |
| Sandbox Cleanup | Daily cleanup of TERMINATED | Reduced quota pressure |

**Resource Sizing Guide**:
| Workload Type | CPU | Memory | Idle Timeout |
|---|---|---|---|
| Simple scripts | 1-2 | 1024-2048 MB | 1800s |
| Data processing | 4 | 4096-8192 MB | 3600s |
| Browser automation | 4 | 4096 MB | 1800s |
| AI inference | 8 | 8192-16384 MB | 3600s |

### 2.4 效率 (Efficiency)

| Category | AgentRun-Specific Requirements | Assessment Criteria |
|---|---|---|
| **自动化** | API-driven operations | ✅ No manual console operations |
| **批量处理** | Parallel sandbox operations | ✅ Batch CreateSandbox/ListSandboxes |
| **模板管理** | Pre-defined templates | ✅ Template library for common scenarios |
| **代码执行** | Context reuse for state preservation | ✅ Multi-execution in single context |
| **MCP集成** | Standardized tool interface | ✅ MCP service for AI agents |

**Efficiency Checklist**:
- [ ] Automation scripts for CRUD operations
- [ ] Template library (3-5 common templates)
- [ ] Context reuse for multi-step code execution
- [ ] Batch sandbox creation for parallel workloads
- [ ] MCP service enabled for AI agent integration

**Efficiency Metrics**:
| Metric | Target | Optimization |
|---|---|---|
| Template creation time | < 10s | Pre-create templates |
| Sandbox creation time | < 30s | Parallel creation |
| Code execution overhead | < 1s | Context reuse |
| Manual operations | 0 | Full automation |

### 2.5 性能 (Performance)

| Category | AgentRun-Specific Requirements | Assessment Criteria |
|---|---|---|
| **响应时间** | API call latency | ✅ < 200ms control plane, < 500ms data plane |
| **代码执行** | Execution timeout optimization | ✅ < 30s per execution |
| **并发处理** | Parallel sandbox operations | ✅ Multiple sandboxes for concurrent tasks |
| **网络优化** | Region proximity | ✅ Same region as dependent services |
| **资源利用率** | CPU/memory usage monitoring | ✅ Health check before execution |

**Performance Checklist**:
- [ ] Region matches dependent services (database, storage)
- [ ] Sandbox health checked before code execution
- [ ] Execution timeout configured appropriately
- [ ] Parallel sandboxes for concurrent workloads
- [ ] File operations batched where possible

**Performance Targets**:
| Operation | Target | Measurement |
|---|---|---|
| CreateTemplate | < 5s | API response time |
| CreateSandbox | < 30s | CREATING → READY transition |
| ExecuteCode (simple) | < 5s | Total execution time |
| ExecuteCode (complex) | < 30s | With timeout configured |
| File read/write | < 1s | Per file operation |

**Performance Optimization**:
| Bottleneck | Solution |
|---|---|
| Slow sandbox creation | Pre-create pool of READY sandboxes |
| Code execution timeout | Split into smaller chunks |
| File operation latency | Batch multiple files |
| Network latency | Same region as services |

---

## 3. Assessment Scorecard

### 3.1 Scoring Criteria

| Score | Criteria |
|---|---|
| **5 (Excellent)** | All requirements met, best practices applied |
| **4 (Good)** | Most requirements met, minor gaps |
| **3 (Acceptable)** | Core requirements met, improvements needed |
| **2 (Poor)** | Critical gaps, remediation required |
| **1 (Critical)** | Major deficiencies, immediate action needed |

### 3.2 Pillar Scores

| Pillar | Score | Status |
|---|---|---|
| 安全 (Security) | - | Assess against checklist |
| 稳定 (Stability) | - | Assess against checklist |
| 成本 (Cost) | - | Assess against checklist |
| 效率 (Efficiency) | - | Assess against checklist |
| 性能 (Performance) | - | Assess against checklist |

### 3.3 Overall Assessment

**Minimum Acceptable Score**: 3.0 average across pillars

**Score Calculation**:
```
Overall = (Security + Stability + Cost + Efficiency + Performance) / 5
```

---

## 4. Improvement Roadmap

### 4.1 Priority Matrix

| Priority | Pillar | Action | Effort | Impact |
|---|---|---|---|
| **P1** | Security | Implement STS credential rotation | Medium | High |
| **P1** | Stability | Add sandbox health monitoring | Low | High |
| **P1** | Cost | Set idle timeout to 1800s | Low | High |
| **P2** | Efficiency | Create template library | Medium | Medium |
| **P2** | Performance | Enable parallel sandbox creation | Medium | Medium |
| **P3** | Stability | Implement retry with backoff | Low | Medium |

### 4.2 Quick Wins (Low Effort, High Impact)

1. **Idle Timeout**: Set to 1800s → 60% cost reduction
2. **Health Check**: Add pre-execution health check → 20% error reduction
3. **Cleanup Script**: Daily sandbox cleanup → Reduced quota pressure

### 4.3 Long-Term Investments

1. **STS Integration**: Credential rotation for security
2. **Template Library**: Pre-defined templates for efficiency
3. **Monitoring Dashboard**: Comprehensive observability

---

## 5. Compliance Checklist

**AgentRun-Specific Well-Architected Compliance**:

### Security
- [ ] ACS3-HMAC-SHA256 signing implemented correctly
- [ ] RAM policy follows least-privilege principle
- [ ] AK/SK stored in secure location (KMS/env vars)
- [ ] PRIVATE network mode for sensitive workloads
- [ ] Sandbox lifecycle limited to < 6 hours

### Stability
- [ ] Sandbox status polled before operations
- [ ] Exponential backoff for 5xx/429 errors
- [ ] Sandbox recreation logic for TERMINATED state
- [ ] Template update validation before apply

### Cost
- [ ] CPU/memory right-sized for workload
- [ ] Idle timeout configured (1800-3600s)
- [ ] TERMINATED sandboxes cleaned up regularly
- [ ] Template reuse maximized

### Efficiency
- [ ] Automation for all CRUD operations
- [ ] Context reuse for multi-step execution
- [ ] Template library available
- [ ] MCP service enabled (if applicable)

### Performance
- [ ] Region matches dependent services
- [ ] Health check before code execution
- [ ] Parallel sandbox operations supported
- [ ] File operations batched

---

## 6. Documentation References

| Pillar | Alibaba Cloud Reference |
|---|---|
| Security | [RAM Best Practices](https://help.aliyun.com/document_detail/28627.html) |
| Stability | [FC Reliability Guide](https://help.aliyun.com/zh/functioncompute/fc/best-practices-reliability) |
| Cost | [FC Cost Optimization](https://help.aliyun.com/zh/functioncompute/fc/best-practices-cost) |
| Performance | [FC Performance Tuning](https://help.aliyun.com/zh/functioncompute/fc/best-practices-performance) |