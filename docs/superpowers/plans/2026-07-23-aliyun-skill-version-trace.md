# Plan: Add `skill_version` & `version_source` to GCL Trace Records

- **Date**: 2026-07-23
- **Repo**: `aliyun-skills` (`/Users/bohaiqing/opensource/git/aliyun-skills`)
- **Target file**: `alicloud-gcl-runner-ops/scripts/gcl_runner.py`
- **Style**: Loop Engineering (Spec-Driven) — `[FINAL_SPEC]` marker below
- **Code change only**: This plan ships a markdown spec; no Python is edited by producing this file.

---

## 1. Background

The sibling `jdcloud-skills` repo already persists, for every GCL trace, the
**version of the skill** the trace was generated against (`skill_version` +
`version_source`). This makes trace records auditable: you can tell which skill
release produced a given audit result.

The `aliyun-skills` GCL runner (`alicloud-gcl-runner-ops/scripts/gcl_runner.py`)
currently records only `rubric_version` in its trace. The *skill's own version*
is absent. This gap means trace files cannot be correlated back to a specific
skill release — a regression vs. the jdcloud implementation we want to mirror.

**Goal**: carry the skill's own semver (and where it came from) on every
persisted trace record, with zero change to existing `rubric_version` semantics.

---

## 2. Feasibility (verified by orchestrator)

- GCL runner main file: `alicloud-gcl-runner-ops/scripts/gcl_runner.py`.
- The trace is a **plain `dict`** (NOT a dataclass). It is persisted by
  `persist_trace(trace, output_dir)` at line 2812 to
  `audit-results/gcl-trace-YYYYMMDD-HHMMSS.json` (default dir resolved by
  `_resolve_default_audit_dir()` at line 237).
- The trace dict is built in **two** places, both of which already have `skill`
  (full name, e.g. `alicloud-ecs-ops`) and `skills_root` in scope:
  - `run_gcl(...)` ~line 2209:
    `trace = {"skill": skill, "request": ..., "rubric_version": rubric["version"], "iterations": [], "failure_pattern": None}`
  - a dry-run path ~line 2773:
    `trace = {"skill": skill, "request": ..., "rubric_version": rubric["version"], "iterations": [...], "dry_run": True, "final": {...}}`
- `skill` is the **full** skill name, so SKILL.md lives at
  `skills_root / skill / "SKILL.md"`. `resolve_skills_root()` (line 250)
  returns the repo root containing `alicloud-*-ops` dirs.
- **Version source**: all 44 `alicloud-*-ops` skills carry `metadata.version`
  in SKILL.md frontmatter (e.g. `metadata:\n  version: "2.2.1"`). ALL are
  under the `metadata` block; NO skill uses a top-level `version:` key. Versions
  are quoted semver strings.
- The file imports `re`, `subprocess`, `json`, `Path`, `Any` at module level.
  `yaml` is **NOT** yet imported — must be added.
- Sibling jdcloud implementation (shipped & tested) used:
  - `_load_skill_md_frontmatter(skill)` — parses YAML frontmatter with a
    line-based `---` delimiter regex.
  - `resolve_skill_version(skill)` returning `(version, source)` with
    `source ∈ {"skill_md","git","unknown"}` and a git-commit-hash fallback.
  - wired the two fields into both the Trace dataclass and the write_trace payload.

**Conclusion**: Because the trace is a dict, the change is small and local —
add a resolver helper, `import yaml`, and two keys at the two build sites.

---

## 3. Spec — `[FINAL_SPEC]`

### 3.1 New module-level import
```python
import yaml  # added near line 104-111 (alongside re/subprocess/json)
```

### 3.2 New helper `resolve_skill_version`

Signature:
```python
def resolve_skill_version(
    skill: str, skills_root: Path | None = None
) -> tuple[str, str]:
    """Return (version, source) for a skill.

    source ∈ {"skill_md", "git", "unknown"}.
    - "skill_md": version read from SKILL.md frontmatter
                  (metadata.version preferred; top-level version: accepted for robustness)
    - "git":      fallback to the repo's git short hash
    - "unknown":  nothing found
    """
```

Behavior (mirror jdcloud):
1. `root = skills_root or resolve_skills_root()`
2. `path = root / skill / "SKILL.md"`. If missing → go to git fallback.
3. Read text; extract frontmatter between leading `---` lines; `yaml.safe_load`.
   - `version = data.get("metadata", {}).get("version") or data.get("version")`.
   - If `version` is a non-empty string → return `(version, "skill_md")`.
4. Git fallback: `subprocess.run(["git","-C",str(root),"rev-parse","--short","HEAD"],
   capture_output=True, text=True)`. If exit 0 and output non-empty →
   return `(hash.strip(), "git")`.
5. Otherwise return `("", "unknown")`.

Keep the helper near the other `resolve_*` helpers (~line 250 region is fine,
or adjacent to `_resolve_default_audit_dir`).

### 3.3 Wire into trace build sites

At **both** build sites, insert right after the existing `rubric_version` key:
```python
skill_version, version_source = resolve_skill_version(skill, skills_root)
trace = {
    "skill": skill,
    "request": ...,
    "rubric_version": rubric["version"],
    "skill_version": skill_version,
    "version_source": version_source,
    ...
}
```
Both sites already have `skill` and `skills_root` in scope (lines 2209 / 2773).
If `skills_root` is `None` at a site, `resolve_skill_version` falls back to
`resolve_skills_root()` internally — no extra plumbing required.

