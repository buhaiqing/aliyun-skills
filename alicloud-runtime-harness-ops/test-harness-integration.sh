#!/bin/bash
# Integration tests for alicloud-runtime-harness-ops shared runtime (PR-8 canonical)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$ROOT")"
LEGACY_ROOT="${REPO_ROOT}/alicloud-skillopt-ops"
PASS=0
FAIL=0

ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== alicloud-runtime-harness-ops integration ==="

for f in scripts/harness-paths.sh scripts/harness-core-lib.sh scripts/harness_runtime.py; do
  [[ -f "$ROOT/$f" ]] && ok "$f exists (canonical)" || bad "$f missing"
done

for f in scripts/skillopt-paths.sh scripts/skillopt-core-lib.sh scripts/skillopt_runtime.py; do
  [[ -f "$LEGACY_ROOT/$f" ]] && ok "legacy $f shim exists" || bad "legacy $f shim missing"
done

if grep -q 'delegates to canonical harness-paths.sh' "$LEGACY_ROOT/scripts/skillopt-paths.sh" 2>/dev/null; then
  ok "skillopt-paths.sh is legacy shim (PR-8)"
else
  bad "skillopt-paths.sh should delegate to harness-paths.sh"
fi

if grep -q 'delegates to canonical harness-core-lib.sh' "$LEGACY_ROOT/scripts/skillopt-core-lib.sh" 2>/dev/null; then
  ok "skillopt-core-lib.sh is legacy shim (PR-8)"
else
  bad "skillopt-core-lib.sh should delegate to harness-core-lib.sh"
fi

if ! grep -q '^skillopt_wrap()' "$LEGACY_ROOT/scripts/skillopt-core-lib.sh" 2>/dev/null; then
  ok "skillopt-core-lib.sh shim has no local skillopt_wrap"
else
  bad "skillopt-core-lib.sh must not contain skillopt_wrap implementation"
fi

# No duplicate runtime.py in cms (representative product)
if [[ -f "$REPO_ROOT/alicloud-cms-ops/scripts/skillopt_runtime.py" ]]; then
  bad "duplicate cms skillopt_runtime.py should be removed"
else
  ok "cms has no local skillopt_runtime.py"
fi

# Product overlay sources shared core
if grep -qE 'skillopt-core-lib\.sh|harness-core-lib\.sh' "$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh"; then
  ok "ecs overlay sources shared core"
else
  bad "ecs overlay missing shared core source"
fi

if [[ -f "$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh" && ! -L "$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh" ]]; then
  ok "ecs harness-lib.sh is canonical file (PR-9)"
else
  bad "ecs harness-lib.sh should be implementation file"
fi

if [[ -L "$REPO_ROOT/alicloud-ecs-ops/scripts/skillopt-lib.sh" ]]; then
  ok "ecs skillopt-lib.sh is legacy symlink (PR-9)"
else
  bad "ecs skillopt-lib.sh should be symlink to harness-lib.sh"
fi

if grep -q '^skillopt_wrap()' "$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh"; then
  bad "ecs overlay should not define skillopt_wrap (moved to core)"
else
  ok "ecs overlay has no local skillopt_wrap"
fi

if grep -q '^skillopt_report()' "$REPO_ROOT/alicloud-ecs-ops/scripts/harness-lib.sh"; then
  bad "ecs overlay should not define skillopt_report (moved to core)"
else
  ok "ecs overlay has no local skillopt_report"
fi

if grep -q '^skillopt_wrap()' "$ROOT/scripts/harness-core-lib.sh"; then
  ok "harness-core-lib defines skillopt_wrap"
else
  bad "harness-core-lib missing skillopt_wrap"
fi

# Langfuse POST helper must use retry and timeout to avoid silent drops.
if grep -A10 '^_skillopt_langfuse_post()' "$ROOT/scripts/harness-core-lib.sh" | grep -qE 'curl.*--retry[[:space:]]+[0-9]+.*--max-time[[:space:]]+[0-9]+|curl.*--max-time[[:space:]]+[0-9]+.*--retry[[:space:]]+[0-9]+'; then
  ok "Langfuse POST uses curl retry + max-time"
