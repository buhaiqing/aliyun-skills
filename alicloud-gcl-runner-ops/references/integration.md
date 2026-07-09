---
name: gcl-runner-integration
description: >-
  Environment setup, credential rules, and bootstrap procedures for
  alicloud-gcl-runner-ops.
license: MIT
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-07"
  parent: ../SKILL.md
---

# GCL Runner Integration

## Prerequisites

- Python 3.10+ (stdlib only — no external dependencies)
- `aliyun` CLI installed and configured
- `ALIBABA_CLOUD_ACCESS_KEY_ID` and `ALIBABA_CLOUD_ACCESS_KEY_SECRET` environment variables set

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | — | Alibaba Cloud AccessKey |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | — | Alibaba Cloud AccessSecret |
| `ALIBABA_CLOUD_REGION_ID` | Yes | — | Default region |
| `ALIYUN_SKILLS_ROOT` | No | `git rev-parse --show-toplevel` | Repository root path |

## Bootstrap

```bash
# 1. Verify CLI
aliyun version

# 2. Verify credentials
echo "${ALIBABA_CLOUD_ACCESS_KEY_ID:?}" > /dev/null

# 3. Locate the runner
python3 "$(git rev-parse --show-toplevel)/alicloud-gcl-runner-ops/scripts/gcl_runner.py" --help
```

## Testing the Runner

```bash
# Run all GCL runner tests
python3 alicloud-gcl-runner-ops/scripts/gcl_runner_test.py -v

# Run all cross-check tests
python3 alicloud-gcl-runner-ops/scripts/gcl_actiontrail_crosscheck_test.py -v
```

## File Layout

```
alicloud-gcl-runner-ops/
├── SKILL.md                    # This file
├── scripts/
│   ├── gcl_runner.py           # Core GCL loop runner
│   ├── gcl_runner_test.py      # 60 unit tests
│   ├── gcl_actiontrail_crosscheck.py   # Cloud-side audit
│   ├── gcl_actiontrail_crosscheck_test.py  # 25 unit tests
│   ├── gcl_cms_alarm_setup.py          # CMS alarm provisioning
│   ├── gcl_passrate_reporter.py        # Pass-rate reporting
│   └── README.md               # Full runner documentation
├── references/
│   ├── gcl-execution.md        # This file
│   └── integration.md          # This file
└── assets/
    └── eval_queries.json       # Trigger evaluation queries
```