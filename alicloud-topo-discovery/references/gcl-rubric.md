# GCL Rubric (Phase 2 — Placeholder)

This rubric is a **placeholder** for full GCL §12 integration (Plan 4).
The 5 standard dimensions from AGENTS.md §12.3 apply:

| Dimension | Scale | Default Threshold |
|-----------|-------|-------------------|
| Correctness | 0/0.5/1 | ≥ 0.5 |
| Safety | 0/1 | = 1 |
| Idempotency | 0/0.5/1 | ≥ 0.5 |
| Traceability | 0/0.5/1 | ≥ 0.5 |
| Spec Compliance | 0/0.5/1 | ≥ 0.5 |

## Per Sub-Mode

| Sub-Mode | Correctness | Safety | Idempotency | Traceability | Spec Compliance |
|----------|-------------|--------|-------------|--------------|-----------------|
| scan-topo | Verify output format | Read-only gate | Same input → same output | CLI cmds captured | Field coverage |
| export-hcl | Field mapping accuracy | No sensitive leak | ID stability | manifest.json complete | Schema compliance |
| baseline | Directory structure | No data deletion | Overwrite idempotent | manifest per baseline | Retention policy |
| baseline-diff | Diff accuracy | Read-only diff | Same diff per input | Report includes timestamps | Risk rating |

> **TODO (Plan 4)**: Integrate with `scripts/gcl_runner.py` per AGENTS.md §12 workflow.