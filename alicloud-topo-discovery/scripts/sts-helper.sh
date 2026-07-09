#!/bin/bash
# ============================================================
# STS AssumeRole helper for alicloud-topo-discovery.
# Sources temporary credentials from Aliyun STS and exports them
# as ALIBABA_CLOUD_ACCESS_KEY_ID / SECRET / SESSION_TOKEN.
#
# Usage:
#   source sts-helper.sh --role-arn arn:acs:ram::1234:role/TopologyReader
#   source sts-helper.sh --role-arn "$ROLE_ARN" --session-name "topo" --duration 3600
#
# Exit codes:
#   0  - Success (caller should source this script)
#   10 - AssumeRole failed (CLI error, network, or permissions)
#   11 - Missing credentials (ALIBABA_CLOUD_ACCESS_KEY_ID not set)
#   12 - Invalid role ARN format
# ============================================================
set -euo pipefail

# ---- Defaults ----
SESSION_NAME="topo-discovery"
DURATION_SECONDS=3600

# ---- Parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --role-arn) ROLE_ARN="$2"; shift 2 ;;
        --session-name) SESSION_NAME="$2"; shift 2 ;;
        --duration) DURATION_SECONDS="$2"; shift 2 ;;
        *) echo "[ERROR] Unknown option: $1" >&2; exit 12 ;;
    esac
done

if [[ -z "${ROLE_ARN:-}" ]]; then
    # No --role-arn given, nothing to do (normal path)
    exit 0
fi

# ---- Validate ARN format ----
if ! echo "$ROLE_ARN" | grep -qP '^arn:acs:ram::[0-9]+:role/.+$'; then
    echo "[ERROR] Invalid role ARN format: $ROLE_ARN" >&2
    echo "[ERROR] Expected: arn:acs:ram::<account_id>:role/<role_name>" >&2
    exit 12
fi

# ---- Check credentials ----
if [[ -z "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" ]]; then
    echo "[ERROR] ALIBABA_CLOUD_ACCESS_KEY_ID not set" >&2
    echo "[ERROR] STS AssumeRole requires primary credentials first." >&2
    exit 11
fi

# ---- AssumeRole ----
echo "[DIAG] Assuming role: $ROLE_ARN" >&2
STS_OUTPUT=$(aliyun sts AssumeRole \
    --RoleArn "$ROLE_ARN" \
    --RoleSessionName "$SESSION_NAME" \
    --DurationSeconds "$DURATION_SECONDS" \
    2>&1) || {
    echo "[ERROR] TYPE=ASSUME_ROLE_FAILED FIX=Check role ARN, permissions, and network" >&2
    echo "[ERROR] aliyun sts output: $STS_OUTPUT" >&2
    exit 10
}

# ---- Extract and export credentials ----
export ALIBABA_CLOUD_ACCESS_KEY_ID=$(echo "$STS_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeyId'])")
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=$(echo "$STS_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['AccessKeySecret'])")
export ALIBABA_CLOUD_SESSION_TOKEN=$(echo "$STS_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['SecurityToken'])")

# Sanity: verify we got non-empty values
if [[ -z "$ALIBABA_CLOUD_ACCESS_KEY_ID" || -z "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" ]]; then
    echo "[ERROR] TYPE=EMPTY_CREDENTIALS FIX=Check STS AssumeRole response" >&2
    exit 10
fi

echo "[RESULT] Credentials assumed, session: $SESSION_NAME, expires: $(echo "$STS_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Credentials']['Expiration'])")" >&2