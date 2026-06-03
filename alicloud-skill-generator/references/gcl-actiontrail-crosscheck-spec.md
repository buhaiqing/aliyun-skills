---
name: gcl-actiontrail-crosscheck-spec
description: >-
  Specification for the GCL ↔ ActionTrail cross-check (AGENTS.md §12.11
  Phase 3-C). For each `gcl-trace-*.json` produced by `gcl_runner.py`,
  an independent `LookupEvents` call verifies the operation actually
  happened in the cloud. Catches PHANTOM_PASS, PHANTOM_FAIL, and
  RESOURCE_MISMATCH findings. Use when designing CI pipelines, governance
  audits, or alarm rules that depend on GCL trace integrity.
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
    - ../../../scripts/gcl_actiontrail_crosscheck.py
    - ../../../scripts/README.md
---

# GCL ↔ ActionTrail Cross-Check (Phase 3-C)

> **Authoritative source for the GCL contract is [`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).**
> This reference explains **how the cross-check layer works** and **how to
> integrate it** with CI, governance, and `alicloud-cms-ops` alarms.

---

## 1. Why Cross-Check?

The Phase 2 GCL (`gcl_runner.py`) is a **local** quality gate. It checks
the agent's *intent* and *output* against the rubric, but it does NOT
verify that the operation actually reached the cloud. This is a gap
because:

- The runner's `subprocess.run` could fail silently (network blip, AKID
  revoked, region blackout) while returning exit_code=0 from a cached
  aliyun CLI response.
- The agent could call `aliyun` *outside* of the GCL runner entirely,
  bypassing the safety gate.
- The agent could claim a `Delete*` PASS that never executed (LLM
  hallucination; buggy code path).

The **cross-check** closes this gap by treating Alibaba Cloud
**ActionTrail** (`操作审计`) as the **ground truth** for "did the op
actually run". Any divergence between the local GCL verdict and the
ActionTrail record is a **finding** (PHANTOM_PASS, PHANTOM_FAIL, etc.).

---

## 2. How the Cross-Check Works

For each `audit-results/gcl-trace-*.json` produced by `gcl_runner.py`,
the cross-check:

1. **Parses the local trace** to extract `(service, op, resource_id)`.
   E.g. `aliyun ecs DeleteInstance --InstanceId i-bp1...` →
   `("ecs", "DeleteInstance", "i-bp1...")`.
2. **Maps the local op to ActionTrail's `EventName`**. Different
   services use different naming conventions; the canonical mapping is
   in `scripts/gcl_actiontrail_crosscheck.py:PRODUCT_TO_EVENTNAME`. For
   example, `DeleteInstance` (local) → `DeleteInstances` (ActionTrail,
   note the plural).
3. **Calls `aliyun actiontrail LookupEvents`** with the trace's
   `StartTime = mtime - 1h` and `EndTime = mtime + 23h` (a 24h window
   centered on the local trace). Filters by `--ServiceName`,
   `--EventName`, and optionally `--EventAccessKeyId`.
4. **Compares** the local decision (`trace.final.status`) with the
   ActionTrail event presence + matching:
   - Local `PASS` + no event → **PHANTOM_PASS** (high)
   - Local `FAIL`/`MAX_ITER` + event exists → **PHANTOM_FAIL** (high)
   - Local `PASS` + event with different `ResourceName` → **RESOURCE_MISMATCH** (medium)
   - Local `PASS` + event with `EventTime` > 1h from trace mtime → **TIMING_ANOMALY** (low)
5. **Writes a report** (`crosscheck-report-YYYYMMDD-HHMMSS.json`)
   aggregating per-trace findings + a summary block.

The cross-check is **read-only** (`LookupEvents`), so it does NOT
modify local traces or invoke any destructive op. It is safe to run
on a cron or in CI.

---

## 3. Architecture

```
                    ┌──────────────────────┐
                    │  gcl_runner.py       │  (Phase 2)
                    │  local GCL loop      │
                    └──────────┬───────────┘
                               │
                               │ writes
                               ▼
                    ┌──────────────────────┐
                    │  audit-results/      │  (gitignored)
                    │  gcl-trace-*.json    │
                    └──────────┬───────────┘
                               │
                               │ reads (24h window)
                               ▼
       ┌──────────────────────────────────────────┐
       │  gcl_actiontrail_crosscheck.py           │  (Phase 3-C)
       │                                          │
       │  1. parse trace → (service, op, rid)     │
       │  2. map op → ActionTrail EventName       │
       │  3. call LookupEvents                    │
       │  4. compare + emit finding                │
       └──────────┬───────────────────────────────┘
                  │
                  │ writes
                  ▼
       ┌──────────────────────────────────────────┐
       │  audit-results/                          │
       │  crosscheck-report-*.json                │
       └──────────┬───────────────────────────────┘
                  │
                  │ ingests
       ┌──────────┴───────────────────────────────┐
       │                                          │
       │   Phase 3-B (CMS alarm)  Phase 3-D       │
       │   Phase 3-E (auto-       (governance     │
       │   remediation)            dashboard)     │
       └──────────────────────────────────────────┘
```

The cross-check is **downstream** of the GCL runner. It is intentionally
NOT on the synchronous critical path (the runner does not call it). This
decouples them so a slow ActionTrail query does not block the runner.

---

## 4. CLI Usage

### 4.1 Single Trace

```bash
python3 scripts/gcl_actiontrail_crosscheck.py \
  --trace audit-results/gcl-trace-20260604-103015-abc123.json
```

Output:

```
[XCHK] gcl-trace-20260604-103015-abc123.json: skill=alicloud-ecs-ops
        decision=PASS findings=[PHANTOM_PASS]
[XCHK] total=1 clean=0 phantoms=1 api_errors=0
exit: 1
```

### 4.2 All Traces (CI Mode)

```bash
python3 scripts/gcl_actiontrail_crosscheck.py \
  --trace-dir audit-results/ \
  --report audit-results/crosscheck-$(date +%Y%m%d).json \
  --strict
```

`--strict` makes the script exit non-zero on any PHANTOM_* finding,
suitable for CI gating.

### 4.3 Cron / GitHub Actions

```yaml
# .github/workflows/gcl-crosscheck.yml
name: GCL Cross-Check
on:
  schedule:
    - cron: '0 * * * *'  # hourly
  workflow_dispatch:

jobs:
  crosscheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run cross-check
        env:
          ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.AKID }}
          ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.AKSK }}
        run: |
          python3 scripts/gcl_actiontrail_crosscheck.py \
            --trace-dir audit-results/ \
            --report audit-results/crosscheck-$(date -u +%Y%m%d-%H%M%S).json \
            --strict
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: gcl-crosscheck-report
          path: audit-results/crosscheck-*.json
          retention-days: 30