else
  bad "Langfuse POST missing curl retry/max-time"
fi

if grep -A35 '^_skillopt_langfuse_create_trace()' "$ROOT/scripts/harness-core-lib.sh" | grep -q '{app: \$app'; then
  ok "Langfuse trace-create metadata includes app"
else
  bad "Langfuse trace-create metadata missing app"
fi

# Paths resolution (canonical)
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  [[ -f "$_SKILLOPT_RUNTIME_PY" ]] && ok "harness-paths resolve harness_runtime.py" || bad "harness-paths failed"
  [[ "$_SKILLOPT_RUNTIME_PY" == *"/harness_runtime.py" ]] && ok "_SKILLOPT_RUNTIME_PY points to harness_runtime.py" || bad "runtime py path wrong: $_SKILLOPT_RUNTIME_PY"
)

# Paths resolution (legacy shim)
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  # shellcheck source=/dev/null
  source "$LEGACY_ROOT/scripts/skillopt-paths.sh"
  [[ -f "$_SKILLOPT_RUNTIME_PY" ]] && ok "legacy skillopt-paths resolve runtime.py" || bad "legacy paths failed"
)

# Python runtime CLI
if grep -q 'span-create' "$ROOT/scripts/harness_runtime.py"; then
  ok "harness_runtime.py span-create subcommand"
else
  bad "harness_runtime.py missing span-create"
fi

if grep -q 'generation-create' "$ROOT/scripts/harness_runtime.py"; then
  ok "harness_runtime.py generation-create subcommand"
else
  bad "harness_runtime.py missing generation-create"
fi

bash -n "$ROOT/scripts/harness-core-lib.sh" && ok "harness-core-lib bash -n" || bad "harness-core-lib syntax"
bash -n "$ROOT/scripts/harness-paths.sh" && ok "harness-paths bash -n" || bad "harness-paths syntax"
bash -n "$LEGACY_ROOT/scripts/skillopt-paths.sh" && ok "legacy skillopt-paths bash -n" || bad "legacy paths syntax"

# SKILLOPT_ENABLED precedence (env / flags)
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="/tmp/skillopt-env-test-$$.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_RETRIES=3
  SKILLOPT_CB_ENABLED=false
  SKILLOPT_CB_THRESHOLD=5
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"
  unset SKILLOPT_ENABLED
  # Hide repo .env so default-false path is deterministic
  _env_file="${REPO_ROOT}/.env"
  _env_hidden=""
  if [[ -f "$_env_file" ]]; then
    _env_hidden="${_env_file}.skillopt-test-hide"
    mv "$_env_file" "$_env_hidden"
  fi
  skillopt_init --RegionId cn-hangzhou
  [[ -f "$_env_hidden" ]] && mv "$_env_hidden" "$_env_file"
  [[ "${SKILLOPT_ENABLED}" == "false" ]] && ok "default SKILLOPT_ENABLED=false" || bad "default enabled wrong"
  SKILLOPT_ENABLED=true
  skillopt_init --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "true" ]] && ok "env SKILLOPT_ENABLED=true without flag" || bad "env enable failed"
  SKILLOPT_ENABLED=true
  skillopt_init --skillopt-disable --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "false" ]] && ok "CLI disable overrides env" || bad "CLI disable failed"
  unset SKILLOPT_ENABLED
  HARNESS_ENABLED=true
  skillopt_init --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "true" && "${HARNESS_ENABLED}" == "true" ]] && ok "HARNESS_ENABLED alias enables self-repair" || bad "HARNESS_ENABLED alias failed"
  HARNESS_ENABLED=true
  skillopt_init --harness-disable --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "false" && "${HARNESS_ENABLED}" == "false" ]] && ok "--harness-disable overrides HARNESS_ENABLED" || bad "--harness-disable failed"
  HARNESS_SESSION_ID="sess-harness-alias-test"
  unset SKILLOPT_SESSION_ID
  skillopt_init --RegionId cn-hangzhou
  [[ "${SKILLOPT_SESSION_ID}" == "sess-harness-alias-test" && "${HARNESS_SESSION_ID}" == "sess-harness-alias-test" ]] && ok "HARNESS_SESSION_ID alias" || bad "HARNESS_SESSION_ID alias failed"
  HARNESS_ENABLED=true
  SKILLOPT_ENABLED=false
  skillopt_init --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "true" && "${HARNESS_ENABLED}" == "true" ]] && ok "HARNESS_ENABLED wins over legacy SKILLOPT_ENABLED" || bad "HARNESS env precedence failed"
  unset HARNESS_ENABLED
  SKILLOPT_ENABLED=true
  skillopt_init --RegionId cn-hangzhou
  [[ "${SKILLOPT_ENABLED}" == "true" && "${HARNESS_ENABLED}" == "true" ]] && ok "legacy SKILLOPT_ENABLED still enables (compat)" || bad "legacy SKILLOPT_ENABLED compat failed"
  skillopt_init --harness-report --RegionId cn-hangzhou
  [[ "${SKILLOPT_REPORT}" == "true" ]] && ok "--harness-report sets SKILLOPT_REPORT" || bad "--harness-report failed"
  type harness_wrap &>/dev/null && ok "harness_wrap alias exported" || bad "harness_wrap missing"
)

