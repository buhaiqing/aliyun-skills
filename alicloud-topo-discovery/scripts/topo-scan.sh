#!/bin/bash
set -euo pipefail

# ---- Argument parsing ----
REPORT_MODE="brief"
REGION_ID="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
OUTPUT_DIR="${TOPO_OUTPUT_DIR:-.}"
ASSUME_ROLE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --assume-role) ASSUME_ROLE="$2"; shift 2 ;;
        --mode|-m) REPORT_MODE="$2"; shift 2 ;;
        --region|-r) REGION_ID="$2"; shift 2 ;;
        --output-dir|-o) OUTPUT_DIR="$2"; shift 2 ;;
        --format|-f) FORMAT="$2"; shift 2 ;;
        --health-json) HEALTH_JSON="$2"; shift 2 ;;
        brief|detailed) REPORT_MODE="$1"; shift ;;
        *) echo "[ERROR] Unknown option: $1"; exit 1 ;;
    esac
done

# Defaults
FORMAT="${FORMAT:-both}"

# ---- STS AssumeRole (optional) ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "$ASSUME_ROLE" ]]; then
    echo "[DIAG] Using cross-account role: $ASSUME_ROLE"
    source "$SCRIPT_DIR/sts-helper.sh" --role-arn "$ASSUME_ROLE"
fi

SCAN_TIMESTAMP=$(date +%FT%T%z)

echo "[DIAG] Starting network topology scan... Mode: $REPORT_MODE | Region: $REGION_ID"

# Safety Gate: Read-Only Verification
FORBIDDEN="Create|Delete|Modify|Update|Associate|Unassociate|Authorize|Revoke|Stop|Start|Reboot|Run|Invoke|Attach|Detach|Release"

verify_cmd() {
    local api_op=$(echo "$1" | grep -oE 'Describe[A-Za-z]+|List[A-Za-z]+|Get[A-Za-z]+' | head -1)
    if echo "$api_op" | grep -qE "^($FORBIDDEN)"; then
        echo "❌ FORBIDDEN: Write operation detected - $api_op | HALT"
        exit 1
    fi
    echo "   ✓ $api_op"
}

# Core Network Resources (Parallel)
verify_cmd "aliyun vpc DescribeVpcs"; aliyun vpc DescribeVpcs --RegionId $REGION_ID > /tmp/topo_vpcs.json &
PID_VPC=$!
verify_cmd "aliyun slb DescribeLoadBalancers"; aliyun slb DescribeLoadBalancers --RegionId $REGION_ID --PageSize 100 > /tmp/topo_slbs.json &
verify_cmd "aliyun vpc DescribeNatGateways"; aliyun vpc DescribeNatGateways --RegionId $REGION_ID --PageSize 50 > /tmp/topo_nats.json &
verify_cmd "aliyun vpc DescribeEipAddresses"; aliyun vpc DescribeEipAddresses --RegionId $REGION_ID --PageSize 50 > /tmp/topo_eips.json &
verify_cmd "aliyun ecs DescribeSecurityGroups"; aliyun ecs DescribeSecurityGroups --RegionId $REGION_ID --PageSize 100 > /tmp/topo_sgs.json &

echo -e "\n📡 Waiting for core network resources..."
wait $PID_VPC

# Parse all VPCs (multi-VPC support)
VPC_IDS=$(python3 -c "import json;d=json.load(open('/tmp/topo_vpcs.json'));vpcs=d.get('Vpcs',{}).get('Vpc',[]);print(' '.join(v['VpcId'] for v in vpcs))" 2>/dev/null || echo "")
FIRST_VPC_ID=$(echo "$VPC_IDS" | awk '{print $1}')

if [ -n "$FIRST_VPC_ID" ]; then
  # Collect VSwitches for the first VPC
  verify_cmd "aliyun vpc DescribeVSwitches"
  aliyun vpc DescribeVSwitches --RegionId $REGION_ID --VpcId $FIRST_VPC_ID --PageSize 50 > /tmp/topo_vswitches.json
  
  # Save multi-VPC context for renderer
  echo "$VPC_IDS" > /tmp/topo_multi_vpc_ids.txt
    verify_cmd "aliyun vpc DescribeVSwitches"
    aliyun vpc DescribeVSwitches --RegionId $REGION_ID --VpcId $VPC_ID --PageSize 50 > /tmp/topo_vswitches.json

    if [ "$REPORT_MODE" = "full" ]; then
        echo -e "\n📡 Phase 2: Detailed Resources..."
        verify_cmd "aliyun ecs DescribeInstances"; aliyun ecs DescribeInstances --RegionId $REGION_ID --PageSize 100 > /tmp/topo_ecs.json &
        verify_cmd "aliyun cs DescribeClustersV1"; aliyun cs DescribeClustersV1 --page_size 50 > /tmp/topo_ack.json &
        verify_cmd "aliyun rds DescribeDBInstances"; aliyun rds DescribeDBInstances --RegionId $REGION_ID --PageSize 100 > /tmp/topo_rds.json &
        echo -e "\n⏳ Waiting for detailed resources..."
    fi
fi

# Report Generation
echo -e "\n📝 Phase 3: Generating Report..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
FORMAT_ARGS="--format $FORMAT"
HEALTH_ARGS=""
[ -n "${HEALTH_JSON:-}" ] && [ -f "$HEALTH_JSON" ] && HEALTH_ARGS="--health-json $HEALTH_JSON"

python3 ./topo-render.py "$OUTPUT_DIR" "$REPORT_MODE" "$SCAN_TIMESTAMP" "$REGION_ID" $FORMAT_ARGS $HEALTH_ARGS
