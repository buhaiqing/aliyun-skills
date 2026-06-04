---
name: gcl-passrate-metrics-guide
description: >-
  Phase 4 integration guide: wire GCL trace pass-rates to CMS custom metrics
  and alarms. Covers `gcl_passrate_reporter.py` CLI, metric namespace, alarm
  thresholds, cron pipeline, and dashboard visualization.
license: MIT
metadata:
  type: meta-reference
  applies_to: alicloud-cms-ops
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../AGENTS.md
  related:
    - rubric.md
    - ../../../scripts/gcl_passrate_reporter.py
    - ../../../scripts/gcl_cms_alarm_setup.py
---

# Phase 4: GCL Pass-Rate Metrics Integration (CMS)

> **Prerequisite:** Phase 3-A/B/C must be running to produce
> `gcl-trace-*.json` files. See `gcl-actiontrail-crosscheck-spec.md`
> and `gcl-cms-alarm-guide.md`.

---

## 1. Architecture

```
cron (every N hours)
  │
  ├── gcl_runner.py                          (Phase 2)
  │     └── audit-results/gcl-trace-*.json
  │
  ├── gcl_actiontrail_crosscheck.py          (Phase 3-C)
  │     └── audit-results/crosscheck-report-*.json
  │
  ├── gcl_passrate_reporter.py               (Phase 4 — this guide)
  │     ├── reads:    gcl-trace-*.json
  │     └── pushes:   aliyun cms PutCustomMetric → acs_custom_gcl
  │
  └── gcl_cms_alarm_setup.py                 (Phase 3-B + Phase 4)
        ├── reads:    crosscheck-report-*.json (phantom alarms)
        └── watches:  acs_custom_gcl metrics (pass-rate alarms)
              ├── GCL-Safety-Fail-Rate    (P1)
              ├── GCL-Correctness-Drop    (P2)
              └── GCL-Traceability-Gap    (P3)
```

The pipeline is **additive** — each phase builds on the previous:

| Phase | Input | Output |
|-------|-------|--------|
| 2 | `aliyun` CLI command | `gcl-trace-*.json` |
| 3-C | `gcl-trace-*.json` | `crosscheck-report-*.json` |
| **4 (this)** | `gcl-trace-*.json` | `acs_custom_gcl` metrics + alarms |

---

## 2. Custom Metric Namespace: `acs_custom_gcl`

### 2.1 Per-Skill Dimension Metrics

| MetricName | Dimensions | Type | Meaning |
|---|---|---|---|
| `gcl_pass_rate_{dim}` | `[{"skill":"alicloud-ecs-ops"}]` | Average | Percentage of traces where this dimension scored ≥ 0.5 |
| `gcl_decision_{decision}` | `[]` | Average | Percentage of all traces with this decision (`pass`, `abort_safety`, `retry`, `max_iter`) |
| `gcl_safety_fail_count` | `[]` | Average | Absolute count of `ABORT_SAFETY` decisions in the window |

Where `{dim}` is one of: `correctness`, `safety`, `idempotency`, `traceability`,
`spec_compliance`, `region_compliance`, `credential_hygiene`, `well_architected`.

### 2.2 Global Metrics (no skill dimension)

| MetricName | Dimensions | Type | Meaning |
|---|---|---|---|
| `gcl_global_pass_rate_{dim}` | `[]` | Average | Overall pass-rate for this dimension across ALL skills |
| `gcl_decision_pass` | `[]` | Average | % of traces with PASS decision |
| `gcl_decision_abort_safety` | `[]` | Average | % of traces with ABORT_SAFETY decision |
| `gcl_decision_retry` | `[]` | Average | % of traces with RETRY decision |
| `gcl_decision_max_iter` | `[]` | Average | % of traces with MAX_ITER decision |
| `gcl_safety_fail_count` | `[]` | Average | Absolute count of SAFETY_FAILs |

### 2.3 Metric Period

All metrics use `Period=300` (5-minute buckets) by default, set by
`gcl_passrate_reporter.py`. The reporting cron should run at least
once per period (every 5 minutes to 1 hour, depending on trace volume).

---

## 3. Alarm Thresholds

These alarms are defined in `scripts/gcl_cms_alarm_setup.py` as Phase 4 entries.

| Alarm Name | Metric | Threshold | Operator | Severity | Meaning |
|---|---|---|---|---|---|
| `GCL-Safety-Fail-Rate` | `gcl_safety_fail_count` | > 1 | `>` | P1 — CRITICAL | 2+ Safety failures in the window — agent may be ignoring Safety gates |
| `GCL-Correctness-Drop` | `gcl_global_pass_rate_correctness` | < 90% | `<` | P2 — HIGH | Correctness pass-rate below 90% — systematic wrong-argument pattern |
| `GCL-Traceability-Gap` | `gcl_global_pass_rate_traceability` | < 80% | `<` | P3 — WARNING | Traces lack full command/response — audit trail degrading |

### 3.1 Threshold Tuning

Initial thresholds are conservative (low false-positive). After 30 days of
data, review and adjust:

```
# Check per-skill correctness pass-rate
python3 scripts/gcl_passrate_reporter.py --trace-dir audit-results/ --since 7d --dry-run

# Read the JSON report for real rates
```

If a dimension consistently hits the alarm, either:
- The rubric is too strict for that skill → relax dimension thresholds per skill
- The Generator has a systematic bug → fix the skill's prompt templates
- The skill is genuinely dangerous → keep the alarm and investigate each firing

---

## 4. CLI Usage

### 4.1 Run the Pass-Rate Reporter

