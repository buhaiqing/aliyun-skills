---
name: gcl-cms-alarm-guide
description: >-
  Phase 3-B integration guide: wire GCL crosscheck-report-*.json phantom-op
  rate to alicloud-cms-ops PutMetricAlarm alarms. Covers alarm threshold
  design, CLI setup script, cron integration, and dashboard visualization.
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
    - ../../../scripts/gcl_actiontrail_crosscheck.py
    - ../../../scripts/gcl_cms_alarm_setup.py
---

# Phase 3-B: GCL Phantom Alarm Integration (CMS)

> **Prerequisite:** Phase 3-C must be running (cron / CI) to produce
> `crosscheck-report-*.json` files. See
> [`gcl-actiontrail-crosscheck-spec.md`](../gcl-actiontrail-crosscheck-spec.md).

---

## 1. Architecture

```
cron (hourly)
  │
  ├── gcl_actiontrail_crosscheck.py          (Phase 3-C)
  │     └── audit-results/crosscheck-report-*.json
  │
  └── gcl_cms_alarm_setup.py                 (Phase 3-B — this doc)
        └── aliyun cms PutMetricAlarm        (creates/updates alarm)
              ├── GCL-Phantom-Pass           (P1: Threshold=0)
              ├── GCL-Phantom-Fail           (P1: Threshold=0)
              ├── GCL-Resource-Mismatch      (P2: Threshold=0)
              ├── GCL-Api-Errors             (P3: Threshold=5)
              └── GCL-Timing-Anomaly         (P4: Threshold=10)
```

The alarm setup script is **idempotent**: it reads the latest
`crosscheck-report-*.json`, compares against thresholds, and only
calls `PutMetricAlarm` if the alarm doesn't exist or the threshold
changes.

---

## 2. Alarm Threshold Design

| Alarm Name | JSON Path | Threshold | Severity | Action |
|---|---|---|---|---|
| `GCL-Phantom-Pass` | `summary.phantoms` (PHANTOM_PASS only) | > 0 | P1 — CRITICAL | Page on-call (phone) |
| `GCL-Phantom-Fail` | `summary.phantoms` (PHANTOM_FAIL only) | > 0 | P1 — CRITICAL | Page on-call (phone) |
| `GCL-Resource-Mismatch` | `summary.by_finding_type.RESOURCE_MISMATCH` | > 0 | P2 — HIGH | Notify SRE (PagerDuty) |
| `GCL-Api-Errors` | `summary.api_errors` | > 5 | P3 — WARNING | Log incident (Slack) |
| `GCL-Timing-Anomaly` | `summary.by_finding_type.TIMING_ANOMALY` | > 10 | P4 — INFO | Weekly review |

**Idempotent update logic:**
- When `gcl_cms_alarm_setup.py` runs, it reads the latest report.
- If `PHANTOM_PASS > 0` and the P1 alarm already exists → skip (already alerted).
- If `PHANTOM_PASS == 0` and the P1 alarm exists → delete the alarm (issue resolved).
- This prevents alarm fatigue: the alarm only fires ONCE per incident.

---

## 3. CLI Setup Script

The companion script `scripts/gcl_cms_alarm_setup.py` creates/updates all
5 phantom alarms in one invocation:

```bash
python3 scripts/gcl_cms_alarm_setup.py \
  --report-dir audit-results/ \
  --contact-group gcl-oncall \
  --webhook "https://hooks.slack.com/services/..." \
  --region cn-hangzhou
```

On first run it creates 5 `PutMetricAlarm` rules. On subsequent runs it
checks the latest report and updates only what changed.

---

## 4. Cron Integration

