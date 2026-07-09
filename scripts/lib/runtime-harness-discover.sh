#!/bin/bash
# scripts/lib/runtime-harness-discover.sh
# Shared wrapper discovery for Runtime Harness migration (Strategy B).
# Accepts legacy *-skillopt-wrapper.sh and new *-harness-wrapper.sh patterns.
#
# Usage (source, do not execute directly):
#   source "$REPO_ROOT/scripts/lib/runtime-harness-discover.sh"
#   rh_find_wrappers "$skill_dir/scripts"
#   rh_skill_has_wrapper "$skill_dir"

# Legacy and canonical (post PR-3) wrapper filename globs — space-separated basenames.
RH_WRAPPER_GLOB_PATTERNS=(
    '*-skillopt-wrapper.sh'
    '*-harness-wrapper.sh'
)

# rh_find_wrappers <scripts_dir>
# Prints one wrapper path per line (sorted, unique).
rh_find_wrappers() {
    local scripts_dir="$1"
    local -a found=()
    local pattern f

    [[ -d "$scripts_dir" ]] || return 0

    for pattern in "${RH_WRAPPER_GLOB_PATTERNS[@]}"; do
        # shellcheck disable=SC2086
        for f in "$scripts_dir"/$pattern; do
            [[ -f "$f" ]] || continue
            found+=("$f")
        done
    done

    if [[ ${#found[@]} -eq 0 ]]; then
        return 0
    fi

    printf '%s\n' "${found[@]}" | sort -u
}

# rh_skill_has_wrapper <skill_dir>
# Exit 0 if skill has at least one wrapper script.
rh_skill_has_wrapper() {
    local skill_dir="$1"
    local count
    count="$(rh_find_wrappers "$skill_dir/scripts" | grep -c . || true)"
    [[ "$count" -gt 0 ]]
}

# rh_list_skill_dirs_with_wrapper [repo_root]
# Prints skill directory paths (relative or absolute per input) one per line.
rh_list_skill_dirs_with_wrapper() {
    local root="${1:-.}"
    local d

    for d in "$root"/alicloud-*-ops; do
        [[ -d "$d" ]] || continue
        if rh_skill_has_wrapper "$d"; then
            printf '%s\n' "$d"
        fi
    done
}

# rh_wrapper_stem <wrapper_path>
# e.g. ecs-skillopt-wrapper.sh -> ecs, vpc-harness-wrapper.sh -> vpc
rh_wrapper_stem() {
    local base
    base="$(basename "$1")"
    base="${base%-skillopt-wrapper.sh}"
    base="${base%-harness-wrapper.sh}"
    printf '%s' "$base"
}
