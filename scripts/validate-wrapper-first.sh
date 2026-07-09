#!/bin/bash
# scripts/validate-wrapper-first.sh
# Static check: every alicloud-*-ops skill with a Runtime Harness wrapper
# (*-skillopt-wrapper.sh legacy or *-harness-wrapper.sh) must
# follow AGENTS.md §15.8 (Wrapper-First Execution Rule). This is the P2
# enforcement layer that complements:
#   - P0  AGENTS.md §15.8 + CI gate that grep for bare `aliyun <product>` calls
#   - P1  runtime `require_skillopt_wrapper` guard + Langfuse bypass alert
#
# Two severity levels:
#   - violation  (P0)  blocks CI; the skill must declare wrapper-first
#   - warning    (P1)  informational; tracks graceful fallback migration
#
# Usage:
#   bash scripts/validate-wrapper-first.sh                              # full audit
#   bash scripts/validate-wrapper-first.sh --skill alicloud-ecs-ops    # one
#   bash scripts/validate-wrapper-first.sh --json                       # CI mode
#   bash scripts/validate-wrapper-first.sh --strict-warnings            # warn also fails
#
# Exit codes:
#   0  no violations (and no warnings if --strict-warnings)
#   1  violations found (P0)
#   2  usage / config error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/runtime-harness-discover.sh
source "$SCRIPT_DIR/lib/runtime-harness-discover.sh"

# ---------- args ----------
TARGET_SKILL=""
JSON_MODE=false
STRICT_WARNINGS=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skill) TARGET_SKILL="$2"; shift 2 ;;
        --json)  JSON_MODE=true; shift ;;
        --strict-warnings) STRICT_WARNINGS=true; shift ;;
        -h|--help)
            sed -n '2,28p' "$0"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

cd "$REPO_ROOT"

# ---------- collect skills ----------
if [[ -n "$TARGET_SKILL" ]]; then
    # --skill accepts:
    #   1. Directory path (e.g. /tmp/scratch/alicloud-test-good-ops or ./alicloud-ecs-ops)
    #   2. Skill name relative to repo root (e.g. alicloud-ecs-ops)
    if [[ -d "$TARGET_SKILL" ]]; then
        skills=("$TARGET_SKILL")
    elif [[ -d "$REPO_ROOT/$TARGET_SKILL" ]]; then
        skills=("$REPO_ROOT/$TARGET_SKILL")
    else
        echo "Error: --skill target not found: $TARGET_SKILL" >&2
        exit 2
    fi
else
    skills=()
    while IFS= read -r d || [[ -n "$d" ]]; do
        [[ -n "$d" ]] || continue
        skills+=("$d")
    done < <(rh_list_skill_dirs_with_wrapper "$REPO_ROOT")
fi

# ---------- output buffers (parallel arrays) ----------
violation_entries=()
warning_entries=()
total=0
checked=0
violations_count=0
warnings_count=0

# json_escape <string>
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//	/ }"
    printf '%s' "$s"
}

# add_issue severity skill rule detail
add_issue() {
    local severity="$1" skill="$2" rule="$3" detail="$4"
    local safe_skill safe_rule safe_detail
    safe_skill=$(json_escape "$skill")
    safe_rule=$(json_escape "$rule")
    safe_detail=$(json_escape "$detail")
    local entry
    entry=$(printf '{"skill":"%s","rule":"%s","detail":"%s"}' \
        "$safe_skill" "$safe_rule" "$safe_detail")

    if [[ "$severity" == "violation" ]]; then
        violation_entries+=("$entry")
        violations_human+="  - [P0] [$skill] $rule: $detail"$'\n'
        violations_count=$((violations_count + 1))
    else
        warning_entries+=("$entry")
        warnings_human+="  - [P1] [$skill] $rule: $detail"$'\n'
        warnings_count=$((warnings_count + 1))
    fi
}

# Init empty human buffer
violations_human=""
warnings_human=""

