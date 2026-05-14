# Governance & Adversarial Review

> **Purpose:** Provides a minimal adversarial review framework for generated skills, catching destructive-action shortcuts, credential leaks, API hallucination, and UX gaps **before** merge. All generated skills MUST pass this review.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14
> **Status:** MANDATORY — no skill may be merged without passing this review

---

## 1. Review Process

### 1.1 Review Stages

Every generated skill MUST pass three review stages before merge:

| Stage | Focus | Reviewer | Artifact |
|-------|-------|----------|----------|
| **Stage 1: Technical Review** | API fidelity, CLI accuracy, security | AI Agent / Senior Engineer | Technical sign-off |
| **Stage 2: UX Review** | Onboarding, interaction, feedback, error handling | UX Reviewer / Product Owner | UX checklist completion |
| **Stage 3: Adversarial Review** | Destructive gates, credential safety, resilience | Security / SRE | Adversarial report |

### 1.2 Review Triggers

Review is REQUIRED when:
- New `alicloud-[product]-ops` skill is generated
- Existing skill undergoes material update (new operations, API version bump)
- OpenAPI spec changes affect operation signatures
- UX specification is updated

---

## 2. Adversarial Scenarios

### 2.1 Security Scenarios

#### Scenario 1: Destructive without Confirmation
**Test:** Search all delete/destroy/remove operations.
**Pass Criteria:** Every destructive operation has explicit user confirmation with resource identifier.
**Fail Action:** Block merge until confirmation pattern added.

#### Scenario 2: Credential Echo / Masking Failure
**Test:** Search all execution flows (CLI output, JIT Go SDK stdout/stderr, log statements, error messages, debug/verbose output, verification scripts) for:
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, `Secret` (as field value context)
- Any case where credential values might leak (e.g., `fmt.Println(config)`, `log.Printf("%+v", ...)`, `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET`)
- JSON/YAML/INI output that includes un-masked credential fields
**Pass Criteria:**
1. No secret value is printed, logged, or echoed in any execution path.
2. ALL credential-related output uses masking: `***`, `<masked>`, or equivalent.
3. Verification scripts check existence only (e.g., `test -n "$var"`), never echo the value.
4. JIT Go SDK scripts never print the `config` struct or `AccessKeySecret` field.
5. `aliyun --debug` output includes a warning about potential credential exposure.
**Fail Action:** Block merge; treat as security incident.

#### Scenario 3: API Hallucination
**Test:** Cross-reference all operationIds, field names, and JSON paths against OpenAPI spec.
**Pass Criteria:** 100% traceability to OpenAPI or verified CLI output.
**Fail Action:** Require doc verification for each hallucinated item.

### 2.2 Resilience Scenarios

#### Scenario 4: Idempotency Gap
**Test:** Simulate executing the same create operation twice.
**Pass Criteria:** Behavior is documented (error, reuse, or duplicate).
**Fail Action:** Document idempotency behavior or add client token.

#### Scenario 5: Throttling Blindness
**Test:** Verify retry logic for 429/Throttling errors.
**Pass Criteria:** Exponential backoff documented; max retries specified.
**Fail Action:** Add throttling handling to recovery table.

#### Scenario 6: Region Drift
**Test:** Check for hardcoded regions in any flow.
**Pass Criteria:** All regions use `{{env.*}}` or `{{user.*}}` placeholders.
**Fail Action:** Replace hardcoded regions with placeholders.

#### Scenario 7: Error Recovery Gap
**Test:** Verify handling of `QuotaExceeded`, `InsufficientBalance`, `InvalidParameter`.
**Pass Criteria:** Each error has documented recovery action.
**Fail Action:** Add missing error patterns to recovery table.

### 2.3 UX Scenarios (NEW)

#### Scenario 8: Onboarding Friction
**Test:** Have a first-time user attempt to execute the first command.
**Pass Criteria:** User succeeds within 60 seconds without external help.
**Fail Action:** Simplify Quick Start; add verification commands.

#### Scenario 9: Excessive Prompting
**Test:** Count interactive prompts for common operations (describe, create, delete).
**Pass Criteria:** ≤ 3 prompts per common operation.
**Fail Action:** Add smart defaults; reduce required user input.

#### Scenario 10: Cryptic Errors
**Test:** Simulate each error category and evaluate message quality.
**Pass Criteria:** Error message follows `[ERROR] code: summary → explanation → fix → next step` format.
**Fail Action:** Rewrite error messages per `user-experience-spec.md` Section 5.

#### Scenario 11: Missing Progress Feedback
**Test:** Execute operations taking > 5 seconds.
**Pass Criteria:** Progress indicator visible with elapsed time and ETA.
**Fail Action:** Add polling progress to long-running operations.

#### Scenario 12: Silent Failures
**Test:** Verify that every operation produces observable output.
**Pass Criteria:** Success/failure is always reported; state changes are visible.
**Fail Action:** Add explicit success/failure feedback to all operations.

### 2.4 AIOps Scenarios (NEW)

