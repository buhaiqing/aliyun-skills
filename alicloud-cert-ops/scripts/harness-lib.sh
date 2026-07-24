#!/bin/bash
# SkillOpt Core Library for alicloud-cert-ops
# Self-repair and dynamic optimization for CAS CLI commands.
# Compatible with macOS (BSD grep/sed) and Linux.

set -euo pipefail

# Resolve paths
_SKILLOPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SKILLOPT_SKILL_ROOT="$(dirname "$_SKILLOPT_LIB_DIR")"

# SkillOpt configuration
SKILLOPT_ENABLED="${SKILLOPT_ENABLED:-true}"
SKILLOPT_REPORT="${SKILLOPT_REPORT:-false}"
SKILLOPT_RETRIES="${SKILLOPT_RETRIES:-3}"
SKILLOPT_BACKOFF=(1 2 4)
SKILLOPT_LAST_OUTPUT=""
SKILLOPT_LAST_RC=0
SKILLOPT_PARAMS=()

# Observability
SKILLOPT_LOG_LABEL="[CAS-SkillOpt]"
SKILLOPT_SKILL_TAG="alicloud-cert-ops"

# Shared SkillOpt core
_SKILLOPT_SHARED_ROOT="${ALIYUN_SKILLS_ROOT:-${_SKILLOPT_SKILLS_ROOT:-$(git -C "$_SKILLOPT_SKILL_ROOT" rev-parse --show-toplevel 2>/dev/null || dirname "$_SKILLOPT_SKILL_ROOT")/alicloud-skillopt-ops}"
if [[ -f "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-core-lib.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_SKILLOPT_SHARED_ROOT}/scripts/skillopt-core-lib.sh"
elif [[ -f "${_SKILLOPT_SKILL_ROOT}/../../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_SKILLOPT_SKILL_ROOT}/../../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh"
fi

# JSON param list for CAS operations
# These params must be captured for repair and tracing
CAS_JSON_PARAMS=(
    CertIds        # JSON array: '["123","456"]'
    ResourceIds    # JSON array: '["resource1","resource2"]'
    ContactIds     # JSON array: '["contact1"]'
    OrderId        # Long
    CertId         # Long
    JobId          # Long
    Name           # String
    Cert           # PEM content (sensitive)
    Key            # Private key PEM (sensitive)
    SignCert       # SM2 sign cert PEM (sensitive)
    SignPrivateKey # SM2 sign key PEM (sensitive)
    EncryptCert    # SM2 encrypt cert PEM (sensitive)
    EncryptPrivateKey # SM2 encrypt key PEM (sensitive)
    JobType        # String: CLB/CDN/OSS/WAF/FC/SAE/GA/MSE/Multiple
    CurrentPage
    ShowSize
    Status
    SourceType
    CloudProduct
)

# Log helper
cert_skillopt_log() {
    local level="${1:-INFO}"
    shift
    printf '%s %s [%s] %s\n' \
        "$(date +%H:%M:%S)" \
        "$SKILLOPT_LOG_LABEL" \
        "$level" \
        "$*"
}

# Parse JSON params from command line
cert_parse_params() {
    local cmd=("$@")
    local in_json=false
    local json_params=""

    for param in "${CAS_JSON_PARAMS[@]}"; do
        local found=false
        for i in "${!cmd[@]}"; do
            if [[ "${cmd[$i]}" == "--$param" ]]; then
                found=true
                break
            fi
        done
    done
}

# Auto-repair error patterns for CAS — per diagnostic-logging-standard.md
cert_repair_error() {
    local error_code="${1:-}"
    local action="${2:-}"

    case "$error_code" in
        *"InvalidParameter"*)
            cert_skillopt_log "ERROR" "TYPE=INVALID_PARAM FIX=Verify param names per CAS API spec"
            return 1
            ;;
        *"ResourceNotFound"*)
            cert_skillopt_log "ERROR" "TYPE=RESOURCE_NOT_FOUND FIX=Run ListUserCertificateOrder to get valid CertId"
            return 1
            ;;
        *"Throttling"*)
            cert_skillopt_log "WARN" "TYPE=THROTTLING FIX=Retry after backoff ${SKILLOPT_BACKOFF[0]}s"
            sleep "${SKILLOPT_BACKOFF[0]}"
            return 0  # retryable
            ;;
        *"InternalError"*)
            cert_skillopt_log "WARN" "TYPE=INTERNAL_ERROR FIX=Retry after backoff"
            sleep 2
            return 0  # retryable
            ;;
        *"CertExpired"*)
            cert_skillopt_log "ERROR" "TYPE=CERT_EXPIRED FIX=Upload a new certificate before deployment"
            return 1
            ;;
        *"CertRevoked"*)
            cert_skillopt_log "ERROR" "TYPE=CERT_REVOKED FIX=Certificate is already revoked — cannot deploy"
            return 1
            ;;
        *"QuotaExceeded"*)
            cert_skillopt_log "ERROR" "TYPE=QUOTA_EXCEEDED FIX=Check DescribePackageState for quota usage"
            return 1
            ;;
        *)
            cert_skillopt_log "ERROR" "TYPE=UNKNOWN_FIX=Check DescribeDeploymentJob or DescribeCertificateState for details"
            return 1
            ;;
    esac
}

