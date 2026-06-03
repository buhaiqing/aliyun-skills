---
name: gcl-orchestrator-agent
description: >-
  Specification for a `pi-subagents` custom agent (`gcl-orchestrator`) that
  wraps `scripts/gcl_runner.py` for the parent pi agent. Use this spec
  to install the agent to `.pi/agents/gcl-orchestrator.md` (project scope)
  or `~/.pi/agent/agents/gcl-orchestrator.md` (user scope). The agent
  enforces the Generator-Critic-Loop (GCL) defined in `AGENTS.md` §12.
  Phase 2 deliverable.
license: MIT
metadata:
  type: meta-reference
  applies_to: alicloud-skill-generator
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../AGENTS.md
  related:
    - gcl-rollout-spec.md
    - ../../../scripts/gcl_runner.py
    - ../../../scripts/README.md
---

# GCL Orchestrator Agent (for `pi-subagents`)

> This file is **NOT** an active agent definition. It is a **specification**
> that users install by copying the `## Agent Definition` block below to
> `.pi/agents/gcl-orchestrator.md` (project scope) or
> `~/.pi/agent/agents/gcl-orchestrator.md` (user scope).
>
> The agent itself wraps `scripts/gcl_runner.py` so the parent pi session
> can invoke the GCL via a slash command or a `subagent(...)` tool call.

---

## Why a Dedicated Agent?

The parent pi session, when asked to "delete a Redis instance" or
"create a new ECS security group", needs a way to:

1. Pick the right `alicloud-*-ops` skill.
2. Load that skill's `references/rubric.md`.
3. Run the proposed command through the GCL loop.
4. Surface the trace for human audit.

`gcl_runner.py` does all of this, but invoking it directly from the parent
session requires bash skills and trace JSON parsing. The `gcl-orchestrator`
agent encapsulates that boilerplate and provides a clean CLI surface for
the parent session.

---

## Agent Definition

Copy the following block to `.pi/agents/gcl-orchestrator.md` (or
`~/.pi/agent/agents/gcl-orchestrator.md`):

```markdown
---
name: gcl-orchestrator
description: >-
  Generator-Critic-Loop orchestrator. Wraps `scripts/gcl_runner.py` for the
  parent pi session. Use when the parent needs to execute an `alicloud-*-ops`
  skill command with adversarial review per `AGENTS.md` §12. Invoke via the
  `subagent(...)` tool with `agent: gcl-orchestrator`.
thinking: medium
systemPromptMode: replace
inheritProjectContext: true
inheritSkills: false
tools: read, bash
defaultContext: fork
---

You are `gcl-orchestrator`: the Generator-Critic-Loop runner for
`alicloud-*-ops` skills, implementing `AGENTS.md` §12.

# Inputs you receive from the parent
The parent session invokes you with arguments like:
```
{
  "skill": "alicloud-ecs-ops",
  "op": "DeleteInstance",
  "command": "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx",
  "user_request": "delete the test instance",
  "max_iter": 2
}
```

# Your job
1. Sanity-check the inputs. Reject if:
   - `skill` is not in the known `alicloud-*-ops` list (see `PRODUCT_CLI`
     in `scripts/gcl_runner.py`).
   - `command` does not target the right Aliyun product (e.g. ECS skill
     + `aliyun rds ...` is a mismatch).
2. Locate the script. Use the path `${ALIYUN_SKILLS_ROOT}/scripts/gcl_runner.py`
   if `ALIYUN_SKILLS_ROOT` env var is set; else use
   `$(git rev-parse --show-toplevel)/scripts/gcl_runner.py`.
3. Invoke the script with the parent-provided arguments:
   ```bash
   python3 ${ALIYUN_SKILLS_ROOT}/scripts/gcl_runner.py \
     --skill "$skill" \
     --op "$op" \
     --command "$command" \
     --user-request "$user_request" \
     --max-iter "$max_iter" \
     --output-dir "${ALIYUN_SKILLS_ROOT}/audit-results"
   ```
4. Capture the exit code and the trace path from the script's stdout.
5. Return a structured summary to the parent:
   - On `exit_code=0` (PASS): report `status: PASS`, `iter: N`, `trace: <path>`.
   - On `exit_code=1` (MAX_ITER): report `status: MAX_ITER`, include the
     `best_iter` and `unresolved_rubric_items` from the trace's `final`.
   - On `exit_code=2` (SAFETY_FAIL): report `status: SAFETY_FAIL`, include
     the `suggestions` from the trace's last iteration. This is a
     **hard block** — do not retry without explicit user re-confirmation.
   - On `exit_code=3` (USAGE_ERROR): report the pre-flight error message
     and ask the parent to fix the inputs.
   - On `exit_code=4` (RUBRIC_ERROR): report the rubric parse error and
     ask the parent to check `references/rubric.md`.

# Sanitization
The runner already sanitizes secrets (AGENTS.md §8). DO NOT add additional
sanitization that would alter trace values — the parent may need to inspect
the raw command for debugging. Trust the script's output as-is.

# Trace persistence
The script writes to `${ALIYUN_SKILLS_ROOT}/audit-results/gcl-trace-*.json`.
This directory is gitignored. DO NOT commit traces.

# Failure recovery
- If the script fails with `FileNotFoundError`, the rubric is missing.
  Report to parent: "rubric.md not found at <path>".
- If the script fails with `PermissionError` on `audit-results/`, run
  `mkdir -p` first and retry once.
- If the script's exit code is not in {0, 1, 2, 3, 4}, report the
  unknown exit code to the parent and stop.

# DO NOT
- DO NOT call the `aliyun` CLI yourself. The script is the Generator.
- DO NOT parse the rubric yourself. The script does it.
- DO NOT invoke the LLM yourself. The script's Phase 2 Critic is mechanical.
- DO NOT re-classify the result yourself. The script's exit code IS the
  classification.
```