```bash
# /etc/cron.d/gcl-phantom-alarm
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
ALIBABA_CLOUD_ACCESS_KEY_ID=<redacted>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<redacted>

# Hourly: cross-check + alarm update
0 * * * * root cd /path/to/aliyun-skills && \
  python3 scripts/gcl_actiontrail_crosscheck.py \
    --trace-dir audit-results/ \
    --report audit-results/crosscheck-$(date -u +\%Y\%m\%d-\%H\%M\%S).json && \
  python3 scripts/gcl_cms_alarm_setup.py \
    --report-dir audit-results/ \
    --contact-group gcl-oncall
```

---

## 5. Alert Response Playbook

| Finding | Action |
|---|---|
| **PHANTOM_PASS** (P1) | (a) Inspect the trace that reported PASS → verify the op actually ran. (b) If yes: trace is correct, crosscheck lag is the issue (ActionTrail ingestion). If not: agent/runner lied → investigate. (c) If confirmed phantom: disable the compromised AKID via `alicloud-ram-ops` immediately. |
| **PHANTOM_FAIL** (P1) | (a) The op ran despite local GCL saying FAIL/ABORT. The safety gate was bypassed. (b) Immediate: disable the AKID. (c) Root cause: was the op run by a parallel session? Was `gcl_runner.py` bypassed? |
| **RESOURCE_MISMATCH** (P2) | (a) Compare trace's `local_resource_id` with ActionTrail's `ResourceName`. (b) If mismatch is real (different resources): the trace is wrong. (c) If ActionTrail data is incomplete (common for some services): document false positive. |
| **API_ERROR** (P3) | (a) ActionTrail LookupErrors failed → check trail status. (b) `aliyun actiontrail GetTrailStatus` → is logging enabled? (c) `aliyun actiontrail DescribeRegions` → are we querying the right region? |
| **TIMING_ANOMALY** (P4) | (a) Check trace mtime vs ActionTrail EventTime. (b) If > 24h: possible replay attack. (c) If < 1h: clock skew or ingestion lag (false positive, can be ignored). |

---

## 6. Dashboard (Grafana / CMS Custom Dashboard)

The 5 phantom alarms can be visualized as a **GCL Phantom Gauge**:

| Panel | Metric | Query | Color |
|---|---|---|---|
| Phantom Pass rate | `gcl_phantom_pass` 24h sum | `sum(gcl_phantom_pass)` | Red if > 0 |
| Phantom Fail rate | `gcl_phantom_fail` 24h sum | `sum(gcl_phantom_fail)` | Red if > 0 |
| Resource Mismatch rate | `gcl_resource_mismatch` 24h sum | `sum(gcl_resource_mismatch)` | Yellow |
| API Error rate | `gcl_api_errors` 24h sum | `sum(gcl_api_errors)` | Yellow |
| Per-skill findings | `gcl_skill_findings` top-N | `topk(5, gcl_skill_findings)` | Heatmap |

Data sources:
- CMS custom metrics from `PutMetricAlarm` feedback.
- Direct `crosscheck-report-*.json` file parsing (for faster drill-down).

---

## 7. What This Guide Does NOT Cover

- ❌ **Real-time streaming.** The alarms are pull-based (cron → crosscheck →
  PutMetricAlarm). For real-time, subscribe to ActionTrail events via
  EventBridge + MNS.
- ❌ **Auto-remediation.** When `PHANTOM_FAIL` fires, the playbook says
  "disable the AKID via RAM" but does not automate it. Phase 3-E (future)
  will automate this with a guarded auto-remediation workflow.
- ❌ **Multi-region alarm aggregation.** The crosscheck currently queries
  one region (the AKID's home region). Cross-region traces will be
  missed. See crosscheck spec §8 Limitations.
- ❌ **Historical data.** Alarms only fire on new crosscheck results.
  Historical phantom rates are not stored in CMS — use the JSON reports
  as the long-term data store.

---

## 8. Changelog
1.0.0 | 2026-06-04 | Phase 3-B phantom alarm integration guide. 5 alarm thresholds
  (P1-P4), CLI setup script, cron integration, alert response playbook,
  Grafana dashboard template. Companion to `scripts/gcl_cms_alarm_setup.py`.