#### Scenario 13: Missing Multi-Metric Correlation
**Test:** Search for multi-metric inspection patterns in monitoring/diagnosis skills.
**Pass Criteria:** Skill defines ≥ 4 anomaly patterns with detection logic and severity.
**Fail Action:** Require multi-metric correlation per `aiops-best-practices.md` Section 2.

#### Scenario 14: No Cross-Skill Delegation Matrix
**Test:** Verify `integration.md` contains Alarm-to-Diagnosis delegation matrix.
**Pass Criteria:** Matrix maps each alarm namespace/metric to primary/secondary diagnosis skill.
**Fail Action:** Require delegation matrix per `aiops-best-practices.md` Section 4.

#### Scenario 15: Missing DAS Integration
**Test:** Check database-related skills for DAS delegation triggers.
**Pass Criteria:** RDS/PolarDB/Redis skills define DAS trigger conditions and operations.
**Fail Action:** Require DAS integration per `aiops-best-practices.md` Section 3.3.

#### Scenario 16: No Alarm Storm Handling
**Test:** Search for alarm storm detection and handling logic.
**Pass Criteria:** Skill defines storm detection criteria and aggregation/suppression workflow.
**Fail Action:** Require alarm storm handling per `aiops-best-practices.md` Section 6.

#### Scenario 17: Missing Knowledge Base
**Test:** Check if `references/knowledge-base.md` exists for diagnostic skills.
**Pass Criteria:** Knowledge base contains ≥ 3 product fault patterns + ≥ 1 cascade pattern.
**Fail Action:** Require knowledge base per `aiops-best-practices.md` Section 7.

#### Scenario 18: No Multi-Round Reflection
**Test:** Check troubleshooting.md for multi-round diagnosis review process.
**Pass Criteria:** Document defines 3-round review with critical reflection questions.
**Fail Action:** Require multi-round reflection per `aiops-best-practices.md` Section 11.

#### Scenario 19: Missing Self-Healing Framework (NEW)
**Test:** Verify all installation flows reference `enhanced-self-healing-framework.md`.
**Pass Criteria:** CLI install, Go runtime JIT, dependency download all follow enhanced self-healing framework with pre-flight checks, error classification, multi-path recovery, health verification, and graceful degradation.
**Fail Action:** Require self-healing framework implementation per `enhanced-self-healing-framework.md`.

#### Scenario 20: Insufficient Self-Healing Coverage (NEW)
**Test:** Check self-healing paths per error type in installation flows.
**Pass Criteria:** Each error type (network, permission, resource, configuration) has ≥ 3 self-healing paths documented.
**Fail Action:** Add missing self-healing paths per error category.

#### Scenario 21: Missing Health Verification (NEW)
**Test:** Verify post-installation health check exists.
**Pass Criteria:** Health check script validates binary existence, permissions, PATH, version, and basic functionality with health score ≥ 8/10.
**Fail Action:** Add health verification step to installation flow.

#### Scenario 22: No Self-Healing Metrics (NEW)
**Test:** Check if self-healing success criteria are documented.
**Pass Criteria:** Self-healing duration < 30s, user intervention rate < 20%, health score ≥ 8/10 documented as success criteria.
**Fail Action:** Add self-healing metrics to success criteria section.

#### Scenario 23: Missing Graceful Degradation (NEW)
**Test:** Verify degradation path exists when self-healing exhausted.
**Pass Criteria:** Clear fallback path (JIT Go SDK → Console → Manual) with user guidance template.
**Fail Action:** Add graceful degradation path and user guidance template.

---

## 3. Governance Checklist

### 3.1 Pre-Merge Checklist

- [ ] All `{{env.*}}` placeholders use correct environment variable names
- [ ] No secret literals in any generated file
- [ ] **Credential masking enforced** — every console/log output path masks `ALIBABA_CLOUD_ACCESS_KEY_SECRET` (or any credential field) with `***` / `<masked>`
- [ ] No `fmt.Println`, `log.Print`, `echo`, or `printf` of credential values in any execution script
- [ ] JIT Go SDK scripts never print the SDK `Config` struct or `AccessKeySecret` field
- [ ] Verification commands check credential existence only (e.g., `test -n`), never echo the value
- [ ] Both `aliyun` and SDK paths documented for each operation (dual-path skills)
- [ ] Safety gates present before destructive operations
- [ ] Retry and timeout policies consistent across operations
- [ ] **UX Onboarding:** Quick Start section present and ≤ 30 seconds to read
- [ ] **UX Interaction:** Common operations require ≤ 3 prompts
- [ ] **UX Feedback:** Success/failure messages follow standardized format
- [ ] **UX Error Handling:** Error messages follow `[ERROR] code → explanation → fix → next step` format
- [ ] **UX Progress:** Operations > 5s show progress indicator
- [ ] **Optimization:** Error taxonomy covers ≥ 10 product-specific codes
- [ ] **Optimization:** Recovery table distinguishes auto-remediation vs HALT
- [ ] **Optimization:** Dependency mapping documented in `core-concepts.md`
- [ ] **AIOps Multi-Metric:** ≥ 4 anomaly patterns with detection logic (for monitoring skills)
- [ ] **AIOps Delegation:** Alarm-to-Diagnosis delegation matrix in `integration.md` (for monitoring skills)
- [ ] **AIOps DAS Integration:** DAS trigger conditions defined (for database skills)
- [ ] **AIOps Knowledge Base:** `references/knowledge-base.md` with ≥ 3 fault patterns (for diagnostic skills)
- [ ] **Self-Healing Framework:** All installation flows reference `enhanced-self-healing-framework.md`
- [ ] **Self-Healing Coverage:** ≥ 3 self-healing paths per error type (network, permission, resource, config)
- [ ] **Self-Healing Health Check:** Post-installation health verification with score ≥ 8/10
- [ ] **Self-Healing Metrics:** Success criteria documented (duration < 30s, intervention < 20%)
- [ ] **Self-Healing Degradation:** Graceful fallback path with user guidance template