# gen-skillopt.sh emits overlay stub (not monolithic lib)
(
  _gen_tmp="${REPO_ROOT}/.runtime/tmp/gen-skillopt-test-$$"
  mkdir -p "$_gen_tmp"
  "$REPO_ROOT/.scripts/gen-skillopt.sh" "$_gen_tmp/alicloud-gen-smoke-ops" Smoke smoke SmokeProduct 'smoke:*' \
    'Dimensions' '' DescribeRegions ResourceNotFound QuotaExceeded >/dev/null
  _lib="$_gen_tmp/alicloud-gen-smoke-ops/scripts/skillopt-lib.sh"
  grep -q 'skillopt-core-lib.sh' "$_lib" && ok "gen-skillopt sources shared core" || bad "gen-skillopt missing core source"
  [[ -f "$_gen_tmp/alicloud-gen-smoke-ops/scripts/harness-lib.sh" ]] && ok "gen-skillopt emits harness-lib.sh" || bad "gen-skillopt missing harness-lib.sh"
  [[ -L "$_gen_tmp/alicloud-gen-smoke-ops/scripts/skillopt-lib.sh" ]] && ok "gen-skillopt emits skillopt-lib symlink" || bad "gen-skillopt missing skillopt-lib shim"
  grep -q '^skillopt_wrap()' "$_lib" && bad "gen-skillopt emitted monolithic wrap" || ok "gen-skillopt has no local skillopt_wrap"
  grep -q '^skillopt_report()' "$_lib" && bad "gen-skillopt emitted local skillopt_report" || ok "gen-skillopt has no local skillopt_report"
  grep -q '^skillopt_report()' "$ROOT/scripts/harness-core-lib.sh" && ok "harness-core-lib defines skillopt_report" || bad "harness-core-lib missing skillopt_report"
  rm -rf "$_gen_tmp"
)

