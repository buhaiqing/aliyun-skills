#!/bin/bash
# scripts/test-runtime-harness-naming-contract.sh
# PR-0 acceptance tests for Runtime Harness naming migration (Strategy B).
# Locks discovery, shared-core wiring, and validator dual-glob behavior before
# PR-1..PR-4 rename work lands.
#
# Usage:
#   bash scripts/test-runtime-harness-naming-contract.sh
#
# Exit codes:
#   0  all assertions pass
#   1  one or more failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISCOVER_LIB="$SCRIPT_DIR/lib/runtime-harness-discover.sh"
VALIDATOR="$SCRIPT_DIR/validate-wrapper-first.sh"
INTEGRATION="$REPO_ROOT/alicloud-runtime-harness-ops/test-harness-integration.sh"
LEGACY_INTEGRATION="$REPO_ROOT/alicloud-skillopt-ops/test-skillopt-integration.sh"

PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== Runtime Harness naming contract (PR-0) ==="

# ---------- 1. Discovery library ----------
echo "--- Discovery library ---"
if [[ -f "$DISCOVER_LIB" ]]; then
    ok "runtime-harness-discover.sh exists"
else
    bad "runtime-harness-discover.sh missing"
fi

# shellcheck source=/dev/null
source "$DISCOVER_LIB"

# ---------- 2. Repo-wide harness wrappers ----------
echo "--- Harness wrapper inventory ---"
wrapper_skills="$(rh_list_skill_dirs_with_wrapper "$REPO_ROOT" | wc -l | tr -d ' ')"
if [[ "$wrapper_skills" -ge 30 ]]; then
    ok "found $wrapper_skills skills with runtime harness wrappers (>= 30)"
else
    bad "expected >= 30 skills with wrappers, found $wrapper_skills"
fi

ecs_wrapper="$REPO_ROOT/alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh"
ecs_harness="$REPO_ROOT/alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
if [[ -x "$ecs_wrapper" ]]; then
    ok "ecs-skillopt-wrapper.sh is executable (legacy)"
else
    bad "ecs-skillopt-wrapper.sh missing or not executable"
fi
if [[ -x "$ecs_harness" ]]; then
    ok "ecs-harness-wrapper.sh is executable (canonical)"
else
    bad "ecs-harness-wrapper.sh missing or not executable"
fi
bash -n "$ecs_harness" 2>/dev/null && ok "ecs-harness-wrapper.sh bash -n" || bad "ecs-harness-wrapper.sh syntax"
if grep -q 'SKILLOPT_LOADED=' "$ecs_harness" 2>/dev/null || grep -q 'skillopt_wrap' "$ecs_harness" 2>/dev/null; then
    ok "ecs-harness-wrapper.sh contains implementation (PR-6)"
else
    bad "ecs-harness-wrapper.sh should be canonical implementation"
fi
if grep -q 'delegates to canonical harness wrapper' "$ecs_wrapper" 2>/dev/null; then
    ok "ecs-skillopt-wrapper.sh is legacy shim (PR-6)"
else
    bad "ecs-skillopt-wrapper.sh should delegate to harness wrapper"
fi
bash -n "$ecs_wrapper" 2>/dev/null && ok "ecs-skillopt-wrapper.sh bash -n" || bad "ecs-skillopt-wrapper.sh syntax"

ecs_harness_lib="$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh"
ecs_skillopt_lib="$REPO_ROOT/alicloud-ecs-ops/scripts/skillopt-lib.sh"
if [[ -f "$ecs_harness_lib" && ! -L "$ecs_harness_lib" ]]; then
    ok "harness-lib.sh is canonical overlay (PR-9)"
else
    bad "harness-lib.sh should be regular file implementation"
fi
if [[ -L "$ecs_skillopt_lib" && "$(readlink "$ecs_skillopt_lib")" == "harness-lib.sh" ]]; then
    ok "skillopt-lib.sh legacy symlink -> harness-lib.sh (PR-9)"
else
    bad "skillopt-lib.sh should symlink to harness-lib.sh"
