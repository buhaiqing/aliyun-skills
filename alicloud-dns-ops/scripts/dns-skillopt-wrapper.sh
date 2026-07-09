#!/usr/bin/env bash
# =============================================================================
# DNS SkillOpt Wrapper — alicloud-dns-ops
# =============================================================================
# This wrapper provides self-repair and dynamic optimization for DNS operations.
# It sources the shared SkillOpt core library for common functionality.
#
# Usage: ./dns-skillopt-wrapper.sh <subcommand> [options]
#
# Subcommands:
#   alidns <operation> [options]  - Public Authoritative DNS operations
#   pvtz <operation> [options]    - PrivateZone operations
#   health                        - Health check for wrapper
#   version                       - Show wrapper version
#
# Environment Variables:
#   ALIBABA_CLOUD_ACCESS_KEY_ID     - Access Key ID (required)
#   ALIBABA_CLOUD_ACCESS_KEY_SECRET - Access Key Secret (required)
#   ALIBABA_CLOUD_REGION_ID         - Region ID (optional, default: cn-hangzhou)
#   SKILLOPT_ENABLED                - Enable SkillOpt features (optional)
#   SKILLOPT_LOG_LABEL              - Log label for this skill (optional)
# =============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Skill metadata
SKILL_NAME="alicloud-dns-ops"
SKILL_TAG="alicloud-dns-ops"
SKILL_VERSION="1.0.0"

# Set skill root directory
_SKILLOPT_SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SKILLOPT_SKILL_TAG="alicloud-dns-ops"
export SKILLOPT_SKILL_NAME="alicloud-dns-ops"
export SKILLOPT_LOG_LABEL="DNS-SkillOpt"
export SKILLOPT_LOG_FILE=""  # Initialize empty to avoid unbound variable

# Load shared SkillOpt core library
if [[ -f "$SCRIPT_DIR/../../alicloud-skillopt-ops/scripts/skillopt-core-lib.sh" ]]; then
    # Source paths first via legacy shim
    if [[ -f "$SCRIPT_DIR/../../alicloud-skillopt-ops/scripts/skillopt-paths.sh" ]]; then
        source "$SCRIPT_DIR/../../alicloud-skillopt-ops/scripts/skillopt-paths.sh"
        if [[ $? -ne 0 ]]; then
            echo "ERROR: Failed to source skillopt-paths.sh" >&2
            exit 1
        fi
    else
        echo "ERROR: skillopt-paths.sh not found" >&2
        exit 1
    fi
    source "$SCRIPT_DIR/../../alicloud-skillopt-ops/scripts/skillopt-core-lib.sh"
elif [[ -f "$SCRIPT_DIR/../../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh" ]]; then
    # Load paths first
    if [[ -f "$SCRIPT_DIR/../../alicloud-runtime-harness-ops/scripts/harness-paths.sh" ]]; then
        source "$SCRIPT_DIR/../../alicloud-runtime-harness-ops/scripts/harness-paths.sh"
        local paths_status=$?
        if [[ $paths_status -ne 0 ]]; then
            echo "ERROR: Failed to source harness-paths.sh (exit code: $paths_status)" >&2
            exit 1
        fi
    else
        echo "ERROR: harness-paths.sh not found" >&2
        exit 1
    fi
    
    # Source core library
    source "$SCRIPT_DIR/../../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh"
    local core_status=$?
    if [[ $core_status -ne 0 ]]; then
        echo "ERROR: Failed to source harness-core-lib.sh (exit code: $core_status)" >&2
        exit 1
    fi
else
    echo "ERROR: SkillOpt core library not found" >&2
    exit 1
fi

# Initialize SkillOpt for this skill
skillopt_init "$SKILL_NAME" "$SKILL_TAG" || {
    echo "ERROR: skillopt_init failed" >&2
    exit 1
}

# =============================================================================
# Helper Functions
# =============================================================================

