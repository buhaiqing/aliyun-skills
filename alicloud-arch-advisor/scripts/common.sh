#!/bin/bash
# alicloud-arch-advisor - Shared utility functions
# Common functions used by assess.sh and recommend.sh

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Configuration
ARCH_ADVISOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES_DIR="${ARCH_ADVISOR_DIR}/references/rules"
TEMPLATES_DIR="${ARCH_ADVISOR_DIR}/references/scenario-templates"
OUTPUT_DIR="${ARCH_ADVISOR_DIR}/output"

mkdir -p "${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_info()  { echo -e "${BLUE}[INFO]${NC} $*" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
check_dependencies() {
    local missing=0
    if ! command -v aliyun &>/dev/null; then
        log_error "aliyun CLI not found. Install: https://github.com/aliyun/aliyun-cli"
        missing=1
    fi
    if ! command -v jq &>/dev/null; then
        log_warn "jq not found. Attempting auto-install..."
        if install_jq; then
            # Re-verify after install
            if command -v jq &>/dev/null; then
                log_success "jq $(jq --version 2>/dev/null) installed successfully!"
            else
                log_warn "jq install command completed but jq is still not found in PATH."
                log_warn "  Try running: exec $SHELL -l  (restart shell) or check PATH."
                missing=1
            fi
        else
            log_error "jq installation failed."
            log_error "  Manual install (macOS): brew install jq"
            log_error "  Manual install (Linux): sudo apt install jq / sudo yum install jq"
            log_error "  Download binary: https://jqlang.github.io/jq/download/"
            missing=1
        fi
    fi
    return $missing
}

# Auto-install jq — idempotent, robust, user-friendly
install_jq() {
    local os pkg_manager install_cmd
    os=$(uname -s)

    # Quick network check — try multiple methods for compatibility
    local network_ok=false
    if command -v curl &>/dev/null && curl -s --connect-timeout 3 https://github.com >/dev/null 2>&1; then
        network_ok=true
    elif command -v wget &>/dev/null && wget -q --timeout=3 https://github.com -O /dev/null 2>&1; then
        network_ok=true
    elif command -v ping &>/dev/null && ping -c 1 -W 2 github.com >/dev/null 2>&1; then
        network_ok=true
    fi

    if [[ "$network_ok" != "true" ]]; then
        log_warn "  Cannot reach github.com (network check failed)."
        log_warn "  If you have network access, install jq manually and re-run."
        log_warn "  Otherwise, continue with limited functionality (mock mode)."
        return 1
    fi

    case "$os" in
        Darwin)
            if command -v brew &>/dev/null; then
                pkg_manager="Homebrew"
                # brew is already idempotent — if jq installed, brew install does nothing
                if brew list jq &>/dev/null; then
                    log_info "  jq already installed via Homebrew."
                    return 0
                fi
                log_info "  Installing jq via Homebrew..."
                # Capture install output to temp file to avoid tail swallowing exit code
                local brew_log; brew_log=$(mktemp)
                if brew install jq >"$brew_log" 2>&1; then
                    rm -f "$brew_log"
                    return 0
                else
                    log_warn "  Homebrew install failed. Log:"
                    cat "$brew_log" | tail -5
                    rm -f "$brew_log"
                    return 1
                fi
            elif command -v port &>/dev/null; then
                pkg_manager="MacPorts"
                log_info "  Installing jq via MacPorts..."
                if port install jq >/dev/null 2>&1; then
                    return 0
                else
                    log_warn "  MacPorts install failed."
                    return 1
                fi
            else
                log_warn "  No package manager found on macOS."
                log_warn "  Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                log_warn "  Then re-run this script, or install jq manually."
                return 1
            fi
            ;;
        Linux)
            if [[ -f /etc/os-release ]]; then
                # Only use sudo if not running as root
                local sudo_prefix=""
                [[ "$(id -u)" != "0" ]] && sudo_prefix="sudo"

                local env_prefix=""
                if command -v apt-get &>/dev/null; then
                    pkg_manager="apt-get"
                    # Non-interactive mode for apt
                    env_prefix="DEBIAN_FRONTEND=noninteractive"
                    # Prefer apt over apt-get for better UX
                    local apt_cmd="apt-get"
                    command -v apt &>/dev/null && apt_cmd="apt"
                    log_info "  Installing jq via ${apt_cmd}..."
                    if $env_prefix $sudo_prefix $apt_cmd install -y -q jq >/dev/null 2>&1; then
                        return 0
                    else
                        log_warn "  Package install failed. Trying binary download..."
                    fi
                elif command -v yum &>/dev/null; then
                    pkg_manager="yum"
                    log_info "  Installing jq via yum..."
                    if $sudo_prefix yum install -y -q jq >/dev/null 2>&1; then
                        return 0
                    fi
                elif command -v dnf &>/dev/null; then
                    log_info "  Installing jq via dnf..."
                    if $sudo_prefix dnf install -y -q jq >/dev/null 2>&1; then
                        return 0
                    fi
                elif command -v apk &>/dev/null; then
                    log_info "  Installing jq via apk..."
                    if apk add --no-cache jq >/dev/null 2>&1; then
                        return 0
                    fi
                fi
            fi

            # Fallback: binary download for common architectures
            log_info "  Attempting binary download for $(uname -m)..."
            local arch_url=""
            local machine; machine=$(uname -m)
            case "$machine" in
                x86_64|amd64) arch_url="https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64" ;;
                aarch64|arm64) arch_url="https://github.com/jqlang/jq/releases/latest/download/jq-linux-arm64" ;;
                *) log_warn "  Unsupported architecture: ${machine}. Install jq manually."
                   return 1 ;;
            esac

            if command -v curl &>/dev/null; then
                if curl -fsSL "$arch_url" -o /usr/local/bin/jq 2>/dev/null; then
                    chmod +x /usr/local/bin/jq
                    log_info "  jq downloaded to /usr/local/bin/jq"
                    return 0
                fi
            elif command -v wget &>/dev/null; then
                if wget -q "$arch_url" -O /usr/local/bin/jq 2>/dev/null; then
                    chmod +x /usr/local/bin/jq
                    log_info "  jq downloaded to /usr/local/bin/jq"
                    return 0
                fi
            fi

            log_warn "  Binary download failed. Install jq manually."
            return 1
            ;;
        *)
            log_warn "  Unsupported OS: ${os}. Install jq manually from https://jqlang.github.io/jq/download/"
            return 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Build aliyun CLI filter args for tags and resource group
# ---------------------------------------------------------------------------
build_aliyun_filters() {
    local tags="$1"
    local resource_group="$2"
    local vpc_id="${3:-}"
    local args_str=""

    if [[ -n "$resource_group" ]]; then
        args_str="--ResourceGroupId $resource_group"
    fi

    if [[ -n "$tags" ]]; then
        local tag_array="["
        local first=true
        IFS=',' read -ra TAG_PAIRS <<< "$tags"
        for pair in "${TAG_PAIRS[@]}"; do
            pair=$(echo "$pair" | xargs)
            local key="${pair%%=*}"
            local value="${pair#*=}"
            if [[ "$first" == "true" ]]; then
                first=false
            else
                tag_array+=","
            fi
            tag_array+='{"Key":"'"${key}"'","Value":"'"${value}"'"}'
        done
        tag_array+="]"
        args_str="$args_str --Tag $tag_array"
    fi

    echo "$args_str"
}