fi

if [[ -f "$REPO_ROOT/alicloud-runtime-harness-ops/SKILL.md" ]]; then
    ok "alicloud-runtime-harness-ops canonical SKILL.md exists"
else
    bad "alicloud-runtime-harness-ops SKILL.md missing"
fi

if grep -q 'Legacy framework skill alias' "$REPO_ROOT/alicloud-skillopt-ops/SKILL.md" 2>/dev/null; then
    ok "alicloud-skillopt-ops is legacy alias (PR-8)"
else
    bad "alicloud-skillopt-ops should be legacy alias after PR-8"
fi

# ---------- 3. Shared core wiring (ecs representative) ----------
echo "--- Shared core wiring (ecs) ---"
ecs_lib="$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh"
harness_core="$REPO_ROOT/alicloud-runtime-harness-ops/scripts/harness-core-lib.sh"
legacy_core_shim="$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-core-lib.sh"

if grep -qE 'skillopt-core-lib\.sh|harness-core-lib\.sh' "$ecs_lib"; then
    ok "ecs overlay sources shared core (legacy path)"
else
    bad "ecs overlay does not source shared core"
fi

if grep -q '^skillopt_wrap()' "$harness_core"; then
    ok "skillopt_wrap defined in harness-core-lib.sh (canonical)"
else
    bad "skillopt_wrap missing from harness-core-lib.sh"
fi

if grep -q 'delegates to canonical harness-core-lib.sh' "$legacy_core_shim" 2>/dev/null \
    && ! grep -q '^skillopt_wrap()' "$legacy_core_shim" 2>/dev/null; then
    ok "skillopt-core-lib.sh is legacy shim (PR-8)"
else
    bad "skillopt-core-lib.sh should shim to harness-core-lib.sh"
fi

if grep -q '^skillopt_wrap()' "$ecs_lib"; then
    bad "ecs overlay must not define skillopt_wrap locally"
else
    ok "ecs overlay has no local skillopt_wrap"
fi

# ---------- 4. Dual-glob discovery (scratch harness-only skill) ----------
echo "--- Dual-glob discovery (scratch) ---"
SCRATCH="$REPO_ROOT/.runtime/test-runtime-harness-contract"
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH/alicloud-test-harness-only-ops/scripts"
cat > "$SCRATCH/alicloud-test-harness-only-ops/scripts/demo-harness-wrapper.sh" <<'EOF'
#!/bin/bash
echo harness-only
EOF
chmod +x "$SCRATCH/alicloud-test-harness-only-ops/scripts/demo-harness-wrapper.sh"

harness_only_count="$(rh_find_wrappers "$SCRATCH/alicloud-test-harness-only-ops/scripts" | wc -l | tr -d ' ')"
if [[ "$harness_only_count" == "1" ]]; then
    ok "rh_find_wrappers discovers *-harness-wrapper.sh"
else
    bad "rh_find_wrappers should find 1 harness wrapper, got $harness_only_count"
fi

if rh_skill_has_wrapper "$SCRATCH/alicloud-test-harness-only-ops"; then
    ok "rh_skill_has_wrapper true for harness-only skill"
else
    bad "rh_skill_has_wrapper should be true for harness-only skill"
fi

stem="$(rh_wrapper_stem "$SCRATCH/alicloud-test-harness-only-ops/scripts/demo-harness-wrapper.sh")"
if [[ "$stem" == "demo" ]]; then
    ok "rh_wrapper_stem strips -harness-wrapper suffix"
else
    bad "rh_wrapper_stem expected demo, got $stem"
fi
rm -rf "$SCRATCH"

# ---------- 5. validate-wrapper-first uses dual glob ----------
echo "--- validate-wrapper-first dual glob ---"
SCRATCH="$REPO_ROOT/.runtime/test-runtime-harness-contract"
rm -rf "$SCRATCH"
mkdir -p "$SCRATCH/alicloud-test-harness-validator-ops/scripts"
cat > "$SCRATCH/alicloud-test-harness-validator-ops/SKILL.md" <<'EOF'
# Harness Validator Test

