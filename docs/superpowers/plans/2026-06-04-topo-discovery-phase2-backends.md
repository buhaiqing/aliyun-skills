# alicloud-topo-discovery Phase 2: Backends & CI/CD

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) to implement.

**Goal:** Add Git and OSS storage backends to baseline management, plus CI/CD integration templates.

**Architecture:** Two new backend modules (`baseline_git.py`, `baseline_oss.py`) following the same interface as `baseline_local.py`. CI/CD templates in `assets/ci-cd-templates/`.

**Tech Stack:** Python 3.10+, pygit2 or `git` CLI (for git backend), `oss2` SDK (for OSS backend), GitHub Actions / GitLab CI.

**Spec Ref:** `docs/superpowers/specs/2026-06-04-topo-discovery-upgrade-design.md` §3.3.3, §3.3.5

---

## File Structure

```
alicloud-topo-discovery/
├── scripts/lib/
│   ├── baseline_git.py       [NEW] GitBackend class
│   └── baseline_oss.py       [NEW] OSSBackend class
├── assets/
│   └── ci-cd-templates/      [NEW]
│       ├── github-actions.yml
│       ├── gitlab-ci.yml
│       └── jenkinsfile
└── tests/
    ├── test_baseline_git.py   [NEW]
    └── test_baseline_oss.py   [NEW]
```

---

## Task 1: Git Backend (2 days)

**Interface** (same as LocalBackend):
```python
class GitBackend:
    def __init__(self, root_dir, repo_url=None, branch="main", commit_user="topo-discovery"):
    def write_baseline(self, snapshot: Path) -> str              # commit SHA
    def list_baselines(self) -> List[date]
    def get_latest(self) -> Optional[Path]
```

**Behavior:**
- Each `write_baseline` commits to `baselines/YYYY-MM-DD/` sub-path in the repo
- Auto-commits with message `baseline: YYYY-MM-DD (N resources)`
- Push on commit (configurable `--push`)
- Falls back to local if push fails (with warning, not error)
- Uses `git` CLI (stdlib, no pygit2 dependency)

**Tests (8):**
- Initialize repo, write baseline, verify commit exists
- Write two baselines, verify both exist as separate commits
- List baselines matches dates
- Push failure falls back to local warning
- Invalid repo_url raises ValueError
- Configurable branch and user name

---

## Task 2: OSS Backend (2 days)

**Interface:**
```python
class OSSBackend:
    def __init__(self, bucket, prefix="baselines/", endpoint=None, ak_id=None, ak_secret=None):
    def write_baseline(self, snapshot: Path) -> str    # OSS object key
    def list_baselines(self) -> List[date]
```

**Behavior:**
- Uploads export directory as `{prefix}/{YYYY-MM-DD}/` objects
- Uses OSS SDK with multipart upload for large snapshots
- Falls back to primary AK env vars if no dedicated OSS creds
- Writes manifest.json last (atomicity signal: partial = no manifest)
- **No ServerSide encryption** (per spec, relies on bucket policy)

**Tests (7):**
- Upload works (mocked)
- Prefix configurable
- Multipart for large files
- Partial upload detected (no manifest = failed)
- Same-date baseline overwrites (idempotent)
- Uses env var fallback when no explicit creds
- Invalid endpoint raises ValueError

---

## Task 3: CI/CD Templates (1 day)

**GitHub Actions** (`.github/workflows/topology-baseline.yml`):
```yaml
name: Topology Baseline
on:
  schedule:
    - cron: '0 2 * * *'    # daily 2 AM
  workflow_dispatch:        # manual trigger

jobs:
  baseline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Set up Python
        uses: actions/setup-python@v5
        with: python-version: '3.10'
      - name: Install deps
        run: pip install alicloud-topo-discovery
      - name: Export baseline
        run: python alicloud-topo-discovery/scripts/baseline-manager.py --backend git --output-dir ./infra-baseline
        env: ${{ secrets.ALIBABA_CLOUD_CREDENTIALS }}
      - name: Commit and push
        run: |
          git add infra-baseline/
          git commit -m "baseline: $(date +%Y-%m-%d)"
          git push
```

**GitLab CI** (`.gitlab-ci.yml`): similar, uses `rules: - if: $CI_PIPELINE_SOURCE == "schedule"`

**Jenkins**: Jenkinsfile with `cron: H 2 * * *`, credentials via Jenkins store

**Tests**: Verify each template is valid YAML/XML and contains required variables.

---

## Tasks & Dependencies

| Task | Duration | Depends On | Deliverable |
|------|----------|------------|-------------|
| 1. Git Backend | 2 days | Plan 1 (baseline_local) | `baseline_git.py`, 8 tests |
| 2. OSS Backend | 2 days | Plan 1 | `baseline_oss.py`, 7 tests |
| 3. CI/CD Templates | 1 day | Tasks 1-2 (interface known) | 3 templates |

Total: ~5 working days (within spec's 1.5-2 weeks estimate).

## AC Coverage

| AC | Covered |
|----|---------|
| AC-3 Git backend CI | ✅ (Task 1 + Task 3) |
| AC-4 OSS backend | ✅ (Task 2) |

## Verification

```bash
pytest alicloud-topo-discovery/tests/test_baseline_git.py -v  # 8 tests
pytest alicloud-topo-discovery/tests/test_baseline_oss.py -v # 7 tests
pytest alicloud-topo-discovery/tests/ -q                      # ~108 total
```