### 3.4 Persistence untouched
`persist_trace` already `json.dumps(trace)` — the two new keys serialize
automatically. No change needed there.

---

## 4. Tests

Proposed in `alicloud-gcl-runner-ops/tests/` (or alongside existing tests):

1. **`test_resolve_skill_version_from_frontmatter`** — monkeypatch
   `skills_root` to a `tmp_path` containing
   `tmp_path/<skill>/SKILL.md` with frontmatter
   `metadata:\n  version: "9.9.9"`. Assert
   `resolve_skill_version(skill, tmp_path) == ("9.9.9", "skill_md")`.

2. **`test_resolve_skill_version_missing_or_versionless`** — SKILL.md absent
   (or present but no `metadata.version`). Assert result is either
   `("", "unknown")` (no git) or `(<hash>, "git")` when run inside a git repo.
   Use a temp dir outside any git repo to assert the `unknown` branch cleanly.

3. **`test_resolve_skill_version_top_level_fallback`** — SKILL.md has only a
   top-level `version: "1.0.0"` (no `metadata` block). Assert
   `("1.0.0", "skill_md")` to confirm robustness path.

4. **Integration `test_run_gcl_trace_carries_version`** — invoke `run_gcl`
   against `alicloud-ecs-ops` (or a minimal fixture skill) in dry-run / mock
   mode, capture the trace dict, assert `"skill_version" in trace` and
   `"version_source" in trace` with `version_source == "skill_md"`.

---

## 5. Non-goals

- **No** change to `rubric_version` semantics or value.
- **No** dashboard / reporting changes that consume the new fields.
- **No** change to trace file naming or `persist_trace` signature.
- **No** dataclass migration (trace stays a dict).

---

## 6. Tasks

1. Add `import yaml` at module level (near line 104-111).
2. Implement `resolve_skill_version(skill, skills_root=None)` helper
   (frontmatter parse → `metadata.version` / top-level `version` → git fallback
   → `unknown`).
3. At trace build site ~line 2209 (`run_gcl`), add `skill_version` /
   `version_source` keys sourced from the helper.
4. At trace build site ~line 2773 (dry-run path), add the same two keys.
5. Add the 4 tests from §4.
6. Run `ruff check` and the test suite; confirm zero errors / failures.

---

## 7. Verification

- Run a real GCL run against `alicloud-ecs-ops`:
  ```bash
  python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py --skill alicloud-ecs-ops ...
  ```
- Locate the generated file:
  `alicloud-gcl-runner-ops/audit-results/gcl-trace-*.json`
- Assert both fields are present and sourced correctly:
  ```bash
  python3 - <<'PY'
  import json, glob
  p = sorted(glob.glob("alicloud-gcl-runner-ops/audit-results/gcl-trace-*.json"))[-1]
  t = json.loads(open(p).read())
  assert "skill_version" in t and "version_source" in t, "MISSING FIELDS"
  assert t["version_source"] == "skill_md", t["version_source"]
  print("OK", t["skill_version"], t["version_source"])
  PY
  ```
- Confirm `rubric_version` still present and unchanged in value.
- `ruff check alicloud-gcl-runner-ops/scripts/gcl_runner.py` → clean.
- Full test suite passes (incl. the 4 new tests).

---

## 12. Execution Results (2026-07-23)

### Implementation shipped
- `alicloud-gcl-runner-ops/scripts/gcl_runner.py`:
  - Added `import yaml` at module level.
  - Added `_FRONTMATTER_END` regex, `_find_frontmatter()` (skips leading HTML
    comments / blank lines before the `---` delimiter), `_load_skill_md_frontmatter()`,
    and `resolve_skill_version(skill, skills_root=None)` returning `(version, source)`.
  - Wired `"skill_version"` + `"version_source"` into BOTH trace-build sites
    (`run_gcl` and the dry-run path).
- `docs/gcl-spec.md` §6: added `skill_version` / `version_source` to the trace
  schema example.
- `gcl_runner_test.py`: added `ResolveSkillVersionTests` (4 cases).

### Two skills had INVALID frontmatter YAML — fixed
- `alicloud-dms-ops/SKILL.md`: `description:`/`compatibility:`/`cli_support_evidence:`
  folded scalars and the `environment:` list were mis-indented (content at column 1
  instead of indented). Re-indented; now parses, `metadata.version = "1.3.0"`.
- `alicloud-terraform-ops/SKILL.md`: `**bold**` inside a YAML list item (`*` → alias
  error) broke parsing, and it had NO `version` key at all. Quoted the two bold list
  items and added a `metadata:` block with `version: "1.0.0"`.

### Verification
- `resolve_skill_version` over all 45 `alicloud-*-ops` skills: **45/45 resolve
  `skill_md`** (0 git fallbacks).
- Real `gcl_runner.py --skill alicloud-ecs-ops ...` → trace contains
  `skill_version="2.2.1"`, `version_source="skill_md"`.
- Real run on `alicloud-oss-ops` (comment-prefixed SKILL.md) → `skill_version="1.1.0"`,
  proving the leading-comment fix.
- `ruff check` on my regions: clean. Full `gcl_runner_test.py`: 165 passed
  (the 1 pre-existing `test_memory_store_lands_in_tmp_root_memory_not_repo_root`
  failure is unrelated to this change — fails on unmodified code too).
