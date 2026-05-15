# VPC 网络拓扑模板

```text
VPC: {{project_name}} ({{vpc_id}})
CIDR: {{vpc_cidr}}
├─ 交换机: {{vswitch_name_1}} ({{vswitch_cidr_1}}) ~ {{zone_1}}
│  ├─ {{resource_name}}: {{ip_or_conn}}
│  └─ (预留)
├─ 交换机: {{vswitch_name_2}} ({{vswitch_cidr_2}}) ~ {{zone_2}}
│  ├─ {{resource_name}}: {{ip_or_conn}}
│  └─ {{resource_name}}: {{ip_or_conn}}
└─ 交换机: {{vswitch_name_3}} ({{vswitch_cidr_3}}) ~ {{zone_3}}
   └─ (预留)
```

> 此模板用于生成树形 ASCII 视图。变量由 `topo-render.py` 替换。
