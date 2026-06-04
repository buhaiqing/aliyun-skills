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
        brief|detailed) REPORT_MODE="$1"; shift ;;
        *) echo "[ERROR] Unknown option: $1"; exit 1 ;;
    esac
done

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
verify_cmd "aliyun slb DescribeLoadBalancers"; aliyun slb DescribeLoadBalancers --RegionId $REGION_ID --PageSize 100 > /tmp/topo_slbs.json &
verify_cmd "aliyun vpc DescribeNatGateways"; aliyun vpc DescribeNatGateways --RegionId $REGION_ID --PageSize 50 > /tmp/topo_nats.json &
verify_cmd "aliyun vpc DescribeEipAddresses"; aliyun vpc DescribeEipAddresses --RegionId $REGION_ID --PageSize 50 > /tmp/topo_eips.json &
verify_cmd "aliyun ecs DescribeSecurityGroups"; aliyun ecs DescribeSecurityGroups --RegionId $REGION_ID --PageSize 100 > /tmp/topo_sgs.json &

echo -e "\n📡 Waiting for core network resources..."

# VSwitch & Detailed Resources
VPC_ID=$(python3 -c "import json;d=json.load(open('/tmp/topo_vpcs.json'));print(d.get('Vpcs',{}).get('Vpc',[{}])[0].get('VpcId',''))")

if [ -n "$VPC_ID" ]; then
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
python3 ./topo-render.py "$OUTPUT_DIR" "$REPORT_MODE" "$SCAN_TIMESTAMP" "$REGION_ID"
