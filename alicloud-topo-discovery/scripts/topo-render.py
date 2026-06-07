#!/usr/bin/env python3
"""Topology renderer — ASCII tree, Mermaid diagram, Markdown report.

Reads JSON data from TOPO_TMP_DIR (env) or /tmp/.
Supports lazy loading: brief mode skips ECS/ACK/RDS files entirely.

Large-scale Mermaid (>50 resources per VSwitch) auto-collapses to avoid OOM.

Usage:
  python3 topo-render.py <output_dir> <mode:brief|full> <timestamp> <region> [--format ascii|mermaid|both] [--health-json path]
"""

import json, sys, os, argparse

# ── Config ──
MERMAID_MAX_NODES = 50  # collapse if any VSwitch has more than this

# ── Argument parsing ──
parser = argparse.ArgumentParser()
parser.add_argument('output_dir')
parser.add_argument('report_mode', choices=('brief', 'full'))
parser.add_argument('timestamp')
parser.add_argument('region_id')
parser.add_argument('--format', choices=('ascii', 'mermaid', 'both'), default='both')
parser.add_argument('--health-json', default=None)
args = parser.parse_args()

output_dir = args.output_dir
report_mode = 'full' if args.report_mode == 'full' else 'brief'
timestamp = args.timestamp
region_id = args.region_id
output_format = args.format

# ── Data directory (concurrent-safe) ──
DATA_DIR = os.environ.get('TOPO_TMP_DIR', '/tmp')

# ── Load data (lazy: brief skips ECS/ACK/RDS) ──
_cache = {}

def load_json(name):
    """Lazy-load a JSON data file from DATA_DIR, cached."""
    if name in _cache:
        return _cache[name]
    path = os.path.join(DATA_DIR, f'{name}.json')
    if not os.path.exists(path):
        _cache[name] = {}
        return _cache[name]
    try:
        with open(path) as f:
            _cache[name] = json.load(f)
        return _cache[name]
    except Exception:
        _cache[name] = {}
        return _cache[name]

# Only load what we need based on mode
BRIEF_FILES = ['vpcs', 'vswitches', 'slbs', 'nats', 'eips', 'sgs']
FULL_FILES = ['ecs', 'ack', 'rds']

for name in BRIEF_FILES:
    load_json(name)
if report_mode == 'full':
    for name in FULL_FILES:
        load_json(name)

# ── Parse loaded data ──
def _get(name, *keys):
    """Safely dig into loaded JSON data."""
    d = _cache.get(name, {})
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, {})
        else:
            return []
    if isinstance(d, list):
        return d
    return []

vpcs  = _get('vpcs', 'Vpcs', 'Vpc')
vsws  = _get('vswitches', 'VSwitches', 'VSwitch')
slbs  = _get('slbs', 'LoadBalancers', 'LoadBalancer')
nats  = _get('nats', 'NatGateways', 'NatGateway')
eips  = _get('eips', 'EipAddresses', 'EipAddress')
sgs   = _get('sgs', 'SecurityGroups', 'SecurityGroup')
ecs   = _get('ecs', 'Instances', 'Instance') if report_mode == 'full' else []
acks  = _get('ack', 'clusters') if report_mode == 'full' else []
rds   = _get('rds', 'Items', 'DBInstance') if report_mode == 'full' else []

# ── Load health overlay (optional) ──
health_data = {}
if args.health_json and os.path.exists(args.health_json):
    try:
        with open(args.health_json) as f:
            health_data = json.load(f)
        print(f"[INFO] Health overlay loaded from {args.health_json}")
    except Exception:
        print(f"[WARN] Failed to load health JSON: {args.health_json}")

def get_health(instance_id, default='✅'):
    h = health_data.get(instance_id, {})
    level = h.get('level', '')
    if level == 'CRITICAL': return '🔴'
    if level == 'WARNING': return '🟡'
    if h.get('z_score', 0) > 2.0: return '🟡'
    return default

# ── Build VSwitch → resources mapping ──
vsw_map = {}
for v in vsws:
    v_id = v.get('VSwitchId', '')
    vsw_map[v_id] = {
        'name': v.get('VSwitchName', ''),
        'cidr': v.get('CidrBlock', ''),
        'zone': v.get('ZoneId', ''),
        'ecs': [], 'slb': [], 'rds': []
    }

for i in ecs:
    vsw = i.get('VpcAttributes', {}).get('VSwitchId', '')
    vsw_map.get(vsw, {}).setdefault('ecs', []).append({
        'name': i.get('InstanceName', ''),
        'id': i.get('InstanceId', ''),
        'ip': i.get('VpcAttributes', {}).get('PrivateIpAddress', {}).get('IpAddress', [''])[0],
        'status': i.get('Status', '')
    })

