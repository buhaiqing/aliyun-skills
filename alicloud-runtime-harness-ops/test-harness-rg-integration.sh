#!/bin/bash
# WT-2 integration test: skillopt_trace_start writes resource_dimensions
# to trace JSON. Independent test file — does not modify existing
# test-harness-integration.sh.
#
# Run with: bash test-harness-rg-integration.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WT2_ROOT="$(dirname "$ROOT")"  # repo root (worktree top)

# Isolated runtime dir
RUNTIME_DIR="$(mktemp -d)"
trap "rm -rf $RUNTIME_DIR" EXIT
export ALIYUN_SKILLS_RUNTIME_ROOT="$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/logs/alicloud-ecs-ops" "$RUNTIME_DIR/traces/alicloud-ecs-ops"

# Harness env
export ALIYUN_SKILLS_ROOT="$WT2_ROOT"
export SKILLS_DIR="$WT2_ROOT"
export SKILLOPT_SKILL_TAG="alicloud-ecs-ops"
export SKILLOPT_SESSION_ID="sess-wt2-$$"
export SKILLOPT_ENABLED=false
export SKILLOPT_LANGFUSE_ENABLED=false
export SKILLOPT_LOG_FILE="$RUNTIME_DIR/logs/alicloud-ecs-ops/test.log"
export SKILLOPT_LOG_FORMAT="text"
export SKILLOPT_RUNTIME_DATA="$RUNTIME_DIR/runtime.json"

PASS=0; FAIL=0
ok()  { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

# Source canonical harness
export _SKILLOPT_SKILL_ROOT="$WT2_ROOT/alicloud-ecs-ops"
# shellcheck source=scripts/harness-paths.sh
source "$ROOT/scripts/harness-paths.sh"
# shellcheck source=scripts/harness-core-lib.sh
source "$ROOT/scripts/harness-core-lib.sh"

echo "=== WT-2 harness RG integration ==="

# === T1: helper emits full schema with values ===
echo "T1: helper RG + RepeatList"
result="$(_skillopt_extract_resource_dimensions \
    --RegionId cn-hangzhou \
    --ResourceGroupId rg-test-pilot \
    --Tag.1.Key env --Tag.1.Value prod \
    --Tag.2.Key team --Tag.2.Value core)"
rg=$(echo "$result" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['resource_group_id'])")
tag_count=$(echo "$result" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())['tags']))")
[[ "$rg" == "rg-test-pilot" ]] && ok "RG extracted" || bad "RG wrong: $rg"
[[ "$tag_count" == "2" ]] && ok "2 tags extracted" || bad "tag count: $tag_count"

# === T2: helper with no RG/Tags emits null/[] ===
echo "T2: helper no RG/Tags"
result="$(_skillopt_extract_resource_dimensions --RegionId cn-hangzhou --PageSize 10)"
rg=$(echo "$result" | python3 -c "import json,sys; v=json.loads(sys.stdin.read())['resource_group_id']; print('null' if v is None else v)")
tags=$(echo "$result" | python3 -c "import json,sys; v=json.loads(sys.stdin.read())['tags']; print(len(v))")
[[ "$rg" == "null" ]] && ok "RG is null" || bad "RG should be null: $rg"
[[ "$tags" == "0" ]] && ok "tags empty" || bad "tags should be 0: $tags"

# === T3: Unicode preserved ===
echo "T3: Unicode tags"
result="$(_skillopt_extract_resource_dimensions --Tag.1.Key 业务线 --Tag.1.Value 核心)"
key=$(echo "$result" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tags'][0]['key'])")
[[ "$key" == "业务线" ]] && ok "Unicode key preserved" || bad "Unicode lost: $key"

# === T4: single key=value ===
echo "T4: single key=value tag"
result="$(_skillopt_extract_resource_dimensions --Tag env=prod --Tag team=core)"
count=$(echo "$result" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())['tags']))")
[[ "$count" == "2" ]] && ok "2 single-KV tags" || bad "count: $count"

# === T5: JSON Tags ===
echo "T5: JSON Tags array"
result="$(_skillopt_extract_resource_dimensions \
    --Tags '[{"key":"env","value":"prod"},{"key":"team","value":"core"}]')"
count=$(echo "$result" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())['tags']))")
[[ "$count" == "2" ]] && ok "JSON Tags parsed" || bad "JSON count: $count"

