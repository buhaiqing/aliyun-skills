---
name: alicloud-alb-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-alb-ops` (ALB — instance lifecycle,
  listeners, server groups, forwarding rules, ACLs, health checks, security
  policies). Phase 1 rollout.
license: MIT
metadata:
  skill: alicloud-alb-ops
  api: ALB 2020-06-16
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-07"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# ALB GCL Prompt Templates (Phase 1 — First Rollout)

Inherits structure from `AGENTS.md` §12.7 and prior pilots. ALB-specific additions: **cascading delete** (`DeleteLoadBalancer` removes all listeners, rules, server group associations); **deletion protection check** mandatory before delete; **server group empty check** after removal (no healthy servers → 503).

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## Generator (excerpt)

```text
You are the Generator in a GCL for Alibaba Cloud ALB.

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- `DeleteLoadBalancer`: must check `DeletionProtectionEnabled == false` first
  (use GetLoadBalancerAttribute). If enabled, HALT — user must disable.
- `DeleteLoadBalancer`: record cascade warning in trace (confirms user
  knows listeners, rules, server groups will be deleted).
- `RemoveServersFromServerGroup`: verify remaining healthy servers > 0
  AFTER removal (otherwise 503).
- `DeleteServerGroup`: verify NOT referenced by any listener/rule
  (use GetListenerAttribute + ListRules).
- `DeleteAcl`: verify NOT associated with any listener (use ListAclRelations).
- `DeleteSecurityPolicy`: verify NOT referenced by any HTTPS listener
  (use ListSecurityPolicyRelations).
- All `{{user.*}}` placeholders MUST be resolved interactively.
```

## Critic (excerpt)

```text
You are the Critic in a GCL for Alibaba Cloud ALB. Read-only.

# Checks
- For `DeleteLoadBalancer`: re-query `GetLoadBalancerAttribute`
  to verify `DeletionProtectionEnabled == false` BEFORE the delete call.
  Check trace for cascade warning acknowledgement.
- For `RemoveServersFromServerGroup`: verify trace captures server
  count before/after removal; alert if remaining count = 0.
- For `DeleteServerGroup` / `DeleteAcl` / `DeleteSecurityPolicy`:
  verify trace shows dependency check (not referenced).
- Apply the per-op Safety sub-rules from `rubric.md` §1.
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
- Suggestions ≤ 3, concrete.
- Do NOT reference the user's original request (rubber-stamping prevention).
```

## Anti-Patterns

| ❌ Anti-Pattern | Why It's Wrong |
|----------------|----------------|
| Deleting ALB without checking deletion protection | Will fail — API returns `DeleteProtectionEnabled` |
| Removing last healthy server from server group | Causes 503 for all clients |
| Deleting a server group still referenced by a listener | API rejects, but G should have checked |
| Not escaping JSON arrays in CLI args | Causes `InvalidParameter` error |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-07 | Initial ALB GCL prompt templates