# ---------- checks ----------
for sd in "${skills[@]}"; do
    total=$((total + 1))
    skill_md="$sd/SKILL.md"
    scripts_dir="$sd/scripts"

    if [[ ! -f "$skill_md" ]]; then
        add_issue violation "$sd" "missing_skill_md" "SKILL.md not found"
        continue
    fi
    checked=$((checked + 1))

    # P0 Check 1: skill declares ## Runtime Rules
    if ! grep -qE '^##[[:space:]]+Runtime Rules' "$skill_md"; then
        add_issue violation "$sd" "missing_runtime_rules_section" \
            "SKILL.md has no '## Runtime Rules' section (AGENTS.md §15.8)"
    fi

    # P0 Check 2: skill declares Wrapper-First CLI path with MANDATORY marker
    if ! grep -qE '(MANDATORY|must|优先使用|必须).*wrapper|wrapper.*MANDATORY|skillopt-wrapper\.sh|harness-wrapper\.sh' "$skill_md"; then
        add_issue violation "$sd" "missing_wrapper_first_declaration" \
            "Runtime Rules table does not declare Wrapper-First CLI path"
    fi

    # P0 Check 3: skill declares Fallback note
    if ! grep -qE 'fall[ -]?back|Fallback|fallback' "$skill_md"; then
        add_issue violation "$sd" "missing_fallback_note" \
            "Runtime Rules does not describe fallback path (when bare aliyun is allowed)"
    fi

    # P0 Check 4: scripts/ contains bare 'aliyun <own_product> <Action>' calls
    if [[ -d "$scripts_dir" ]]; then
        own_product=""
        while IFS= read -r _wp || [[ -n "$_wp" ]]; do
            [[ -n "$_wp" ]] || continue
            own_product="$(rh_wrapper_stem "$_wp")"
            break
        done < <(rh_find_wrappers "$scripts_dir")
        [[ -z "$own_product" ]] && own_product=$(basename "$sd" | sed 's/^alicloud-//; s/-ops$//')

        bare_aliyun=$(grep -rEn "(^|[[:space:]])aliyun[[:space:]]+${own_product}[[:space:]]+[A-Z]" \
            "$scripts_dir" --include='*.sh' 2>/dev/null \
            | grep -v '\-\-skillopt-' \
            | grep -v 'echo ' \
            | grep -v 'SKILLOPT_' \
            | grep -vE '^\s*#' \
            || true)
        if [[ -n "$bare_aliyun" ]]; then
            add_issue violation "$sd" "bare_aliyun_in_scripts" \
                "scripts/ contains bare 'aliyun $own_product <Action>' call (own product, should use wrapper)"
        fi
    fi

    # P1 Check 5: graceful fallback migration
    while IFS= read -r wrapper || [[ -n "$wrapper" ]]; do
        [[ -n "$wrapper" ]] || continue

        if ! grep -qE 'SKILLOPT_LOADED=' "$wrapper"; then
            add_issue warning "$sd" "wrapper_not_graceful" \
                "$(basename "$wrapper") does not implement SKILLOPT_LOADED graceful fallback (P1 migration)"
        fi
        if ! grep -qE 'source[[:space:]]+"?\$\{?SCRIPT_DIR\}?/(skillopt-lib|harness-lib)\.sh' "$wrapper"; then
            add_issue warning "$sd" "wrapper_does_not_source_lib" \
                "$(basename "$wrapper") does not source skillopt-lib.sh or harness-lib.sh (P1 migration)"
        fi
    done < <(rh_find_wrappers "$scripts_dir")
done

# Build JSON arrays
join_by() {
    local d="$1"; shift
    if [[ $# -eq 0 ]]; then return; fi
    local first="$1"; shift
    printf '%s' "$first"
    for item in "$@"; do
        printf '%s%s' "$d" "$item"
    done
}
violations_json="[$(join_by , "${violation_entries[@]+"${violation_entries[@]}"}")]"
warnings_json="[$(join_by , "${warning_entries[@]+"${warning_entries[@]}"}")]"

# ---------- report ----------
if $JSON_MODE; then
    printf '{"total_skills":%d,"checked":%d,"violations":%d,"warnings":%d,"details":{"violations":%s,"warnings":%s}}\n' \
        "$total" "$checked" "$violations_count" "$warnings_count" \
        "$violations_json" "$warnings_json"
else
    echo "=== validate-wrapper-first.sh ==="
    echo "Repo:    $REPO_ROOT"
    echo "Skills:  $total (with Runtime Harness wrapper)"
    echo "Checked: $checked"
    echo "Violations (P0, fail CI):  $violations_count"
    echo "Warnings   (P1, track):    $warnings_count"
    echo
    if [[ $violations_count -gt 0 ]]; then
        echo "❌ P0 Violations:"
        printf '%s' "$violations_human"
    else
        echo "✅ No P0 violations — all wrapper-first skills declare Runtime Rules + MANDATORY + Fallback."
    fi
    echo
    if [[ $warnings_count -gt 0 ]]; then
        echo "⚠️  P1 Warnings (graceful fallback migration, not CI-blocking):"
        printf '%s' "$warnings_human"
        echo "    → Migrate by re-running .scripts/gen-skillopt.sh or copying the pattern from"
        echo "      alicloud-oss-ops/scripts/oss-skillopt-wrapper.sh (lines 31-116)"
    else
        echo "✅ No P1 warnings — all wrappers implement graceful fallback."
    fi
    echo
    echo "Reference: AGENTS.md §15.8 (Wrapper-First Execution Rule)"
fi

# Exit code policy
if [[ $violations_count -gt 0 ]]; then
    exit 1
fi
if $STRICT_WARNINGS && [[ $warnings_count -gt 0 ]]; then
    exit 1
fi
exit 0
