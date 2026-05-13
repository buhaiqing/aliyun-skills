# Governance & Adversarial Review (Placeholder)

> **Status:** TO BE IMPLEMENTED — this file is a placeholder for future governance integration.

## Purpose

This document will provide a minimal adversarial review framework for generated skills, catching:
- Destructive-action shortcuts
- Credential leaks in instructions
- API hallucination before merge

## Minimal Adversarial Scenarios (Planned)

When implemented, reviewers will run through these scenarios against each skill:

1. **Destructive without confirmation** — Does the skill document explicit user consent before delete/destroy?
2. **Credential echo** — Does any instruction print, log, or echo secret values?
3. **API hallucination** — Are all operationIds, fields, and paths traceable to OpenAPI spec?
4. **Idempotency gap** — What happens if the same create operation is executed twice?
5. **Throttling blindness** — Does the skill account for rate limits and backoff?
6. **Region drift** — Does the skill hardcode a region or use `{{env.*}}` / `{{user.*}}`?
7. **Error recovery gap** — What happens on `QuotaExceeded` / `InsufficientBalance`?

## Governance Checklist (Planned)

- All `{{env.*}}` placeholders use correct environment variable names
- No secret literals in any generated file
- Both `aliyun` and SDK paths documented for each operation (dual-path skills)
- Safety gates present before destructive operations
- Retry and timeout policies consistent across operations

## See Also

- [JD Cloud governance reference](../jdcloud-skills/jdcloud-skill-generator/references/governance-and-adversarial-review.md)
- [Agent Skill OpenSpec](https://agentskills.io/specification)
