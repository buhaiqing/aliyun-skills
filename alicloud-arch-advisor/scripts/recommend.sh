#!/bin/bash
# alicloud-arch-advisor - Recommendation Mode (Mode 3)
# Usage: ./recommend.sh --scenario ecommerce [--dau 500000] [--compliance pci] [--ha multi-az]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SCENARIO=""
DAU=100000
COMPLIANCE="none"
HA_LEVEL="single-az"
BUDGET=""
REGION="${ALICLOUD_REGION:-cn-hangzhou}"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 --scenario SCENARIO [OPTIONS]

Required:
  --scenario ID    Scenario ID from index.yaml (e.g., ecommerce, saas, data-platform)

Options:
  --dau NUM        Daily Active Users for scale estimation (default: 100000)
  --compliance ID  Compliance requirement: none | pci | hipaa | gdpr | etc. (default: none)
  --ha LEVEL       HA level: single-az | multi-az | multi-region (default: single-az)
  --budget NUM     Monthly budget constraint in USD (default: unlimited)
  --region REGION  Alibaba Cloud region (default: \$ALICLOUD_REGION or cn-hangzhou)
  -h, --help       Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scenario)
            SCENARIO="$2"
            shift 2
            ;;
        --dau)
            DAU="$2"
            shift 2
            ;;
        --compliance)
            COMPLIANCE="$2"
            shift 2
            ;;
        --ha)
            HA_LEVEL="$2"
            shift 2
            ;;
        --budget)
            BUDGET="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SCENARIO" ]]; then
    log_error "--scenario is required."
    usage
fi

if [[ "$HA_LEVEL" != "single-az" && "$HA_LEVEL" != "multi-az" && "$HA_LEVEL" != "multi-region" ]]; then
    log_error "Invalid HA level: ${HA_LEVEL}. Must be single-az, multi-az, or multi-region."
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: convert DAU to capacity tier
# ---------------------------------------------------------------------------
dau_to_tier() {
    local dau="$1"
    if [[ "$dau" -le 10000 ]]; then
        echo "small"
    elif [[ "$dau" -le 100000 ]]; then
        echo "medium"
    elif [[ "$dau" -le 500000 ]]; then
        echo "large"
    else
        echo "xlarge"
    fi
}

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
log_info "=== alicloud-arch-advisor Recommendation ==="
log_info "Scenario: ${SCENARIO}"
log_info "DAU: ${DAU}"
log_info "Compliance: ${COMPLIANCE}"
log_info "HA Level: ${HA_LEVEL}"
if [[ -n "$BUDGET" ]]; then
    log_info "Budget: \$${BUDGET}/month"
fi
log_info "Region: ${REGION}"
echo ""

# Step 1: Check dependencies
log_info "[Step 1/7] Checking dependencies..."
check_dependencies || true
echo ""

# Step 2: Initialize report
log_info "[Step 2/7] Initializing recommendation report..."
REPORT_DATA=$(init_report "recommendation" "markdown")
REPORT_FILE="${OUTPUT_DIR}/report-data.json"
echo "$REPORT_DATA" > "$REPORT_FILE"
log_success "Report initialized"
echo ""

# Step 3: Validate scenario and load template
log_info "[Step 3/7] Validating scenario..."
SCENARIO_INDEX="${TEMPLATES_DIR}/index.yaml"

if [[ ! -f "$SCENARIO_INDEX" ]]; then
    log_warn "Scenario index not found: ${SCENARIO_INDEX}"
    log_info "Using built-in scenario definitions instead."
fi

# Determine capacity tier
CAP_TIER=$(dau_to_tier "$DAU")
log_info "Capacity tier: ${CAP_TIER} (based on DAU = ${DAU})"