## Runtime Rules
| CLI path | MANDATORY: Use ./scripts/demo-harness-wrapper.sh; fallback to native aliyun demo when wrapper missing. |
EOF
cat > "$SCRATCH/alicloud-test-harness-validator-ops/scripts/demo-harness-wrapper.sh" <<'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
fi
EOF
chmod +x "$SCRATCH/alicloud-test-harness-validator-ops/scripts/demo-harness-wrapper.sh"

rc=0
bash "$VALIDATOR" --skill "$SCRATCH/alicloud-test-harness-validator-ops" --json > "$SCRATCH/validator.json" 2>&1 || rc=$?
violations="$(python3 -c "import json; print(json.load(open('$SCRATCH/validator.json'))['violations'])" 2>/dev/null || echo ERR)"
if [[ "$rc" == "0" && "$violations" == "0" ]]; then
    ok "validate-wrapper-first accepts harness-only wrapper skill (P0=0)"
else
    bad "validate-wrapper-first harness-only skill rc=$rc violations=$violations"
fi
rm -rf "$SCRATCH"

# ---------- 6. Existing validator smoke ----------
echo "--- validate-wrapper-first smoke ---"
if bash "$SCRIPT_DIR/test-validate-wrapper-first.sh"; then
    ok "test-validate-wrapper-first.sh green"
else
    bad "test-validate-wrapper-first.sh failed"
fi

# ---------- 7. Shared SkillOpt integration (structure) ----------
echo "--- Shared runtime integration ---"
if [[ -x "$INTEGRATION" ]]; then
    if bash "$INTEGRATION"; then
        ok "alicloud-runtime-harness-ops/test-harness-integration.sh green"
    else
        bad "alicloud-runtime-harness-ops/test-harness-integration.sh failed"
    fi
else
    bad "harness integration test missing or not executable"
fi
if [[ -x "$LEGACY_INTEGRATION" ]]; then
    if bash "$LEGACY_INTEGRATION" >/dev/null 2>&1; then
        ok "legacy test-skillopt-integration.sh delegates and passes"
    else
        bad "legacy test-skillopt-integration.sh failed"
    fi
else
    bad "legacy integration test shim missing"
fi

# ---------- 8. HARNESS_* env aliases (PR-2) ----------
echo "--- HARNESS env aliases ---"
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="/tmp/runtime-harness-alias-test-$$.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_RETRIES=3
  SKILLOPT_CB_ENABLED=false
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-paths.sh"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-core-lib.sh"
  _env_file="${REPO_ROOT}/.env"
  _env_hidden=""
  if [[ -f "$_env_file" ]]; then
    _env_hidden="${_env_file}.harness-test-hide"
    mv "$_env_file" "$_env_hidden"
  fi
  unset SKILLOPT_ENABLED HARNESS_ENABLED
  HARNESS_ENABLED=true
  skillopt_init --RegionId cn-hangzhou
  [[ -f "$_env_hidden" ]] && mv "$_env_hidden" "$_env_file"
  if [[ "${SKILLOPT_ENABLED}" == "true" ]]; then
    ok "HARNESS_ENABLED maps to SKILLOPT_ENABLED"
  else
    bad "HARNESS_ENABLED should set SKILLOPT_ENABLED=true"
  fi
)