for l in slbs:
    vsw = l.get('VSwitchId', '')
    vsw_map.get(vsw, {}).setdefault('slb', []).append({
        'name': l.get('LoadBalancerName', ''),
        'id': l.get('LoadBalancerId', ''),
        'ip': l.get('Address', ''),
        'eip': l.get('EipAddress', {}).get('IpAddress', '')
    })

for d in rds:
    vsw = d.get('VSwitchId', '')
    vsw_map.get(vsw, {}).setdefault('rds', []).append({
        'name': d.get('DBInstanceDescription', ''),
        'id': d.get('DBInstanceId', ''),
        'conn': d.get('ConnectionString', '')
    })

# ── Detect large-scale mode for Mermaid ──
total_resources = sum(len(vs.get('ecs',[])) + len(vs.get('slb',[])) + len(vs.get('rds',[])) for vs in vsw_map.values())
large_scale = total_resources > MERMAID_MAX_NODES
if large_scale:
    print(f"[INFO] Large topology ({total_resources} resources > {MERMAID_MAX_NODES}), Mermaid using aggregated view")

# Primary VPC
primary_vpc = vpcs[0] if vpcs else {}
vpc_id = primary_vpc.get('VpcId', '')
vpc_name = primary_vpc.get('VpcName', '') or vpc_id
project_name = os.getenv('TOPO_PROJECT_NAME', vpc_name)

# ── Helper: resource line with health ──
def resource_line(it, indent='│  '):
    h = get_health(it.get('id', ''))
    if 'ip' in it and 'eip' in it and it['eip']:
        return f"{indent}{h} {it['name']}: {it['ip']} ({it['eip']})"
    elif 'ip' in it:
        return f"{indent}{h} {it['name']}: {it['ip']}"
    else:
        return f"{indent}{h} {it['name']}: {it.get('conn', '')}"

