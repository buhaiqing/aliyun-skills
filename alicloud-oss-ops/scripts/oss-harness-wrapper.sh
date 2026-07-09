#!/bin/bash
# OSS Runtime Harness wrapper
# Graceful fallback: sources harness-lib.sh if available, falls back to direct aliyun CLI.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$SKILL_ROOT")"

# Load .env without overriding variables already set in the parent shell.
oss_skillopt_load_env_files() {
    local env_file
    for env_file in "$REPO_ROOT/.env" "$SKILL_ROOT/.env"; do
        if declare -f _skillopt_load_env_file >/dev/null 2>&1; then
            _skillopt_load_env_file "$env_file"
            continue
        fi
        [[ -f "$env_file" ]] || continue
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
            local key="${line%%=*}"
            local value="${line#*=}"
            key="$(echo "$key" | xargs)"
            value="$(echo "$value" | xargs)"
            if [[ -n "$key" && -z "${!key+x}" ]]; then
                export "$key=$value"
            fi
        done < "$env_file"
    done
}

SKILLOPT_LOADED=false
if [ -f "$SCRIPT_DIR/harness-lib.sh" ]; then
    # shellcheck source=harness-lib.sh
    source "$SCRIPT_DIR/harness-lib.sh"
    SKILLOPT_LOADED=true
elif [ -f "$SCRIPT_DIR/skillopt-lib.sh" ]; then
    # shellcheck source=skillopt-lib.sh
    source "$SCRIPT_DIR/skillopt-lib.sh"
    SKILLOPT_LOADED=true
else
    echo "[WARN] harness-lib.sh not found at $SCRIPT_DIR — falling back to direct aliyun CLI" >&2
fi

# Pre-load credentials and SkillOpt/Langfuse config from .env (skillopt_init reloads safely).
oss_skillopt_load_env_files

PRODUCT="oss"
if [[ ${#} -gt 0 && ("$1" == "oss" || "$1" == "oss2") ]]; then
    PRODUCT="$1"
    shift
fi

if [[ "${#}" -lt 1 ]]; then
    cat >&2 <<'EOF'
Usage: oss-skillopt-wrapper.sh [oss|oss2] <subcommand> [aliyun-params...] [--skillopt-* flags]

Runtime Harness / SkillOpt flags (stripped before calling aliyun):
  --skillopt-enable              Enable self-repair and dynamic optimization
  --skillopt-disable             Disable Runtime Harness self-repair
  --skillopt-langfuse-enable     Enable Langfuse remote tracing
  --skillopt-langfuse-disable    Disable Langfuse remote tracing
  --skillopt-session-id <id>     Shared session id for multi-step workflows
  --skillopt-report              Output Markdown operations summary (no CLI call)
  --skillopt-cb-enable           Enable circuit breaker
  --skillopt-cb-disable          Disable circuit breaker

Environment (.env auto-loaded, no manual source required):
  ${REPO_ROOT}/.env              e.g. aliyun-skills/.env (repo root)
  ${SKILL_ROOT}/.env             e.g. alicloud-oss-ops/.env (skill-local)
  Typical keys: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET,
                ALIBABA_CLOUD_REGION_ID, SKILLOPT_LANGFUSE_ENABLED, LANGFUSE_*

Example:
  ./oss-skillopt-wrapper.sh ls --skillopt-langfuse-enable \
      --skillopt-session-id sess-oss-$(date +%s)
EOF
    exit 1
fi

SUBCMD="$1"; shift

# Validate: action must be present and not a --skillopt-* flag.
# Without this guard, a caller that passes only --skillopt-* flags
# gets `aliyun oss --skillopt-enable` → "is not a vaild command"
# (the aliyun CLI's typo, not ours). Fast-fail with an actionable error.
if [[ -z "$SUBCMD" || "$SUBCMD" == --skillopt-* || "$SUBCMD" == --harness-* ]]; then
    cat >&2 <<EOF
ERROR: missing <subcommand> before --skillopt-* flags.
       Invocation form: $0 [oss|oss2] <subcommand> [args...] [--skillopt-* flags]
       Note: the subcommand is an ossutil verb (ls, mb, cp, rm, stat, set-acl, ...),
             NOT a PascalCase OpenAPI name (ListBuckets, PutBucket, ...). The
             aliyun oss subcommand is deprecated and only accepts ossutil verbs.
EOF
    exit 64
fi

if [ "$SKILLOPT_LOADED" = true ]; then
    skillopt_wrap "$PRODUCT" "$SUBCMD" "$@"
else
    # Fallback: call aliyun directly, stripping any --skillopt-* flags
    FILTERED_ARGS=()
    skip_next=false
    for arg in "$@"; do
        if [[ "$skip_next" == true ]]; then
            skip_next=false
            continue
        fi
        case "$arg" in
            --skillopt-session-id|--skillopt-log-file|--skillopt-retries|--skillopt-backoff|--skillopt-cb-threshold|--skillopt-cb-cooldown)
                skip_next=true
                ;;
            --skillopt-*)
                ;;
            *)
                FILTERED_ARGS+=("$arg")
                ;;
        esac
    done
    aliyun "$PRODUCT" "$SUBCMD" "${FILTERED_ARGS[@]}"
fi
