# GCL Runner Scripts (Phase 2 of `AGENTS.md` §12)

This directory contains the **Phase 2 deliverables** of the
Generator-Critic-Loop (GCL) adversarial quality gate, defined in
[`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).

## Files

| File | Purpose |
|---|---|
| `gcl_runner.py` | Standalone Python 3.10+ CLI runner. Zero external dependencies. |
| `gcl_runner_test.py` | Pure-stdlib `unittest` suite. 100 tests. **Run on Python 3.10** (see [Python 3.10 Baseline](#python-310-baseline-mandatory)). |
| `gcl_cms_alarm_setup.py` | **Phase 3-B + Phase 4** alarm setup: idempotent PutMetricAlarm creator for phantom-op findings AND real pass-rate metrics. Reads `crosscheck-report-*.json`, creates/updates 5 phantom alarms (GCL-Phantom-Pass/Fail/Resource-Mismatch/Api-Errors/Timing-Anomaly). Also creates 3 pass-rate alarms (GCL-Safety-Fail-Rate, GCL-Correctness-Drop, GCL-Traceability-Gap) watching `acs_custom_gcl` namespace. |
| `gcl_actiontrail_crosscheck.py` | **Phase 3-C** cross-checker: verifies GCL traces against ActionTrail `LookupEvents`. Catches `PHANTOM_PASS` / `PHANTOM_FAIL` / `RESOURCE_MISMATCH` / `TIMING_ANOMALY`. |
| `gcl_actiontrail_crosscheck_test.py` | Pure-stdlib `unittest` suite. 25 tests, ~0.01s runtime. |
| `gcl_passrate_reporter.py` | **Phase 4** pass-rate reporter: aggregates GCL traces, computes per-skill and per-dimension pass-rates, pushes to CMS custom metrics (`acs_custom_gcl`). |
| `gcl_smart_alarm_engine.py` | **Phase 7** smart alert engine: pattern-driven dynamic alerting with auto-degradation. Detects `resource_safety_repeated`, `region_safety_burst`, etc. |
| `gcl_smart_alarm_cms_setup.py` | **Phase 7** CMS alarm setup for smart alert metrics. |
| `gcl_smart_alarm_test.py` | Unit tests for smart alarm engine (79 tests). |
| `gcl_smart_alarm_integration_test.py` | Integration tests for smart alarm + runner (12 tests). |
| `README-Smart-Alert.md` | **Phase 7** usage guide for smart alert loop. |
| `gcl_memory.py` | **§16** Execution Memory Index: `memory_store()`, `memory_retrieve()`, `memory_maintain()`. Pure Python 3.10+ stdlib. |
| `gcl_reflexion.py` | **§15** Reflexion Memory (Layer 2): failures + R4 success + R5 cross-skill + R6 remediation. |
| `gcl_reflexion_test.py` | **§15** Unit tests for reflexion (75+). |
| `gcl_memory_e2e_test.py` | **E2E-M1** Layer 1 → Layer 2 → report integration tests. |
| `memory_preflight.py` | **R2** Unified pre-flight retrieval (`preflight_retrieve`) for Layers 1–3 prompt slots. |
| `gcl_memory_test.py` | **§16** Unit tests for memory index. |
| `README.md` | This file. |

## What `gcl_runner.py` Does

Implements the loop flow from `AGENTS.md` §12.4:

```
[0] Pre-flight  — load rubric, resolve env.* / user.*, sanitize secrets
[0.5] Memory    — R2: `memory_preflight.py` → trace["memory_preflight"] + prompt slots
[1] Generate    — invoke the command (subprocess) and capture trace
[2] Critique    — re-classify output using the rubric's regex hot-spots
[3] Decide      — apply termination rules from `AGENTS.md` §12.5
```

And persists the trace per `AGENTS.md` §12.6:

```
./audit-results/gcl-trace-YYYYMMDD-HHMMSS-<rand6>.json
```

## Python 3.10 Baseline (MANDATORY)

CI and `pyproject.toml` pin **Python 3.10**. All scripts in this directory must run on 3.10 without extra dependencies.

| Do | Don't |
|----|-------|
| `datetime.now(tz=timezone.utc)` | `datetime.now(tz=datetime.UTC)` — **3.11+ only** |
| `from datetime import timezone` | `import tomllib` — **3.11+ only** |
| Run tests on 3.10 before push | Assume local 3.12 == CI |

```bash
# From repo root (same as CI gcl-test job; unittest needs cwd under scripts/)
python3 scripts/check_py310_compat.py
cd alicloud-gcl-runner-ops/scripts && python3 -m unittest gcl_runner_test -v
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

### Test accuracy / regression assessment (mechanical Critic)

When validating skill changes (not only cloud runtime), pass a JSON file via
`--test-assessment` (or embed `test_assessment` on the generator trace).
The mechanical Critic evaluates **accuracy over coverage** per
[`docs/gcl-critic-test-assessment-block.md`](../../docs/gcl-critic-test-assessment-block.md):

- `tests_accurate: false` → `blocking=true`, suggestion `TEST_ACCURACY: ...`, `decide()` → `RETRY` / `MAX_ITER`
- `regression_required: true` without `regression_runs_passed: true` (or `regression_evidence`) → `REGRESSION: ...`

Example:

```bash
python3 gcl_runner.py --skill alicloud-ecs-ops --op DescribeInstances \
  --command "./alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh DescribeInstances --PageSize 1" \
  --dry-run \
  --test-assessment /tmp/test-assessment.json
```

```json
{
  "tests_accurate": true,
  "regression_required": true,
  "regression_runs_passed": true,
  "regression_suites": ["bash alicloud-ecs-ops/test-skillopt-backward-compatibility.sh"]
}
```

## Phase 3-A: LLM-Based Critic (implemented 2026-06)

The default Critic is mechanical (pure regex). You can opt-in to LLM-based
Critic via `--critic-mode llm|hybrid` and configure endpoint in `.env`:

- **mechanical**: (default) pure-Python regex scoring, no LLM call needed
- **hybrid**: mechanical for hard safety gates (safety/credentials/wrapper compliance), LLM for nuanced scoring (**recommended production** when LLM is configured)
- **llm**: pure LLM scoring, mechanical is not used

The current implementation:
- Reuses existing `prompt-templates.md` (already present for every required/recommended skill)
- Calls OpenAI-compatible `/v1/chat/completions` endpoint (configurable via `GCL_CRITIC_LLM_ENDPOINT`)
- Strict JSON output matching the mechanical schema; scores clamped to 0/0.5/1
- Fail-open by default (`GCL_CRITIC_LLM_FAIL_OPEN=true`): LLM fails → fall back to default scores
- Pure stdlib `urllib` — no extra dependencies

### Configuring LLM Critic

```bash
# In your .env (root of repo; .env is gitignored)
GCL_CRITIC_MODE=hybrid
GCL_CRITIC_LLM_ENDPOINT=https://api.openai.com/v1/chat/completions
GCL_CRITIC_LLM_API_KEY=sk-xxxxxxx
GCL_CRITIC_LLM_MODEL=gpt-4o-mini
GCL_CRITIC_LLM_TIMEOUT=30
GCL_CRITIC_LLM_FAIL_OPEN=true
```

### Example invocation

```bash
python gcl_runner.py \
  --critic-mode hybrid \
  --skill alicloud-ecs-ops \
  --op DeleteInstance \
  --command "aliyun ecs DeleteInstance --InstanceId i-bp1xxxxxxxxxx --Force true"
```

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
| Phase 3 | LLM-based Critic, ActionTrail cross-check | ✅ Shipped 2026-06-04 |
| Phase 4 | CMS alarm on SAFETY_FAIL rate + pass-rate metrics | ✅ Shipped 2026-06-04 |
| Phase 5 | Auto-rollout to 7 `recommended` skills (SLB, ACK, etc.) | ✅ Shipped 2026-06-04 |
| Phase 6 | Hallucination Detection (H) pre-execution gate | ✅ Shipped 2026-06-10 |
| Phase 7 | Smart Alert Loop — pattern-driven auto-degradation | ✅ Shipped 2026-06-13 |

## Layer 2 Reflexion CLI (`gcl_reflexion.py`)

Wrapper failures (plan **B**) and offline L1 aggregation (plan **C**) — see [`docs/memory-strategy.md`](../../docs/memory-strategy.md).

```bash
# Plan B: store allowlisted wrapper failure from local trace JSON
python3 gcl_reflexion.py store-wrapper-lite \
  --skill alicloud-ecs-ops \
  --trace-file .runtime/traces/alicloud-ecs-ops/trace-*.json

# Plan C: promote failed wrapper L1 entries (dry-run / apply)
python3 gcl_reflexion.py promote-from-memory \
  --memory-root .runtime/memory

make memory-maintain-apply   # includes promote-from-memory --apply

# Optional: regenerate docs/failure-patterns.md after maintain+promote
GCL_REFLEXION_REPORT_ON_MAINTAIN=true make memory-maintain-apply

# Report + maintain (unchanged)
python3 gcl_reflexion.py report
python3 gcl_reflexion.py maintain --apply
```

## Related

- [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate) — canonical GCL spec
- [`alicloud-skill-generator/references/gcl-rollout-spec.md`](../alicloud-skill-generator/references/gcl-rollout-spec.md) — how to generate GCL files for a new skill
- [`alicloud-skill-generator/references/gcl-orchestrator-agent.md`](../alicloud-skill-generator/references/gcl-orchestrator-agent.md) — pi-subagents agent definition that wraps this script
- [`README-Smart-Alert.md`](./README-Smart-Alert.md) — Phase 7 Smart Alert Loop usage guide
- `audit-results/` — gitignored; ephemeral trace storage