# Wrapper-self-call exemption (AGENTS.md §15.8) — ensure the P0 guard
# does NOT block a wrapper script from running aliyun on the user's behalf,
# but DOES still block a direct aliyun call from a non-wrapper script.
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-slb-ops"
  SKILLOPT_SKILL_TAG="alicloud-slb-ops"
  SKILLOPT_LOG_FILE="/tmp/skillopt-guard-test-$$.log"
  SKILLOPT_LOG_FORMAT=text
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"

  # Case 1: NOT inside skillopt_wrap → guard refuses (rc=64)
  if require_skillopt_wrapper "slb" "DescribeLoadBalancers"; then
    bad "guard allowed direct aliyun call (should be blocked)"
  else
    ok "guard blocks direct aliyun call (rc=64)"
  fi

  # Case 2: call the guard through a function literally named "skillopt_wrap"
  # (matching real wrapper path: wrapper -> skillopt_wrap -> here).
  skillopt_wrap() {
    require_skillopt_wrapper "slb" "DescribeLoadBalancers"
  }
  if skillopt_wrap; then
    ok "guard allows call originating from skillopt_wrap"
  else
    bad "guard wrongly blocked skillopt_wrap call chain"
  fi
  unset -f skillopt_wrap

  # Case 3: _SKILLOPT_SKIP_WRAPPER_CHECK=1 still bypasses everything.
  _SKILLOPT_SKIP_WRAPPER_CHECK=1
  if require_skillopt_wrapper "slb" "DescribeLoadBalancers"; then
    ok "guard bypassed via _SKILLOPT_SKIP_WRAPPER_CHECK=1"
  else
    bad "guard did not honor _SKILLOPT_SKIP_WRAPPER_CHECK=1"
  fi
  unset _SKILLOPT_SKIP_WRAPPER_CHECK
)

# End-to-end: slb wrapper itself, with SkillOpt disabled (default), must
# be able to call aliyun without the P0 guard tripping. We stub aliyun to
# avoid hitting the real cloud.
(
  _stub_dir="/tmp/skillopt-stub-$$"
  mkdir -p "$_stub_dir"
  cat >"$_stub_dir/aliyun" <<'EOF'
#!/bin/bash
echo '{"LoadBalancers":{"LoadBalancer":[{"LoadBalancerId":"lb-stub","LoadBalancerName":"stub"}]}}'
EOF
  chmod +x "$_stub_dir/aliyun"
  # Prepend stub dir to PATH (do not concatenate the entire $PATH as a single string).
  out="$(PATH="$_stub_dir:$PATH" bash "$REPO_ROOT/alicloud-slb-ops/scripts/slb-harness-wrapper.sh" DescribeLoadBalancers --RegionId cn-hangzhou 2>&1)" || true
  if echo "$out" | grep -q 'WRAPPER REQUIRED'; then
    bad "slb wrapper hit P0 self-block"
  elif echo "$out" | grep -q 'lb-stub'; then
    ok "slb wrapper reached aliyun stub (lb-stub)"
  else
    bad "slb wrapper produced unexpected output: $out"
  fi
  rm -rf "$_stub_dir"
)

# Local trace + memory_store_lite without Langfuse (default wrapper path)
(
  _lt_root="${REPO_ROOT}/.runtime/tmp/skillopt-local-trace-$$"
  mkdir -p "$_lt_root/traces"
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="$_lt_root/test.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_LANGFUSE_ENABLED=false
  SKILLOPT_SESSION_ID="sess-local-trace-$$"
  ALIBABA_CLOUD_RUNTIME_DIR="$_lt_root"
  export ALIYUN_SKILLS_ROOT="$REPO_ROOT"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"

  _mem_dir="${REPO_ROOT}/.runtime/memory/alicloud-ecs-ops"
  _mem_file="${_mem_dir}/LocalTraceSmoke.jsonl"
  mkdir -p "$_mem_dir"
  _lines_before=0
  [[ -f "$_mem_file" ]] && _lines_before="$(wc -l < "$_mem_file" | tr -d ' ')"

  skillopt_session_init
  skillopt_trace_start "ecs" "LocalTraceSmoke" "--RegionId" "cn-hangzhou"
  _skillopt_memory_preflight_r2 "ecs" "LocalTraceSmoke"
  skillopt_trace_end "success" "" '{"Code":200}'

  _trace_n="$(find "$_lt_root/traces" -name 'trace-*.json' 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$_trace_n" -ge 1 ]]; then
    ok "local trace JSON written without Langfuse"
  else
    bad "local trace JSON missing (expected >=1, got $_trace_n)"
  fi

  _first_log_line="$(head -1 "$_lt_root/test.log" 2>/dev/null || true)"
  # Expect exactly [timestamp] [label] message. The bug repeats the timestamp in the message.
  _iso_count="$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+?[0-9]{4}' <<< "$_first_log_line" | wc -l | tr -d ' ')"
  if [[ "$_iso_count" -eq 1 && "$_first_log_line" =~ ^\[[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+?[0-9]{4}\]\ \[.*SkillOpt\]\ .+ ]]; then
    ok "text log format is [timestamp] [label] message"
  else
    bad "text log format malformed ($_iso_count timestamp(s)): $_first_log_line"
  fi

  _lines_after=0
  [[ -f "$_mem_file" ]] && _lines_after="$(wc -l < "$_mem_file" | tr -d ' ')"
  if [[ "$_lines_after" -gt "$_lines_before" ]]; then
    ok "memory_store_lite appended Layer 1 entry without Langfuse"
  else
    bad "memory_store_lite did not append (before=$_lines_before after=$_lines_after)"
  fi

  if jq -e '.memory_preflight.slots' "$_lt_root/traces"/trace-*.json >/dev/null 2>&1; then
    ok "R2 preflight merged into local trace"
  else
    bad "memory_preflight missing from local trace"
  fi

  rm -rf "$_lt_root"
)