# ---------- 9. gen-skillopt emits canonical harness + legacy skillopt (PR-6) ----------
echo "--- gen-skillopt wrapper layout (PR-6) ---"
(
  _gen_tmp="${REPO_ROOT}/.runtime/tmp/gen-harness-pr6-test-$$"
  mkdir -p "$_gen_tmp"
  "$REPO_ROOT/.scripts/gen-skillopt.sh" "$_gen_tmp/alicloud-gen-harness-ops" Harness harness HarnessProduct 'harness:*' \
    'Dimensions' '' DescribeRegions ResourceNotFound QuotaExceeded >/dev/null
  _gh="$_gen_tmp/alicloud-gen-harness-ops/scripts/harness-harness-wrapper.sh"
  _gs="$_gen_tmp/alicloud-gen-harness-ops/scripts/harness-skillopt-wrapper.sh"
  if [[ -x "$_gh" ]] && grep -qE 'SKILLOPT_LOADED=|skillopt_wrap' "$_gh"; then
    ok "gen-skillopt emits canonical harness wrapper"
  else
    bad "gen-skillopt missing canonical harness-harness-wrapper.sh"
  fi
  if [[ -x "$_gs" ]] && grep -q 'delegates to canonical harness wrapper' "$_gs"; then
    ok "gen-skillopt emits legacy skillopt shim"
  else
    bad "gen-skillopt missing legacy harness-skillopt-wrapper.sh shim"
  fi
  rm -rf "$_gen_tmp"
)

# ---------- 10. Repo-wide PR-6 inversion ----------
echo "--- PR-6 wrapper inversion (all skills) ---"
_inv_ok=0
_inv_bad=0
while IFS= read -r _so || [[ -n "$_so" ]]; do
    [[ -n "$_so" ]] || continue
    _ha="${_so/skillopt-wrapper/harness-wrapper}"
    [[ -f "$_ha" ]] || { _inv_bad=$((_inv_bad + 1)); continue; }
    if grep -q 'delegates to canonical harness wrapper' "$_so" \
        && grep -qE 'SKILLOPT_LOADED=|skillopt_wrap' "$_ha" 2>/dev/null; then
        _inv_ok=$((_inv_ok + 1))
    else
        _inv_bad=$((_inv_bad + 1))
    fi
done < <(find "$REPO_ROOT"/alicloud-*-ops/scripts -maxdepth 1 -name '*-skillopt-wrapper.sh' 2>/dev/null | sort)
if [[ "$_inv_ok" -ge 40 && "$_inv_bad" -eq 0 ]]; then
    ok "PR-6 inversion: $_inv_ok skillopt shims -> harness implementations"
else
    bad "PR-6 inversion: ok=$_inv_ok bad=$_inv_bad (expected >=40 ok, 0 bad)"
fi

# ---------- 11. PR-7 HARNESS env / CLI single track ----------
echo "--- PR-7 HARNESS env single track ---"
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="/tmp/runtime-harness-pr7-$$.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_RETRIES=3
  SKILLOPT_CB_ENABLED=false
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-paths.sh"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-core-lib.sh"
  _env_file="${REPO_ROOT}/.env"
  _env_hidden=""
  if [[ -f "$_env_file" ]]; then
    _env_hidden="${_env_file}.harness-pr7-hide"
    mv "$_env_file" "$_env_hidden"
  fi
  HARNESS_ENABLED=true
  SKILLOPT_ENABLED=false
  skillopt_init --RegionId cn-hangzhou
  [[ -f "$_env_hidden" ]] && mv "$_env_hidden" "$_env_file"
  if [[ "${SKILLOPT_ENABLED}" == "true" ]]; then
    ok "HARNESS_ENABLED wins over legacy SKILLOPT_ENABLED"
  else
    bad "HARNESS env precedence failed"
  fi
  skillopt_init --harness-retries 9 --RegionId cn-hangzhou
  if [[ "${SKILLOPT_RETRIES}" == "9" ]]; then
    ok "--harness-retries CLI alias"
  else
    bad "--harness-retries failed"
  fi
)

# ---------- 12. PR-8 framework path inversion ----------
echo "--- PR-8 framework path inversion ---"
_harness_py="$REPO_ROOT/alicloud-runtime-harness-ops/scripts/harness_runtime.py"
_legacy_py="$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt_runtime.py"
if [[ -f "$_harness_py" ]]; then
    ok "harness_runtime.py in canonical framework skill"
else
    bad "harness_runtime.py missing"
fi
if [[ -L "$_legacy_py" || -f "$_legacy_py" ]]; then
    ok "legacy skillopt_runtime.py shim present"
else
    bad "legacy skillopt_runtime.py shim missing"