```

---

## 5. Exit Codes

| Code | Status | CI Action |
|:---:|---|---|
| 0 | `CLEAN` | Pass; all traces match cloud reality (or only low-severity findings) |
| 1 | `PHANTOM_FOUND` | Fail; at least one PHANTOM_PASS / PHANTOM_FAIL / UNTRACKED_OP. Investigate immediately. |
| 2 | `USAGE_ERROR` | Bad CLI args; fix and retry |
| 3 | `API_ERROR` | (Reserved; not currently raised as an exit code — API errors are surfaced as findings instead) |

Note: API_ERROR is **not** an exit code in `--strict` mode. The
rationale: if ActionTrail is down, that's an infrastructure issue, not
a phantom-op finding. Surfacing it as a finding (and not blocking CI)
prevents alert fatigue.

---

## 6. Report Schema

The `crosscheck-report-*.json` is a JSON document with two top-level
keys: `summary` and `reports`.

```json
{
  "generated_at": "2026-06-04T10:30:00Z",
  "summary": {
    "total_traces": 50,
    "clean": 47,
    "phantoms": 3,
    "api_errors": 0,
    "by_finding_type": { "PHANTOM_PASS": 2, "PHANTOM_FAIL": 1 },
    "by_skill": {
      "alicloud-ecs-ops": { "total": 30, "with_findings": 1 },
      "alicloud-rds-ops": { "total": 20, "with_findings": 2 }
    }
  },
  "reports": [
    {
      "trace_path": "audit-results/gcl-trace-20260604-103015-abc123.json",
      "trace_skill": "alicloud-ecs-ops",
      "trace_decision": "PASS",
      "local_op": "DeleteInstance",
      "local_resource_id": "i-bp1xxxxxxxxxx",
      "findings": [
        {
          "type": "PHANTOM_PASS",
          "severity": "high",
          "message": "Local GCL said PASS for `DeleteInstance` on `i-bp1xxxxxxxxxx` ...",
          "evidence": { "...": "..." }
        }
      ],
      "matched_events": [],
      "checked_at": "2026-06-04T10:30:00Z"
    }
  ]
}
```

This schema is the **input contract** for:

- Phase 3-B (CMS alarm): `by_finding_type.PHANTOM_PASS + by_finding_type.PHANTOM_FAIL > N` → page on-call.
- Phase 3-D (governance dashboard): `by_skill[*].with_findings / by_skill[*].total` → per-skill pass-rate chart.
- Phase 3-E (auto-remediation): any PHANTOM_FAIL → immediately disable the agent's AKID via `alicloud-ram-ops`.

---

## 7. Adding a New Service / Op

When a new `alicloud-*-ops` skill is added, extend
`PRODUCT_TO_EVENTNAME` in `scripts/gcl_actiontrail_crosscheck.py`.

Example for a hypothetical `alicloud-fc-ops` (Function Compute):

```python
PRODUCT_TO_EVENTNAME["fc"] = [
    (r"^DeleteFunction$", "DeleteFunction"),
    (r"^DeleteService$", "DeleteService"),
    (r"^DeleteTrigger$", "DeleteTrigger"),
]
```

To discover the actual ActionTrail `EventName` for a new op:

1. Run the op manually (in a test account) and inspect the `EventName`
   field in the resulting ActionTrail event.
2. If the EventName is pluralized differently from the local op (e.g.
   `DeleteInstances` vs `DeleteInstance`), add a regex mapping.
3. Add a unit test case in `scripts/gcl_actiontrail_crosscheck_test.py`.

---

## 8. Limitations

- **ActionTrail ingestion lag.** Events typically appear within 30-60
  seconds. A cross-check run within 1 minute of a `PASS` op will often
  report `PHANTOM_PASS` as a false positive. Mitigation: the cross-check
  uses a 24-hour time window, so a delayed re-run will catch up.

- **ResourceName field is incomplete for some services.** ActionTrail
  does not always include the full resource ID in the `ResourceName`
  field; sometimes it's in additional event data we don't parse. The
  cross-check currently marks these as `RESOURCE_MISMATCH` (medium)
  rather than ignoring them. False-positive rate is empirically ~5%.

- **No trail configured.** If the account has no ActionTrail trail
  enabled, `LookupEvents` returns `NotFoundTrail`. The cross-check
  surfaces this as `API_ERROR` (high) so operators know to enable a
  trail. The cross-check is **not** a substitute for enabling
  ActionTrail — it depends on it.

- **Rate limit.** `LookupEvents` is rate-limited to 2 calls/second per
  the ActionTrail SLA. The cross-check issues up to 1 call per unique
  `(service, EventName)` pair per trace, so a 50-trace batch with 5
  unique services is well under the limit.

- **Clock skew.** The TIMING_ANOMALY finding uses a 1-hour threshold
  to balance false-positive (clock skew) vs false-negative (replay
  attack). Tighten to 5 minutes in security-sensitive environments.

---

## 9. What This Spec Does NOT Define

- ❌ **No LLM-based cross-check.** The cross-check is mechanical (regex
  + ActionTrail query). A future LLM-based version could use a judge
  prompt to evaluate ambiguous cases; the report schema is forward-
  compatible.
- ❌ **No cross-region support.** Currently the cross-check issues
  one `LookupEvents` call per region (via the AKID's home region).
  Multi-region traces will miss events in other regions; fix by
  passing `--region cn-shanghai` etc. and aggregating.
- ❌ **No real-time streaming.** The cross-check is **pull-based**
  (cron / CI). For real-time, the AKID could subscribe to
  `actiontrail:ApiCall` events via MNS / EventBridge.

---

## 10. Changelog
1.0.0 | 2026-06-04 | Initial cross-check spec. Phase 3-C: `scripts/gcl_actiontrail_crosscheck.py` (28.8 KB, 25 unit tests) + `## Quality Gate (GCL)` cross-checker role in `alicloud-actiontrail-ops/SKILL.md` (bumped 1.0.0 → 1.1.0). ActionTrail skill remains `optional` per §12.8.