# Failed wrapper: L1 error_code from API Code + B path Layer 2 (allowlisted)
(
  _lt_root="${REPO_ROOT}/.runtime/tmp/skillopt-l2-fail-$$"
  mkdir -p "$_lt_root/traces"
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="$_lt_root/test.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_LANGFUSE_ENABLED=false
  SKILLOPT_SESSION_ID="sess-l2-fail-$$"
  ALIBABA_CLOUD_RUNTIME_DIR="$_lt_root"
  export ALIYUN_SKILLS_ROOT="$REPO_ROOT"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"

  _op="L2FailSmoke$$"
  _mem_file="${REPO_ROOT}/.runtime/memory/alicloud-ecs-ops/${_op}.jsonl"
  mkdir -p "${REPO_ROOT}/.runtime/memory/alicloud-ecs-ops"
  _lines_before=0
  [[ -f "$_mem_file" ]] && _lines_before="$(wc -l < "$_mem_file" | tr -d ' ')"

  skillopt_session_init
  skillopt_trace_start "ecs" "$_op" "--RegionId" "cn-hangzhou"
  _reflex="${REPO_ROOT}/.runtime/reflexion/reflexion.json"
  _l2_before=0
  if [[ -f "$_reflex" ]]; then
    _l2_before="$(jq --arg op "$_op" '[.cli_parameter[]? | select(.command | contains($op))] | length' "$_reflex" 2>/dev/null || echo 0)"
  fi
  skillopt_trace_end "failed" "exit_code_1" '{"Code":"InvalidParameter","Message":"RegionId invalid"}'

  _lines_after=0
  [[ -f "$_mem_file" ]] && _lines_after="$(wc -l < "$_mem_file" | tr -d ' ')"
  if [[ "$_lines_after" -gt "$_lines_before" ]]; then
    _last_line="$(tail -1 "$_mem_file")"
    if echo "$_last_line" | jq -e '.error_code == "InvalidParameter"' >/dev/null 2>&1; then
      ok "failed wrapper wrote L1 error_code from API Code (exit_code_* fallback)"
    else
      bad "L1 entry missing error_code=InvalidParameter: $_last_line"
    fi
  else
    bad "failed wrapper did not append L1 entry"
  fi

  _l2_after=0
  if [[ -f "$_reflex" ]]; then
    _l2_after="$(jq --arg op "$_op" '[.cli_parameter[]? | select(.command | contains($op))] | length' "$_reflex" 2>/dev/null || echo 0)"
  fi
  if [[ "$_l2_after" -gt "$_l2_before" ]]; then
    ok "trace_end hook wrote allowlisted failure to Layer 2"
  else
    bad "Layer 2 pattern not created by trace_end (before=$_l2_before after=$_l2_after)"
  fi

  if [[ -f "$_reflex" ]]; then
    jq --arg op "$_op" '.cli_parameter = [.cli_parameter[]? | select(.command | contains($op) | not)]' \
      "$_reflex" > "${_reflex}.tmp" && mv "${_reflex}.tmp" "$_reflex"
  fi
  rm -rf "$_lt_root"
)

