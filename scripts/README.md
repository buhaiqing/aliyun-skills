# GCL Runner Scripts (Phase 2 of `AGENTS.md` §12)

This directory contains the **Phase 2 deliverables** of the
Generator-Critic-Loop (GCL) adversarial quality gate, defined in
[`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).

## Files

| File | Purpose |
|---|---|
| `gcl_runner.py` | Standalone Python 3.10+ CLI runner. Zero external dependencies. |
| `gcl_runner_test.py` | Pure-stdlib `unittest` suite. 60 tests, ~0.02s runtime. |
| `gcl_cms_alarm_setup.py` | **Phase 3-B** alarm setup: idempotent PutMetricAlarm creator for phantom-op findings. Reads `crosscheck-report-*.json`, creates/updates 5 alarms (GCL-Phantom-Pass/Fail/Resource-Mismatch/Api-Errors/Timing-Anomaly). |
| `gcl_actiontrail_crosscheck.py` | **Phase 3-C** cross-checker: verifies GCL traces against ActionTrail `LookupEvents`. Catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`. |
| `gcl_actiontrail_crosscheck_test.py` | Pure-stdlib `unittest` suite. 25 tests, ~0.01s runtime. |
| `README.md` | This file. |

## What `gcl_runner.py` Does

Implements the loop flow from `AGENTS.md` §12.4:

```
[0] Pre-flight  — load rubric, resolve env.* / user.*, sanitize secrets
[1] Generate    — invoke the command (subprocess) and capture trace
[2] Critique    — re-classify output using the rubric's regex hot-spots
[3] Decide      — apply termination rules from `AGENTS.md` §12.5
```

And persists the trace per `AGENTS.md` §12.6:

```
./audit-results/gcl-trace-YYYYMMDD-HHMMSS-<rand6>.json
```

## Quick Start

### 1. Pass-Through (real `aliyun` command)

```bash
# Ensure you have ALIBABA_CLOUD_ACCESS_KEY_ID / _SECRET set
export ALIBABA_CLOUD_ACCESS_KEY_ID=LTAI5xxxxxx
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=xxxxxx

python3 scripts/gcl_runner.py \
  --skill alicloud-ecs-ops \
  --op DeleteInstance \
  --command "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx --Force true"
echo "exit: $?"  # 0 = PASS, 1 = MAX_ITER, 2 = SAFETY_FAIL
```

The script will:

1. Load `alicloud-ecs-ops/references/rubric.md` and parse its per-op sub-rules
   and detection regex list.
2. Pre-flight: verify `--skill` is known, `aliyun ecs` matches the skill,
   `DeleteInstance` is documented in the rubric, and the command does not
   contain an inlined secret.
3. Run the command via `subprocess.run` with a 300s timeout.
4. Re-classify the result with the rubric's regex list (the "Critic").
5. Apply termination rules from `AGENTS.md` §12.5.
6. Persist the trace to `./audit-results/gcl-trace-<ts>.json`.

### 2. Dry-Run (Critic-Only Regression)

```bash
python3 scripts/gcl_runner.py \
  --skill alicloud-mongodb-ops \
  --op dropDatabase \
  --command "mongosh --host pc-bp1 --eval 'db.legacy.dropDatabase()'" \
  --user-request "drop legacy_db" \
  --dry-run
```

The `--dry-run` flag skips the subprocess and synthesizes a generator trace
with the user-supplied command. Use it to **test the Critic's regex detection
without actually executing the command** — useful for offline rubric
evaluation and CI integration tests.

### 3. Custom Rubric Path

```bash
python3 scripts/gcl_runner.py \
  --skill alicloud-ecs-ops \
  --op DeleteInstance \
  --command "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx" \
  --rubric /path/to/custom-rubric.md \
  --output-dir /custom/audit-dir
```

## Exit Codes

| Code | Status | Meaning | Action |
|:---:|---|---|---|
| 0 | `PASS` | All rubric dimensions ≥ threshold (0.5) | Done |
| 1 | `MAX_ITER` | Reached `max_iter`; best-so-far returned | Inspect trace, refine rubric |
| 2 | `SAFETY_FAIL` | Safety = 0 (destructive regex matched, op not documented, or secret inlined) | **ABORT**; do not retry without user re-confirmation |
| 3 | `USAGE_ERROR` | Bad CLI args, wrong product prefix, op not in rubric, inlined secret | Fix CLI invocation |
| 4 | `RUBRIC_ERROR` | Rubric file missing or unparseable | Check `references/rubric.md` exists and is well-formed |

## How the Critic Works (Phase 2)

The Phase 2 Critic is a **pure-Python regex re-classifier**, not an LLM
call. This is a deliberate design choice:

- **Deterministic** — the same input always produces the same output
- **CI-friendly** — runs in <100ms; no API keys, no network
- **Reproducible** — same rubric, same command, same result
- **Auditable** — every score is explained by a regex match (see
  `critic.matched_regexes` in the trace)

The rubric's "Detection Regex" table is the Critic's score function. The
Critic applies every regex to `(command + stdout + stderr)` and computes:

```python
for pattern, risk in rubric["regexes"]:
    if re.search(pattern, full_text, ...):
        matched.append(...)
        if _risk_severity(risk) > _risk_severity(highest_risk):
            highest_risk = risk

# Safety is 0 if any DESTRUCTIVE-* or FATAL regex matched
safety = 0 if "DESTRUCTIVE" in highest_risk or "FATAL" in highest_risk else 1
```

For the 5 core dimensions (Correctness, Safety, Idempotency,
Traceability, Spec Compliance) and 3 Aliyun extensions (Region Compliance,
Credential Hygiene, Well-Architected), the scoring is documented in
`gcl_runner.py:critique()`.

## Phase 3: LLM-Based Critic (future)

The current Critic is mechanical. A future Phase 3 may add an LLM-based
Critic that uses the rubric as a "judge prompt" and the trace as the
"context" — useful for subtle safety questions the regex list cannot
catch. The script's design makes this drop-in:

- The `critique()` function takes `(op, trace, rubric)` and returns the
  same dict shape regardless of internal implementation.
- A future `critique_llm(op, trace, rubric)` could replace the regex
  re-classifier without changing the loop flow, persistence, or CLI.

## Integration with Parent Agent (pi)

A parent pi agent can invoke this script via `bash` and parse the trace
JSON for downstream decisions. A reusable agent definition is provided in
`alicloud-skill-generator/references/gcl-orchestrator-agent.md` —
install it to `.pi/agents/gcl-orchestrator.md` (project scope) or
`~/.pi/agent/agents/gcl-orchestrator.md` (user scope) to enable the
`/gcl-orchestrator` slash command.

## Testing

```bash
# Run all 60 runner tests
python3 scripts/gcl_runner_test.py

# Run all 25 crosscheck tests
python3 scripts/gcl_actiontrail_crosscheck_test.py

# Run with verbose output
python3 -m unittest scripts.gcl_runner_test -v 2>/dev/null \
  || (cd /Users/bohaiqing/opensource/git/aliyun-skills && \
      python3 scripts/gcl_runner_test.py -v)

# Run a specific test class
python3 -c "
import sys
sys.path.insert(0, 'scripts')
import unittest
import gcl_runner_test
suite = unittest.TestLoader().loadTestsFromTestCase(gcl_runner_test.SanitizeTests)
unittest.TextTestRunner(verbosity=2).run(suite)
"
```

## Design Decisions

| Decision | Why |
|---|---|
| **Pure stdlib** (no `click` / `pyyaml` / `httpx`) | Repo is `pyproject.toml`-managed; adding deps would require `uv pip install` everywhere |
| **Mechanical Critic (not LLM)** | Deterministic, CI-friendly, free; LLM Critic is a Phase 3 drop-in |
| **Subprocess for Generator (not SDK)** | Matches `aliyun` CLI as the primary path per `cli-first` / `dual-path` skills; SDK is a separate path documented in `references/api-sdk-usage.md` |
| **Trace persisted as JSON (not SQLite)** | AGENTS.md §12.6 specifies JSON; humans can `jq` it; downstream tools (CMS / ActionTrail) can ingest |
| **Schema is exactly AGENTS.md §12.6** | Future Phase 2 tools can ingest all 14 skills' traces uniformly |
| **Regex list parsed from rubric, not hard-coded** | Adding a new skill = adding a new rubric. No code change. |
| **`--dry-run` keeps the user's command** | The Critic needs the real command to classify it; just skip the subprocess |
| **Inlined secret → USAGE_ERROR (exit 3)**, not silently sanitized | Surface the bug; never silently fix a security issue (AGENTS.md §8) |

## What This Script Does NOT Do (Phase 2 Boundaries)

- ❌ **Does not call any LLM.** Phase 3 will add `critique_llm()`.
- ❌ **Does not handle multi-step operations** (e.g. `DeleteVpc` requires
  `DescribeVSwitches` → `DeleteVSwitch` for each → `DeleteVpc`). The
  rubric's per-op sub-rules describe the cascade, but the runner executes
  one command per invocation. For multi-step ops, **wrap them in a shell
  script and pass the script as `--command`**.
- ❌ **Does not auto-retry on transient errors** (throttling, network
  blips). The runner executes once per iteration. The Generator's
  template (in `references/prompt-templates.md`) is the right place to
  add retry-with-backoff logic.
- ❌ **Does not invoke ActionTrail / CMS for cross-checks** (AGENTS.md
  §12.11 Phase 3-4). That's a future enhancement.
- ❌ **Does not enforce the `gcl_classification` field** in rubric
  frontmatter. Phase 3 will reject `--skill` if its rubric is
  `classification: optional` (read-only skills don't need GCL).

## Future Work (per `AGENTS.md` §12.11)

| Phase | Scope | Status |
|---|---|---|
| Phase 2 (this) | Mechanical Critic, subprocess Generator, JSON trace | ✅ Shipped 2026-06-04 |
| Phase 3 | LLM-based Critic, ActionTrail cross-check | Pending |
| Phase 4 | CMS alarm on SAFETY_FAIL rate | Pending |
| Phase 5 | Auto-rollout to 7 `recommended` skills (SLB, ACK, etc.) | Pending |

## Related

- [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate) — canonical GCL spec
- [`alicloud-skill-generator/references/gcl-rollout-spec.md`](../alicloud-skill-generator/references/gcl-rollout-spec.md) — how to generate GCL files for a new skill
- [`alicloud-skill-generator/references/gcl-orchestrator-agent.md`](../alicloud-skill-generator/references/gcl-orchestrator-agent.md) — pi-subagents agent definition that wraps this script
- `audit-results/` — gitignored; ephemeral trace storage