# Validate DNS record format
validate_dns_record() {
    local record_type="$1"
    local record_value="$2"
    
    case "$record_type" in
        A)
            if [[ ! "$record_value" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                echo "ERROR: Invalid IPv4 address format: $record_value" >&2
                return 1
            fi
            ;;
        AAAA)
            if [[ ! "$record_value" =~ ^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$ ]]; then
                echo "ERROR: Invalid IPv6 address format: $record_value" >&2
                return 1
            fi
            ;;
        CNAME|NS)
            if [[ ! "$record_value" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.?$ ]]; then
                echo "ERROR: Invalid domain name format: $record_value" >&2
                return 1
            fi
            ;;
        MX)
            if [[ ! "$record_value" =~ ^[0-9]{1,3}\ +[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.?$ ]]; then
                echo "ERROR: Invalid MX record format: $record_value" >&2
                return 1
            fi
            ;;
        TXT)
            if [[ ${#record_value} -gt 255 ]]; then
                echo "ERROR: TXT record too long (max 255 characters): ${#record_value}" >&2
                return 1
            fi
            ;;
        SRV)
            if [[ ! "$record_value" =~ ^[0-9]{1,3}\ +[0-9]{1,3}\ +[0-9]{1,5}\ +[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.?$ ]]; then
                echo "ERROR: Invalid SRV record format: $record_value" >&2
                return 1
            fi
            ;;
        CAA)
            if [[ ! "$record_value" =~ ^[0-9]{1,3}\ +[a-z]+\ +".*"$ ]]; then
                echo "ERROR: Invalid CAA record format: $record_value" >&2
                return 1
            fi
            ;;
        *)
            echo "ERROR: Unsupported record type: $record_type" >&2
            return 1
            ;;
    esac
    
    return 0
}

# Validate TTL value
validate_ttl() {
    local ttl="$1"
    
    if [[ ! "$ttl" =~ ^[0-9]+$ ]]; then
        echo "ERROR: TTL must be a number: $ttl" >&2
        return 1
    fi
    
    if [[ "$ttl" -lt 60 || "$ttl" -gt 86400 ]]; then
        echo "ERROR: TTL must be between 60 and 86400 seconds: $ttl" >&2
        return 1
    fi
    
    return 0
}