### 3.2 Post-Merge Monitoring

After merge, monitor for:
- User escalation rate (target: < 10%)
- Task completion rate (target: > 90%)
- Error recovery rate (target: > 80%)
- Average prompts per operation (target: ≤ 3)

---

## 4. Review Templates

### 4.1 UX Review Template

```markdown
## UX Review: alicloud-[product]-ops

### Onboarding
- [ ] Quick Start section exists
- [ ] Prerequisites clearly listed with verification commands
- [ ] First command is copy-paste ready
- [ ] New user can succeed within 60 seconds

### Interaction
- [ ] Describe/List operations require ≤ 1 prompt
- [ ] Create operations require ≤ 2 prompts
- [ ] Delete operations require 1 prompt + confirmation
- [ ] Smart defaults documented for optional parameters

### Feedback
- [ ] Success messages include resource ID and next steps
- [ ] Failure messages include error code, explanation, fix
- [ ] Progress shown for operations > 5s
- [ ] All feedback is human-readable

### Error Handling
- [ ] Error messages follow standardized format
- [ ] Recovery steps are concrete and actionable
- [ ] Escalation template includes all required fields
- [ ] No secrets exposed in error messages

### Reviewer Sign-off
Reviewer: _______________ Date: _______________ Result: PASS / FAIL
```

### 4.2 Adversarial Review Template

```markdown
## Adversarial Review: alicloud-[product]-ops

### Security
- [ ] Scenario 1: Destructive operations have confirmation
- [ ] Scenario 2: No credential echo — ALL outputs use `***` / `<masked>` masking
- [ ] Scenario 2a: Verification scripts check existence only, never echo the value
- [ ] Scenario 2b: JIT Go SDK scripts never print `Config` struct or `AccessKeySecret`
- [ ] Scenario 3: All APIs traceable to OpenAPI

### Resilience
- [ ] Scenario 4: Idempotency documented
- [ ] Scenario 5: Throttling handled
- [ ] Scenario 6: No hardcoded regions
- [ ] Scenario 7: All errors have recovery

### UX
- [ ] Scenario 8: Onboarding succeeds within 60s
- [ ] Scenario 9: ≤ 3 prompts per common operation
- [ ] Scenario 10: Error messages are user-friendly
- [ ] Scenario 11: Progress shown for long ops
- [ ] Scenario 12: No silent failures

### AIOps
- [ ] Scenario 13: Multi-metric correlation patterns present (monitoring skills)
- [ ] Scenario 14: Cross-skill delegation matrix defined (monitoring skills)
- [ ] Scenario 15: DAS integration configured (database skills)
- [ ] Scenario 16: Alarm storm handling defined (monitoring skills)
- [ ] Scenario 17: Knowledge base with fault patterns (diagnostic skills)
- [ ] Scenario 18: Multi-round reflection process (diagnostic skills)

### Self-Healing (NEW)
- [ ] Scenario 19: Self-healing framework referenced in all installation flows
- [ ] Scenario 20: ≥ 3 self-healing paths per error type (network, permission, resource, config)
- [ ] Scenario 21: Health verification with score ≥ 8/10 after installation
- [ ] Scenario 22: Self-healing metrics documented (duration < 30s, intervention < 20%)
- [ ] Scenario 23: Graceful degradation path with user guidance template

### Reviewer Sign-off
Reviewer: _______________ Date: _______________ Result: PASS / FAIL
```

---

## 5. Escalation and Exceptions

### 5.1 Exception Process

If a skill cannot meet a requirement:
1. Document the exception with justification
2. Propose mitigation or workaround
3. Obtain approval from skill owner and security reviewer
4. Create tracking issue for future resolution

### 5.2 Continuous Improvement

- Monthly review of adversarial findings
- Quarterly update of scenario library
- Annual overhaul of governance framework

---

## See Also

- [Enhanced Self-Healing Framework](enhanced-self-healing-framework.md) — **MANDATORY** self-healing patterns for installation flows
- [User Experience Specification](user-experience-spec.md)
- [Optimization Analysis](optimization-analysis.md)
- [Prompt Library](prompt-library.md)
- [AIOps Best Practices](aiops-best-practices.md)
- [Agent Skills Open Specification](https://agentskills.io/specification)

---

*This governance document is mandatory. No skill may be merged without passing all three review stages including self-healing compliance.*
