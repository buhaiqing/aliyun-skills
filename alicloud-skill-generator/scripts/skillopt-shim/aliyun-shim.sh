#!/bin/bash
# aliyun-shim.sh — intercepts `aliyun <product>` calls and routes them through
# the per-skill SkillOpt wrapper. Once sourced, `aliyun mongodb DescribeDBInstances`
# physically cannot bypass `./alicloud-mongodb-ops/scripts/mongodb-skillopt-wrapper.sh`.
#
# USAGE:  source aliyun-shim.sh
#         (or run ./enable.sh to install persistently into your shell rc)
#
# ESCAPE HATCH:  command aliyun ...   # bypasses the shim, calls native binary
#
# KNOWN LIMITATIONS:
#   * Only intercepts calls where the FIRST positional arg is a product code.
#     `aliyun --profile prod oss ls` (flag-first) is NOT intercepted —
#     use `aliyun oss ls --profile prod` instead, or `command aliyun ...`.
#   * Product registry is hardcoded below. When a new wrapped skill is added,
#     add an entry. Both friendly names and CLI-canonical product codes are
#     accepted (e.g., "mongodb" and "dds" both route to alicloud-mongodb-ops).
#
# OBSERVABILITY:
#   SKILLOPT_SHIM_LOG=1              — enable logging
#   SKILLOPT_SHIM_LOG_FILE=<path>    — override log file
#                                       default: <repo>/.runtime/skillopt-shim.log
#
# Maintenance: this file is shared infrastructure. Owned by the
# alicloud-skill-generator meta-skill. Do not duplicate per-product.