# === T6: skillopt_trace_start writes resource_dimensions to trace JSON ===
echo "T6: trace JSON has resource_dimensions"
TRACE_DIR_GLOBAL="$RUNTIME_DIR/traces/alicloud-ecs-ops"
PRE=$(ls "$TRACE_DIR_GLOBAL" 2>/dev/null | wc -l | tr -d ' ')
skillopt_trace_start "ecs" "DescribeInstances" \
    --RegionId cn-hangzhou \
    --ResourceGroupId rg-full-test \
    --Tag.1.Key env --Tag.1.Value prod
POST=$(ls "$TRACE_DIR_GLOBAL" 2>/dev/null | wc -l | tr -d ' ')
[[ "$POST" -gt "$PRE" ]] && ok "trace file created" || bad "no new trace file"

latest=$(ls -t "$TRACE_DIR_GLOBAL"/*.json | head -1)
[[ -f "$latest" ]] || { bad "trace file missing"; exit 1; }

rg=$(jq -r '.resource_dimensions.resource_group_id' "$latest")
tag_count=$(jq -r '.resource_dimensions.tags | length' "$latest")
tag_key=$(jq -r '.resource_dimensions.tags[0].key' "$latest")
tag_value=$(jq -r '.resource_dimensions.tags[0].value' "$latest")
[[ "$rg" == "rg-full-test" ]] && ok "trace JSON .resource_dimensions.resource_group_id" || bad "RG wrong: $rg"
[[ "$tag_count" == "1" ]] && ok "trace JSON has 1 tag" || bad "tag count: $tag_count"
[[ "$tag_key" == "env" ]] && ok "tag key correct" || bad "tag key: $tag_key"
[[ "$tag_value" == "prod" ]] && ok "tag value correct" || bad "tag value: $tag_value"

# === T7: old fields preserved (zero-regression on schema) ===
echo "T7: old trace JSON schema fields preserved"
has_trace_id=$(jq -r 'has("trace_id")' "$latest")
has_session=$(jq -r 'has("session_id")' "$latest")
has_skill=$(jq -r 'has("skill")' "$latest")
has_input=$(jq -r 'has("input")' "$latest")
has_params=$(jq -r 'has("params")' "$latest")
[[ "$has_trace_id" == "true" ]] && ok "trace_id preserved" || bad "trace_id missing"
[[ "$has_session" == "true" ]] && ok "session_id preserved" || bad "session_id missing"
[[ "$has_skill" == "true" ]] && ok "skill preserved" || bad "skill missing"
[[ "$has_input" == "true" ]] && ok "input preserved" || bad "input missing"
[[ "$has_params" == "true" ]] && ok "params preserved" || bad "params missing"

# === T8: trace_start without RG/Tags still writes resource_dimensions ===
echo "T8: no RG/Tags → resource_dimensions with null/[]"
skillopt_trace_start "ecs" "DescribeInstances" --RegionId cn-hangzhou --PageSize 10
latest=$(ls -t "$TRACE_DIR_GLOBAL"/*.json | head -1)
rg=$(jq -r '.resource_dimensions.resource_group_id' "$latest")
tags_len=$(jq -r '.resource_dimensions.tags | length' "$latest")
[[ "$rg" == "null" ]] && ok "no-RG → null" || bad "no-RG should be null: $rg"
[[ "$tags_len" == "0" ]] && ok "no-tags → empty array" || bad "no-tags should be 0: $tags_len"

# === T9: fallback when parser file missing ===
echo "T9: parser fallback (file missing)"
PARSE_PY="$WT2_ROOT/alicloud-gcl-runner-ops/scripts/_extract_resource_dimensions.py"
mv "$PARSE_PY" "$PARSE_PY.bak"
result="$(_skillopt_extract_resource_dimensions --ResourceGroupId rg-x --Tag.1.Key env --Tag.1.Value prod)"
rg=$(echo "$result" | python3 -c "import json,sys; v=json.loads(sys.stdin.read())['resource_group_id']; print('null' if v is None else v)")
tags=$(echo "$result" | python3 -c "import json,sys; v=json.loads(sys.stdin.read())['tags']; print(len(v))")
mv "$PARSE_PY.bak" "$PARSE_PY"
[[ "$rg" == "null" ]] && ok "fallback RG → null" || bad "fallback RG: $rg"
[[ "$tags" == "0" ]] && ok "fallback tags → empty" || bad "fallback tags: $tags"

# === T10: WT-1 standalone test still passes ===
echo "T10: WT-1 parser tests still green (zero regression)"
if (cd "$WT2_ROOT/alicloud-gcl-runner-ops/scripts" && \
    python3 -m unittest _extract_resource_dimensions_test 2>&1 | grep -q "^OK$"); then
    ok "WT-1 parser tests OK"
else
    bad "WT-1 parser tests regressed"
fi

# === T11: trace JSON top-level missing_dimensions=true when no RG/Tags ===
echo "T11: missing_dimensions=true when caller skipped both dims"
skillopt_trace_start "ecs" "DescribeInstances" \
    --RegionId cn-hangzhou --PageSize 10
latest=$(ls -t "$TRACE_DIR_GLOBAL"/*.json | head -1)
md=$(jq -r '.missing_dimensions' "$latest")
warn=$(jq -r '.warning // "null"' "$latest")
suggest=$(jq -r '.suggestion // "null"' "$latest")
[[ "$md" == "true" ]] && ok "missing_dimensions=true at top level" || bad "missing_dimensions should be true: $md"
[[ "$warn" != "null" && "$warn" != "" ]] && ok "warning text populated" || bad "warning empty: $warn"
[[ "$suggest" != "null" && "$suggest" != "" ]] && ok "suggestion text populated" || bad "suggestion empty: $suggest"
[[ "$warn" == *"default resource-group filtering"* ]] && ok "warning mentions default-filter fact" || bad "warning missing key phrase"
[[ "$suggest" == *"--ResourceGroupId"* ]] && ok "suggestion actionable (RG flag)" || bad "suggestion missing flag"
# Top-level field ALSO nested in resource_dimensions
nested_md=$(jq -r '.resource_dimensions.missing_dimensions' "$latest")
[[ "$nested_md" == "true" ]] && ok "nested in resource_dimensions" || bad "nested missing_dimensions: $nested_md"

# === T12: missing_dimensions=false when caller specified RG ===
echo "T12: missing_dimensions=false when RG set"
skillopt_trace_start "ecs" "DescribeInstances" \
    --RegionId cn-hangzhou --ResourceGroupId rg-full-test
latest=$(ls -t "$TRACE_DIR_GLOBAL"/*.json | head -1)
md=$(jq -r '.missing_dimensions' "$latest")
warn=$(jq -r '.warning // "null"' "$latest")
[[ "$md" == "false" ]] && ok "missing_dimensions=false" || bad "should be false: $md"
[[ "$warn" == "null" ]] && ok "warning null when RG set" || bad "warning should be null: $warn"

# === T13: missing_dimensions=false when only Tags set ===
echo "T13: missing_dimensions=false when only Tags set"
skillopt_trace_start "ecs" "DescribeInstances" \
    --RegionId cn-hangzhou \
    --Tag.1.Key env --Tag.1.Value prod
latest=$(ls -t "$TRACE_DIR_GLOBAL"/*.json | head -1)
md=$(jq -r '.missing_dimensions' "$latest")
warn=$(jq -r '.warning // "null"' "$latest")
[[ "$md" == "false" ]] && ok "missing_dimensions=false (Tags only)" || bad "should be false: $md"
[[ "$warn" == "null" ]] && ok "warning null when Tags set" || bad "warning should be null"

# === T14: helper fallback (file missing) sets missing_dimensions=true ===
echo "T14: helper fallback still has missing_dimensions=true"
PARSE_PY="$WT2_ROOT/alicloud-gcl-runner-ops/scripts/_extract_resource_dimensions.py"
mv "$PARSE_PY" "$PARSE_PY.bak"
result="$(_skillopt_extract_resource_dimensions --ResourceGroupId rg-x --Tag.1.Key env --Tag.1.Value prod)"
rg=$(echo "$result" | python3 -c "import json,sys; v=json.loads(sys.stdin.read())['resource_group_id']; print('null' if v is None else v)")
md=$(echo "$result" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['missing_dimensions'])")
mv "$PARSE_PY.bak" "$PARSE_PY"
[[ "$rg" == "null" ]] && ok "fallback RG → null" || bad "fallback RG: $rg"
[[ "$md" == "True" ]] && ok "fallback missing_dimensions=true" || bad "fallback missing_dimensions: $md"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1