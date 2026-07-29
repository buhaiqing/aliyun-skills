#!/bin/bash
# scripts/validate-wrapper-first-docs.sh
#
# Doc-compliance gate (Generator GCL gate): every product skill that ships a
# Runtime Harness wrapper (*-harness-wrapper.sh or *-skillopt-wrapper.sh) MUST
# declare the MANDATORY wrapper-first rule in its SKILL.md.
#
# Required literals (per AGENTS.md §15.8):
#   - the canonical declaration block: "EXECUTION MANDATORY RULE"
#   - a reference to the wrapper entrypoint: both "harness-wrapper" and
#     "skillopt-wrapper" (the block must mention the preferred harness wrapper
#     and the legacy shim), so a mention inside an unrelated code example does
#     not yield a false PASS.
#
# Discovery reuses scripts/lib/runtime-harness-discover.sh (same helper
# validate-wrapper-first.sh uses) to enumerate skills that have a wrapper.
#
# Exit codes:
#   0  every wrapper-skill SKILL.md declares the MANDATORY wrapper-first rule
#   1  one or more wrapper-skill SKILL.md is missing the declaration
#   2  usage / environment error

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/runtime-harness-discover.sh
source "$SCRIPT_DIR/lib/runtime-harness-discover.sh"

cd "$REPO_ROOT"

skills=()
while IFS= read -r d || [[ -n "$d" ]]; do
    [[ -n "$d" ]] || continue
    skills+=("$d")
done < <(rh_list_skill_dirs_with_wrapper "$REPO_ROOT")

if [[ ${#skills[@]} -eq 0 ]]; then
    echo "No skills with a Runtime Harness wrapper found — nothing to check."
    exit 0
fi

total=${#skills[@]}
pass=0
fail=0

echo "=== validate-wrapper-first-docs.sh ==="
echo "Skills with a wrapper: $total"
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

    # Precise contract: the canonical "> **EXECUTION MANDATORY RULE**" block must
    # exist AND reference both the harness wrapper and the legacy skillopt shim.
    if grep -qE 'EXECUTION MANDATORY RULE' "$skill_md"; then
        has_mandatory_block=true
    fi
    if grep -qE 'harness-wrapper' "$skill_md" && grep -qE 'skillopt-wrapper' "$skill_md"; then
        has_both_wrappers=true
    fi

    if $has_mandatory_block && $has_both_wrappers; then
        echo "PASS: $name — declares MANDATORY wrapper-first (EXECUTION MANDATORY RULE + harness/skillopt wrappers)"
        pass=$((pass + 1))
    else
        echo "FAIL: $name — missing wrapper-first declaration"
        $has_mandatory_block || echo "      - 'EXECUTION MANDATORY RULE' block not found in SKILL.md"
        $has_both_wrappers || echo "      - SKILL.md must reference BOTH 'harness-wrapper' and 'skillopt-wrapper'"
        fail=$((fail + 1))
    fi
done

echo
echo "Summary: $pass PASS / $fail FAIL (of $total wrapper-skills)"

if [[ $fail -gt 0 ]]; then
    exit 1
fi
exit 0