# Validate weight value
validate_weight() {
    local weight="$1"
    
    if [[ ! "$weight" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Weight must be a number: $weight" >&2
        return 1
    fi
    
    if [[ "$weight" -lt 1 || "$weight" -gt 100 ]]; then
        echo "ERROR: Weight must be between 1 and 100: $weight" >&2
        return 1
    fi
    
    return 0
}

# Check domain exists
check_domain_exists() {
    local domain_name="$1"
    
    local result
    result=$(aliyun alidns DescribeDomainInfo --DomainName "$domain_name" 2>/dev/null) || {
        echo "ERROR: Domain not found in DNS service: $domain_name" >&2
        return 1
    }
    
    return 0
}

# Check record conflicts
check_record_conflicts() {
    local domain_name="$1"
    local record_name="$2"
    local record_type="$3"
    
    # Check for CNAME conflicts
    if [[ "$record_type" == "CNAME" ]]; then
        local a_records
        a_records=$(aliyun alidns DescribeDomainRecords \
            --DomainName "$domain_name" \
            --RRKeyWord "$record_name" \
            --TypeKeyWord "A" 2>/dev/null | jq '.DomainRecords.Record | length') || a_records=0
        
        local aaaa_records
        aaaa_records=$(aliyun alidns DescribeDomainRecords \
            --DomainName "$domain_name" \
            --RRKeyWord "$record_name" \
            --TypeKeyWord "AAAA" 2>/dev/null | jq '.DomainRecords.Record | length') || aaaa_records=0
        
        if [[ "$a_records" -gt 0 || "$aaaa_records" -gt 0 ]]; then
            echo "ERROR: Cannot add CNAME record when A/AAAA records exist" >&2
            return 1
        fi
    fi
    
    # Check for A/AAAA conflicts with CNAME
    if [[ "$record_type" == "A" || "$record_type" == "AAAA" ]]; then
        local cname_records
        cname_records=$(aliyun alidns DescribeDomainRecords \
            --DomainName "$domain_name" \
            --RRKeyWord "$record_name" \
            --TypeKeyWord "CNAME" 2>/dev/null | jq '.DomainRecords.Record | length') || cname_records=0
        
        if [[ "$cname_records" -gt 0 ]]; then
            echo "ERROR: Cannot add A/AAAA record when CNAME record exists" >&2
            return 1
        fi
    fi
    
    return 0
}

# =============================================================================
# Main Subcommand Handlers
# =============================================================================

# Handle alidns operations
handle_alidns() {
    local operation="$1"
    shift
    
    case "$operation" in
        AddDomain)
            local domain_name="$1"
            echo "Adding domain: $domain_name"
            aliyun alidns AddDomain --DomainName "$domain_name"
            ;;
            
        DescribeDomains)
            aliyun alidns DescribeDomains "$@"
            ;;
            
        DescribeDomainInfo)
            local domain_name="$1"
            aliyun alidns DescribeDomainInfo --DomainName "$domain_name"
            ;;
            
        DeleteDomain)
            local domain_name="$1"
            echo "WARNING: Deleting domain will remove all records" >&2
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted" >&2
                return 1
            fi
            aliyun alidns DeleteDomain --DomainName "$domain_name"
            ;;
            
        AddRecord)
            local domain_name="" record_name="" record_type="" record_value="" ttl=600 line="default" weight=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --DomainName) domain_name="$2"; shift 2 ;;
                    --RR) record_name="$2"; shift 2 ;;
                    --Type) record_type="$2"; shift 2 ;;
                    --Value) record_value="$2"; shift 2 ;;
                    --TTL) ttl="$2"; shift 2 ;;
                    --Line) line="$2"; shift 2 ;;
                    --Weight) weight="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            # Validate inputs
            if [[ -z "$domain_name" || -z "$record_name" || -z "$record_type" || -z "$record_value" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            validate_dns_record "$record_type" "$record_value" || return 1
            validate_ttl "$ttl" || return 1
            
            if [[ -n "$weight" ]]; then
                validate_weight "$weight" || return 1
            fi
            
            check_domain_exists "$domain_name" || return 1
            check_record_conflicts "$domain_name" "$record_name" "$record_type" || return 1
            
            echo "Adding $record_type record for $record_name.$domain_name"
            local cmd="aliyun alidns AddRecord --DomainName $domain_name --RR $record_name --Type $record_type --Value $record_value --TTL $ttl --Line $line"
            
            if [[ -n "$weight" ]]; then
                cmd="$cmd --Weight $weight"
            fi
            
            eval "$cmd"
            ;;
            
        UpdateDomainRecord)
            local record_id="" record_name="" record_type="" record_value="" ttl=600 line="default" weight=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --RecordId) record_id="$2"; shift 2 ;;
                    --RR) record_name="$2"; shift 2 ;;
                    --Type) record_type="$2"; shift 2 ;;
                    --Value) record_value="$2"; shift 2 ;;
                    --TTL) ttl="$2"; shift 2 ;;
                    --Line) line="$2"; shift 2 ;;
                    --Weight) weight="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            # Validate inputs
            if [[ -z "$record_id" || -z "$record_name" || -z "$record_type" || -z "$record_value" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            validate_dns_record "$record_type" "$record_value" || return 1
            validate_ttl "$ttl" || return 1
            
            if [[ -n "$weight" ]]; then
                validate_weight "$weight" || return 1
            fi
            
            echo "Updating record: $record_id"
            local cmd="aliyun alidns UpdateDomainRecord --RecordId $record_id --RR $record_name --Type $record_type --Value $record_value --TTL $ttl --Line $line"
            
            if [[ -n "$weight" ]]; then
                cmd="$cmd --Weight $weight"
            fi
            
            eval "$cmd"
            ;;
            
        DeleteDomainRecord)
            local record_id="$1"
            
            echo "WARNING: Deleting record $record_id" >&2
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted" >&2
                return 1
            fi
            
            aliyun alidns DeleteDomainRecord --RecordId "$record_id"
            ;;
            
        DescribeDomainRecords)
            aliyun alidns DescribeDomainRecords "$@"
            ;;
            
        EnableDomainRecord)
            local record_id="$1"
            aliyun alidns EnableDomainRecord --RecordId "$record_id"
            ;;
            
        DisableDomainRecord)
            local record_id="$1"
            aliyun alidns DisableDomainRecord --RecordId "$record_id"
            ;;
            
        DescribeLines)
            local domain_name="$1"
            aliyun alidns DescribeLines --DomainName "$domain_name"
            ;;
            
        AddGtmAddressPool)
            local name="" type="" addr=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --Name) name="$2"; shift 2 ;;
                    --Type) type="$2"; shift 2 ;;
                    --Addr) addr="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$name" || -z "$type" || -z "$addr" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun alidns AddGtmAddressPool --Name "$name" --Type "$type" --Addr "$addr"
            ;;
            
        UpdateGtmAddressPool)
            local pool_id="" health_check_config=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --PoolId) pool_id="$2"; shift 2 ;;
                    --HealthCheckConfig) health_check_config="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$pool_id" || -z "$health_check_config" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun alidns UpdateGtmAddressPool --PoolId "$pool_id" --HealthCheckConfig "$health_check_config"
            ;;
            
        DescribeGtmInstanceStatus)
            local instance_id="$1"
            aliyun alidns DescribeGtmInstanceStatus --InstanceId "$instance_id"
            ;;
            
        SwitchGtmFailoverAddressPool)
            local instance_id="$1"
            echo "WARNING: Triggering GTM failover" >&2
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted" >&2
                return 1
            fi
            
            aliyun alidns SwitchGtmFailoverAddressPool --InstanceId "$instance_id"
            ;;
            
        EnableDnssec)
            local domain_name="$1"
            aliyun alidns EnableDnssec --DomainName "$domain_name"
            ;;
            
        DisableDnssec)
            local domain_name="$1"
            aliyun alidns DisableDnssec --DomainName "$domain_name"
            ;;
            
        DescribeDnssecStatus)
            local domain_name="$1"
            aliyun alidns DescribeDnssecStatus --DomainName "$domain_name"
            ;;
            
        DescribeDnsLogs)
            local domain_name="" start_date="" end_date=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --DomainName) domain_name="$2"; shift 2 ;;
                    --StartDate) start_date="$2"; shift 2 ;;
                    --EndDate) end_date="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$domain_name" || -z "$start_date" || -z "$end_date" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun alidns DescribeDnsLogs --DomainName "$domain_name" --StartDate "$start_date" --EndDate "$end_date"
            ;;
            
        *)
            echo "ERROR: Unknown alidns operation: $operation" >&2
            return 1
            ;;
    esac
}