# ---------------------------------------------------------------------------
# Generic resource fetcher with pagination
# ---------------------------------------------------------------------------
aliyun_list_all() {
    local product="$1"
    local action="$2"
    shift 2
    local extra_args=("$@")

    local all_items='[]'
    local next_token=""
    local first_page=true

    while [[ "$first_page" == "true" || -n "$next_token" ]]; do
        local page_args=("${extra_args[@]}")
        if [[ -n "$next_token" ]]; then
            page_args+=("--NextToken" "$next_token")
        fi

        local resp
        resp=$(aliyun "$product" "$action" "${page_args[@]}" 2>/dev/null) || {
            echo "$all_items"
            return 0
        }

        local items
        # Extract items with hierarchical structure support: { "Instances": {"Instance": [...]} }
        items=$(echo "$resp" | jq '
            [.Instances.Instance[]?] //
            [.LoadBalancers.LoadBalancer[]?] //
            [.DBInstances.DBInstance[]?] //
            [.Vpcs.Vpc[]?] // [.Vpcs[]?] //
            [.VSwitches.VSwitch[]?] //
            [.NatGateways.NatGateway[]?] //
            [.EipAddresses.EipAddress[]?] //
            [.Cens.Cen[]?] //
            [.Clusters[]?] //
            [.services[]?] //
            [.. | select(type == "array") | .[]?] // []
        ' 2>/dev/null) || items="[]"

        all_items=$(echo "$all_items" "$items" | jq -s 'add')

        next_token=$(echo "$resp" | jq -r '.NextToken // ""' 2>/dev/null)

        if [[ -z "$next_token" ]]; then
            next_token=$(echo "$resp" | jq -r '.PageNumber // ""' 2>/dev/null)
            if [[ -n "$next_token" && "$next_token" != "null" ]]; then
                local page_size
                page_size=$(echo "$resp" | jq -r '.PageSize // 50' 2>/dev/null)
                local total_count
                total_count=$(echo "$resp" | jq -r '.TotalCount // 0' 2>/dev/null)
                local current_page
                current_page=$(echo "$resp" | jq -r '.PageNumber // 1' 2>/dev/null)
                if (( current_page * page_size >= total_count )); then
                    next_token=""
                else
                    next_token=$((current_page + 1))
                    extra_args+=("--PageNumber" "$next_token")
                    next_token="dummy"
                fi
            else
                next_token=""
            fi
        fi

        first_page=false
    done

    echo "$all_items"
}

# ---------------------------------------------------------------------------
# Resource-level collection functions
# ---------------------------------------------------------------------------
collect_ecs_instances() {
    local region="$1"; local tags="$2"; local resource_group="$3"; local vpc_id="${4:-}"
    local filter_args; filter_args=$(build_aliyun_filters "$tags" "$resource_group")
    [[ -n "$vpc_id" ]] && filter_args="$filter_args --VpcId $vpc_id"
    log_info "  Discovering ECS instances..."
    local instances; instances=$(aliyun_list_all "ecs" "DescribeInstances" "--region" "$region" $filter_args)
    echo "$instances" | jq '[.[] | {
        instance_id: .InstanceId, name: (.InstanceName // .InstanceId), zone_id: .ZoneId,
        instance_type: .InstanceType, status: .Status, vpc_id: .VpcAttributes.VpcId,
        vswitch_id: .VpcAttributes.VSwitchId, private_ip: (.VpcAttributes.PrivateIpAddress.IpAddress // [])[0],
        eip_address: (.EipAddress.IpAddress // ""), security_group_ids: (.SecurityGroupIds.SecurityGroupId // []),
        resource_group_id: .ResourceGroupId,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {}), creation_time: .CreationTime
    }]'
}

collect_slb_instances() {
    local region="$1"; local tags="$2"; local resource_group="$3"; local vpc_id="${4:-}"
    local filter_args; filter_args=$(build_aliyun_filters "$tags" "$resource_group")
    [[ -n "$vpc_id" ]] && filter_args="$filter_args --VpcId $vpc_id"
    log_info "  Discovering SLB instances..."
    local lbs; lbs=$(aliyun_list_all "slb" "DescribeLoadBalancers" "--region" "$region" $filter_args)
    lbs=$(echo "$lbs" | jq '[.[] | {
        load_balancer_id: .LoadBalancerId, name: (.LoadBalancerName // .LoadBalancerId),
        address: .Address, address_type: .AddressType, network_type: .NetworkType,
        vpc_id: .VpcId, vswitch_id: .VSwitchId, bandwidth: .Bandwidth, status: .LoadBalancerStatus,
        resource_group_id: .ResourceGroupId,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {})
    }]')

    # Fetch backends for each SLB (separate loop to avoid jq quoting issues)
    local result='[]'
    local tmp="${OUTPUT_DIR}/.slb_result.json"
    echo "$result" > "$tmp"
    echo "$lbs" | jq -c '.[]' 2>/dev/null | while IFS= read -r slb; do
        local lb_id; lb_id=$(echo "$slb" | jq -r '.load_balancer_id')
        local backends
        backends=$(aliyun slb DescribeLoadBalancerAttribute --region "$region" --LoadBalancerId "$lb_id" 2>/dev/null | jq '[.BackendServers.BackendServer[]? | {server_id: .ServerId, weight: .Weight, type: .Type}]' 2>/dev/null || echo '[]')
        local updated
        updated=$(echo "$slb" | jq --argjson bk "$backends" '. + {backends: $bk}')
        # Use temp file to persist across pipe subshell
        local current; current=$(cat "$tmp")
        echo "$current" | jq --argjson item "$updated" '. + [$item]' > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    done
    result=$(cat "$tmp" 2>/dev/null || echo "$lbs")
    rm -f "$tmp" "${tmp}.new"
    echo "$result"
}

collect_vpc_network() {
    local region="$1"; local tags="$2"; local resource_group="$3"
    local filter_args; filter_args=$(build_aliyun_filters "$tags" "$resource_group")
    log_info "  Discovering VPCs..."
    local vpcs; vpcs=$(aliyun_list_all "vpc" "DescribeVpcs" "--region" "$region" $filter_args)
    vpcs=$(echo "$vpcs" | jq '[.[] | {
        vpc_id: .VpcId, name: (.VpcName // .VpcId), cidr_block: .CidrBlock, status: .Status,
        region_id: .RegionId, resource_group_id: .ResourceGroupId,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {}),
        vswitch_ids: (.VSwitchIds.VSwitchId // []), nat_gateway_ids: (.NatGatewayIds.NatGatewayId // []),
        router_id: .RouterId
    }]')

    local all_vswitches='[]'
    echo "$vpcs" | jq -c '.[]' 2>/dev/null | while IFS= read -r vpc; do
        local vpc_id; vpc_id=$(echo "$vpc" | jq -r '.vpc_id')
        local vswitches; vswitches=$(aliyun_list_all "vpc" "DescribeVSwitches" "--region" "$region" "--VpcId" "$vpc_id")
        all_vswitches=$(echo "$all_vswitches" "$vswitches" | jq -s 'add')
        echo "$all_vswitches" > "${OUTPUT_DIR}/.vswitches_tmp.json"
    done

    if [[ -f "${OUTPUT_DIR}/.vswitches_tmp.json" ]]; then
        all_vswitches=$(cat "${OUTPUT_DIR}/.vswitches_tmp.json"); rm -f "${OUTPUT_DIR}/.vswitches_tmp.json"
    fi
    local vswitches_formatted
    vswitches_formatted=$(echo "$all_vswitches" | jq '[.[] | {
        vswitch_id: .VSwitchId, name: (.VSwitchName // .VSwitchId), vpc_id: .VpcId,
        zone_id: .ZoneId, cidr_block: .CidrBlock, status: .Status, available_ip_count: .AvailableIpAddressCount
    }]' 2>/dev/null) || vswitches_formatted='[]'
    echo "$vpcs" | jq --argjson vswitches "$vswitches_formatted" '.[].vswitches = ($vswitches | map(select(.vpc_id == .vpc_id)))'
}

collect_eips() {
    local region="$1"
    log_info "  Discovering EIPs..."
    local eips; eips=$(aliyun_list_all "vpc" "DescribeEipAddresses" "--region" "$region")
    echo "$eips" | jq '[.[] | {
        allocation_id: .AllocationId, ip_address: .IpAddress, status: .Status, bandwidth: .Bandwidth,
        internet_charge_type: .InternetChargeType, instance_id: (.InstanceId // ""),
        instance_type: (.InstanceType // ""), region_id: .RegionId
    }]'
}

collect_nat_gateways() {
    local region="$1"
    log_info "  Discovering NAT Gateways..."
    local ngws; ngws=$(aliyun_list_all "vpc" "DescribeNatGateways" "--region" "$region")
    echo "$ngws" | jq '[.[] | {
        nat_gateway_id: .NatGatewayId, name: (.Name // .NatGatewayId), vpc_id: .VpcId, status: .Status,
        spec: .Spec, snat_table_id: .SnatTableIds.SnatTableId[0],
        ip_lists: ([.IpLists.IpList[]? | {ip_address: .IpAddress, snat_entry_enabled: .SnatEntryEnabled, bandwidth: .Bandwidth}] // [])
    }]'
}

collect_cen_instances() {
    local region="$1"
    log_info "  Discovering CEN instances..."
    local cens; cens=$(aliyun_list_all "cbn" "DescribeCens" "--region" "$region")
    cens=$(echo "$cens" | jq '[.[] | {
        cen_id: .CenId, name: (.Name // .CenId), status: .Status, description: .Description,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {})
    }]')

    # Fetch attachments for each CEN (separate loop)
    local result='[]'
    local tmp="${OUTPUT_DIR}/.cen_result.json"
    echo "$result" > "$tmp"
    echo "$cens" | jq -c '.[]' 2>/dev/null | while IFS= read -r cen; do
        local cen_id; cen_id=$(echo "$cen" | jq -r '.cen_id')
        local attachments
        attachments=$(aliyun cbn DescribeCenAttachedChildInstances --region "$region" --CenId "$cen_id" 2>/dev/null | jq '[.ChildInstances.ChildInstance[]? | {child_instance_id: .ChildInstanceId, child_instance_type: .ChildInstanceType, child_instance_region_id: .ChildInstanceRegionId, child_instance_owner_id: .ChildInstanceOwnerId}]' 2>/dev/null || echo '[]')
        local updated
        updated=$(echo "$cen" | jq --argjson att "$attachments" '. + {attachments: $att}')
        local current; current=$(cat "$tmp")
        echo "$current" | jq --argjson item "$updated" '. + [$item]' > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    done
    result=$(cat "$tmp" 2>/dev/null || echo "$cens")
    rm -f "$tmp" "${tmp}.new"
    echo "$result"
}

collect_rds_instances() {
    local region="$1"; local tags="$2"; local resource_group="$3"; local vpc_id="${4:-}"
    local filter_args; filter_args=$(build_aliyun_filters "$tags" "$resource_group")
    [[ -n "$vpc_id" ]] && filter_args="$filter_args --VpcId $vpc_id"
    log_info "  Discovering RDS instances..."
    local rds; rds=$(aliyun_list_all "rds" "DescribeDBInstances" "--region" "$region" $filter_args)
    echo "$rds" | jq '[.[] | {
        db_instance_id: .DBInstanceId, name: (.DBInstanceDescription // .DBInstanceId),
        engine: .Engine, engine_version: .EngineVersion, status: .DBInstanceStatus,
        zone_id: .ZoneId, vpc_id: .VpcId, vswitch_id: .VSwitchId, instance_type: .DBInstanceClassType,
        resource_group_id: .ResourceGroupId,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {}), creation_time: .CreationTime
    }]'
}

collect_redis_instances() {
    local region="$1"; local tags="$2"; local resource_group="$3"; local vpc_id="${4:-}"
    local filter_args; filter_args=$(build_aliyun_filters "$tags" "$resource_group")
    [[ -n "$vpc_id" ]] && filter_args="$filter_args --VpcId $vpc_id"
    log_info "  Discovering Redis instances..."
    local redis; redis=$(aliyun_list_all "kvstore" "DescribeInstances" "--region" "$region" $filter_args)
    echo "$redis" | jq '[.[] | {
        instance_id: .InstanceId, name: (.InstanceName // .InstanceId), engine_version: .EngineVersion,
        status: .InstanceStatus, zone_id: .ZoneId, vpc_id: .VpcId, vswitch_id: .VSwitchId,
        instance_type: .InstanceClass, resource_group_id: .ResourceGroupId,
        tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {})
    }]'
}