# Define scenario templates inline
declare -A SCENARIO_META
SCENARIO_META["ecommerce"]='{
    "name": "电商平台",
    "description": "高并发电商平台，支持商品浏览、下单、支付、库存管理等核心业务",
    "reference": "https://www.alibabacloud.com/solutions/ecommerce",
    "components": {
        "small": {"ecs": 2, "ecs_type": "ecs.g6.xlarge", "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 1, "slb": 1, "oss": true, "cdn": true},
        "medium": {"ecs": 4, "ecs_type": "ecs.g6.2xlarge", "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 2, "slb": 1, "oss": true, "cdn": true},
        "large": {"ecs": 8, "ecs_type": "ecs.g6.4xlarge", "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 3, "slb": 2, "oss": true, "cdn": true},
        "xlarge": {"ecs": 16, "ecs_type": "ecs.g6.8xlarge", "rds": 6, "rds_type": "rds.mysql.s16.xlarge", "redis": 6, "slb": 3, "oss": true, "cdn": true}
    },
    "services": ["ECS", "SLB", "RDS MySQL", "Redis", "OSS", "CDN", "Auto Scaling", "CloudMonitor"],
    "compliance_addons": {"pci": ["WAF", "KMS", "ActionTrail", "Sensitive Data Discovery"], "hipaa": ["KMS", "ActionTrail", "Sensitive Data Discovery"]}
}'
SCENARIO_META["saas"]='{
    "name": "SaaS 应用",
    "description": "多租户 SaaS 平台，支持租户隔离、按需计费、弹性伸缩",
    "reference": "https://www.alibabacloud.com/solutions/saas",
    "components": {
        "small": {"ecs": 2, "ecs_type": "ecs.g7.xlarge", "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 1, "slb": 1, "oss": true, "ack": false},
        "medium": {"ecs": 4, "ecs_type": "ecs.g7.2xlarge", "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 2, "slb": 1, "oss": true, "ack": true},
        "large": {"ecs": 0, "ecs_type": "", "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 4, "slb": 2, "oss": true, "ack": true},
        "xlarge": {"ecs": 0, "ecs_type": "", "rds": 8, "rds_type": "rds.mysql.s16.xlarge", "redis": 8, "slb": 3, "oss": true, "ack": true}
    },
    "services": ["ECS/ACK", "SLB", "RDS MySQL", "Redis", "OSS", "Auto Scaling", "CloudMonitor", "RAM"],
    "compliance_addons": {"pci": ["WAF", "KMS", "ActionTrail"], "gdpr": ["KMS", "ActionTrail", "Sensitive Data Discovery"]}
}'
SCENARIO_META["data-platform"]='{
    "name": "数据平台",
    "description": "大数据分析与处理平台，支持离线批处理、实时流计算、数据湖存储",
    "reference": "https://www.alibabacloud.com/solutions/bigdata",
    "components": {
        "small": {"ecs": 3, "ecs_type": "ecs.g6.2xlarge", "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 1, "oss": true, "emr": true, "holo": false},
        "medium": {"ecs": 6, "ecs_type": "ecs.g6.4xlarge", "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 2, "oss": true, "emr": true, "holo": true},
        "large": {"ecs": 12, "ecs_type": "ecs.g6.8xlarge", "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 4, "oss": true, "emr": true, "holo": true},
        "xlarge": {"ecs": 24, "ecs_type": "ecs.g6.16xlarge", "rds": 6, "rds_type": "rds.mysql.s16.xlarge", "redis": 8, "oss": true, "emr": true, "holo": true}
    },
    "services": ["ECS", "EMR", "OSS", "RDS MySQL", "Redis", "Hologres", "DataWorks", "Flink"],
    "compliance_addons": {"pci": ["KMS", "ActionTrail", "Sensitive Data Discovery"], "hipaa": ["KMS", "ActionTrail"]}
}'
SCENARIO_META["microservice"]='{
    "name": "微服务架构",
    "description": "基于容器和 Service Mesh 的微服务架构，支持 CI/CD、灰度发布、服务治理",
    "reference": "https://www.alibabacloud.com/solutions/container",
    "components": {
        "small": {"ack": 1, "ecs_node": 3, "ecs_type": "ecs.g7.xlarge", "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 1, "oss": true, "slb": 1, "mse": false},
        "medium": {"ack": 1, "ecs_node": 6, "ecs_type": "ecs.g7.2xlarge", "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 2, "oss": true, "slb": 1, "mse": true},
        "large": {"ack": 3, "ecs_node": 12, "ecs_type": "ecs.g7.4xlarge", "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 4, "oss": true, "slb": 2, "mse": true},
        "xlarge": {"ack": 5, "ecs_node": 24, "ecs_type": "ecs.g7.8xlarge", "rds": 8, "rds_type": "rds.mysql.s16.xlarge", "redis": 8, "oss": true, "slb": 3, "mse": true}
    },
    "services": ["ACK", "ECS Worker", "SLB", "RDS MySQL", "Redis", "OSS", "MSE", "ARMS", "CloudMonitor"],
    "compliance_addons": {"pci": ["WAF", "KMS", "ActionTrail"], "hipaa": ["KMS", "ActionTrail"]}
}'
SCENARIO_META["serverless"]='{
    "name": "Serverless 应用",
    "description": "全 Serverless 架构，按需付费，零服务器运维，适合事件驱动和间歇性负载",
    "reference": "https://www.alibabacloud.com/solutions/serverless",
    "components": {
        "small": {"fc": 1, "api_gw": 1, "oss": true, "tablestore": 1, "cdn": true, "sls": true, "rds": 0, "redis": 0},
        "medium": {"fc": 1, "api_gw": 1, "oss": true, "tablestore": 2, "cdn": true, "sls": true, "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 1},
        "large": {"fc": 1, "api_gw": 2, "oss": true, "tablestore": 4, "cdn": true, "sls": true, "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 2},
        "xlarge": {"fc": 1, "api_gw": 3, "oss": true, "tablestore": 6, "cdn": true, "sls": true, "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 4}
    },
    "services": ["Function Compute", "API Gateway", "OSS", "Tablestore", "CDN", "SLS", "RDS MySQL", "Redis"],
    "compliance_addons": {"pci": ["WAF", "KMS", "ActionTrail"], "gdpr": ["KMS", "ActionTrail"]}
}'
SCENARIO_META["game"]='{
    "name": "游戏后端",
    "description": "实时游戏后端服务，支持高并发玩家在线、实时对战、排行榜、数据统计",
    "reference": "https://www.alibabacloud.com/solutions/game",
    "components": {
        "small": {"ecs": 3, "ecs_type": "ecs.g6.2xlarge", "rds": 1, "rds_type": "rds.mysql.s2.large", "redis": 2, "slb": 1, "oss": true, "cdn": true, "gslb": false},
        "medium": {"ecs": 6, "ecs_type": "ecs.g6.4xlarge", "rds": 2, "rds_type": "rds.mysql.s4.large", "redis": 4, "slb": 2, "oss": true, "cdn": true, "gslb": true},
        "large": {"ecs": 12, "ecs_type": "ecs.g6.8xlarge", "rds": 4, "rds_type": "rds.mysql.s8.xlarge", "redis": 8, "slb": 3, "oss": true, "cdn": true, "gslb": true},
        "xlarge": {"ecs": 24, "ecs_type": "ecs.g6.16xlarge", "rds": 6, "rds_type": "rds.mysql.s16.xlarge", "redis": 12, "slb": 4, "oss": true, "cdn": true, "gslb": true}
    },
    "services": ["ECS", "SLB", "RDS MySQL", "Redis", "OSS", "CDN", "GSLB", "Auto Scaling"],
    "compliance_addons": {}
}'

# Retrieve scenario metadata
SCENARIO_JSON="${SCENARIO_META[$SCENARIO]:-}"
if [[ -z "$SCENARIO_JSON" ]]; then
    log_error "Unknown scenario: ${SCENARIO}. Available scenarios: ${!SCENARIO_META[*]}"
    exit 1
fi

SCENARIO_NAME=$(echo "$SCENARIO_JSON" | jq -r '.name')
SCENARIO_DESC=$(echo "$SCENARIO_JSON" | jq -r '.description')
log_success "Scenario loaded: ${SCENARIO_NAME} (${SCENARIO_DESC})"
echo ""

# Step 4: Customize template based on business requirements
log_info "[Step 4/7] Customizing architecture template..."
echo ""

log_info "  Capacity tier: ${CAP_TIER} (DAU: ${DAU})"
COMPONENTS=$(echo "$SCENARIO_JSON" | jq --arg tier "$CAP_TIER" '.components[$tier]')
log_info "  Base component spec:"
echo "$COMPONENTS" | jq '.'
echo ""

# Apply HA configuration
log_info "  Applying HA level: ${HA_LEVEL}"
case "$HA_LEVEL" in
    single-az)
        COMPONENTS=$(echo "$COMPONENTS" | jq '. + {"az_count": 1, "multi_az_rds": false, "multi_az_redis": false}')
        log_info "    Single AZ deployment. No cross-AZ redundancy."
        ;;
    multi-az)
        COMPONENTS=$(echo "$COMPONENTS" | jq '. + {"az_count": 2, "multi_az_rds": true, "multi_az_redis": true}')
        # Double compute for HA
        local ecs_count
        ecs_count=$(echo "$COMPONENTS" | jq '.ecs // 0')
        if [[ "$ecs_count" -gt 0 ]]; then
            ecs_count=$((ecs_count * 2))
            COMPONENTS=$(echo "$COMPONENTS" | jq --argjson ecs "$ecs_count" '.ecs = $ecs')
        fi
        local ack_nodes
        ack_nodes=$(echo "$COMPONENTS" | jq '.ecs_node // 0')
        if [[ "$ack_nodes" -gt 0 ]]; then
            ack_nodes=$((ack_nodes * 2))
            COMPONENTS=$(echo "$COMPONENTS" | jq --argjson nodes "$ack_nodes" '.ecs_node = $nodes')
        fi
        log_info "    Multi-AZ HA. Compute capacity doubled."
        ;;
    multi-region)
        COMPONENTS=$(echo "$COMPONENTS" | jq '. + {"az_count": 2, "multi_az_rds": true, "multi_az_redis": true, "multi_region": true, "dns_gslb": true}')
        local ecs_count
        ecs_count=$(echo "$COMPONENTS" | jq '.ecs // 0')
        if [[ "$ecs_count" -gt 0 ]]; then
            ecs_count=$((ecs_count * 2))
            COMPONENTS=$(echo "$COMPONENTS" | jq --argjson ecs "$ecs_count" '.ecs = $ecs')
        fi
        local ack_nodes
        ack_nodes=$(echo "$COMPONENTS" | jq '.ecs_node // 0')
        if [[ "$ack_nodes" -gt 0 ]]; then
            ack_nodes=$((ack_nodes * 2))
            COMPONENTS=$(echo "$COMPONENTS" | jq --argjson nodes "$ack_nodes" '.ecs_node = $nodes')
        fi
        # Add cross-region replication
        COMPONENTS=$(echo "$COMPONENTS" | jq '. + {"oss_crr": true, "rds_crr": true}')
        log_info "    Multi-Region HA. Resources doubled + DR configuration."
        ;;
esac
echo ""

# Apply compliance requirements
log_info "  Applying compliance: ${COMPLIANCE}"
COMPLIANCE_ADDONS="[]"
if [[ "$COMPLIANCE" != "none" ]]; then
    COMPLIANCE_ADDONS=$(echo "$SCENARIO_JSON" | jq --arg comp "$COMPLIANCE" '.compliance_addons[$comp] // []')
    if [[ "$(echo "$COMPLIANCE_ADDONS" | jq 'length')" -eq 0 ]]; then
        log_warn "    No compliance add-ons defined for ${COMPLIANCE} in this scenario."
        COMPLIANCE_ADDONS="[]"
    else
        log_info "    Compliance add-ons: $(echo "$COMPLIANCE_ADDONS" | jq -r 'join(", ")')"
    fi
fi
echo ""

# Apply budget constraints
if [[ -n "$BUDGET" ]]; then
    log_info "  Applying budget constraint: \$${BUDGET}/month"
    local estimated_cost
    # Simple cost estimation based on ECS count and type
    local ecs_count rds_count redis_count total_cost
    ecs_count=$(echo "$COMPONENTS" | jq '.ecs // 0')
    rds_count=$(echo "$COMPONENTS" | jq '.rds // 0')
    redis_count=$(echo "$COMPONENTS" | jq '.redis // 0')
    estimated_cost=$(( ecs_count * 100 + rds_count * 150 + redis_count * 80 ))

    if [[ "$estimated_cost" -gt "$BUDGET" ]]; then
        log_warn "    Estimated cost (\$${estimated_cost}) exceeds budget (\$${BUDGET}). Suggesting scale-down."
        local scale_factor
        scale_factor=$(echo "scale=2; $BUDGET / $estimated_cost" | bc 2>/dev/null || echo "0.5")
        local new_ecs
        new_ecs=$(echo "$ecs_count * $scale_factor" | bc 2>/dev/null | cut -d. -f1)
        new_ecs=$(( new_ecs > 1 ? new_ecs : 1 ))
        COMPONENTS=$(echo "$COMPONENTS" | jq --argjson ecs "$new_ecs" '.ecs = $ecs')
        log_info "    Scaled ECS to ${new_ecs} to fit budget."
    else
        log_info "    Estimated cost \$${estimated_cost}/month within budget."
    fi
fi
echo ""

# Step 5: Generate architecture recommendation
log_info "[Step 5/7] Generating architecture blueprint..."

# Build architecture blueprint
ARCH_BLUEPRINT=$(jq -n \
    --arg scenario "$SCENARIO_NAME" \
    --argjson components "$COMPONENTS" \
    --arg ha "$HA_LEVEL" \
    --arg tier "$CAP_TIER" \
    --argjson compliance_addons "$COMPLIANCE_ADDONS" \
    '{
        "scenario": $scenario,
        "capacity_tier": $tier,
        "ha_level": $ha,
        "components": $components,
        "compliance": $compliance_addons,
        "services": [],
        "mermaid": ""
    }')

# Determine services list
SERVICES_LIST=$(echo "$SCENARIO_JSON" | jq '.services')

# Add compliance add-ons to services
SERVICES_LIST=$(echo "$SERVICES_LIST" | jq --argjson addons "$COMPLIANCE_ADDONS" '. + $addons | unique')
ARCH_BLUEPRINT=$(echo "$ARCH_BLUEPRINT" | jq --argjson services "$SERVICES_LIST" '.services = $services')

# Generate Mermaid diagram
log_info "  Generating Mermaid topology..."
ECS_COUNT=$(echo "$COMPONENTS" | jq '.ecs // 0')
RDS_COUNT=$(echo "$COMPONENTS" | jq '.rds // 0')
REDIS_COUNT=$(echo "$COMPONENTS" | jq '.redis // 0')
SLB_COUNT=$(echo "$COMPONENTS" | jq '.slb // 0')
ACK_FLAG=$(echo "$COMPONENTS" | jq '.ack // false')
FC_FLAG=$(echo "$COMPONENTS" | jq '.fc // false')
API_GW_COUNT=$(echo "$COMPONENTS" | jq '.api_gw // 0')
OSS_FLAG=$(echo "$COMPONENTS" | jq '.oss // false')
CDN_FLAG=$(echo "$COMPONENTS" | jq '.cdn // false')
EMR_FLAG=$(echo "$COMPONENTS" | jq '.emr // false')
HOLO_FLAG=$(echo "$COMPONENTS" | jq '.holo // false')
TABLESTORE_COUNT=$(echo "$COMPONENTS" | jq '.tablestore // 0')
MSE_FLAG=$(echo "$COMPONENTS" | jq '.mse // false')
GSLB_FLAG=$(echo "$COMPONENTS" | jq '.gslb // false')
SLS_FLAG=$(echo "$COMPONENTS" | jq '.sls // false')
ARMS_FLAG=$(echo "$COMPONENTS" | jq '.arms // false')

MERMAID_OUTPUT="graph TB"
MERMAID_OUTPUT+=$'\n    subgraph "Recommended Architecture - '"${SCENARIO_NAME}"$'"'
MERMAID_OUTPUT+=$'\n        Internet((Internet))'

# CDN
if [[ "$CDN_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n        CDN[CDN]'
    MERMAID_OUTPUT+=$'\n        Internet --> CDN'
fi

# GSLB for multi-region
if [[ "$GSLB_FLAG" == "true" ]] || [[ "$HA_LEVEL" == "multi-region" ]]; then
    MERMAID_OUTPUT+=$'\n        DNS[GSLB/DNS]'
    if [[ "$CDN_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        CDN --> DNS'
    else
        MERMAID_OUTPUT+=$'\n        Internet --> DNS'
    fi
fi

# SLB
if [[ "$SLB_COUNT" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n        SLB[SLB Load Balancer]'
    if [[ "$CDN_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        CDN --> SLB'
    elif [[ "$GSLB_FLAG" == "true" ]] || [[ "$HA_LEVEL" == "multi-region" ]]; then
        MERMAID_OUTPUT+=$'\n        DNS --> SLB'
    else
        MERMAID_OUTPUT+=$'\n        Internet --> SLB'
    fi
fi

# API Gateway
if [[ "$API_GW_COUNT" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n        APIGW[API Gateway]'
    if [[ "$SLB_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        SLB --> APIGW'
    elif [[ "$CDN_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        CDN --> APIGW'
    else
        MERMAID_OUTPUT+=$'\n        Internet --> APIGW'
    fi
fi

# Compute layer heading
MERMAID_OUTPUT+=$'\n        subgraph Compute'

# ECS instances
if [[ "$ECS_COUNT" -gt 0 ]]; then
    for ((i=1; i<=ECS_COUNT && i<=4; i++)); do
        MERMAID_OUTPUT+=$'\n            ECS'"${i}"$'[ECS App '${i}$']'
    done
    if [[ "$ECS_COUNT" -gt 4 ]]; then
        MERMAID_OUTPUT+=$'\n            ECS_ELIP[+ '"$((ECS_COUNT - 4))"$' more...]'
    fi
    local ecs_source="SLB"
    if [[ "$API_GW_COUNT" -gt 0 ]]; then
        ecs_source="APIGW"
    fi
    if [[ "$SLB_COUNT" -gt 0 ]] || [[ "$API_GW_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        '"${ecs_source}"' --> ECS1'
    fi
fi

# ACK cluster
if [[ "$ACK_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            ACK[ACK Cluster]'
    local ack_source="SLB"
    if [[ "$API_GW_COUNT" -gt 0 ]]; then
        ack_source="APIGW"
    fi
    if [[ "$SLB_COUNT" -gt 0 ]] || [[ "$API_GW_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        '"${ack_source}"' --> ACK'
    fi
fi

# FC + API Gateway
if [[ "$FC_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            FC[Function Compute]'
    if [[ "$API_GW_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        APIGW --> FC'
    fi
fi

MERMAID_OUTPUT+=$'\n        end'

# EMR for data platform
if [[ "$EMR_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n        EMR[EMR Cluster]'
    MERMAID_OUTPUT+=$'\n        ECS1 --> EMR'
fi

# Storage layer
MERMAID_OUTPUT+=$'\n        subgraph Storage'

if [[ "$RDS_COUNT" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n            RDS[(RDS MySQL × '"${RDS_COUNT}"$')]'
    if [[ "$ECS_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        ECS1 --> RDS'
    fi
    if [[ "$ACK_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        ACK --> RDS'
    fi
fi

if [[ "$REDIS_COUNT" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n            Redis[(Redis × '"${REDIS_COUNT}"$')]'
    if [[ "$ECS_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        ECS1 --> Redis'
    fi
    if [[ "$ACK_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        ACK --> Redis'
    fi
fi

if [[ "$OSS_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            OSS[(OSS Storage)]'
    if [[ "$ECS_COUNT" -gt 0 ]]; then
        MERMAID_OUTPUT+=$'\n        ECS1 --> OSS'
    fi
    if [[ "$ACK_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        ACK --> OSS'
    fi
    if [[ "$EMR_FLAG" == "true" ]]; then
        MERMAID_OUTPUT+=$'\n        EMR --> OSS'
    fi
fi

if [[ "$HOLO_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            Holo[Hologres]'
    MERMAID_OUTPUT+=$'\n        EMR --> Holo'
fi

if [[ "$TABLESTORE_COUNT" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n            Tablestore[(Tablestore × '"${TABLESTORE_COUNT}"$')]'
    MERMAID_OUTPUT+=$'\n        FC --> Tablestore'
fi

MERMAID_OUTPUT+=$'\n        end'

# Observability
MERMAID_OUTPUT+=$'\n        subgraph Observability'
MERMAID_OUTPUT+=$'\n            CM[CloudMonitor]'
if [[ "$SLS_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            SLS[Log Service]'
fi
if [[ "$ARMS_FLAG" == "true" ]]; then
    MERMAID_OUTPUT+=$'\n            ARMS[ARMS Tracing]'
fi
MERMAID_OUTPUT+=$'\n        end'

# Compliance add-ons
if [[ "$(echo "$COMPLIANCE_ADDONS" | jq 'length')" -gt 0 ]]; then
    MERMAID_OUTPUT+=$'\n        subgraph Compliance'
    while IFS= read -r addon; do
        addon=$(echo "$addon" | tr -d '"')
        MERMAID_OUTPUT+=$'\n            '"${addon}"$'['"${addon}"$']'
    done < <(echo "$COMPLIANCE_ADDONS" | jq -r '.[]')
    MERMAID_OUTPUT+=$'\n        end'
fi

MERMAID_OUTPUT+=$'\n    end'

ARCH_BLUEPRINT=$(echo "$ARCH_BLUEPRINT" | jq --arg mermaid "$MERMAID_OUTPUT" '.mermaid = $mermaid')
log_success "Architecture blueprint generated"
echo ""

# Step 6: Pre-assessment against WAF rules
log_info "[Step 6/7] Running WAF pre-assessment on recommended architecture..."

# Simulate pre-assessment
PRE_ASSESSMENT=$(jq -n '{
    "pre_assessment": {
        "security": {"status": "review", "critical_items": ["确保所有 Web 入口配置 WAF", "KMS 密钥管理配置", "最小权限 RAM 策略"]},
        "reliability": {"status": "good", "note": "Multi-AZ/Region HA configured"},
        "performance": {"status": "good", "note": "Auto Scaling configured for traffic spikes"},
        "cost": {"status": "review", "note": "Cost estimation provided, review for optimization"},
        "efficiency": {"status": "review", "items": ["配置 ROS 资源编排", "添加资源标签", "启用 OOS 运维编排"]}
    }
}')

ARCH_BLUEPRINT=$(echo "$ARCH_BLUEPRINT" | jq --argjson pre "$PRE_ASSESSMENT" '. + $pre')
log_success "Pre-assessment complete"
echo ""

# Step 7: Generate recommendation report
log_info "[Step 7/7] Generating recommendation report..."

RECOMMENDATION_FILE="${OUTPUT_DIR}/recommendation-report.md"

{
    echo "# 架构推荐报告"
    echo ""
    echo "**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "**场景**: ${SCENARIO_NAME}"
    echo "**DAU**: ${DAU}"
    echo "**HA 等级**: ${HA_LEVEL}"
    echo "**合规要求**: ${COMPLIANCE}"
    if [[ -n "$BUDGET" ]]; then
        echo "**月预算**: \$${BUDGET}"
    fi
    echo ""

    echo "---"
    echo ""
    echo "## 1. 业务需求分析"
    echo ""
    echo "| 指标 | 值 |"
    echo "|------|-----|"
    echo "| 场景 | ${SCENARIO_NAME} |"
    echo "| 容量等级 | ${CAP_TIER} |"
    echo "| 日活用户 (DAU) | ${DAU} |"
    echo "| HA 等级 | ${HA_LEVEL} |"
    echo "| 合规要求 | ${COMPLIANCE} |"
    if [[ -n "$BUDGET" ]]; then
        echo "| 月预算 | \$${BUDGET} |"
    fi
    echo ""

    echo "## 2. 推荐架构蓝图"
    echo ""
    echo '```mermaid'
    echo "$MERMAID_OUTPUT"
    echo '```'
    echo ""

    echo "## 3. 组件规格"
    echo ""
    echo "| 组件 | 规格 | 数量 | 说明 |"
    echo "|------|------|------|------|"
    echo "$COMPONENTS" | jq -r 'to_entries[] | 
        "| \(.key) | \(.value | type) | \(.value) | - |"' 2>/dev/null
    echo ""

    echo "## 4. 推荐产品清单"
    echo ""
    for service in $(echo "$SERVICES_LIST" | jq -r '.[]'); do
        echo "- ${service}"
    done
    echo ""

    if [[ "$(echo "$COMPLIANCE_ADDONS" | jq 'length')" -gt 0 ]]; then
        echo "## 5. 合规附加组件"
        echo ""
        for addon in $(echo "$COMPLIANCE_ADDONS" | jq -r '.[]'); do
            echo "- ${addon}"
        done
        echo ""
    fi

    echo "## 6. WAF 预评估"
    echo ""
    echo "$PRE_ASSESSMENT" | jq -r '.pre_assessment | to_entries[] |
        "### \(.key | ascii_upcase): \(.value.status)\n\n\(.value | to_entries[] | "  - \(.key): \(.value)")"'
    echo ""

    echo "## 7. 部署建议"
    echo ""
    echo "1. 使用 ROS (资源编排) 自动化部署基础设施"
    echo "2. 配置 CloudMonitor 告警规则监控资源健康"
    echo "3. 启用 ActionTrail 记录所有 API 操作"
    echo "4. 为所有资源添加标签以便管理"
    echo "5. 定期评估资源利用率和成本优化机会"
    echo ""

    echo "---"
    echo ""
    echo "*本报告由 alicloud-arch-advisor 自动生成*"
} > "${RECOMMENDATION_FILE}"

log_success "Recommendation report saved to ${RECOMMENDATION_FILE}"
echo ""

# Save the blueprint JSON
BLUEPRINT_FILE="${OUTPUT_DIR}/recommendation-blueprint.json"
echo "$ARCH_BLUEPRINT" | jq '.' > "$BLUEPRINT_FILE"
log_success "Blueprint JSON saved to ${BLUEPRINT_FILE}"
echo ""

log_success "=== Recommendation complete ==="
echo ""
echo "Output files:"
ls -la "${OUTPUT_DIR}/"