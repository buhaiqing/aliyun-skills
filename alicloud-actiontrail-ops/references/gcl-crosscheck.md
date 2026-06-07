# Quality Gate (GCL) — ActionTrail Cross-Checker

This skill participates in the Generator-Critic-Loop (GCL) defined in
[`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate)
in a **non-destructive cross-checker role**. Per `AGENTS.md` §12.8, this
skill is classified as `optional` (read-only audit) and is therefore **not
required to host its own `references/rubric.md` + `references/prompt-templates.md`**.

| Aspect | Setting |
|---|---|
| Required? | **No** (Phase 3-C, read-only audit) |
| GCL role | **Cross-checker** — verifies GCL traces against cloud-side ActionTrail events |
| Companion script | [`alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py`](../../alicloud-gcl-runner-ops/alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py) |
| Companion reference | [`alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md`](../alicloud-skill-generator/references/gcl-actiontrail-crosscheck-spec.md) |

## What the Cross-Check Catches

| Finding | Severity | Meaning |
|---|---|---|
| `PHANTOM_PASS` | high | Local GCL said PASS but no ActionTrail event exists (op never ran) |
| `PHANTOM_FAIL` | high | Local GCL said FAIL but ActionTrail has events (safety gate bypassed) |
| `RESOURCE_MISMATCH` | medium | Event exists but `ResourceName` differs from local trace's args |
| `TIMING_ANOMALY` | low | Event time > 1 hour from trace mtime (replay / clock drift / ingestion lag) |
| `API_ERROR` | high | LookupEvents failed; cross-check infrastructure issue (NOT a phantom) |
| `UNPARSEABLE_TRACE` | low | Trace command is not `aliyun ...` (dry-run, data-plane op) |

## Usage (companion script)

```bash
# Cross-check a single trace
python3 alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py \
  --trace audit-results/gcl-trace-20260604-103015-abc123.json

# Cross-check ALL traces (CI mode)
python3 alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck.py \
  --trace-dir audit-results/ \
  --report audit-results/crosscheck-$(date +%Y%m%d).json \
  --strict
```

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-06-04 | Phase 3-C: cross-checker role added. Companion script `gcl_actiontrail_crosscheck.py` (28.8 KB, 25 unit tests). ActionTrail remains `optional` per §12.8. |