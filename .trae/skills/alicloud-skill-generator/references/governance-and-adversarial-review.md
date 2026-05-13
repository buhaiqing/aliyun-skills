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

#### Scenario 2: Credential Echo
**Test:** Search for `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, password fields in output.
**Pass Criteria:** No secret value printed, logged, or echoed in any flow.
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

---

## 3. Governance Checklist

### 3.1 Pre-Merge Checklist

- [ ] All `{{env.*}}` placeholders use correct environment variable names
- [ ] No secret literals in any generated file
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
- [ ] Scenario 2: No credential echo
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

- [User Experience Specification](user-experience-spec.md)
- [Optimization Analysis](optimization-analysis.md)
- [Prompt Library](prompt-library.md)
- [Agent Skills Open Specification](https://agentskills.io/specification)

---

*This governance document is mandatory. No skill may be merged without passing all three review stages.*