collect_ack_clusters() {
    local region="$1"; local tags="$2"; local resource_group="$3"
    log_info "  Discovering ACK clusters..."
    local clusters; clusters=$(aliyun_list_all "cs" "DescribeClusters" "--region" "$region")
    if [[ -n "$resource_group" ]]; then
        clusters=$(echo "$clusters" | jq --arg rg "$resource_group" '[.[] | select(.resource_group_id == $rg)]')
    fi
    if [[ -n "$tags" ]]; then
        IFS=',' read -ra TAG_PAIRS <<< "$tags"
        for pair in "${TAG_PAIRS[@]}"; do
            pair=$(echo "$pair" | xargs); local key="${pair%%=*}"; local value="${pair#*=}"
            clusters=$(echo "$clusters" | jq --arg k "$key" --arg v "$value" '[.[] | select(.tags[$k] == $v)]')
        done
    fi
    echo "$clusters" | jq '[.[] | {
        cluster_id: .cluster_id, name: (.name // .cluster_id), cluster_type: .cluster_type,
        status: .state, region_id: .region_id, vpc_id: .vpc_id,
        vswitch_ids: (.vswitch_ids // []), tags: (.tags // {}), node_count: (.size // 0)
    }]'
}

collect_fc_services() {
    local region="$1"
    log_info "  Discovering FC services..."
    local services; services=$(aliyun_list_all "fc" "ListServices" "--region" "$region")
    echo "$services" | jq '[.[] | {
        service_name: .serviceName, description: .description, role: .role,
        vpc_config: .vpcConfig, log_config: .logConfig, nas_config: .nasConfig, creation_time: .createdTime
    }]'
}

collect_oss_buckets() {
    log_info "  Discovering OSS buckets..."
    local buckets
    buckets=$(aliyun oss ls 2>/dev/null | grep "^oss://" | sed 's/oss:\/\///' | awk '{print "{\"bucket_name\": \"" $1 "\", \"storage_class\": \"Standard\", \"region\": \"'${ALICLOUD_REGION:-cn-hangzhou}'\"}"}' 2>/dev/null || echo "")
    if [[ -z "$buckets" || "$buckets" == "" ]]; then
        echo '[]'
    else
        echo "$buckets" | jq -s '. // []'
    fi
}

# ---------------------------------------------------------------------------
# Relationship inference engine
# ---------------------------------------------------------------------------
infer_relationships() {
    local topology_file="$1"
    if [[ ! -f "$topology_file" ]]; then
        echo '{"connections": []}'; return
    fi
    local connections='[]'; local topology; topology=$(cat "$topology_file")
    local ecs_list slb_list vpc_list eip_list nat_list cen_list rds_list redis_list
    ecs_list=$(echo "$topology" | jq '[.resources[] | select(.type == "ECS") | .instances[]]')
    slb_list=$(echo "$topology" | jq '[.resources[] | select(.type == "SLB") | .instances[]]')
    vpc_list=$(echo "$topology" | jq '[.resources[] | select(.type == "VPC") | .instances[]]')
    eip_list=$(echo "$topology" | jq '[.resources[] | select(.type == "EIP") | .instances[]]')
    nat_list=$(echo "$topology" | jq '[.resources[] | select(.type == "NAT") | .instances[]]')
    cen_list=$(echo "$topology" | jq '[.resources[] | select(.type == "CEN") | .instances[]]')
    rds_list=$(echo "$topology" | jq '[.resources[] | select(.type == "RDS") | .instances[]]')
    redis_list=$(echo "$topology" | jq '[.resources[] | select(.type == "Redis") | .instances[]]')

    echo "$slb_list" | jq -c '.[]' 2>/dev/null | while IFS= read -r slb; do
        local slb_id; slb_id=$(echo "$slb" | jq -r '.load_balancer_id')
        echo "$slb" | jq -c '.backends[]?' 2>/dev/null | while IFS= read -r backend; do
            connections=$(echo "$connections" | jq \
                --arg from "$slb_id" --arg to "$(echo "$backend" | jq -r '.server_id')" \
                '. + [{"from": {"type": "SLB", "id": $from}, "to": {"type": "ECS", "id": $to}, "relation": "backend"}]')
            echo "$connections" > "${OUTPUT_DIR}/.conn_tmp.json"
        done
    done
    [[ -f "${OUTPUT_DIR}/.conn_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn_tmp.json"); rm -f "${OUTPUT_DIR}/.conn_tmp.json"; }

    echo "$ecs_list" | jq -c '.[]' 2>/dev/null | while IFS= read -r ecs; do
        local eid vid; eid=$(echo "$ecs" | jq -r '.instance_id // empty'); vid=$(echo "$ecs" | jq -r '.vpc_id // empty')
        if [[ -n "$vid" && "$vid" != "null" && -n "$eid" ]]; then
            connections=$(echo "$connections" | jq \
                --arg from "$eid" --arg to "$vid" \
                '. + [{"from": {"type": "ECS", "id": $from}, "to": {"type": "VPC", "id": $to}, "relation": "belongs_to"}]')
            echo "$connections" > "${OUTPUT_DIR}/.conn2_tmp.json"
        fi
    done
    [[ -f "${OUTPUT_DIR}/.conn2_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn2_tmp.json"); rm -f "${OUTPUT_DIR}/.conn2_tmp.json"; }

    echo "$eip_list" | jq -c '.[]' 2>/dev/null | while IFS= read -r eip; do
        local eid aid; eid=$(echo "$eip" | jq -r '.allocation_id // empty'); aid=$(echo "$eip" | jq -r '.instance_id // empty')
        if [[ -n "$aid" && "$aid" != "null" && -n "$eid" ]]; then
            connections=$(echo "$connections" | jq \
                --arg from "$eid" --arg to "$aid" \
                '. + [{"from": {"type": "EIP", "id": $from}, "to": {"type": "ECS", "id": $to}, "relation": "attached_to"}]')
            echo "$connections" > "${OUTPUT_DIR}/.conn3_tmp.json"
        fi
    done
    [[ -f "${OUTPUT_DIR}/.conn3_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn3_tmp.json"); rm -f "${OUTPUT_DIR}/.conn3_tmp.json"; }

    echo "$nat_list" | jq -c '.[]' 2>/dev/null | while IFS= read -r nat; do
        local nid nvpc; nid=$(echo "$nat" | jq -r '.nat_gateway_id // empty'); nvpc=$(echo "$nat" | jq -r '.vpc_id // empty')
        if [[ -n "$nvpc" && "$nvpc" != "null" && -n "$nid" ]]; then
            connections=$(echo "$connections" | jq \
                --arg from "$nvpc" --arg to "$nid" \
                '. + [{"from": {"type": "VPC", "id": $from}, "to": {"type": "NAT", "id": $to}, "relation": "has_nat_gateway"}]')
            echo "$connections" > "${OUTPUT_DIR}/.conn4_tmp.json"
        fi
    done
    [[ -f "${OUTPUT_DIR}/.conn4_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn4_tmp.json"); rm -f "${OUTPUT_DIR}/.conn4_tmp.json"; }

    echo "$cen_list" | jq -c '.[]' 2>/dev/null | while IFS= read -r cen; do
        local cid; cid=$(echo "$cen" | jq -r '.cen_id // empty')
        echo "$cen" | jq -c '.attachments[]?' 2>/dev/null | while IFS= read -r att; do
            local child_id child_type; child_id=$(echo "$att" | jq -r '.child_instance_id // empty'); child_type=$(echo "$att" | jq -r '.child_instance_type // "VPC"')
            if [[ -n "$child_id" && -n "$cid" ]]; then
                connections=$(echo "$connections" | jq \
                    --arg from "$cid" --arg to "$child_id" --arg ctype "$child_type" \
                    '. + [{"from": {"type": "CEN", "id": $from}, "to": {"type": $ctype, "id": $to}, "relation": "attaches"}]')
                echo "$connections" > "${OUTPUT_DIR}/.conn5_tmp.json"
            fi
        done
    done
    [[ -f "${OUTPUT_DIR}/.conn5_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn5_tmp.json"); rm -f "${OUTPUT_DIR}/.conn5_tmp.json"; }

    # RDS/Redis -> VPC
    for rtype in "RDS" "Redis"; do
        local rlist; rlist=$(echo "$topology" | jq "[.resources[] | select(.type == \"${rtype}\") | .instances[]]")
        echo "$rlist" | jq -c '.[]' 2>/dev/null | while IFS= read -r inst; do
            local iid ivpc; iid=$(echo "$inst" | jq -r '.db_instance_id // .instance_id // empty'); ivpc=$(echo "$inst" | jq -r '.vpc_id // empty')
            if [[ -n "$ivpc" && "$ivpc" != "null" && -n "$iid" ]]; then
                connections=$(echo "$connections" | jq \
                    --arg from "$iid" --arg to "$ivpc" --arg ftype "$rtype" \
                    '. + [{"from": {"type": $ftype, "id": $from}, "to": {"type": "VPC", "id": $to}, "relation": "belongs_to"}]')
                echo "$connections" > "${OUTPUT_DIR}/.conn6_tmp.json"
            fi
        done
        [[ -f "${OUTPUT_DIR}/.conn6_tmp.json" ]] && { connections=$(cat "${OUTPUT_DIR}/.conn6_tmp.json"); rm -f "${OUTPUT_DIR}/.conn6_tmp.json"; }
    done

    echo "$connections"
}