# ── Render ASCII ──
def render_ascii():
    lines = []
    lines.append(f"# {project_name} - 阿里云网络拓扑与资源清单")
    lines.append(f"> 生成时间: {timestamp} | 区域: {region_id} | 模式: {'详细' if report_mode == 'full' else '简报'}")
    lines.append("---")
    lines.append("## 🏗️ VPC 网络拓扑")
    lines.append("")
    lines.append(f"**VPC**: {vpc_name} ({vpc_id})  **CIDR**: {primary_vpc.get('CidrBlock', '')}")
    lines.append("```")

    for vid, vs in vsw_map.items():
        lines.append(f"├─ 交换机: {vs['name']} ({vs['cidr']}) ~ {vs['zone']}")
        items = vs.get('ecs', []) + vs.get('slb', []) + vs.get('rds', [])
        if not items:
            lines.append("│  └─ (预留)")
        else:
            for idx, it in enumerate(items[:MERMAID_MAX_NODES]):
                last = idx == len(items) - 1 or idx == MERMAID_MAX_NODES - 1
                pfx = "│  └─ " if last else "│  ├─ "
                lines.append(resource_line(it, f"   {pfx}"))
            if len(items) > MERMAID_MAX_NODES:
                lines.append(f"   │  └─ ... ({len(items) - MERMAID_MAX_NODES} more)")
    lines.append("```")
    lines.append("")
    if len(vpcs) > 1:
        lines.append(f"> 💡 检测到 {len(vpcs)} 个 VPC，当前展示主 VPC ({vpc_id})。其余 VPC: {', '.join(v.get('VpcId','') for v in vpcs[1:])}")
        lines.append("")
    lines.append("---")
    lines.append("")

    # Health summary
    if health_data:
        lines.append("## 💚 健康状态总览")
        lines.append("")
        lines.append("| 资源 | 类型 | 健康 | 异常评分 |")
        lines.append("|---|---|---|---|")
        for rid, h in health_data.items():
            hl = h.get('level', '')
            z = h.get('z_score', 0)
            emoji = '🔴' if hl == 'CRITICAL' else ('🟡' if hl == 'WARNING' else '✅')
            lines.append(f"| {rid} | {h.get('type','')} | {emoji} | {z} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Resource stats
    lines.append("## 📊 资源统计")
    lines.append("| 资源类型 | 数量 | 明细 |")
    lines.append("|---|---|---|")
    lines.append(f"| VPC | {len(vpcs)} | {vpc_name}" + (f" + {len(vpcs)-1} more" if len(vpcs) > 1 else "") + " |")
    lines.append(f"| VSwitch | {len(vsws)} | {primary_vpc.get('CidrBlock', '')} |")
    lines.append(f"| ECS | {len(ecs)} | {len(ecs)} Running |")
    lines.append(f"| SLB/CLB | {len(slbs)} | {len(slbs)} active |")
    lines.append(f"| EIP | {len(eips)} | {len(eips)} InUse |")
    lines.append(f"| NAT | {len(nats)} | {len(nats)} Available |")
    lines.append(f"| 安全组 | {len(sgs)} | — |")

    if report_mode == 'full':
        lines.append("")
        lines.append("### 详细清单")
        lines.append("| 类型 | 名称/ID | 规格/引擎 | IP/连接串 | 可用区 |")
        lines.append("|---|---|---|---|---|")
        for i in ecs:
            lines.append(f"| {get_health(i.get('InstanceId',''),'')} ECS | {i.get('InstanceName','')} | {i.get('InstanceType','')} | {i.get('VpcAttributes',{}).get('PrivateIpAddress',{}).get('IpAddress',[''])[0]} | {i.get('ZoneId','')} |")
        for d in rds:
            lines.append(f"| {get_health(d.get('DBInstanceId',''),'')} RDS | {d.get('DBInstanceDescription','')} | {d.get('Engine','')} {d.get('EngineVersion','')} ({d.get('DBInstanceMemory','')}MB) | {d.get('ConnectionString','')} | {d.get('ZoneId','')} |")
        for c in acks:
            lines.append(f"| ACK | {c.get('name','')} | {c.get('cluster_spec','')} | {c.get('control_plane_endpoints_config',{}).get('internal_dns_config',{}).get('enabled','N/A')} | {c.get('zone_id','')} |")

    lines.append("")
    lines.append("---")
    lines.append("> 由 alicloud-topo-discovery 生成 | 安全模式: READ-ONLY")
    return '\n'.join(lines)

# ── Render Mermaid ──
def render_mermaid():
    lines = []
    lines.append("```mermaid")
    lines.append("graph TB")
    lines.append(f"    subgraph VPC[{vpc_name} ({vpc_id})]")
    lines.append(f"        style VPC fill:#e8f4fd,stroke:#3b82f6")

    for vid, vs in vsw_map.items():
        safe_vsw = f"vsw_{vid.replace('-','_')[:20]}"
        lines.append(f"    subgraph {safe_vsw}[{vs['name']} | {vs['cidr']} ~ {vs['zone']}]")
        items = vs.get('ecs', []) + vs.get('slb', []) + vs.get('rds', [])

        if large_scale and len(items) > MERMAID_MAX_NODES:
            # Aggregated view: one node per resource type with count
            ecs_count = len(vs.get('ecs', []))
            slb_count = len(vs.get('slb', []))
            rds_count = len(vs.get('rds', []))
            parts = []
            if ecs_count:
                parts.append(f"ECS x{ecs_count}")
            if slb_count:
                parts.append(f"SLB x{slb_count}")
            if rds_count:
                parts.append(f"RDS x{rds_count}")
            label = " | ".join(parts) if parts else "(预留)"
            safe_id = f"agg_{vid.replace('-','_')[:20]}"
            lines.append(f"        {safe_id}[\"{label}\"]")
        else:
            for it in items:
                safe_id = f"res_{it.get('id','').replace('-','_')[:20] or it['name'][:20]}"
                label = f"{get_health(it.get('id',''),'✅')} {it['name']}"
                if 'ip' in it:
                    label += f"\\n{it['ip']}"
                lines.append(f"        {safe_id}[{label}]")
            if not items:
                lines.append(f"        empty_spot[(\"(预留)\")]")
        lines.append("    end")

    # EIP → SLB connections
    for l in slbs:
        slb_id = l.get('LoadBalancerId', '')
        slb_ip = l.get('EipAddress', {}).get('IpAddress', '')
        if slb_ip:
            safe_eip = f"eip_{slb_ip.replace('.','_')}"
            safe_slb = f"res_{slb_id.replace('-','_')[:20] or l.get('LoadBalancerName','')[:20]}"
            lines.append(f"    {safe_eip}((\"{slb_ip}\")) --> {safe_slb}")

    lines.append("    end")
    lines.append("```")
    return '\n'.join(lines)


# ── Render and write output ──
os.makedirs(output_dir, exist_ok=True)
ascii_content = render_ascii()
mermaid_content = render_mermaid()

if output_format in ('ascii', 'both'):
    path = os.path.join(output_dir, "report.md")
    if output_format == 'both':
        # Insert Mermaid diagram after the ASCII topology section
        parts = ascii_content.split("---\n")
        if len(parts) >= 2:
            first_part = parts[0]
            rest = "---\n".join(parts[1:])
            combined = first_part + "---\n\n## 🎨 拓扑关系图\n\n" + mermaid_content + "\n\n---\n" + rest
        else:
            combined = ascii_content + "\n\n## 🎨 拓扑关系图\n\n" + mermaid_content
    else:
        combined = ascii_content
    with open(path, 'w') as f:
        f.write(combined)
    print(f"✅ Report: {path} ({os.path.getsize(path)} bytes)")

if output_format in ('mermaid',):
    path = os.path.join(output_dir, "topology.mermaid.md")
    with open(path, 'w') as f:
        f.write(mermaid_content)
    print(f"✅ Mermaid: {path} ({os.path.getsize(path)} bytes)")