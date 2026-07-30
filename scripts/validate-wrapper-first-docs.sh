#!/bin/bash
# scripts/validate-wrapper-first-docs.sh
#
# Doc-compliance + wrapper-existence gate (Generator GCL gate):
# every PRODUCT skill MUST
#   1. declare the MANDATORY wrapper-first rule in its SKILL.md, AND
#   2. ship a canonical Runtime Harness wrapper at scripts/*-harness-wrapper.sh.
#
# The two library skills (alicloud-runtime-harness-ops, alicloud-skillopt-ops)
# are exempt — they PROVIDE the harness, they do not consume a product wrapper.
# alicloud-skill-generator is a meta-skill (generator), not a product skill.
#
# Required SKILL.md literals (per AGENTS.md §15.8):
#   - the canonical declaration block: "EXECUTION MANDATORY RULE"
#   - a reference to the wrapper entrypoint: both "harness-wrapper" and
#     "skillopt-wrapper" (the block must mention the preferred harness wrapper
#     and the legacy shim), so a mention inside an unrelated code example does
#     not yield a false PASS.
#
# Exit codes:
#   0  every product skill declares wrapper-first AND ships a wrapper
#   1  one or more product skills fail the declaration or wrapper check
#   2  usage / environment error

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/runtime-harness-discover.sh
source "$SCRIPT_DIR/lib/runtime-harness-discover.sh"

cd "$REPO_ROOT"

# Library skills that provide the harness are exempt from the wrapper check.
EXEMPT_LIBS=("alicloud-runtime-harness-ops" "alicloud-skillopt-ops" "alicloud-skill-generator")

skills=()
for d in "$REPO_ROOT"/alicloud-*-ops; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    skip=false
    for ex in "${EXEMPT_LIBS[@]}"; do
        [[ "$name" == "$ex" ]] && skip=true && break
    done
    $skip && continue
    skills+=("$d")
done

if [[ ${#skills[@]} -eq 0 ]]; then
    echo "No product skills found — nothing to check."
    exit 0
fi

total=${#skills[@]}
pass=0
fail=0

echo "=== validate-wrapper-first-docs.sh ==="
echo "Product skills checked: $total (libraries exempt: ${EXEMPT_LIBS[*]})"
echo

for sd in "${skills[@]}"; do
    skill_md="$sd/SKILL.md"
    name="$(basename "$sd")"

    if [[ ! -f "$skill_md" ]]; then
        echo "FAIL: $name — SKILL.md not found"
        fail=$((fail + 1))
        continue
    fi

    has_mandatory_block=false
    has_both_wrappers=false
    has_wrapper_script=false

    # Precise contract: the canonical "> **EXECUTION MANDATORY RULE**" block must
    # exist AND reference both the harness wrapper and the legacy skillopt shim.
    if grep -qE 'EXECUTION MANDATORY RULE' "$skill_md"; then
        has_mandatory_block=true
    fi
    if grep -qE 'harness-wrapper' "$skill_md" && grep -qE 'skillopt-wrapper' "$skill_md"; then
        has_both_wrappers=true
    fi

    # P5: every product skill must ship a canonical harness wrapper.
    if ls "$sd/scripts/"*-harness-wrapper.sh >/dev/null 2>&1; then
        has_wrapper_script=true
    fi

    if $has_mandatory_block && $has_both_wrappers && $has_wrapper_script; then
        echo "PASS: $name — declares MANDATORY wrapper-first + ships *-harness-wrapper.sh"
        pass=$((pass + 1))
    else
        echo "FAIL: $name — wrapper-first compliance gap"
        $has_mandatory_block || echo "      - 'EXECUTION MANDATORY RULE' block not found in SKILL.md"
        $has_both_wrappers || echo "      - SKILL.md must reference BOTH 'harness-wrapper' and 'skillopt-wrapper'"
        $has_wrapper_script || echo "      - missing scripts/*-harness-wrapper.sh"
        fail=$((fail + 1))
    fi
done

echo
echo "Summary: $pass PASS / $fail FAIL (of $total product skills)"

if [[ $fail -gt 0 ]]; then
    exit 1
fi
exit 0