# Guard: do not load twice in the same shell.
if [[ -n "${_SKILLOPT_SHIM_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi
_SKILLOPT_SHIM_LOADED=1

# ----------------------------------------------------------------------------
# Skill registry. Each entry: "user-input:skill-dir:wrapper-basename:wrapper-product-arg"
#   * user-input         = what the user types after `aliyun` (e.g. "mongodb")
#   * skill-dir          = the alicloud-*-ops directory (no trailing slash)
#   * wrapper-basename   = the wrapper script filename inside scripts/
#   * wrapper-product-arg = the product code the wrapper expects as $1
#                            (may differ from user-input due to CLI aliasing:
#                             aliyun mongodb → dds, aliyun ack → cs, aliyun redis → r-kvstore)
#
# Add new entries when onboarding a wrapped skill. Keep alphabetized by user-input.
# ----------------------------------------------------------------------------
_SKILLOPT_SHIM_REGISTRY=(
  "ack:alicloud-ack-ops:ack-skillopt-wrapper.sh:cs"
  "cms:alicloud-cms-ops:cms-skillopt-wrapper.sh:cms"
  "cs:alicloud-ack-ops:ack-skillopt-wrapper.sh:cs"
  "dds:alicloud-mongodb-ops:mongodb-skillopt-wrapper.sh:dds"
  "ecs:alicloud-ecs-ops:ecs-skillopt-wrapper.sh:ecs"
  "mongodb:alicloud-mongodb-ops:mongodb-skillopt-wrapper.sh:dds"
  "oss:alicloud-oss-ops:oss-skillopt-wrapper.sh:oss"
  "r-kvstore:alicloud-redis-ops:redis-skillopt-wrapper.sh:r-kvstore"
  "rds:alicloud-rds-ops:rds-skillopt-wrapper.sh:rds"
  "redis:alicloud-redis-ops:redis-skillopt-wrapper.sh:r-kvstore"
  "slb:alicloud-slb-ops:slb-skillopt-wrapper.sh:slb"
  "vpc:alicloud-vpc-ops:vpc-skillopt-wrapper.sh:vpc"
)

# ----------------------------------------------------------------------------
# Resolve the aliyun-skills repo root by walking up from PWD.
# Echoes the root on match, returns 1 otherwise.
# ----------------------------------------------------------------------------
_skillopt_shim_root() {
  local dir="${PWD}"
  while [[ "$dir" != "/" ]]; do
    if compgen -G "$dir/alicloud-*-ops" >/dev/null 2>&1; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# ----------------------------------------------------------------------------
# Append a structured line to the observability log (opt-in).
# MUST silently no-op on any failure — the shim can never block the user's
# command because of a logging failure.
# ----------------------------------------------------------------------------
_skillopt_shim_log() {
  [[ "${SKILLOPT_SHIM_LOG:-0}" == "1" ]] || return 0
  local log="${SKILLOPT_SHIM_LOG_FILE:-}"
  if [[ -z "$log" ]]; then
    local root
    root="$(_skillopt_shim_root 2>/dev/null)" || return 0
    log="${root}/.runtime/skillopt-shim.log"
  fi
  mkdir -p "$(dirname "$log")" 2>/dev/null || return 0
  printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "$log" 2>/dev/null
  return 0
}

# ----------------------------------------------------------------------------
# Look up an entry in the registry by user-input product code.
# On match, sets globals _SHIM_SKILL, _SHIM_WRAPPER, _SHIM_WRAPPER_ARG
# and returns 0. Returns 1 on miss.
# ----------------------------------------------------------------------------
_skillopt_shim_lookup() {
  local product="$1"
  local entry user skill wrapper wrapper_arg
  for entry in "${_SKILLOPT_SHIM_REGISTRY[@]}"; do
    IFS=':' read -r user skill wrapper wrapper_arg <<< "$entry"
    if [[ "$user" == "$product" ]]; then
      _SHIM_SKILL="$skill"
      _SHIM_WRAPPER="$wrapper"
      _SHIM_WRAPPER_ARG="$wrapper_arg"
      return 0
    fi
  done
  return 1
}

# ----------------------------------------------------------------------------
# THE SHIM: override `aliyun` so wrapped products are forced through
# the per-skill wrapper. Native aliyun binary is preserved as the
# escape hatch via `command aliyun`.
# ----------------------------------------------------------------------------
aliyun() {
  local first="${1:-}"

  # No args, or first arg is a flag → pass through to native binary.
  # This is the documented limitation: only `aliyun <product> <action>`
  # (product-first) is intercepted. Flag-first invocations bypass.
  if [[ -z "$first" || "$first" == -* ]]; then
    command aliyun "$@"
    return $?
  fi

  local product="$first"

  # CLI-level (non-product) subcommands — pass through unchanged.
  case "$product" in
    help|version|configure|completion)
      command aliyun "$@"
      return $?
      ;;
  esac

  # Look up the wrapper for this product.
  if ! _skillopt_shim_lookup "$product"; then
    # No wrapper registered — pass through.
    # NORMAL case for `aliyun sts ...`, `aliyun ram ...`, `aliyun polardb ...`, etc.
    _skillopt_shim_log "PASSTHROUGH product=$product reason=no_wrapper"
    command aliyun "$@"
    return $?
  fi

  # Resolve repo root.
  local root
  if ! root="$(_skillopt_shim_root)"; then
    # Not inside an aliyun-skills checkout — can't find the wrapper.
    # Pass through with a one-line warning so the user knows why.
    echo "[skillopt-shim] WARN: aliyun-skills repo not found from $PWD; falling back to native aliyun" >&2
    _skillopt_shim_log "BYPASS product=$product reason=no_repo_root path=$PWD"
    command aliyun "$@"
    return $?
  fi

  local wrapper_path="${root}/${_SHIM_SKILL}/scripts/${_SHIM_WRAPPER}"
  if [[ ! -x "$wrapper_path" ]]; then
    echo "[skillopt-shim] WARN: wrapper not executable at $wrapper_path; falling back to native aliyun" >&2
    _skillopt_shim_log "BYPASS product=$product reason=wrapper_missing path=$wrapper_path"
    command aliyun "$@"
    return $?
  fi

  # All checks passed — route through the wrapper.
  # Wrapper convention: `wrapper.sh <product-arg> <subcmd> [args...]`
  # Pass the wrapper's product-arg as $1, then everything else.
  _skillopt_shim_log "INTERCEPT product=$product skill=$_SHIM_SKILL wrapper=$wrapper_path wrapper_arg=$_SHIM_WRAPPER_ARG"
  "$wrapper_path" "$_SHIM_WRAPPER_ARG" "${@:2}"
}