```bash
# Default: last 24h, push to CMS
python3 scripts/gcl_passrate_reporter.py \
  --trace-dir audit-results/ \
  --region cn-hangzhou

# Last 7d, dry-run (no CMS call)
python3 scripts/gcl_passrate_reporter.py \
  --trace-dir audit-results/ \
  --since 7d \
  --dry-run

# Save report locally without pushing
python3 scripts/gcl_passrate_reporter.py \
  --trace-dir audit-results/ \
  --since 24h \
  --output passrate-20260604.json
```

### 4.2 Setup Corresponding Alarms

```bash
# Create/update all 3 pass-rate alarms (idempotent)
python3 scripts/gcl_cms_alarm_setup.py \
  --report-dir audit-results/ \
  --contact-group gcl-oncall \
  --region cn-hangzhou

# Dry-run
python3 scripts/gcl_cms_alarm_setup.py --dry-run
```

### 4.3 Verify Metrics in CMS

```bash
# Check that custom metrics were created
aliyun cms DescribeCustomMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_custom_gcl

# Check a specific alarm exists
aliyun cms DescribeMetricAlarmList \
  --RegionId cn-hangzhou \
  --AlarmName GCL-Safety-Fail-Rate
```

---

## 5. Cron Integration

Recommended: run the reporter before the alarm setup in the same cron job.

```bash
# /etc/cron.d/gcl-passrate-alarm
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
ALIBABA_CLOUD_ACCESS_KEY_ID=<redacted>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<redacted>

# Hourly: pass-rate report → CMS → alarm reconciliation
0 * * * * root cd /path/to/aliyun-skills && \
  python3 scripts/gcl_passrate_reporter.py \
    --trace-dir audit-results/ \
    --since 24h && \
  python3 scripts/gcl_cms_alarm_setup.py \
    --report-dir audit-results/ \
    --contact-group gcl-oncall
```

The `--since 24h` window ensures the reporter always covers the last day.
If traces are sparse, increase to `--since 7d` for better signal.

---

## 6. Dashboard (Grafana / CMS Custom Dashboard)

### 6.1 GCL Pass-Rate Panel

| Panel | Metric | Query | Color |
|---|---|---|---|
| Safety Pass-Rate | `gcl_global_pass_rate_safety` | `avg(gcl_global_pass_rate_safety)` | Green ≥ 100%, Red < 100% |
| Correctness Pass-Rate | `gcl_global_pass_rate_correctness` | `avg(gcl_global_pass_rate_correctness)` | Green ≥ 95%, Yellow 80-95%, Red < 80% |
| Traceability Pass-Rate | `gcl_global_pass_rate_traceability` | `avg(gcl_global_pass_rate_traceability)` | Green ≥ 90%, Yellow 70-90%, Red < 70% |
| SAFETY_FAIL Count | `gcl_safety_fail_count` | `sum(gcl_safety_fail_count)` | Red if > 0 |
| Decision Distribution | `gcl_decision_*` | Stacked bar | PASS green, RETRY yellow, ABORT red |

### 6.2 Per-Skill Heatmap

| Column | Metric | Color coding |
|---|---|---|
| Skill | `gcl_pass_rate_safety{skill="alicloud-ecs-ops"}` | Green ≥ 100% |
| Skill | `gcl_pass_rate_correctness{skill="alicloud-ecs-ops"}` | Green ≥ 95% |
| Skill (cont.) | ... | ... |

---

## 7. Alert Response Playbook

| Alarm | Trigger | Action |
|---|---|---|
| **GCL-Safety-Fail-Rate** | 2+ SAFETY_FAILs | (1) List failing traces: `ls -t audit-results/gcl-trace-*.json \| head -5`. (2) Check each trace's `decision` and `critic.suggestions`. (3) If Generator bypassed a Safety gate: fix the skill's prompt templates. (4) If Critic was incorrect: adjust the rubric's regex. (5) Acknowledge via CMS. |
| **GCL-Correctness-Drop** | Correctness < 90% | (1) Find low-correctness skils: `python3 gcl_passrate_reporter.py --dry-run`. (2) For each low skill, check recent traces for wrong-argument patterns. (3) Common cause: API response shape changed. (4) Fix: update the skill's API response fields in `references/api-sdk-usage.md`. |
| **GCL-Traceability-Gap** | Traceability < 80% | (1) Inspect traces missing `result_excerpt` or `request_id`. (2) Likely cause: timeouts or truncated output. (3) Fix: increase timeout in `gcl_runner.py` or add retry-with-backoff to the Generator template. |

---

## 8. What This Guide Does NOT Cover

- ❌ **Real-time streaming.** Metrics are push-based (cron → PutCustomMetric).
  For near-real-time, pair with EventBridge → CMS custom event source.
- ❌ **Auto-remediation.** When Safety fail-rate spikes, the playbook says
  "investigate and fix" but does not auto-pause the agent. Future Phase 4-B
  may add circuit-breaker (disable AKID or pause GCL runner on SRE threshold).
- ❌ **Cross-region aggregation.** Each region has its own `acs_custom_gcl`
  namespace. Multi-region dashboards need a Grafana multi-source query.
- ❌ **Historical retention.** CMS custom metrics retain 30 days by default.
  For longer retention, export traces to OSS via `ossutil cp`.

---

## 9. Changelog

1.0.0 | 2026-06-04 | Phase 4 pass-rate metrics integration guide. Custom metric
  schema (`acs_custom_gcl` namespace), 3 alarm thresholds (P1-P3), CLI usage,
  cron integration, Grafana dashboard, alert playbook.