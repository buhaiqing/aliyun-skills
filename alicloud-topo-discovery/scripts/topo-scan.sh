#!/bin/bash
set -euo pipefail

# ---- Argument parsing ----
REPORT_MODE="brief"
REGION_ID="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
OUTPUT_DIR="${TOPO_OUTPUT_DIR:-.}"
ASSUME_ROLE=""

TOPO_TMP_EXTERNAL=""  # set to 1 when --tmp-dir is explicitly provided
while [[ $# -gt 0 ]]; do
    case "$1" in
        --assume-role) ASSUME_ROLE="$2"; shift 2 ;;
        --mode|-m) REPORT_MODE="$2"; shift 2 ;;
        --region|-r) REGION_ID="$2"; shift 2 ;;
        --output-dir|-o) OUTPUT_DIR="$2"; shift 2 ;;
        --format|-f) FORMAT="$2"; shift 2 ;;
        --health-json) HEALTH_JSON="$2"; shift 2 ;;
        --tmp-dir) TMP_DATA_DIR="$2"; TOPO_TMP_EXTERNAL=1; shift 2 ;;
        brief|detailed) REPORT_MODE="$1"; shift ;;
        *) echo "[ERROR] Unknown option: $1"; exit 1 ;;
    esac
done

# Defaults
FORMAT="${FORMAT:-both}"

# ---- Concurrent safety: unique temp dir per run ----
# If not explicitly provided, generate one
TMP_DATA_DIR="${TMP_DATA_DIR:-/tmp/topo_scan_$$_$(date +%s)}"
mkdir -p "$TMP_DATA_DIR"
export TOPO_TMP_DIR="$TMP_DATA_DIR"

# ---- STS AssumeRole (optional) ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "$ASSUME_ROLE" ]]; then
    echo "[DIAG] Using cross-account role: $ASSUME_ROLE"
    source "$SCRIPT_DIR/sts-helper.sh" --role-arn "$ASSUME_ROLE"
fi

SCAN_TIMESTAMP=$(date +%FT%T%z)

echo "[DIAG] Starting network topology scan... Mode: $REPORT_MODE | Region: $REGION_ID | Tmp: $TMP_DATA_DIR"

# Safety Gate: Read-Only Verification (optimized: dedup by API name)
FORBIDDEN="Create|Delete|Modify|Update|Associate|Unassociate|Authorize|Revoke|Stop|Start|Reboot|Run|Invoke|Attach|Detach|Release"
_VERIFIED=""  # space-separated list of already-checked APIs

verify_cmd() {
    local api_op="${1##* }"
    api_op="${api_op%% *}"
    # dedup: skip if already verified
    case " $_VERIFIED " in
        *" $api_op "*) return 0 ;;
    esac
    [[ "$api_op" =~ ^($FORBIDDEN) ]] && { echo "❌ FORBIDDEN: Write operation detected - $api_op | HALT"; exit 1; }
    _VERIFIED="$_VERIFIED $api_op"
    echo "   ✓ $api_op"
}

# ---- Phase 1: Parallel data collection ----
verify_cmd "aliyun vpc DescribeVpcs"
aliyun vpc DescribeVpcs --RegionId $REGION_ID > "$TMP_DATA_DIR/vpcs.json" &
PID_VPC=$!
verify_cmd "aliyun slb DescribeLoadBalancers"
aliyun slb DescribeLoadBalancers --RegionId $REGION_ID --PageSize 100 > "$TMP_DATA_DIR/slbs.json" &
verify_cmd "aliyun vpc DescribeNatGateways"
aliyun vpc DescribeNatGateways --RegionId $REGION_ID --PageSize 50 > "$TMP_DATA_DIR/nats.json" &
verify_cmd "aliyun vpc DescribeEipAddresses"
aliyun vpc DescribeEipAddresses --RegionId $REGION_ID --PageSize 50 > "$TMP_DATA_DIR/eips.json" &
verify_cmd "aliyun ecs DescribeSecurityGroups"
aliyun ecs DescribeSecurityGroups --RegionId $REGION_ID --PageSize 100 > "$TMP_DATA_DIR/sgs.json" &

echo -e "\n📡 Waiting for core network resources..."
wait $PID_VPC

# Parse all VPCs for multi-VPC support
VPC_IDS=$(python3 -c "import json;d=json.load(open('$TMP_DATA_DIR/vpcs.json'));vpcs=d.get('Vpcs',{}).get('Vpc',[]);print(' '.join(v['VpcId'] for v in vpcs))" 2>/dev/null || echo "")
FIRST_VPC_ID=$(echo "$VPC_IDS" | awk '{print $1}')

if [ -n "$FIRST_VPC_ID" ]; then
  # Collect VSwitches for the first VPC
  verify_cmd "aliyun vpc DescribeVSwitches"
  aliyun vpc DescribeVSwitches --RegionId $REGION_ID --VpcId $FIRST_VPC_ID --PageSize 50 > "$TMP_DATA_DIR/vswitches.json"
  
  # Save multi-VPC context for renderer
  echo "$VPC_IDS" > "$TMP_DATA_DIR/multi_vpc_ids.txt"

  if [ "$REPORT_MODE" = "full" ]; then
      echo -e "\n📡 Phase 2: Detailed Resources..."
      verify_cmd "aliyun ecs DescribeInstances"
      aliyun ecs DescribeInstances --RegionId $REGION_ID --PageSize 100 > "$TMP_DATA_DIR/ecs.json" &
      verify_cmd "aliyun cs DescribeClustersV1"
      aliyun cs DescribeClustersV1 --page_size 50 > "$TMP_DATA_DIR/ack.json" &
      verify_cmd "aliyun rds DescribeDBInstances"
      aliyun rds DescribeDBInstances --RegionId $REGION_ID --PageSize 100 > "$TMP_DATA_DIR/rds.json" &
      echo -e "\n⏳ Waiting for detailed resources..."
  fi
else
  # No VPC found — create empty files for safety
  echo "[]" > "$TMP_DATA_DIR/vswitches.json"
  echo "" > "$TMP_DATA_DIR/multi_vpc_ids.txt"
fi

# ---- Phase 2: Report Generation ----
echo -e "\n📝 Phase 3: Generating Report..."
cd "$SCRIPT_DIR"
FORMAT_ARGS="--format $FORMAT"
HEALTH_ARGS=""
[ -n "${HEALTH_JSON:-}" ] && [ -f "$HEALTH_JSON" ] && HEALTH_ARGS="--health-json $HEALTH_JSON"

# Pass temp dir to renderer via environment variable
TOPO_TMP_DIR="$TMP_DATA_DIR" python3 ./topo-render.py \
  "$OUTPUT_DIR" "$REPORT_MODE" "$SCAN_TIMESTAMP" "$REGION_ID" \
  $FORMAT_ARGS $HEALTH_ARGS

# Cleanup: only if we created the tmp dir (no explicit --tmp-dir)
# When caller passes --tmp-dir, they manage the lifecycle
if [ -z "${TOPO_TMP_EXTERNAL:-}" ]; then
    rm -rf "$TMP_DATA_DIR" 2>/dev/null || true
fi