# Fallback Session ID must include entropy beyond workdir+date.
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-ecs-ops"
  SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
  SKILLOPT_LOG_FILE="/tmp/skillopt-sess-entropy-$$.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_LANGFUSE_ENABLED=false
  unset SKILLOPT_SESSION_ID TRAE_SESSION_ID CLAUDE_CONVERSATION_ID OPENCODE_SESSION_ID CODEBUDDY_SESSION_ID IDE_SESSION_ID HARNESS_SESSION_ID
  export ALIYUN_SKILLS_ROOT="$REPO_ROOT"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"

  export USER="entropy-test-a"
  skillopt_session_init
  _sess_a="$SKILLOPT_SESSION_ID"
  unset SKILLOPT_SESSION_ID
  export USER="entropy-test-b"
  skillopt_session_init
  _sess_b="$SKILLOPT_SESSION_ID"
  if [[ "$_sess_a" != "$_sess_b" ]]; then
    ok "fallback Session ID varies by USER"
  else
    bad "fallback Session ID collides across USER: $_sess_a"
  fi
  rm -f "/tmp/skillopt-sess-entropy-$$.log"
)

# Repo-centralized default paths (no ALIBABA_CLOUD_RUNTIME_DIR override)
(
  _SKILLOPT_SKILL_ROOT="$REPO_ROOT/alicloud-slb-ops"
  SKILLOPT_SKILL_TAG="alicloud-slb-ops"
  SKILLOPT_LOG_FILE="/tmp/skillopt-central-path-$$.log"
  SKILLOPT_LOG_FORMAT=text
  SKILLOPT_LANGFUSE_ENABLED=false
  SKILLOPT_SESSION_ID="sess-central-path-$$"
  unset ALIBABA_CLOUD_RUNTIME_DIR
  export ALIYUN_SKILLS_ROOT="$REPO_ROOT"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-paths.sh"
  # shellcheck source=/dev/null
  source "$ROOT/scripts/harness-core-lib.sh"

  _want_trace="${REPO_ROOT}/.runtime/traces/alicloud-slb-ops"
  _want_session="${REPO_ROOT}/.runtime/sessions/alicloud-slb-ops"
  if [[ "$_SKILLOPT_TRACE_DIR" == "$_want_trace" && "$_SKILLOPT_SESSIONS_DIR" == "$_want_session" ]]; then
    ok "default trace/session dirs are repo-centralized per skill tag"
  else
    bad "centralized paths wrong: trace=$_SKILLOPT_TRACE_DIR session=$_SKILLOPT_SESSIONS_DIR"
  fi

  skillopt_session_init
  skillopt_trace_start "slb" "CentralPathSmoke" "--RegionId" "cn-hangzhou"
  skillopt_trace_end "success" "" '{"Code":200}'
  if [[ -f "${_want_trace}/trace-${SKILLOPT_SESSION_ID}-"*.json ]]; then
    ok "repo-central trace file written under .runtime/traces/<skill>"
  else
    _found="$(find "$_want_trace" -name 'trace-*.json' 2>/dev/null | head -1 || true)"
    if [[ -n "$_found" ]]; then
      ok "repo-central trace file written: $_found"
    else
      bad "repo-central trace file missing under $_want_trace"
    fi
  fi
  rm -f "/tmp/skillopt-central-path-$$.log"
  rm -f "${_want_session}/skillopt-session-${SKILLOPT_SESSION_ID}.json" 2>/dev/null || true
  rm -f "${_want_trace}"/trace-"${SKILLOPT_SESSION_ID}"-*.json 2>/dev/null || true
)

echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