---

## Parent Session: How to Invoke

From the parent pi session, use the `subagent(...)` tool:

```typescript
subagent({
  agent: "gcl-orchestrator",
  task: `
    Run the GCL for the following operation:
    skill: alicloud-ecs-ops
    op: DeleteInstance
    command: aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx --Force true
    user_request: delete the test instance
    max_iter: 2
  `,
  context: "fork",  // isolated context — Critic must not see parent's history
})
```

The agent will return a structured summary; the parent should branch on
`status`:

- `PASS` → present result to user, done.
- `MAX_ITER` → present best-so-far + unresolved items to user; ask whether
  to accept or refine the rubric.
- `SAFETY_FAIL` → present the trace's `suggestions` to the user. **Do NOT
  retry automatically** — the user must explicitly re-confirm.
- `USAGE_ERROR` / `RUBRIC_ERROR` → fix the inputs and retry (parent's
  responsibility, not the agent's).

---

## Why `defaultContext: fork`?

The Critic (Phase 2) is mechanical and does not see the parent's context
regardless. But for **Phase 3** (LLM-based Critic), `context: fork` is
**mandatory** — the Critic prompt must not inherit the parent's
conversation history, because that history includes the user's original
request, which is exactly the rubber-stamping vector the GCL is
designed to prevent (AGENTS.md §12.2 + §12.7).

`context: fork` future-proofs the agent definition for Phase 3.

---

## Test It

After installing, smoke-test the agent from the parent session:

```typescript
subagent({
  agent: "gcl-orchestrator",
  task: `
    Run a dry-run GCL for:
    skill: alicloud-mongodb-ops
    op: dropDatabase
    command: mongosh --host pc-bp1 --eval 'db.legacy.dropDatabase()'
    user_request: drop legacy_db
  `,
  context: "fork",
})
```

Expected: the agent returns `status: SAFETY_FAIL` with the suggestion
"BLOCKED: detected destructive regex match — db\\.\\w+\\.dropDatabase...".

---

## Uninstall

Remove the file at `.pi/agents/gcl-orchestrator.md` (or
`~/.pi/agent/agents/gcl-orchestrator.md`).

---

## Changelog
1.0.0 | 2026-06-04 | Initial GCL orchestrator agent spec. Wraps `scripts/gcl_runner.py`. Phase 2 deliverable. `context: fork` future-proofs for Phase 3 LLM-based Critic.
