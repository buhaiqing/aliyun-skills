---
template_id: "sniff-report"
phase: "Phase 1: 拓扑初判"
---

# [NET] 链路拓扑初判报告

**客户:** `{{customer}}` | **时间:** `{{timestamp}}` | **区域:** `{{regions}}`

---

## [NOTE] 如何阅读这份报告

> 拓扑初判是巡检的第一步：先搞清楚"有什么资源"和"它们怎么连的"，再去做深度诊断。
> 如果拓扑中有无法自动归类的资源（置信度 ≤ 0.8），需要人工确认后再继续。

---

## VPC 网络结构

```
{{topology_tree}}
```

### 子网与资源分布

| 子网 | CIDR | 资源 |
|---|---|---|
{% for subnet in subnets %}
| {{subnet.name}} | {{subnet.cidr}} | {{subnet.resources \| join(", ")}} |
{% endfor %}

---

## 链路拓扑

```
客户入口 (EIP)
  DOWN
SLB (负载均衡)
  ├── 后端 ECS 组 A (核心服务)
  ├── 后端 ECS 组 B (API 服务)
  └── 后端 ECS 组 C (管理后台)
  DOWN
RDS (数据库) ── Redis (缓存)
  DOWN
NAT (出网) ── 安全组防护
```

---

## 资源清单

### ECS 实例

| 实例ID | 名称 | 规格 | 区域 | 状态 | 标签 |
|---|---|---|---|---|---|
{% for ecs in ecs_instances %}
| {{ecs.id}} | {{ecs.name}} | {{ecs.type}} | {{ecs.region}} | {{ecs.status}} | {{ecs.tags}} |
{% endfor %}

### SLB 实例

| 实例ID | 名称 | 规格 | 地址类型 | 带宽 |
|---|---|---|---|---|
{% for slb in slb_instances %}
| {{slb.id}} | {{slb.name}} | {{slb.spec}} | {{slb.address_type}} | {{slb.bandwidth}} |
{% endfor %}

### RDS 实例

| 实例ID | 名称 | 引擎 | 规格 | 存储 |
|---|---|---|---|---|
{% for rds in rds_instances %}
| {{rds.id}} | {{rds.name}} | {{rds.engine}} | {{rds.spec}} | {{rds.storage}} |
{% endfor %}

### Redis 实例

| 实例ID | 名称 | 规格 | 最大连接数 |
|---|---|---|---|
{% for redis in redis_instances %}
| {{redis.id}} | {{redis.name}} | {{redis.spec}} | {{redis.max_connections}} |
{% endfor %}

### 安全组 (高危规则检查)

{% for sg in security_groups %}
{% if sg.has_danger_rules %}
- [WARN] **{{sg.id}}** ({{sg.name}}): 存在高危规则 `0.0.0.0/0` 开放端口 {{sg.danger_ports}}
{% endif %}
{% endfor %}

---

## 待确认的资源

{% if unclassified_resources %}
| 资源类型 | 资源ID | 名称 | 原因 |
|---|---|---|---|
{% for r in unclassified_resources %}
| {{r.type}} | {{r.id}} | {{r.name}} | {{r.reason}} |
{% endfor %}

> [WARN] 以上资源无法自动归类，请人工确认归属后继续 Phase 2。
{% else %}
PASS 所有资源均已自动归类。
{% endif %}

---

## 下一步

{% if needs_human_confirm %}
**请确认上述待分类资源后再执行 Phase 2 深度巡检。**
{% else %}
PASS 自动进入 Phase 2 深度巡检。
{% endif %}