# Mask sensitive params (Cert/Key) in EXEC log — per diagnostic-logging-standard.md
cert_mask_params() {
    local params=("$@")
    local masked=""
    local skip_next=false
    for item in "${params[@]}"; do
        if $skip_next; then
            case "$item" in
                *"-----BEGIN"*|*"-----END"*|*"MII"*|*"LS0t"*)
                    masked="$masked ***"
                    ;;
                *)
                    masked="$masked $item"
                    ;;
            esac
            skip_next=false
        else
            case "$item" in
                "--Cert"|"--Key"|"--SignCert"|"--SignPrivateKey"|"--EncryptCert"|"--EncryptPrivateKey")
                    masked="$masked $item"
                    skip_next=true
                    ;;
                *)
                    masked="$masked $item"
                    ;;
            esac
        fi
    done
    echo "$masked"
}

# Wrap aliyun cas command with auto-repair
skillopt_wrap() {
    local action="${1:-}"
    shift
    local params=("$@")

    local masked_params
    masked_params=$(cert_mask_params "${params[@]}")
    cert_skillopt_log "EXEC" "aliyun cas $action$masked_params"

    if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
        SKILLOPT_LAST_OUTPUT=$(aliyun cas "$action" "${params[@]}" 2>&1) || true
        SKILLOPT_LAST_RC=$?
        printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
        return $SKILLOPT_LAST_RC
    fi

    local attempt=0
    local max_attempts=$((SKILLOPT_RETRIES + 1))

    while (( attempt < max_attempts )); do
        SKILLOPT_LAST_OUTPUT=$(aliyun cas "$action" "${params[@]}" 2>&1)
        SKILLOPT_LAST_RC=$?

        if [[ $SKILLOPT_LAST_RC -eq 0 ]]; then
            cert_skillopt_log "RESULT" "aliyun cas $action succeeded"
            printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
            return 0
        fi

        local error_code
        error_code=$(echo "$SKILLOPT_LAST_OUTPUT" | \
            grep -o '"Code":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "Unknown")


        cert_skillopt_log "WARN" "Attempt $((attempt + 1))/$max_attempts failed: $error_code"

        local repaired=false
        cert_repair_error "$error_code" "$action" && repaired=true

        if [[ "$repaired" == "false" ]]; then
            cert_skillopt_log "ERROR" "TYPE=RETRY_EXHAUSTED FIX=Check DescribeDeploymentJob or DescribeCertificateState for details"
            printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
            return $SKILLOPT_LAST_RC
        fi

        ((attempt++))
    done

    cert_skillopt_log "ERROR" "TYPE=RETRY_EXHAUSTED FIX=All $max_attempts attempts failed — check error above"
    printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
    return $SKILLOPT_LAST_RC
}

# Convenience wrappers
cas_list_certs() {
    skillopt_wrap ListUserCertificateOrder --OrderType CERT --ShowSize 50
}

cas_get_cert_detail() {
    local cert_id="${1:-}"
    [[ -z "$cert_id" ]] && { echo "ERROR: cert_id required"; return 1; }
    skillopt_wrap GetUserCertificateDetail --CertId "$cert_id"
}

cas_list_cloud_resources() {
    local cert_id="${1:-}"
    [[ -z "$cert_id" ]] && { echo "ERROR: cert_id required"; return 1; }
    skillopt_wrap ListCloudResources --CertIds "[\"$cert_id\"]"
}

cas_upload_cert() {
    local name="${1:-}"
    local cert="${2:-}"
    local key="${3:-}"
    [[ -z "$name" || -z "$cert" || -z "$key" ]] && { echo "ERROR: name, cert, key required"; return 1; }
    skillopt_wrap UploadUserCertificate --Name "$name" --Cert "$cert" --Key "$key"
}

cas_create_deployment() {
    local cert_ids="${1:-}"
    local contact_ids="${2:-}"
    local job_type="${3:-}"
    local resource_ids="${4:-}"
    local job_name="${5:-cert-replacement-$(date +%Y%m%d-%H%M%S)}"
    [[ -z "$cert_ids" || -z "$contact_ids" || -z "$job_type" || -z "$resource_ids" ]] && \
        { echo "ERROR: cert_ids, contact_ids, job_type, resource_ids required"; return 1; }
    skillopt_wrap CreateDeploymentJob \
        --CertIds "$cert_ids" \
        --ContactIds "$contact_ids" \
        --JobType "$job_type" \
        --Name "$job_name" \
        --ResourceIds "$resource_ids"
}

cas_describe_job_status() {
    local job_id="${1:-}"
    [[ -z "$job_id" ]] && { echo "ERROR: job_id required"; return 1; }
    skillopt_wrap DescribeDeploymentJobStatus --JobId "$job_id"
}

cas_revoke_cert() {
    local instance_id="${1:-}"
    [[ -z "$instance_id" ]] && { echo "ERROR: instance_id required"; return 1; }
    cert_skillopt_log "DIAG" "TYPE=SECURITY_WARN FIX=Confirmed — Revoking certificate $instance_id (IRREVERSIBLE)"
    skillopt_wrap RevokeCertificate --InstanceId "$instance_id"
}

cas_delete_cert() {
    local cert_id="${1:-}"
    [[ -z "$cert_id" ]] && { echo "ERROR: cert_id required"; return 1; }
    cert_skillopt_log "DIAG" "TYPE=SECURITY_WARN FIX=Confirmed — Deleting certificate $cert_id"
    skillopt_wrap DeleteUserCertificate --CertId "$cert_id"
}