# Handle pvtz operations
handle_pvtz() {
    local operation="$1"
    shift
    
    case "$operation" in
        CreateZone)
            local zone_name="" remark=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --ZoneName) zone_name="$2"; shift 2 ;;
                    --Remark) remark="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$zone_name" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun pvtz CreateZone --ZoneName "$zone_name" --Remark "$remark"
            ;;
            
        DescribeZones)
            aliyun pvtz DescribeZones "$@"
            ;;
            
        DescribeZoneInfo)
            local zone_id="$1"
            aliyun pvtz DescribeZoneInfo --ZoneId "$zone_id"
            ;;
            
        DeleteZone)
            local zone_id="$1"
            echo "WARNING: Deleting PrivateZone $zone_id" >&2
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted" >&2
                return 1
            fi
            
            aliyun pvtz DeleteZone --ZoneId "$zone_id"
            ;;
            
        AddZoneRecord)
            local zone_id="" rr="" type="" value=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --ZoneId) zone_id="$2"; shift 2 ;;
                    --Rr) rr="$2"; shift 2 ;;
                    --Type) type="$2"; shift 2 ;;
                    --Value) value="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$zone_id" || -z "$rr" || -z "$type" || -z "$value" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            validate_dns_record "$type" "$value" || return 1
            
            aliyun pvtz AddZoneRecord --ZoneId "$zone_id" --Rr "$rr" --Type "$type" --Value "$value"
            ;;
            
        DescribeZoneRecords)
            aliyun pvtz DescribeZoneRecords "$@"
            ;;
            
        UpdateZoneRecord)
            local record_id="" rr="" type="" value=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --RecordId) record_id="$2"; shift 2 ;;
                    --Rr) rr="$2"; shift 2 ;;
                    --Type) type="$2"; shift 2 ;;
                    --Value) value="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$record_id" || -z "$rr" || -z "$type" || -z "$value" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            validate_dns_record "$type" "$value" || return 1
            
            aliyun pvtz UpdateZoneRecord --RecordId "$record_id" --Rr "$rr" --Type "$type" --Value "$value"
            ;;
            
        DeleteZoneRecord)
            local record_id="$1"
            echo "WARNING: Deleting PrivateZone record $record_id" >&2
            read -p "Are you sure? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted" >&2
                return 1
            fi
            
            aliyun pvtz DeleteZoneRecord --RecordId "$record_id"
            ;;
            
        BindZoneVpc)
            local zone_id="" vpcs=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --ZoneId) zone_id="$2"; shift 2 ;;
                    --Vpcs) vpcs="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$zone_id" || -z "$vpcs" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun pvtz BindZoneVpc --ZoneId "$zone_id" --Vpcs "$vpcs"
            ;;
            
        UnbindZoneVpc)
            local zone_id="" vpcs=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --ZoneId) zone_id="$2"; shift 2 ;;
                    --Vpcs) vpcs="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$zone_id" || -z "$vpcs" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun pvtz UnbindZoneVpc --ZoneId "$zone_id" --Vpcs "$vpcs"
            ;;
            
        DescribeZoneVpcList)
            local zone_id="$1"
            aliyun pvtz DescribeZoneVpcList --ZoneId "$zone_id"
            ;;
            
        AddForwardRule)
            local zone_name="" vpcs=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --ZoneName) zone_name="$2"; shift 2 ;;
                    --Vpcs) vpcs="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            
            if [[ -z "$zone_name" || -z "$vpcs" ]]; then
                echo "ERROR: Missing required parameters" >&2
                return 1
            fi
            
            aliyun pvtz AddForwardRule --ZoneName "$zone_name" --Vpcs "$vpcs"
            ;;
            
        *)
            echo "ERROR: Unknown pvtz operation: $operation" >&2
            return 1
            ;;
    esac
}