fi
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/alicloud-skillopt-ops/scripts/skillopt-paths.sh"
  if [[ "$_SKILLOPT_RUNTIME_PY" == *"/harness_runtime.py" ]]; then
    ok "legacy paths resolve to harness_runtime.py"
  else
    bad "legacy paths should resolve harness_runtime.py, got: $_SKILLOPT_RUNTIME_PY"
  fi
)

# ---------- 13. PR-9 overlay lib inversion (all skills) ----------
echo "--- PR-9 overlay lib inversion (all skills) ---"
_lib_ok=0
_lib_bad=0
while IFS= read -r _so || [[ -n "$_so" ]]; do
    [[ -n "$_so" ]] || continue
    _skill="$(dirname "$(dirname "$_so")")"
    _ha="${_so%/*}/harness-lib.sh"
    [[ -f "$_ha" && ! -L "$_ha" ]] || { _lib_bad=$((_lib_bad + 1)); continue; }
    if [[ -L "$_so" && "$(readlink "$_so")" == "harness-lib.sh" ]]; then
        _lib_ok=$((_lib_ok + 1))
    else
        _lib_bad=$((_lib_bad + 1))
    fi
done < <(find "$REPO_ROOT"/alicloud-*-ops/scripts -maxdepth 1 -name 'skillopt-lib.sh' 2>/dev/null | sort)
if [[ "$_lib_ok" -ge 40 && "$_lib_bad" -eq 0 ]]; then
    ok "PR-9 inversion: $_lib_ok skillopt-lib shims -> harness-lib implementations"
else
    bad "PR-9 inversion: ok=$_lib_ok bad=$_lib_bad (expected >=40 ok, 0 bad)"
fi

# ---------- 14. PR-9b wrapper sources harness-lib.sh ----------
echo "--- PR-9b wrapper harness-lib source ---"
_w9b_ok=0
_w9b_bad=0
while IFS= read -r _wh || [[ -n "$_wh" ]]; do
    [[ -n "$_wh" ]] || continue
    if grep -qE 'source "\$SCRIPT_DIR/harness-lib\.sh"|source "\$\{SCRIPT_DIR\}/harness-lib\.sh"' "$_wh" 2>/dev/null \
        || grep -q 'harness-lib.sh' "$_wh" 2>/dev/null; then
        _w9b_ok=$((_w9b_ok + 1))
    else
        _w9b_bad=$((_w9b_bad + 1))
    fi
done < <(find "$REPO_ROOT"/alicloud-*-ops/scripts -maxdepth 1 -name '*-harness-wrapper.sh' 2>/dev/null | sort)
if [[ "$_w9b_ok" -ge 46 && "$_w9b_bad" -eq 0 ]]; then
    ok "PR-9b: $_w9b_ok harness wrappers reference harness-lib.sh"
else
    bad "PR-9b: ok=$_w9b_ok bad=$_w9b_bad (expected >=46 ok, 0 bad)"
fi

# ---------- 15. skillopt-integration.md must not misname Runtime Harness ----------
echo "--- skillopt-integration.md terminology ---"
if rg -q 'integration of Microsoft SkillOpt' "$REPO_ROOT"/alicloud-*/references/skillopt-integration.md 2>/dev/null; then
    bad "skillopt-integration.md must not claim Microsoft SkillOpt implementation"
else
    ok "skillopt-integration.md: no Microsoft SkillOpt implementation misnaming"
fi
if rg -q '^- \[.+\] — Microsoft SkillOpt integration for self-repair' "$REPO_ROOT"/alicloud-*/SKILL.md 2>/dev/null; then
    bad "SKILL.md Related docs must not describe Runtime Harness as Microsoft SkillOpt"
else
    ok "SKILL.md Related docs: no Microsoft SkillOpt misnaming"
fi

# ---------- Summary ----------
echo "=============================================="
echo "PASS: $PASS  FAIL: $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "✅ Runtime Harness naming contract — all checks passed"
    exit 0
fi
echo "❌ Runtime Harness naming contract — failures detected"
exit 1
