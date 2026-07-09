# User Experience Specification — Alibaba Cloud Skill Generator

> **Purpose:** Defines user experience (UX) requirements and design patterns that MUST be integrated into every generated `alicloud-[product]-ops` skill. This specification ensures generated skills are intuitive, accessible, and confidence-inspiring for operators.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14
> **Status:** MANDATORY — all generated skills MUST pass UX review against this spec

---

## Table of Contents

1. [UX Design Principles](#1-ux-design-principles)
2. [Onboarding & Guidance](#2-onboarding--guidance)
3. [Interaction Design](#3-interaction-design)
4. [Feedback Mechanisms](#4-feedback-mechanisms)
5. [Error Handling & Recovery](#5-error-handling--recovery)
6. [UX Review & Validation](#6-ux-review--validation)
7. [Appendix: UX Patterns Library](#7-appendix-ux-patterns-library)

---

## 1. UX Design Principles

### 1.1 Core Principles

All generated skills MUST adhere to these five core principles:

| Principle | Description | Success Criteria |
|-----------|-------------|------------------|
| **Clarity** | Every action and its consequence is unambiguous | User never wonders "what just happened?" |
| **Efficiency** | Common tasks require minimal steps | 80% of tasks complete in ≤ 3 prompts |
| **Forgiveness** | Mistakes are recoverable with clear guidance | User can undo or recover from any non-destructive error |
| **Consistency** | Patterns are uniform across all alicloud skills | User learns once, applies everywhere |
| **Transparency** | System state is always visible | User always knows what the system is doing |

### 1.2 UX Maturity Model for Generated Skills

| Level | Name | Characteristics |
|-------|------|-----------------|
| 1 | Functional | Skill works; minimal UX consideration |
| 2 | Usable | Basic guidance; clear error messages |
| 3 | Comfortable | Onboarding flow; consistent patterns; helpful defaults |
| 4 | Delightful | Anticipates needs; proactive suggestions; minimal friction |
| 5 | Intuitive | Feels like natural conversation; zero learning curve |

**Target:** All generated skills MUST achieve **Level 3 (Comfortable)** minimum. Level 4 is encouraged for P0 skills.

---

## 2. Onboarding & Guidance

### 2.1 Quick Start Section (Mandatory)

Every `SKILL.md` MUST include a **Quick Start** section immediately after the Overview. This section must enable a first-time user to execute their first command within 60 seconds.

**Required Structure:**

```markdown
## Quick Start

### What This Skill Does
[One sentence describing the skill's primary purpose]

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check CLI and credentials
aliyun {{product}} DescribeRegions
```

### Your First Command
```bash
# Example: List resources
aliyun {{product}} Describe{{Resources}} --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand {{product}} architecture
- [Common Operations](#execution-flows) — Create, manage, and delete resources
- [Troubleshooting](references/troubleshooting.md) — Fix common issues
```

### 2.2 Capability Overview

After Quick Start, provide a **Capability Overview** table:

```markdown
## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create | Create a new {{resource}} | Medium | Low |
| Describe | View {{resource}} details | Low | None |
| Modify | Change {{resource}} configuration | Medium | Medium |
| Delete | Remove a {{resource}} | Low | **High** — irreversible |
| List | View all {{resources}} | Low | None |
```

### 2.3 Contextual Help

Every operation section MUST include:
- **When to use this operation** (2–3 bullet points)
- **What you need** (prerequisites for this specific operation)
- **What to expect** (outcome description)

**Example:**
```markdown
### Operation: Create {{Resource}}

**When to use:**
- You need a new {{resource}} for your application
- You want to provision resources in a specific region and zone

**What you need:**
- Region ID (e.g., `cn-hangzhou`)
- {{Resource}} name (unique within account)
- [Other required parameters]

**What to expect:**
- A new {{resource}} will be created in the specified region
- Creation typically takes [X] seconds/minutes
- You will receive a {{resource}} ID for future operations
```

### 2.4 Progressive Disclosure

Information MUST be presented progressively:
- **Level 1 (Summary):** One-line description + command example
- **Level 2 (Details):** Parameter table + common options
- **Level 3 (Advanced):** Full parameter reference + edge cases

Users should be able to complete common tasks at Level 1 or 2 without expanding Level 3.

---

## 3. Interaction Design

### 3.1 Prompt Minimization

**Rule:** Ask the user for information ONLY when it cannot be:
1. Inferred from environment variables (`{{env.*}}`)
2. Defaulted safely
3. Derived from previous context

**Prompt Budget per Operation:**

| Operation Type | Max Prompts | Notes |
|----------------|-------------|-------|
| Describe / List | 0–1 | Should be fully automated with env vars |
| Create | 1–2 | Name + region (region can default from env) |
| Modify | 1–2 | Resource ID + change specification |
| Delete | 1 + confirmation | Resource ID + explicit confirmation |

### 3.2 Smart Defaults

Every optional parameter SHOULD have a smart default:

| Parameter | Smart Default | Rationale |
|-----------|---------------|-----------|
| Region | `{{env.ALIBABA_CLOUD_REGION_ID}}` | User's configured region |
| Name | `[product]-[resource]-[timestamp]` | Unique, descriptive, sortable |
| Zone | First available zone in region | Simplifies provisioning |
| Timeout | 300s | Balances patience and responsiveness |
| PageSize | 50 | Reasonable batch size for list operations |

**Default Presentation:**
```
Region [cn-hangzhou]: _
# Press Enter to accept default, or type a different region
```

### 3.3 Confirmation Patterns

**Destructive Operations MUST use explicit confirmation:**

```markdown
⚠️ **Destructive Action Confirmation**

You are about to DELETE the following resource:
- Name: {{user.resource_name}}
- ID: {{user.resource_id}}
- Region: {{user.region}}

This action is **IRREVERSIBLE**. All data will be permanently lost.

Type the resource name "{{user.resource_name}}" to confirm: _
```

**Non-destructive operations SHOULD NOT require confirmation** (to reduce friction).

### 3.4 Progress Indication

For operations taking > 5 seconds, MUST show progress:

```
Step 1/4: Validating credentials... ✓
Step 2/4: Checking region availability... ✓
Step 3/4: Creating resource... ⏳ (elapsed: 12s, estimated: 30s)
Step 4/4: Validating creation... pending
```

**Polling Progress:**
```
Waiting for resource to reach "Running" state...
Current: Creating... (poll 3/60, elapsed: 15s)
```

### 3.5 Command Composition Assistance

Provide copy-paste ready command blocks:

```markdown
**Ready-to-use command:**
```bash
aliyun {{product}} Create{{Resource}} \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --{{Resource}}Name "my-resource" \
  # Add other parameters as needed
```
```

---

## 4. Feedback Mechanisms

### 4.1 Success Feedback

Every successful operation MUST provide:

```markdown
✅ **Success**

Operation: Create {{Resource}}
Resource ID: {{output.resource_id}}
Name: {{user.resource_name}}
Region: {{user.region}}
Status: {{output.status}}
Time taken: {{elapsed_seconds}}s

**What you can do next:**
- [Describe this resource](link-to-describe)
- [Create another](link-to-create)
- [View all resources](link-to-list)
```

### 4.2 Failure Feedback

Every failed operation MUST provide:

```markdown
❌ **Operation Failed**

Error: {{error.code}}
Message: {{error.human_readable}}
Request ID: {{error.request_id}}

**What happened:**
{{error.explanation}}

**How to fix:**
{{error.remediation}}

**Next steps:**
1. {{error.next_action_1}}
2. {{error.next_action_2}}
3. If the issue persists, [escalate with this Request ID](link-to-escalation)
```

### 4.3 Progress Feedback

For long-running operations:

```markdown
⏳ **Operation in Progress**

Operation: Create {{Resource}}
Resource ID: {{output.resource_id}}
Current state: {{output.status}}
Elapsed: {{elapsed_seconds}}s
Estimated remaining: {{estimated_remaining}}s

Polling every {{poll_interval}}s...
[====================>    ] 75%
```

### 4.4 Implicit Feedback

State changes SHOULD be observable:
- After create: resource appears in list
- After delete: resource disappears from list
- After modify: describe shows updated values

### 4.5 Feedback Timing

| Operation Duration | Feedback Type |
|-------------------|---------------|
| < 1s | Immediate result |
| 1–5s | Result with brief "Done" message |
| 5–30s | Progress indicator + final result |
| > 30s | Detailed progress + ETA + final result |

---

## 5. Error Handling & Recovery

### 5.1 Error Message Design

All error messages MUST follow this format:

```
[ERROR] {error.code}: {human_readable_summary}

What happened:
{2-3 sentence explanation in plain language}

How to fix:
{1-3 concrete steps}

Next step:
{single actionable instruction}
```

**Example:**
```
[ERROR] InvalidParameter.RegionId: The specified region is not valid or not supported.

What happened:
The region "ap-unknown-1" you provided is not a valid Alibaba Cloud region ID, 
or this product is not available in that region.

How to fix:
1. Check available regions: aliyun {{product}} DescribeRegions
2. Use a supported region (e.g., cn-hangzhou, cn-beijing)
3. Verify your ALIBABA_CLOUD_REGION_ID environment variable

Next step:
Run "aliyun {{product}} DescribeRegions" to see available regions.
```

### 5.2 Error Categories and Handling

| Category | User-Friendly Prefix | Auto-Recoverable | Action |
|----------|---------------------|-------------------|--------|
| Credential | "Authentication failed" | No | HALT with setup instructions |
| Region | "Region not available" | No | Suggest valid regions |
| Resource Not Found | "Resource not found" | No | Suggest list command |
| Quota | "Quota exceeded" | No | HALT with quota increase link |
| Throttling | "Rate limit reached" | Yes (retry) | Auto-retry with backoff |
| Invalid Parameter | "Invalid input" | Yes (fix) | Prompt for correction |
| Internal Error | "Server error" | Yes (retry) | Retry 3x, then HALT |
| Network | "Connection failed" | Yes (retry) | Retry with exponential backoff |

### 5.3 Recovery Patterns

**Pattern 1: Retry with Backoff**
```markdown
⚠️ Throttling detected. Retrying in {backoff_seconds}s...
(Attempt {current}/{max})
```

**Pattern 2: Suggest Alternative**
```markdown
❌ Resource creation failed: QuotaExceeded

You have reached your quota limit ({{current}}/{{limit}}).

Alternatives:
1. Request quota increase: [link]
2. Delete unused resources: aliyun {{product}} Delete{{Resource}} --{{Id}} "xxx"
3. Use a different region with available quota
```

**Pattern 3: Partial Success**
```markdown
⚠️ Partial Success

Completed: 3/5 resources created
Failed:
- resource-4: InvalidParameter (fixable)
- resource-5: QuotaExceeded (not fixable)

Options:
1. Retry failed items only
2. Continue with 3 resources
3. Rollback all (delete created resources)
```

### 5.4 Escalation Template

When HALT is necessary, provide this standardized escalation block:

```markdown
🛑 **Escalation Required**

This issue cannot be resolved automatically.

**Please provide the following information to support:**
- Request ID: {{error.request_id}}
- Operation: {{operation.name}}
- Resource ID: {{user.resource_id}}
- Error Code: {{error.code}}
- Timestamp: {{timestamp}}

**Support Channels:**
- Alibaba Cloud Console Ticket: https://workorder.console.aliyun.com/
- Include the Request ID for faster resolution
```

---

## 6. UX Review & Validation

### 6.1 UX Review Checklist

Before any generated skill is marked complete, it MUST pass this UX review:

#### Onboarding
- [ ] Quick Start section exists and is ≤ 30 seconds to read
- [ ] Prerequisites are clearly listed with verification commands
- [ ] First command example is copy-paste ready
- [ ] Capability Overview table is present

#### Interaction
- [ ] Common operations require ≤ 3 prompts
- [ ] Smart defaults are documented for all optional parameters
- [ ] Destructive operations have explicit confirmation
- [ ] Progress is shown for operations > 5s

#### Feedback
- [ ] Success messages include resource ID and next steps
- [ ] Failure messages include error code, explanation, and fix steps
- [ ] Long-running operations show progress and ETA
- [ ] All feedback is human-readable (not raw JSON)

#### Error Handling
- [ ] All error categories have user-friendly messages
- [ ] Recovery steps are concrete and actionable
- [ ] Escalation template includes all required fields
- [ ] No secret values are exposed in error messages

### 6.2 UX Validation Method

1. **First-time user test:** Have someone unfamiliar with the skill complete 3 common tasks
2. **Error scenario test:** Simulate each error category and verify message quality
3. **Timing test:** Measure time to complete common operations
4. **Accessibility review:** Ensure all output is screen-reader friendly

### 6.3 UX Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to First Success | < 60s | From first prompt to successful operation |
| Task Completion Rate | > 90% | % of users who complete task without escalation |
| Error Recovery Rate | > 80% | % of errors resolved without human support |
| User Satisfaction | > 4.0/5 | Post-task rating |
| Prompt Count (common tasks) | ≤ 3 | Average prompts per common operation |

---

## 7. Appendix: UX Patterns Library

### Pattern: Guided Wizard

For complex multi-step operations:

```markdown
## Wizard: Create Complex Resource

This wizard will guide you through creating a {{resource}} with all required configurations.

**Step 1/5: Basic Configuration**
- Name: [user input]
- Region: [default from env]

**Step 2/5: Network Configuration**
- VPC: [list available / create new]
- VSwitch: [list available / create new]

**Step 3/5: Security Configuration**
- Security Group: [list available / create new]

**Step 4/5: Review**
[Summary of all choices]
Confirm? [Y/n]

**Step 5/5: Execution**
[Progress indicator]
[Result]
```

### Pattern: Batch Operation

For operating on multiple resources:

```markdown
## Batch Operation: Start Multiple Instances

Resources selected: 5 instances
- i-xxx1 (stopped)
- i-xxx2 (stopped)
- i-xxx3 (stopped)
- i-xxx4 (already running — skip)
- i-xxx5 (stopped)

Action: Start 4 instances
Confirm? [Y/n]

Progress:
[====>                ] 1/4 started
```

### Pattern: Dry Run

For validating operations without executing:

```markdown
## Dry Run: Delete Resource

This shows what WOULD happen without actually doing it:

Would delete: {{resource_id}}
Would free: {{attached_resources}}
Would impact: {{dependent_resources}}

To actually delete, run with --confirm flag.
```

---

*This specification is mandatory for all skills generated by `alicloud-skill-generator`. Update it as UX best practices evolve.*