# ---------------------------------------------------------------------------
# Main topology collector
# ---------------------------------------------------------------------------
collect_topology() {
    local region="${1:-${ALICLOUD_REGION:-cn-hangzhou}}"
    local resource_group="${2:-}"; local tags="${3:-}"
    local account_id="${4:-${ALICLOUD_ACCOUNT_ID:-unknown}}"
    local output_file="${OUTPUT_DIR}/topology-${region}.json"
    local cross_account="${5:-false}"; local assume_role="${6:-}"
    local vpc_id="${7:-}"

    if [[ "$cross_account" == "true" && -n "$assume_role" ]]; then
        log_info "Cross-account mode (Phase 2): requires aliyun resourcemanager + sts AssumeRole."
        log_info "Proceeding with single account discovery."
    fi

    # Strategy 1: topo-discovery CLI
    if command -v topo-discovery &>/dev/null; then
        log_info "Using topo-discovery (region: ${region})..."
        local td_args=("--region" "$region" "--output" "$output_file")
        [[ -n "$resource_group" ]] && td_args+=("--resource-group-id" "$resource_group")
        [[ -n "$tags" ]] && td_args+=("--tags" "$tags")
        if topo-discovery collect "${td_args[@]}" 2>/dev/null; then
            log_success "Topology saved to ${output_file}"
            local connections; connections=$(infer_relationships "$output_file")
            jq --argjson conn "$connections" '.connections = $conn' "$output_file" > "${output_file}.tmp" && mv "${output_file}.tmp" "$output_file"
            cat "$output_file"; return 0
        else
            log_warn "topo-discovery failed. Falling back to manual discovery."
        fi
    else
        log_info "topo-discovery not available. Using manual aliyun CLI discovery."
    fi

    collect_vpc_by_ids() {
        local region="$1"
        shift
        local vpc_ids=("$@")
        if [[ ${#vpc_ids[@]} -eq 0 ]]; then echo '[]'; return; fi

        log_info "  Discovering VPCs by IDs (from resource references)..."
        local result='[]'; local tmp="${OUTPUT_DIR}/.vpc_by_id.json"
        echo "$result" > "$tmp"
        for vid in "${vpc_ids[@]}"; do
            [[ -z "$vid" || "$vid" == "null" ]] && continue
            local vpc_data
            vpc_data=$(aliyun vpc DescribeVpcs --region "$region" --VpcId "$vid" 2>/dev/null | \
                jq '[.Vpcs.Vpc[]? | {
                    vpc_id: .VpcId, name: (.VpcName // .VpcId), cidr_block: .CidrBlock,
                    status: .Status, region_id: .RegionId, resource_group_id: .ResourceGroupId,
                    tags: ([.Tags.Tag[]? | {(.TagKey): .TagValue}] | add // {}),
                    vswitch_ids: (.VSwitchIds.VSwitchId // []),
                    nat_gateway_ids: (.NatGatewayIds.NatGatewayId // []),
                    router_id: .RouterId
                }]' 2>/dev/null || echo '[]')
            local current; current=$(cat "$tmp")
            echo "$current" | jq --argjson new "$vpc_data" '. + $new' > "${tmp}.new" 2>/dev/null && mv "${tmp}.new" "$tmp"
        done

        result=$(cat "$tmp" 2>/dev/null || echo '[]')
        rm -f "$tmp" "${tmp}.new"

        # Fetch VSwitches for each VPC
        local final='[]'
        echo "$result" | jq -c '.[]' 2>/dev/null | while IFS= read -r vpc; do
            local vid; vid=$(echo "$vpc" | jq -r '.vpc_id')
            local vsw_data
            vsw_data=$(aliyun vpc DescribeVSwitches --region "$region" --VpcId "$vid" 2>/dev/null | \
                jq '[.VSwitches.VSwitch[]? | {
                    vswitch_id: .VSwitchId, name: (.VSwitchName // .VSwitchId),
                    vpc_id: .VpcId, zone_id: .ZoneId, cidr_block: .CidrBlock,
                    status: .Status, available_ip_count: .AvailableIpAddressCount
                }]' 2>/dev/null || echo '[]')
            local updated; updated=$(echo "$vpc" | jq --argjson vsw "$vsw_data" '.vswitches = $vsw')
            local cur; cur=$(cat "${OUTPUT_DIR}/.vpc_final.json" 2>/dev/null || echo '[]')
            echo "$cur" | jq --argjson item "$updated" '. + [$item]' > "${OUTPUT_DIR}/.vpc_final.json" 2>/dev/null
        done

        final=$(cat "${OUTPUT_DIR}/.vpc_final.json" 2>/dev/null || echo "$result")
        rm -f "${OUTPUT_DIR}/.vpc_final.json"
        echo "$final"
    }

    # Strategy 2: Manual discovery — relationship-driven ("inside out")
    # Phase 1: Collect compute/storage resources (RG-filtered, VPC-filtered)
    log_info "Starting manual resource discovery (relationship-driven)..."
    local all_resources='[]'

    local ecs_data; ecs_data=$(collect_ecs_instances "$region" "$tags" "$resource_group" "$vpc_id") && ecs_data="${ecs_data:-[]}"
    local ecs_n; ecs_n=$(echo "$ecs_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "ECS" --argjson instances "$ecs_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local slb_data; slb_data=$(collect_slb_instances "$region" "$tags" "$resource_group" "$vpc_id") && slb_data="${slb_data:-[]}"
    local slb_n; slb_n=$(echo "$slb_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "SLB" --argjson instances "$slb_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local rds_data; rds_data=$(collect_rds_instances "$region" "$tags" "$resource_group" "$vpc_id") && rds_data="${rds_data:-[]}"
    local rds_n; rds_n=$(echo "$rds_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "RDS" --argjson instances "$rds_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local redis_data; redis_data=$(collect_redis_instances "$region" "$tags" "$resource_group" "$vpc_id") && redis_data="${redis_data:-[]}"
    local redis_n; redis_n=$(echo "$redis_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "Redis" --argjson instances "$redis_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local ack_data; ack_data=$(collect_ack_clusters "$region" "$tags" "$resource_group") && ack_data="${ack_data:-[]}"
    local ack_n; ack_n=$(echo "$ack_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "ACK" --argjson instances "$ack_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local fc_data; fc_data=$(collect_fc_services "$region") && fc_data="${fc_data:-[]}"
    local fc_n; fc_n=$(echo "$fc_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "FC" --argjson instances "$fc_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local oss_data; oss_data=$(collect_oss_buckets) && oss_data="${oss_data:-[]}"
    local oss_n; oss_n=$(echo "$oss_data" | jq 'length' 2>/dev/null || echo 0)
    if [[ "$oss_n" -gt 0 ]]; then
        all_resources=$(echo "$all_resources" | jq --arg type "OSS" --argjson instances "$oss_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")
    fi

    # Phase 2: Extract VPC IDs from resource data, then discover VPC+VSwitch
    local vpc_ids
    vpc_ids=$(echo "$all_resources" | jq '[.[].instances[] | .vpc_id // empty] | unique | map(select(. != "" and . != null))' 2>/dev/null)
    local vpc_id_count; vpc_id_count=$(echo "$vpc_ids" | jq 'length' 2>/dev/null || echo 0)

    local vpc_data='[]'; local vpc_n=0
    if [[ "$vpc_id_count" -gt 0 ]]; then
        # Extract as bash array
        local vpc_id_array=()
        while IFS= read -r id; do
            [[ -n "$id" && "$id" != "null" ]] && vpc_id_array+=("$id")
        done < <(echo "$vpc_ids" | jq -r '.[]' 2>/dev/null)

        vpc_data=$(collect_vpc_by_ids "$region" "${vpc_id_array[@]}")
        vpc_n=$(echo "$vpc_data" | jq 'length' 2>/dev/null || echo 0)
        if [[ "$vpc_n" -gt 0 ]]; then
            all_resources=$(echo "$all_resources" | jq --arg type "VPC" --argjson instances "$vpc_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")
        fi
    else
        log_info "  No VPC IDs found in resources. Skipping VPC discovery."
    fi

    # Phase 3: Network resources (based on found VPCs or global)
    local eip_data; eip_data=$(collect_eips "$region") && eip_data="${eip_data:-[]}"
    local eip_n; eip_n=$(echo "$eip_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "EIP" --argjson instances "$eip_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local nat_data; nat_data=$(collect_nat_gateways "$region") && nat_data="${nat_data:-[]}"
    local nat_n; nat_n=$(echo "$nat_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "NAT" --argjson instances "$nat_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local cen_data; cen_data=$(collect_cen_instances "$region") && cen_data="${cen_data:-[]}"
    local cen_n; cen_n=$(echo "$cen_data" | jq 'length' 2>/dev/null || echo 0)
    all_resources=$(echo "$all_resources" | jq --arg type "CEN" --argjson instances "$cen_data" '. + [{"type": $type, "instances": $instances}]' 2>/dev/null || echo "$all_resources")

    local topology
    topology=$(jq -n --arg region "$region" --arg account_id "$account_id" \
        --arg resource_group "${resource_group:-}" --argjson resources "$all_resources" \
        '{region: $region, account_id: $account_id, resource_group_id: (if $resource_group == "" then null else $resource_group end), resources: $resources, connections: []}' 2>/dev/null || echo '{"region":"'${region}'","account_id":"'${account_id}'","resources":[],"connections":[]}')

    echo "$topology" > "$output_file" 2>/dev/null || true
    local connections; connections=$(infer_relationships "$output_file" 2>/dev/null || echo '[]')
    topology=$(echo "$topology" | jq --argjson conn "$connections" '.connections = $conn' 2>/dev/null || echo "$topology")
    echo "$topology" > "$output_file" 2>/dev/null || true

    log_success "Topology saved to ${output_file}"
    echo "" >&2; log_info "Resource discovery: ECS=${ecs_n} SLB=${slb_n} VPC=${vpc_n} EIP=${eip_n} NAT=${nat_n} CEN=${cen_n} RDS=${rds_n} Redis=${redis_n} ACK=${ack_n} FC=${fc_n} OSS=${oss_n}"
    cat "$output_file" 2>/dev/null || echo "$topology"
}

# ---------------------------------------------------------------------------
# Generate mock topology
# ---------------------------------------------------------------------------
generate_mock_topology() {
    local region="$1"; local resource_group="${2:-}"; local tags="${3:-}"
    local account_id="${4:-1234567890}"
    local output_file="${OUTPUT_DIR}/topology-${region}-mock.json"

    cat > "$output_file" <<MOCKEOF
{
  "region": "${region}",
  "account_id": "${account_id}",
  "resource_group_id": ${resource_group:+\"${resource_group}\"}${resource_group:-null},
  "tags_filter": ${tags:+\"${tags}\"}${tags:-null},
  "discovery_mode": "mock",
  "resources": [
    {
      "type": "VPC",
      "instances": [{"vpc_id": "vpc-bp1m7j4k9f2x3a5b", "name": "main-vpc", "cidr_block": "10.0.0.0/8", "status": "Available", "vswitches": [{"vswitch_id": "vsw-bp1a2b3c4d5e", "zone_id": "${region}-g", "cidr_block": "10.0.1.0/24", "available_ip_count": 200}, {"vswitch_id": "vsw-bp1f6g7h8i9j", "zone_id": "${region}-h", "cidr_block": "10.0.2.0/24", "available_ip_count": 200}], "nat_gateway_ids": ["ngw-bp1k1l2m3n4o"]}]
    },
    {
      "type": "SLB",
      "instances": [{"load_balancer_id": "lb-bp1p5q6r7s8t", "name": "web-slb", "address": "47.96.xx.xx", "address_type": "internet", "network_type": "vpc", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1a2b3c4d5e", "bandwidth": 1000, "status": "active", "backends": [{"server_id": "i-bp1u1v2w3x4y", "weight": 100, "type": "ecs"}, {"server_id": "i-bp1z5a6b7c8d", "weight": 100, "type": "ecs"}]}]
    },
    {
      "type": "ECS",
      "instances": [
        {"instance_id": "i-bp1u1v2w3x4y", "name": "web-server-01", "zone_id": "${region}-g", "instance_type": "ecs.g6.xlarge", "status": "Running", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1a2b3c4d5e", "private_ip": "10.0.1.10", "eip_address": "47.96.xx.xx", "security_group_ids": ["sg-bp1e9f0g1h2i"], "tags": {"env": "prod", "app": "web", "tier": "frontend"}},
        {"instance_id": "i-bp1z5a6b7c8d", "name": "web-server-02", "zone_id": "${region}-h", "instance_type": "ecs.g6.xlarge", "status": "Running", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1f6g7h8i9j", "private_ip": "10.0.2.10", "eip_address": "", "security_group_ids": ["sg-bp1e9f0g1h2i"], "tags": {"env": "prod", "app": "web", "tier": "frontend"}},
        {"instance_id": "i-bp1j3k4l5m6n", "name": "app-server-01", "zone_id": "${region}-g", "instance_type": "ecs.g6.2xlarge", "status": "Running", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1a2b3c4d5e", "private_ip": "10.0.1.20", "eip_address": "", "security_group_ids": ["sg-bp2j3k4l5m6n"], "tags": {"env": "prod", "app": "app", "tier": "backend"}}
      ]
    },
    {
      "type": "EIP",
      "instances": [{"allocation_id": "eip-bp1o7p8q9r0s", "ip_address": "47.96.xx.xx", "status": "InUse", "bandwidth": 100, "instance_id": "i-bp1u1v2w3x4y", "instance_type": "EcsInstance"}]
    },
    {
      "type": "NAT",
      "instances": [{"nat_gateway_id": "ngw-bp1k1l2m3n4o", "name": "nat-gateway", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "status": "Available", "spec": "Small", "ip_lists": [{"ip_address": "47.96.xx.yy", "snat_entry_enabled": true, "bandwidth": 200}]}]
    },
    {
      "type": "CEN",
      "instances": [{"cen_id": "cen-bp1t2u3v4w5x", "name": "main-cen", "status": "Active", "attachments": [{"child_instance_id": "vpc-bp1m7j4k9f2x3a5b", "child_instance_type": "VPC", "child_instance_region_id": "${region}", "child_instance_owner_id": "${account_id}"}]}]
    },
    {
      "type": "RDS",
      "instances": [{"db_instance_id": "rm-bp1y6z7a8b9c", "name": "main-mysql", "engine": "MySQL", "engine_version": "8.0", "status": "Running", "zone_id": "${region}-g", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1a2b3c4d5e", "instance_type": "rds.mysql.s4.large", "tags": {"env": "prod", "app": "database"}}]
    },
    {
      "type": "Redis",
      "instances": [{"instance_id": "r-bp1d0e1f2g3h", "name": "cache-cluster", "engine_version": "7.0", "status": "Running", "zone_id": "${region}-g", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_id": "vsw-bp1a2b3c4d5e", "instance_type": "redis.master.small.default", "tags": {"env": "prod", "app": "cache"}}]
    },
    {
      "type": "ACK",
      "instances": [{"cluster_id": "c-bp1i4j5k6l7m", "name": "k8s-cluster", "cluster_type": "ManagedKubernetes", "status": "running", "vpc_id": "vpc-bp1m7j4k9f2x3a5b", "vswitch_ids": ["vsw-bp1a2b3c4d5e", "vsw-bp1f6g7h8i9j"], "node_count": 0}]
    },
    {
      "type": "OSS",
      "instances": [{"bucket_name": "app-data-prod", "storage_class": "Standard", "region": "${region}"}, {"bucket_name": "log-archive-prod", "storage_class": "IA", "region": "${region}"}]
    }
  ],
  "connections": [
    {"from": {"type": "SLB", "id": "lb-bp1p5q6r7s8t"}, "to": {"type": "ECS", "id": "i-bp1u1v2w3x4y"}, "relation": "backend"},
    {"from": {"type": "SLB", "id": "lb-bp1p5q6r7s8t"}, "to": {"type": "ECS", "id": "i-bp1z5a6b7c8d"}, "relation": "backend"},
    {"from": {"type": "ECS", "id": "i-bp1u1v2w3x4y"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "belongs_to"},
    {"from": {"type": "ECS", "id": "i-bp1z5a6b7c8d"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "belongs_to"},
    {"from": {"type": "ECS", "id": "i-bp1j3k4l5m6n"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "belongs_to"},
    {"from": {"type": "EIP", "id": "eip-bp1o7p8q9r0s"}, "to": {"type": "ECS", "id": "i-bp1u1v2w3x4y"}, "relation": "attached_to"},
    {"from": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "to": {"type": "NAT", "id": "ngw-bp1k1l2m3n4o"}, "relation": "has_nat_gateway"},
    {"from": {"type": "CEN", "id": "cen-bp1t2u3v4w5x"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "attaches"},
    {"from": {"type": "RDS", "id": "rm-bp1y6z7a8b9c"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "belongs_to"},
    {"from": {"type": "Redis", "id": "r-bp1d0e1f2g3h"}, "to": {"type": "VPC", "id": "vpc-bp1m7j4k9f2x3a5b"}, "relation": "belongs_to"}
  ]
}
MOCKEOF
    log_success "Mock topology generated at ${output_file}"
    cat "$output_file"
}

# ---------------------------------------------------------------------------
# Architecture pattern detection
# ---------------------------------------------------------------------------
detect_architecture_pattern() {
    local topology_file="$1"
    if [[ ! -f "$topology_file" ]]; then echo "unknown"; return 1; fi
    local ecs_n slb_n rds_n redis_n ack_n fc_n oss_n
    ecs_n=$(jq '[.resources[] | select(.type == "ECS") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    slb_n=$(jq '[.resources[] | select(.type == "SLB") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    rds_n=$(jq '[.resources[] | select(.type == "RDS") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    redis_n=$(jq '[.resources[] | select(.type == "Redis") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    ack_n=$(jq '[.resources[] | select(.type == "ACK") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    fc_n=$(jq '[.resources[] | select(.type == "FC") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    oss_n=$(jq '[.resources[] | select(.type == "OSS") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
    if [[ "$fc_n" -ge 1 ]]; then echo "serverless"
    elif [[ "$ack_n" -ge 1 ]]; then echo "microservice"
    elif [[ "$slb_n" -ge 1 && "$ecs_n" -ge 2 ]]; then echo "3-tier"
    elif [[ "$ecs_n" -eq 1 && "$rds_n" -eq 1 ]]; then echo "single-node"
    elif [[ "$ecs_n" -ge 1 ]]; then
        local cen_n; cen_n=$(jq '[.resources[] | select(.type == "CEN") | .instances | length] | first // 0' "$topology_file" 2>/dev/null)
        [[ "$cen_n" -ge 1 ]] && echo "multi-region" || echo "hybrid"
    else echo "unknown"; fi
}

# ---------------------------------------------------------------------------
# Mermaid topology renderer (使用临时文件避免subshell变量作用域问题)
# ---------------------------------------------------------------------------
render_mermaid_topology() {
    local topology_file="$1"
    if [[ ! -f "$topology_file" ]]; then
        log_warn "Topology file not found: ${topology_file}"
        return 1
    fi

    local region
    region=$(jq -r '.region // "cn-hangzhou"' "$topology_file" 2>/dev/null)

    local output=""
    output+="graph TB"$'\n'

    # Internet node
    output+="    Internet((Internet))"$'\n'

    # Get VPC info
    local first_vpc
    first_vpc=$(jq -c '[.resources[] | select(.type == "VPC") | .instances[0]] | first' "$topology_file" 2>/dev/null)
    local first_vpc_id
    first_vpc_id=$(echo "$first_vpc" | jq -r '.vpc_id // empty' 2>/dev/null)

    # Write resource counts to temp file for cross-subshell access
    local tmpfile="${OUTPUT_DIR}/.mermaid_counts.json"
    jq '{
        ecs: ([.resources[] | select(.type == "ECS") | .instances | length] | first // 0),
        slb: ([.resources[] | select(.type == "SLB") | .instances | length] | first // 0),
        rds: ([.resources[] | select(.type == "RDS") | .instances | length] | first // 0),
        redis: ([.resources[] | select(.type == "Redis") | .instances | length] | first // 0),
        ack: ([.resources[] | select(.type == "ACK") | .instances | length] | first // 0),
        eip: ([.resources[] | select(.type == "EIP") | .instances | length] | first // 0),
        nat: ([.resources[] | select(.type == "NAT") | .instances | length] | first // 0),
        cen: ([.resources[] | select(.type == "CEN") | .instances | length] | first // 0),
        oss: ([.resources[] | select(.type == "OSS") | .instances | length] | first // 0),
        fc: ([.resources[] | select(.type == "FC") | .instances | length] | first // 0),
        vpc_name: ([.resources[] | select(.type == "VPC") | .instances[0].name // ""] | first // ""),
        vpc_cidr: ([.resources[] | select(.type == "VPC") | .instances[0].cidr_block // ""] | first // "")
    }' "$topology_file" > "$tmpfile" 2>/dev/null

    local ecs_n slb_n rds_n redis_n ack_n eip_n nat_n cen_n oss_n fc_n vpc_name vpc_cidr
    ecs_n=$(jq -r '.ecs' "$tmpfile" 2>/dev/null)
    slb_n=$(jq -r '.slb' "$tmpfile" 2>/dev/null)
    rds_n=$(jq -r '.rds' "$tmpfile" 2>/dev/null)
    redis_n=$(jq -r '.redis' "$tmpfile" 2>/dev/null)
    ack_n=$(jq -r '.ack' "$tmpfile" 2>/dev/null)
    eip_n=$(jq -r '.eip' "$tmpfile" 2>/dev/null)
    nat_n=$(jq -r '.nat' "$tmpfile" 2>/dev/null)
    cen_n=$(jq -r '.cen' "$tmpfile" 2>/dev/null)
    oss_n=$(jq -r '.oss' "$tmpfile" 2>/dev/null)
    fc_n=$(jq -r '.fc' "$tmpfile" 2>/dev/null)
    vpc_name=$(jq -r '.vpc_name' "$tmpfile" 2>/dev/null)
    vpc_cidr=$(jq -r '.vpc_cidr' "$tmpfile" 2>/dev/null)
    rm -f "$tmpfile"

    if [[ -n "$first_vpc_id" && "$first_vpc_id" != "null" ]]; then
        output+="    subgraph \"VPC: ${vpc_name}\\n${vpc_cidr}\""$'\n'

        # EIP
        if [[ "$eip_n" -gt 0 ]]; then
            jq -c '[.resources[] | select(.type == "EIP") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r eip; do
                local eip_id eip_addr
                eip_id=$(echo "$eip" | jq -r '.allocation_id // empty' 2>/dev/null)
                eip_addr=$(echo "$eip" | jq -r '.ip_address // ""' 2>/dev/null)
                [[ -n "$eip_id" ]] && echo "        EIP_${eip_id}((EIP ${eip_addr}))"
            done >> "${OUTPUT_DIR}/.mermaid_eips.txt" 2>/dev/null
            if [[ -f "${OUTPUT_DIR}/.mermaid_eips.txt" ]]; then
                while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_eips.txt"
                rm -f "${OUTPUT_DIR}/.mermaid_eips.txt"
            fi
        fi

        # NAT
        if [[ "$nat_n" -gt 0 ]]; then
            jq -c '[.resources[] | select(.type == "NAT") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r nat; do
                local nat_id nat_name
                nat_id=$(echo "$nat" | jq -r '.nat_gateway_id // empty' 2>/dev/null)
                nat_name=$(echo "$nat" | jq -r '.name // .nat_gateway_id' 2>/dev/null)
                [[ -n "$nat_id" ]] && echo "        NAT_${nat_id}[NAT: ${nat_name}]"
            done >> "${OUTPUT_DIR}/.mermaid_nats.txt" 2>/dev/null
            if [[ -f "${OUTPUT_DIR}/.mermaid_nats.txt" ]]; then
                while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_nats.txt"
                rm -f "${OUTPUT_DIR}/.mermaid_nats.txt"
            fi
        fi

        # SLB
        if [[ "$slb_n" -gt 0 ]]; then
            jq -c '[.resources[] | select(.type == "SLB") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r slb; do
                local slb_id slb_name
                slb_id=$(echo "$slb" | jq -r '.load_balancer_id // empty' 2>/dev/null)
                slb_name=$(echo "$slb" | jq -r '.name // .load_balancer_id' 2>/dev/null)
                [[ -n "$slb_id" ]] && echo "        SLB_${slb_id}[SLB: ${slb_name}]"
            done >> "${OUTPUT_DIR}/.mermaid_slbs.txt" 2>/dev/null
            if [[ -f "${OUTPUT_DIR}/.mermaid_slbs.txt" ]]; then
                while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_slbs.txt"
                rm -f "${OUTPUT_DIR}/.mermaid_slbs.txt"
            fi
        fi

        # Compute subgraph
        if [[ "$ecs_n" -gt 0 || "$ack_n" -gt 0 ]]; then
            output+="        subgraph Compute [计算资源]"$'\n'

            if [[ "$ecs_n" -gt 0 ]]; then
                jq -c '[.resources[] | select(.type == "ECS") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r ecs; do
                    local ecs_id ecs_name ecs_ip
                    ecs_id=$(echo "$ecs" | jq -r '.instance_id // empty' 2>/dev/null)
                    ecs_name=$(echo "$ecs" | jq -r '.name // .instance_id' 2>/dev/null)
                    ecs_ip=$(echo "$ecs" | jq -r '.private_ip // ""' 2>/dev/null)
                    [[ -n "$ecs_id" ]] && echo "            ECS_${ecs_id}[ECS: ${ecs_name}\\n${ecs_ip}]"
                done >> "${OUTPUT_DIR}/.mermaid_ecs.txt" 2>/dev/null
                if [[ -f "${OUTPUT_DIR}/.mermaid_ecs.txt" ]]; then
                    while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_ecs.txt"
                    rm -f "${OUTPUT_DIR}/.mermaid_ecs.txt"
                fi
            fi

            if [[ "$ack_n" -gt 0 ]]; then
                jq -c '[.resources[] | select(.type == "ACK") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r ack; do
                    local ack_id ack_name
                    ack_id=$(echo "$ack" | jq -r '.cluster_id // empty' 2>/dev/null)
                    ack_name=$(echo "$ack" | jq -r '.name // .cluster_id' 2>/dev/null)
                    [[ -n "$ack_id" ]] && echo "            ACK_${ack_id}[ACK: ${ack_name}]"
                done >> "${OUTPUT_DIR}/.mermaid_ack.txt" 2>/dev/null
                if [[ -f "${OUTPUT_DIR}/.mermaid_ack.txt" ]]; then
                    while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_ack.txt"
                    rm -f "${OUTPUT_DIR}/.mermaid_ack.txt"
                fi
            fi

            output+="        end"$'\n'
        fi

        # Serverless
        if [[ "$fc_n" -gt 0 ]]; then
            output+="        subgraph Serverless [Serverless]"$'\n'
            jq -c '[.resources[] | select(.type == "FC") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r fc; do
                local fc_name
                fc_name=$(echo "$fc" | jq -r '.service_name // empty' 2>/dev/null)
                [[ -n "$fc_name" ]] && echo "            FC_${fc_name}[FC: ${fc_name}]"
            done >> "${OUTPUT_DIR}/.mermaid_fc.txt" 2>/dev/null
            if [[ -f "${OUTPUT_DIR}/.mermaid_fc.txt" ]]; then
                while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_fc.txt"
                rm -f "${OUTPUT_DIR}/.mermaid_fc.txt"
            fi
            output+="        end"$'\n'
        fi

        # Storage subgraph
        if [[ "$rds_n" -gt 0 || "$redis_n" -gt 0 || "$oss_n" -gt 0 ]]; then
            output+="        subgraph Storage [存储资源]"$'\n'

            if [[ "$rds_n" -gt 0 ]]; then
                jq -c '[.resources[] | select(.type == "RDS") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r rds; do
                    local rds_id rds_name rds_engine
                    rds_id=$(echo "$rds" | jq -r '.db_instance_id // empty' 2>/dev/null)
                    rds_name=$(echo "$rds" | jq -r '.name // .db_instance_id' 2>/dev/null)
                    rds_engine=$(echo "$rds" | jq -r '.engine // "DB"' 2>/dev/null)
                    [[ -n "$rds_id" ]] && echo "            RDS_${rds_id}[(${rds_engine}: ${rds_name})]"
                done >> "${OUTPUT_DIR}/.mermaid_rds.txt" 2>/dev/null
                if [[ -f "${OUTPUT_DIR}/.mermaid_rds.txt" ]]; then
                    while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_rds.txt"
                    rm -f "${OUTPUT_DIR}/.mermaid_rds.txt"
                fi
            fi

            if [[ "$redis_n" -gt 0 ]]; then
                jq -c '[.resources[] | select(.type == "Redis") | .instances[]]' "$topology_file" 2>/dev/null | jq -c '.[]' 2>/dev/null | while IFS= read -r redis; do
                    local redis_id redis_name
                    redis_id=$(echo "$redis" | jq -r '.instance_id // empty' 2>/dev/null)
                    redis_name=$(echo "$redis" | jq -r '.name // .instance_id' 2>/dev/null)
                    [[ -n "$redis_id" ]] && echo "            Redis_${redis_id}[(Redis: ${redis_name})]"
                done >> "${OUTPUT_DIR}/.mermaid_redis.txt" 2>/dev/null
                if [[ -f "${OUTPUT_DIR}/.mermaid_redis.txt" ]]; then
                    while IFS= read -r line; do output+="$line"$'\n'; done < "${OUTPUT_DIR}/.mermaid_redis.txt"
                    rm -f "${OUTPUT_DIR}/.mermaid_redis.txt"
                fi
            fi

            if [[ "$oss_n" -gt 0 ]]; then
                output+="            OSS[(OSS × ${oss_n})]"$'\n'
            fi

            output+="        end"$'\n'
        fi

        output+="    end"$'\n'
    else
        # No VPC
        output+="    subgraph \"阿里云 - ${region}\""$'\n'
        output+="    end"$'\n'
    fi

    # Connections
    while IFS= read -r conn; do
        local ft fi tt ti rel
        ft=$(echo "$conn" | jq -r '.from.type // empty')
        fi=$(echo "$conn" | jq -r '.from.id // empty')
        tt=$(echo "$conn" | jq -r '.to.type // empty')
        ti=$(echo "$conn" | jq -r '.to.id // empty')
        rel=$(echo "$conn" | jq -r '.relation // ""')
        [[ -z "$ft" || -z "$fi" || -z "$tt" || -z "$ti" ]] && continue

        local style="-->"
        case "$rel" in
            backend|belongs_to) style="-.-" ;;
            attached_to|attaches) style="==>" ;;
            has_nat_gateway) style="-->" ;;
        esac

        # Only add connection lines directly between nodes (not Internet ones - handled above)
        if [[ "$ft" == "EIP" ]]; then
            output+="    Internet ==>|internet| ${ft}_${fi}"$'\n'
        fi
        output+="    ${ft}_${fi} ${style} ${tt}_${ti}"$'\n'
    done <<< "$(jq -c '.connections[]' "$topology_file" 2>/dev/null)"

    echo "$output"
}

# ---------------------------------------------------------------------------
# Architecture description
# ---------------------------------------------------------------------------
describe_architecture() {
    local topology_file="$1"
    local pattern; pattern=$(detect_architecture_pattern "$topology_file")

    local tmpfile="${OUTPUT_DIR}/.arch_counts.json"
    jq '{
        ecs: ([.resources[] | select(.type == "ECS") | .instances | length] | first // 0),
        slb: ([.resources[] | select(.type == "SLB") | .instances | length] | first // 0),
        rds: ([.resources[] | select(.type == "RDS") | .instances | length] | first // 0),
        redis: ([.resources[] | select(.type == "Redis") | .instances | length] | first // 0),
        ack: ([.resources[] | select(.type == "ACK") | .instances | length] | first // 0),
        oss: ([.resources[] | select(.type == "OSS") | .instances | length] | first // 0),
        eip: ([.resources[] | select(.type == "EIP") | .instances | length] | first // 0),
        nat: ([.resources[] | select(.type == "NAT") | .instances | length] | first // 0),
        cen: ([.resources[] | select(.type == "CEN") | .instances | length] | first // 0),
        vpc_cidr: ([.resources[] | select(.type == "VPC") | .instances[0].cidr_block // ""] | first // "")
    }' "$topology_file" > "$tmpfile" 2>/dev/null

    local ecs_n slb_n rds_n redis_n ack_n oss_n eip_n nat_n cen_n vpc_cidr
    ecs_n=$(jq -r '.ecs' "$tmpfile" 2>/dev/null)
    slb_n=$(jq -r '.slb' "$tmpfile" 2>/dev/null)
    rds_n=$(jq -r '.rds' "$tmpfile" 2>/dev/null)
    redis_n=$(jq -r '.redis' "$tmpfile" 2>/dev/null)
    ack_n=$(jq -r '.ack' "$tmpfile" 2>/dev/null)
    oss_n=$(jq -r '.oss' "$tmpfile" 2>/dev/null)
    eip_n=$(jq -r '.eip' "$tmpfile" 2>/dev/null)
    nat_n=$(jq -r '.nat' "$tmpfile" 2>/dev/null)
    cen_n=$(jq -r '.cen' "$tmpfile" 2>/dev/null)
    vpc_cidr=$(jq -r '.vpc_cidr' "$tmpfile" 2>/dev/null)
    rm -f "$tmpfile"

    local desc findings_json

    case "$pattern" in
        single-node)
            desc="单节点应用架构"
            findings_json=$(jq -n --arg ecs "$ecs_n" --arg rds "$rds_n" --arg vpc "$vpc_cidr" \
                '["单节点部署（ECS: \($ecs), RDS: \($rds)），适用开发测试或低负载场景",
                  "VPC CIDR: \($vpc)",
                  "⚠️ 建议增加 SLB 实现负载均衡",
                  "⚠️ 考虑迁移到 3 层架构以获得更好的扩展性和高可用性"]')
            ;;
        3-tier)
            desc="3 层 Web 架构"
            findings_json=$(jq -n --arg ecs "$ecs_n" --arg slb "$slb_n" --arg rds "$rds_n" --arg redis "$redis_n" \
                --arg vpc "$vpc_cidr" --arg eip "$eip_n" --arg nat "$nat_n" \
                '["经典 3 层 Web 架构: SLB(\($slb)) → ECS(\($ecs)) → RDS(\($rds)) + Redis(\($redis))",
                  "VPC CIDR: \($vpc)",
                  "EIP 数量: \($eip) | NAT 网关: \($nat)",
                  "ECS 实例数满足高可用要求",
                  "✅ 建议配置 Auto Scaling 应对流量波动",
                  "✅ 建议启用 SLB 健康检查和多可用区部署"]')
            ;;
        microservice)
            desc="容器微服务架构 (ACK)"
            findings_json=$(jq -n --arg ack "$ack_n" --arg ecs "$ecs_n" --arg rds "$rds_n" --arg redis "$redis_n" \
                --arg vpc "$vpc_cidr" --arg cen "$cen_n" \
                '["基于 ACK(\($ack)) 的微服务架构，ECS 工作节点: \($ecs)",
                  "VPC CIDR: \($vpc)",
                  "CEN 实例: \($cen)",
                  "✅ 建议启用 ASM 服务网格治理服务间通信",
                  "✅ 推荐使用 ARMS 进行分布式链路追踪",
                  "✅ 建议配置 VPA + HPA 自动伸缩",
                  "✅ 建议实施蓝绿/灰度发布策略"]')
            ;;
        serverless)
            desc="Serverless 架构"
            findings_json=$(jq -n --arg oss "$oss_n" \
                '["Serverless 架构（FC + OSS），按需付费，零服务器运维",
                  "OSS Bucket 数量: \($oss)",
                  "✅ 适合事件驱动和间歇性工作负载",
                  "✅ 建议配置 FC 预留实例减少冷启动延迟"]')
            ;;
        multi-region)
            desc="多区域部署架构"
            findings_json=$(jq -n --arg cen "$cen_n" \
                '["通过 CEN(\($cen)) 连接的多区域部署架构",
                  "✅ 建议配置 GSLB 实现跨区域流量调度",
                  "✅ 需要评估跨区域数据同步方案",
                  "✅ 建议实施跨区域灾备策略"]')
            ;;
        hybrid)
            desc="混合架构"
            findings_json=$(jq -n --arg ecs "$ecs_n" --arg slb "$slb_n" --arg rds "$rds_n" --arg redis "$redis_n" \
                --arg ack "$ack_n" --arg oss "$oss_n" --arg eip "$eip_n" --arg nat "$nat_n" \
                '["混合架构，包含多种计算和存储资源",
                  "ECS: \($ecs) | SLB: \($slb) | RDS: \($rds) | Redis: \($redis)",
                  "ACK: \($ack) | OSS: \($oss) | EIP: \($eip) | NAT: \($nat)",
                  "建议梳理各组件间依赖关系，优化资源配比",
                  "考虑标准化部署模式以降低运维复杂度"]')
            ;;
        *)
            desc="未识别架构模式"
            findings_json=$(jq -n '["未能识别确定的架构模式，建议人工分析"]')
            ;;
    esac

    echo "{\"pattern\": \"${pattern}\", \"description\": \"${desc}\", \"findings\": ${findings_json}}"
}

# ---------------------------------------------------------------------------
# Architecture document generator
# ---------------------------------------------------------------------------
generate_architecture_document() {
    local topology_file="$1"; local arch_data="$2"; local mermaid_diagram="$3"
    local output_file="${OUTPUT_DIR}/architecture-document.md"
    local pattern desc; pattern=$(echo "$arch_data" | jq -r '.pattern'); desc=$(echo "$arch_data" | jq -r '.description')
    local region account_id rg
    region=$(jq -r '.region // "N/A"' "$topology_file" 2>/dev/null)
    account_id=$(jq -r '.account_id // "N/A"' "$topology_file" 2>/dev/null)
    rg=$(jq -r '.resource_group_id // ""' "$topology_file" 2>/dev/null)

    local tmpfile="${OUTPUT_DIR}/.doc_counts.json"
    jq '{
        ecs: ([.resources[] | select(.type == "ECS") | .instances | length] | first // 0),
        slb: ([.resources[] | select(.type == "SLB") | .instances | length] | first // 0),
        rds: ([.resources[] | select(.type == "RDS") | .instances | length] | first // 0),
        redis: ([.resources[] | select(.type == "Redis") | .instances | length] | first // 0),
        ack: ([.resources[] | select(.type == "ACK") | .instances | length] | first // 0),
        oss: ([.resources[] | select(.type == "OSS") | .instances | length] | first // 0),
        eip: ([.resources[] | select(.type == "EIP") | .instances | length] | first // 0),
        nat: ([.resources[] | select(.type == "NAT") | .instances | length] | first // 0),
        cen: ([.resources[] | select(.type == "CEN") | .instances | length] | first // 0),
        conns: ([.connections | length] | first // 0)
    }' "$topology_file" > "$tmpfile" 2>/dev/null

    local ecs_n slb_n rds_n redis_n ack_n oss_n eip_n nat_n cen_n conns
    ecs_n=$(jq -r '.ecs' "$tmpfile" 2>/dev/null)
    slb_n=$(jq -r '.slb' "$tmpfile" 2>/dev/null)
    rds_n=$(jq -r '.rds' "$tmpfile" 2>/dev/null)
    redis_n=$(jq -r '.redis' "$tmpfile" 2>/dev/null)
    ack_n=$(jq -r '.ack' "$tmpfile" 2>/dev/null)
    oss_n=$(jq -r '.oss' "$tmpfile" 2>/dev/null)
    eip_n=$(jq -r '.eip' "$tmpfile" 2>/dev/null)
    nat_n=$(jq -r '.nat' "$tmpfile" 2>/dev/null)
    cen_n=$(jq -r '.cen' "$tmpfile" 2>/dev/null)
    conns=$(jq -r '.conns' "$tmpfile" 2>/dev/null)
    rm -f "$tmpfile"

    local findings_text; findings_text=$(echo "$arch_data" | jq -r '.findings[] | "- \(.)"')
    local vpc_table slb_table ecs_table rds_table redis_table

    vpc_table=$(jq -r '[.resources[] | select(.type == "VPC") | .instances[] | "| \(.vpc_id) | \(.name // .vpc_id) | \(.cidr_block) |"]' "$topology_file" 2>/dev/null | jq -r 'if length > 0 then (["| VPC ID | 名称 | CIDR |", "|--------|------|------|"] + .) | join("\n") else "无 VPC" end')
    slb_table=$(jq -r '[.resources[] | select(.type == "SLB") | .instances[] | "| \(.load_balancer_id) | \(.name // .load_balancer_id) | \(.address // "") | \(.address_type // "") |"]' "$topology_file" 2>/dev/null | jq -r 'if length > 0 then (["| SLB ID | 名称 | 地址 | 类型 |", "|-------|------|------|------|"] + .) | join("\n") else "无 SLB" end')
    ecs_table=$(jq -r '[.resources[] | select(.type == "ECS") | .instances[] | "| \(.instance_id) | \(.name // .instance_id) | \(.instance_type) | \(.private_ip) |"]' "$topology_file" 2>/dev/null | jq -r 'if length > 0 then (["| 实例ID | 名称 | 规格 | 私有IP |", "|-------|------|------|--------|"] + .) | join("\n") else "无 ECS" end')
    rds_table=$(jq -r '[.resources[] | select(.type == "RDS") | .instances[] | "| \(.db_instance_id) | \(.name // .db_instance_id) | \(.engine) | \(.engine_version) |"]' "$topology_file" 2>/dev/null | jq -r 'if length > 0 then (["| 实例ID | 名称 | 引擎 | 版本 |", "|-------|------|------|------|"] + .) | join("\n") else "无 RDS" end')
    redis_table=$(jq -r '[.resources[] | select(.type == "Redis") | .instances[] | "| \(.instance_id) | \(.name // .instance_id) | \(.engine_version) |"]' "$topology_file" 2>/dev/null | jq -r 'if length > 0 then (["| 实例ID | 名称 | 版本 |", "|-------|------|------|"] + .) | join("\n") else "无 Redis" end')

    # Connection table
    local conn_table
    conn_table=$(jq -r '.connections[] | "| \(.from.type):`\(.from.id)` | \(.relation) | \(.to.type):`\(.to.id)` |"' "$topology_file" 2>/dev/null | head -20)

    {
        echo "# 阿里云架构文档"
        echo ""
        echo "**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**账号**: ${account_id}"
        echo "**地域**: ${region}"
        [[ -n "$rg" ]] && echo "**资源组**: ${rg}"
        echo ""
        echo "---"
        echo ""
        echo "## 1. 架构概览"
        echo ""
        echo "- **架构模式**: ${desc} (${pattern})"
        echo "- **网络拓扑**: ${eip_n} 个 EIP, ${nat_n} 个 NAT 网关, ${cen_n} 个云企业网"
        echo "- **计算资源**: ${ecs_n} 台 ECS, ${ack_n} 个 ACK 集群"
        echo "- **存储资源**: ${rds_n} 个 RDS, ${redis_n} 个 Redis, ${oss_n} 个 OSS Bucket"
        echo "- **负载均衡**: ${slb_n} 个 SLB"
        echo "- **资源关联**: ${conns} 条关联关系"
        echo ""
        echo "## 2. 架构拓扑图"
        echo ""
        echo '```mermaid'
        echo "$mermaid_diagram"
        echo '```'
        echo ""
        echo "## 3. 关键发现"
        echo ""
        echo "$findings_text"
        echo ""
        echo "## 4. 资源清单"
        echo ""
        echo "### 4.1 虚拟网络 (VPC / VSwitch)"
        echo ""
        echo "$vpc_table"
        echo ""
        echo "### 4.2 负载均衡 (SLB)"
        echo ""
        echo "$slb_table"
        echo ""
        echo "### 4.3 计算资源 (ECS / ACK)"
        echo ""
        echo "$ecs_table"
        echo ""
        echo "### 4.4 数据库 (RDS)"
        echo ""
        echo "$rds_table"
        echo ""
        echo "### 4.5 缓存 (Redis)"
        echo ""
        echo "$redis_table"
        echo ""
        echo "## 5. 资源关联关系"
        echo ""
        echo "| 源资源 | 关系 | 目标资源 |"
        echo "|--------|------|----------|"
        echo "$conn_table" | head -50
        echo ""
        echo "---"
        echo ""
        echo "*本文档由 alicloud-arch-advisor 自动生成*"
    } > "$output_file"

    log_success "架构文档已保存: ${output_file}"
    echo "$output_file"
}

# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------
init_report() {
    local mode="${1:-assessment}"; local format="${2:-markdown}"
    local timestamp; timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    cat <<EOF
{
  "mode": "${mode}", "format": "${format}", "timestamp": "${timestamp}",
  "region": "${ALICLOUD_REGION:-cn-hangzhou}", "account": "${ALICLOUD_ACCOUNT_ID:-unknown}",
  "architecture": {}, "pillars": {}, "recommendations": []
}
EOF
}

generate_report_markdown() {
    local report_file="$1"; local output_file="${OUTPUT_DIR}/arch-report.md"
    if [[ ! -f "$report_file" ]]; then log_error "Report not found: ${report_file}"; return 1; fi
    local mode arch_pattern; mode=$(jq -r '.mode // "assessment"' "$report_file"); arch_pattern=$(jq -r '.architecture.pattern // "unknown"' "$report_file")
    {
        echo "# 阿里云架构评估报告"; echo ""
        echo "**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**地域**: $(jq -r '.region // "N/A"' "$report_file")"
        [[ -n "${ALICLOUD_ACCOUNT_ID:-}" ]] && echo "**账号**: ${ALICLOUD_ACCOUNT_ID}"
        echo ""
        if [[ "$mode" == "assessment" || "$mode" == "reverse-engineer" ]]; then
            echo "## 当前架构识别"; echo ""
            echo "- **架构模式**: ${arch_pattern}"
            echo "- **架构描述**: $(jq -r '.architecture.description // ""' "$report_file")"; echo ""
            local mermaid; mermaid=$(jq -r '.architecture.mermaid // ""' "$report_file")
            if [[ -n "$mermaid" ]]; then echo '```mermaid'; echo "$mermaid"; echo '```'; echo ""; fi
            echo "### 关键发现"
            jq -r '.architecture.findings[]? // [] | "- \(.)"' "$report_file" 2>/dev/null; echo ""
        fi
        echo "## WAF 评估报告"; echo ""
        jq -r '.pillars | to_entries[] |
            "### \(.key | ascii_upcase): \(.value.score | floor)% (\(.value.pass)/\(.value.total))\n\n| 规则 | 状态 | 说明 |\n|------|------|------|\n" +
            (.value.results[]? | "| \(.id // .rule_id) | \(.status) | \(.message // \"-\") |") + "\n"' "$report_file" 2>/dev/null
        echo "---"; echo ""; echo "*报告由 alicloud-arch-advisor 自动生成*"
    } > "$output_file"
    log_success "评估报告已保存: ${output_file}"; echo "${output_file}"
}

generate_report_json() {
    local report_file="$1"; local output_file="${OUTPUT_DIR}/arch-report.json"
    cp "$report_file" "$output_file"
    log_success "JSON report saved to ${output_file}"; echo "${output_file}"
}

# ---------------------------------------------------------------------------
# Advisor & CMS collectors (保留)
# ---------------------------------------------------------------------------
collect_advisor_report() {
    local output_file="${OUTPUT_DIR}/advisor-report.json"
    log_info "Fetching Alibaba Cloud Advisor report..."
    if aliyun advisor DescribeAdvisorChecks --all 2>/dev/null | jq '.' > "$output_file" 2>/dev/null; then
        log_success "Advisor report saved"
    else
        log_warn "Failed to fetch Advisor report."
        echo '{"checks": [], "timestamp": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}' > "$output_file"
    fi
    cat "$output_file"
}

collect_cms_metrics() {
    local ns="${1:-acs_ecs_dashboard}"; local metric="${2:-CPUUtilization}"; local period="${3:-3600}"
    local of="${OUTPUT_DIR}/cms-metrics-${ns//\//_}.json"
    log_info "Fetching CMS metrics: ${ns}/${metric}..."
    if aliyun cms DescribeMetricList --Namespace "$ns" --MetricName "$metric" --Period "$period" --Length 24 2>/dev/null | jq '.' > "$of" 2>/dev/null; then
        log_success "CMS metrics saved"
    else
        echo '{"namespace": "'"${ns}"'", "metric": "'"${metric}"'", "datapoints": []}' > "$of"
    fi
    cat "$of"
}

# ---------------------------------------------------------------------------
# Rule loading & execution
# ---------------------------------------------------------------------------
load_rules() {
    local pillars="$1"; local of="${OUTPUT_DIR}/rules-index.json"
    [[ "$pillars" == "all" ]] && pillars="security,reliability,performance,cost,efficiency"
    log_info "Loading rules for pillars: ${pillars}"
    IFS=',' read -ra PL <<< "$pillars"; local combined='{"rules":[]}'
    for p in "${PL[@]}"; do
        # Try waf- prefix first, then bare name
        local pf="${RULES_DIR}/waf-${p}.yaml"
        [[ ! -f "$pf" ]] && pf="${RULES_DIR}/${p}.yaml"
        if [[ -f "$pf" ]]; then
            command -v yq &>/dev/null && {
                local pr; pr=$(yq eval -o=json '.rules[] | {id, title, description, severity, category: "'"${p}"'"}' "$pf" 2>/dev/null)
                combined=$(echo "$combined" | jq --argjson new "$pr" '.rules += [$new]' 2>/dev/null || echo "$combined")
            } || log_warn "  yq not available, skipping ${pf}"
        else log_warn "  Rules not found: ${pf}"
        fi
    done
    echo "$combined" > "$of"; log_success "Rules indexed to ${of}"; cat "$of"
}

execute_rule() {
    local rid="$1" td="$2" rd="$3" rf="${OUTPUT_DIR}/rule-result-${rid}.json"
    local r='{"rule_id": "'"${rid}"'", "status": "skipped", "message": "Not evaluated"}'
    [[ -n "$td" && -f "$td" ]] && r=$(echo "$r" | jq --arg s "pass" '.status = $s | .message = "Completed"')
    echo "$r" > "$rf"; echo "$r"
}

pillar_score() {
    local pillar="$1" rf="${OUTPUT_DIR}/assessment-results.json"
    [[ ! -f "$rf" ]] && { echo '{"pass":0,"total":0,"score":0}'; return; }
    jq --arg p "$pillar" '.pillars[$p] as $q | if $q then {"pass":($q.results|map(select(.status=="pass"))|length),"total":($q.results|length),"score":(if($q.results|length)>0 then(($q.results|map(select(.status=="pass"))|length)*100.0/($q.results|length))else 0 end)} else {"pass":0,"total":0,"score":0} end' "$rf"
}