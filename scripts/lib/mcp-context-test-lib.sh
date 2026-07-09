#!/usr/bin/env bash
# Shared L1 fixture runner for MCP context platform tests.
mcp_context_run_l1_suite() {
    local platform="$1"
    local collect_script="$2"
    local fixtures_root="$3"
    shift 3
    # remaining args: case_dir expected_loaded_min expected_invoked_min expected_util (or -1 to skip)
    local PASS=0 FAIL=0
    ok() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
    bad() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

    echo "=== MCP context L1: $platform ==="
    bash -n "$collect_script" && ok "collect script bash -n" || bad "collect syntax"

    while [[ $# -ge 4 ]]; do
        local case_dir="$1" lmin="$2" imin="$3" util="$4"
        shift 4
        local dir="${fixtures_root}/${case_dir}"
        local out
        out="$(bash "$collect_script" --fixture-dir "$dir")"
        if mcp_context_assert_valid "$out" "$case_dir"; then
            ok "$case_dir schema valid"
        else
            bad "$case_dir invalid schema"
            continue
        fi
        local lc ic u
        lc="$(jq '.mcp_tools_loaded | length' <<< "$out")"
        ic="$(jq '.mcp_tools_invoked | length' <<< "$out")"
        u="$(jq -r '.mcp_tool_utilization' <<< "$out")"
        [[ "$lc" -ge "$lmin" ]] && ok "$case_dir loaded>=$lmin ($lc)" || bad "$case_dir loaded $lc < $lmin"
        [[ "$ic" -ge "$imin" ]] && ok "$case_dir invoked>=$imin ($ic)" || bad "$case_dir invoked $ic < $imin"
        if [[ "$util" != "-1" ]]; then
            if awk -v u="$u" -v e="$util" 'BEGIN{exit !(u+0 == e+0)}'; then
                ok "$case_dir utilization=$util"
            else
                bad "$case_dir utilization $u != $util"
            fi
        fi
    done

    echo "=== $platform: $PASS passed, $FAIL failed ==="
    [[ $FAIL -eq 0 ]]
}
