#!/bin/bash
# network-diagnostic-suite.sh v2.0
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:-$(curl -s http://100.100.100.200/latest/meta-data/instance-id 2>/dev/null || echo 'unknown')}"
REGION="${REGION:-$(curl -s http://100.100.100.200/latest/meta-data/region-id 2>/dev/null || echo 'unknown')}"
REPORT_DIR="/tmp/net-diag-reports"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT_JSON="${REPORT_DIR}/net-diag-${INSTANCE_ID}-${TIMESTAMP}.json"
REPORT_MD="${REPORT_DIR}/net-diag-${INSTANCE_ID}-${TIMESTAMP}.md"
mkdir -p "${REPORT_DIR}"
echo "==== ECS Network Diagnostic Suite v2.0 ===="
echo "Instance: ${INSTANCE_ID} | Region: ${REGION}"
# Phase 0: Detect interface & network type
ACTIVE_IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -v lo | head -1 | sed 's/@.*//')
[ -z "${ACTIVE_IFACE}" ] && ACTIVE_IFACE="eth0"
echo "Active interface: ${ACTIVE_IFACE}"
DEFAULT_GW=$(ip route show default | awk '{print $3}' 2>/dev/null || echo "")
# Check public IP via ECS metadata
HAS_PUBLIC_IP=false
ECS_PUBLIC_IP=$(curl -s --connect-timeout 2 http://100.100.100.200/latest/meta-data/public-ipv4 2>/dev/null || echo "")
[ -n "${ECS_PUBLIC_IP}" ] && HAS_PUBLIC_IP=true
echo "Network type: $($HAS_PUBLIC_IP && echo 'public' || echo 'intranet-only')"
# Phase 1: Tool check
echo "[PHASE-1] Tool Pre-flight"
for cmd in ip ss ping route sysctl cat awk; do
  command -v "$cmd" >/dev/null 2>&1 && echo "  OK: $cmd" || { echo "  MISS: $cmd"; exit 1; }
done
for cmd in ethtool tcpdump mtr sar nstat; do
  command -v "$cmd" >/dev/null 2>&1 && echo "  OK(opt): $cmd" || echo "  MISS(opt): $cmd"
done
# Phase 2: Baseline
echo "[PHASE-2] Baseline"
BASELINE_CONN=$(ss -s | head -1 || echo "N/A")
BASELINE_DEV=$(cat /proc/net/dev | awk -v iface="${ACTIVE_IFACE}" '$1 ~ iface":" {print}')
BASELINE_ROUTE=$(ip route show 2>/dev/null || echo "N/A")
NIC_STATS="N/A"; NIC_DRIVER="N/A"
if command -v ethtool >/dev/null 2>&1; then
  NIC_STATS=$(ethtool -S "${ACTIVE_IFACE}" 2>/dev/null | grep -iE "(drop|error|overrun|discard|miss)" || echo "clean")
  NIC_DRIVER=$(ethtool -i "${ACTIVE_IFACE}" 2>/dev/null | grep driver | awk '{print $2}' || echo "N/A")
fi
echo "  NIC driver: ${NIC_DRIVER}"
# Phase 3: Connectivity (single ping)
echo "[PHASE-3] Connectivity"
PING_TARGET="${DEFAULT_GW:-127.0.0.1}"
$HAS_PUBLIC_IP && PING_TARGET="223.5.5.5"
echo "  Target: ${PING_TARGET}"
PO=$(ping -c 5 -i 0.2 -W 2 "${PING_TARGET}" 2>/dev/null || echo "FAIL")
PG=$(echo "${PO}" | tail -1 | awk -F/ '{print $5}' || echo "N/A")
PL=$(echo "${PO}" | grep -oP '\d+(?=% packet loss)' || echo "100")
echo "  RTT=${PG}ms loss=${PL}%"
# Phase 4: Workload
echo "[PHASE-4] Workload"
RX1=$(cat /proc/net/dev | awk -v iface="${ACTIVE_IFACE}" '$1 ~ iface":" {print $2}')
TX1=$(cat /proc/net/dev | awk -v iface="${ACTIVE_IFACE}" '$1 ~ iface":" {print $10}')
WLM="idle-sampling"
if $HAS_PUBLIC_IP; then
  echo "  Downloading test file..."
  curl -s -o /dev/null --connect-timeout 5 --max-time 10 https://speedtest.tele2.net/10MB.zip 2>/dev/null || true &
  CP=$!; sleep 12; kill $CP 2>/dev/null || true; wait $CP 2>/dev/null || true
  WLM="curl-download"
else
  echo "  Intranet-only, sampling 10s..."
  sleep 10
fi
RX2=$(cat /proc/net/dev | awk -v iface="${ACTIVE_IFACE}" '$1 ~ iface":" {print $2}')
TX2=$(cat /proc/net/dev | awk -v iface="${ACTIVE_IFACE}" '$1 ~ iface":" {print $10}')
DRX=$((RX2-RX1)); DTX=$((TX2-TX1))
echo "  Delta RX=${DRX}B TX=${DTX}B"

# Phase 5: Post-load + nstat
echo "[PHASE-5] Post-load + Advanced"
SS=$(ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn | head -5)
echo "$SS"
NSTAT_OUT=""
if command -v nstat >/dev/null 2>&1; then
  NSTAT_OUT=$(nstat -az | grep -v " 0$" | head -20 || echo "all-zero")
  echo "nstat:"
  echo "${NSTAT_OUT}"
fi
# Ephemeral ports
PR=$(cat /proc/sys/net/ipv4/ip_local_port_range 2>/dev/null || echo "")
if [ -n "${PR}" ]; then
  S=$(echo "${PR}" | awk '{print $1}'); E=$(echo "${PR}" | awk '{print $2}')
  TP=$((E-S+1)); TW=$(ss -tan state time-wait 2>/dev/null | tail -n +2 | wc -l || echo 0)
  echo "Port range: ${S}-${E} (${TP} total, TIME_WAIT=${TW})"
fi

# Phase 6: Tuning
echo "[PHASE-6] Tuning Audit"
echo "tcp_cc=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo N/A)"
echo "somaxconn=$(sysctl -n net.core.somaxconn 2>/dev/null || echo N/A)"
echo "backlog=$(sysctl -n net.core.netdev_max_backlog 2>/dev/null || echo N/A)"
echo "conntrack=$(sysctl -n net.netfilter.nf_conntrack_max 2>/dev/null || echo N/A)"

# Phase 7: JSON report
cat > "${REPORT_JSON}" <<JSONEOF
{
  "report_id": "net-diag-${INSTANCE_ID}-${TIMESTAMP}",
  "suite_version": "2.0",
  "instance_id": "${INSTANCE_ID}",
  "region": "${REGION}",
  "network_type": "$($HAS_PUBLIC_IP && echo 'public' || echo 'intranet-only')",
  "active_interface": "${ACTIVE_IFACE}",
  "nic_driver": "${NIC_DRIVER}",
  "phases": {
    "baseline": {"connections": "${BASELINE_CONN}"},
    "connectivity": {"target": "${PING_TARGET}", "avg_rtt_ms": "${PG}", "loss_pct": "${PL}"},
    "workload": {"method": "${WLM}"},
    "post_load": {"delta_rx_bytes": ${DRX}, "delta_tx_bytes": ${DTX}}
  },
  "verdict": "Suite complete."
}
JSONEOF

# Markdown report
cat > "${REPORT_MD}" <<MDEOF
# ECS Network Diagnostic Report v2.0

## Instance
| Field | Value |
|-------|-------|
| ID | ${INSTANCE_ID} |
| Region | ${REGION} |
| Type | $($HAS_PUBLIC_IP && echo 'Public' || echo 'Intranet-Only') |
| Interface | ${ACTIVE_IFACE} |
| NIC Driver | ${NIC_DRIVER} |
| Gateway | ${DEFAULT_GW:-N/A} |

## Connectivity
| Target | RTT(ms) | Loss(%) |
|--------|:-------:|:-------:|
| ${PING_TARGET} | ${PG} | ${PL} |

## Tuning
| Parameter | Value |
|-----------|-------|
| tcp_cc | $(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo N/A) |
| somaxconn | $(sysctl -n net.core.somaxconn 2>/dev/null || echo N/A) |

## Kernel TCP (nstat)
\`\`\`
${NSTAT_OUT}
\`\`\`

## Ephemeral Ports
Range: ${S:-N/A}-${E:-N/A} | Total: ${TP:-N/A} | TIME_WAIT: ${TW:-N/A}

## Workload
RX Delta: ${DRX} bytes | TX Delta: ${DTX} bytes

## Verdict
Suite v2.0 completed. Full JSON: ${REPORT_JSON}
MDEOF

echo "Done."
echo "JSON: ${REPORT_JSON}"
echo "MD: ${REPORT_MD}"
