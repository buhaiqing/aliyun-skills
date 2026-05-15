#!/usr/bin/env python3
import json, sys, os

output_dir, report_mode, timestamp, region_id = sys.argv[1:5]

def load_json(f):
    try: return json.load(open(f))
    except: return {}

vpcs = load_json('/tmp/topo_vpcs.json').get('Vpcs',{}).get('Vpc',[{}])[0] if load_json('/tmp/topo_vpcs.json').get('Vpcs',{}).get('Vpc') else {}
vswitches = load_json('/tmp/topo_vswitches.json').get('VSwitches',{}).get('VSwitch',[])
slbs = load_json('/tmp/topo_slbs.json').get('LoadBalancers',{}).get('LoadBalancer',[])
nats = load_json('/tmp/topo_nats.json').get('NatGateways',{}).get('NatGateway',[])
eips = load_json('/tmp/topo_eips.json').get('EipAddresses',{}).get('EipAddress',[])
ecs = load_json('/tmp/topo_ecs.json').get('Instances',{}).get('Instance',[]) if report_mode == 'full' else []
acks = load_json('/tmp/topo_ack.json').get('clusters',[]) if report_mode == 'full' else []
rds = load_json('/tmp/topo_rds.json').get('Items',{}).get('DBInstance',[]) if report_mode == 'full' else []
sgs = load_json('/tmp/topo_sgs.json').get('SecurityGroups',{}).get('SecurityGroup',[])

vsw_map = {}
for v in vswitches:
    vsw_map[v['VSwitchId']] = {'name': v.get('VSwitchName',''), 'cidr': v['CidrBlock'], 'zone': v['ZoneId'], 'ecs':[], 'slb':[], 'rds':[]}

for i in ecs:
    vsw = i.get('VpcAttributes',{}).get('VSwitchId','')
    vsw_map.get(vsw,{}).setdefault('ecs',[]).append({'name': i.get('InstanceName',''), 'ip': i.get('VpcAttributes',{}).get('PrivateIpAddress',{}).get('IpAddress',[''])[0]})

for l in slbs:
    vsw = l.get('VSwitchId','')
    vsw_map.get(vsw,{}).setdefault('slb',[]).append({'name': l['LoadBalancerName'], 'ip': l['Address'], 'eip': l.get('EipAddress',{}).get('IpAddress','')})

for d in rds:
    vsw = d.get('VSwitchId','')
    vsw_map[vsw].setdefault('rds',[]).append({'name': d.get('DBInstanceDescription',''), 'conn': d['ConnectionString']})

vpc_id = vpcs.get('VpcId','')
vpc_name = vpcs.get('VpcName','') or vpc_id
project_name = os.getenv('TOPO_PROJECT_NAME', vpc_name)

lines = [f"# {project_name} - 阿里云网络拓扑与资源清单\n", f"> 生成时间: {timestamp} | 区域: {region_id} | 模式: {'详细' if report_mode== 'full' else '简报'}\n---\n"]
lines.append("## 🏗️ VPC 网络拓扑\n")
lines.append(f"**VPC**: {vpc_name} ({vpc_id})  **CIDR**: {vpcs.get('CidrBlock','')}")
lines.append("```")

for vid, vs in vsw_map.items():
    lines.append(f"├─ 交换机: {vs['name']} ({vs['cidr']}) ~ {vs['zone']}")
    items = vs['ecs'] + vs['slb'] + vs['rds']
    if not items: lines.append("│  └─ (预留)")
    else:
        for i, it in enumerate(items):
            last = i == len(items)-1
            pfx = "│  └─ " if last else "│  ├─ "
            if 'ip' in it and 'eip' in it and it['eip']:
                lines.append(f"   {pfx}{it['name']}: {it['ip']} ({it['eip']})")
            elif 'ip' in it:
                lines.append(f"   {pfx}{it['name']}: {it['ip']}")
            else:
                lines.append(f"   {pfx}{it['name']}: {it.get('conn','')}")
lines.append("```\n---\n")

lines.append("## 📊 资源统计\n| 资源类型 | 数量 ||")
lines.append("|---|---|-||")
lines.append(f"| VPC | 1 | {vpc_name} |")
lines.append(f"| VSwitch | {len(vswitches)} | {vpcs.get('CidrBlock','')} |")
lines.append(f"| ECS | {len(ecs)} | {len(ecs)} Running |")
lines.append(f"| SLB/CLB | {len(slbs)} | {len(slbs)} active |")
lines.append(f"| EIP | {len(eips)} | {len(eips)} InUse |")
lines.append(f"| NAT | {len(nats)} | {len(nats)} Available |")
if report_mode == 'full':
    lines.append("\n### 详细清单\n| 类型 | 名称/ID | 规格/引擎 | IP/连接串 | 可用区 |")
    lines.append("|---|---|---|---|---|")
    for i in ecs: lines.append(f"| ECS | {i['InstanceName']} | {i['InstanceType']} | {i['VpcAttributes']['PrivateIpAddress']['IpAddress'][0]} | {i['ZoneId']} |")
    for d in rds: lines.append(f"| RDS | {d['DBInstanceDescription']} | {d['Engine']} {d['EngineVersion']} ({d['DBInstanceMemory']}MB) | {d['ConnectionString']} | {d['ZoneId']} |")
    for c in acks: lines.append(f"| ACK | {c['name']} | {c['cluster_spec']} | {c['control_plane_endpoints_config'].get('internal_dns_config',{}).get('enabled','N/A')} | {c['zone_id']} |")

lines.append("\n---\n> 由 alicloud-topo-discovery 生成 | 安全模式: READ-ONLY")

os.makedirs(output_dir, exist_ok=True)
path = os.path.join(output_dir, "report.md")
with open(path, 'w') as f: f.write('\n'.join(lines))
print(f"✅ Report: {path} ({os.path.getsize(path)} bytes)")