# Health check
handle_health() {
    echo "DNS SkillOpt Wrapper Health Check"
    echo "=================================="
    echo "Skill: $SKILL_NAME"
    echo "Version: $SKILL_VERSION"
    echo "Wrapper: $0"
    echo ""
    
    # Check credentials
    if [[ -z "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" || -z "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
        echo "ERROR: Credentials not set" >&2
        return 1
    fi
    
    echo "Credentials: OK"
    
    # Check aliyun CLI
    if ! command -v aliyun &> /dev/null; then
        echo "ERROR: aliyun CLI not found" >&2
        return 1
    fi
    
    echo "aliyun CLI: OK"
    
    # Check SkillOpt core library
    if [[ -f "$SCRIPT_DIR/../../alicloud-skillopt-ops/scripts/skillopt-core-lib.sh" ]]; then
        echo "SkillOpt Core: OK"
    elif [[ -f "$SCRIPT_DIR/../../alicloud-runtime-harness-ops/scripts/harness-core-lib.sh" ]]; then
        echo "Harness Core: OK"
    else
        echo "ERROR: Core library not found" >&2
        return 1
    fi
    
    echo ""
    echo "All checks passed"
    return 0
}

# Show version
handle_version() {
    echo "DNS SkillOpt Wrapper"
    echo "Skill: $SKILL_NAME"
    echo "Version: $SKILL_VERSION"
    echo "Wrapper: $0"
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    local command="${1:-}"
    shift || true
    
    case "$command" in
        alidns)
            handle_alidns "$@"
            ;;
        pvtz)
            handle_pvtz "$@"
            ;;
        health)
            handle_health
            ;;
        version)
            handle_version
            ;;
        *)
            echo "Usage: $0 <command> [options]" >&2
            echo "" >&2
            echo "Commands:" >&2
            echo "  alidns <operation> [options]  - Public Authoritative DNS operations" >&2
            echo "  pvtz <operation> [options]    - PrivateZone operations" >&2
            echo "  health                        - Health check for wrapper" >&2
            echo "  version                       - Show wrapper version" >&2
            echo "" >&2
            echo "Examples:" >&2
            echo "  $0 alidns AddDomain example.com" >&2
            echo "  $0 alidns AddRecord --DomainName example.com --RR www --Type A --Value 1.2.3.4" >&2
            echo "  $0 pvtz CreateZone --ZoneName internal.example.com" >&2
            echo "  $0 health" >&2
            return 1
            ;;
    esac
}

main "$@"