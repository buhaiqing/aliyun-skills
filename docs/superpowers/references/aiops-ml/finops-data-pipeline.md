# FinOps 数据采集管道 — 数据采集全链路

> 本文件定义完整的数据采集流程，覆盖 ECS/RDS/Redis/SLB/OSS/K8s 所有资源。
> Agent 直接使用本文件中的命令和代码，无需外部搜索。

---

## 1. 采集顺序与依赖

```
1. 并行拉取各产品列表
   ├─ ECS: DescribeInstances
   ├─ RDS: DescribeDBInstances
   ├─ Redis: r-kvstore DescribeInstances
   ├─ SLB: DescribeLoadBalancers
   └─ K8s: cs GET /clusters
           └─ cs GET /clusters/{id}/nodes

2. 并行拉取云监控指标（--api-version 2019-05-01 必须）
   ├─ ECS: acs_ecs_dashboard
   ├─ RDS: acs_rds_dashboard
   ├─ Redis: acs_kvstore_dashboard
   └─ SLB: acs_slb_dashboard

3. 并行拉取标签（最后，不阻塞指标采集）
   └─ ResourceManager ListResources

4. 汇聚：统一 DataFrame + Tag join
```

---

## 2. ECS 数据采集（含云盘）

```bash
# ① 实例列表
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --PageSize 100

# ② 云盘列表（disk_gb 必须从此获取）
aliyun ecs DescribeDisks \
  --RegionId cn-hangzhou \
  --PageSize 100 \
  --DiskType cloud_efficiency,cloud_ssd

# ③ 7天 CPU/内存平均（并行，每个实例一次）
aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName cpu.utilization \
  --Dimensions "[{\"instanceId\":\"$InstanceId\"}]" \
  --Period 3600 \
  --StartTime "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --api-version 2019-05-01

aliyun cms DescribeMetricList \
  --Namespace acs_ecs_dashboard \
  --MetricName memory.usedutilization \
  --Dimensions "[{\"instanceId\":\"$InstanceId\"}]" \
  --Period 3600 \
  --StartTime "$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --api-version 2019-05-01
```

**ECS 采集 Python 实现**：

```python
import pandas as pd, json, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

def cli(cmd: str) -> dict:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout)

def fetch_ecs_instances(region: str = 'cn-hangzhou') -> pd.DataFrame:
    """拉取 ECS 实例列表 + 云盘大小"""
    raw = cli(f'aliyun ecs DescribeInstances --RegionId {region} --PageSize 100')
    instances = raw.get('Instances', {}).get('Instance', [])
    
    # 云盘大小（按 InstanceId 分组）
    disks_raw = cli(f'aliyun ecs DescribeDisks --RegionId {region} --PageSize 100 --DiskType cloud_efficiency,cloud_ssd')
    disks = disks_raw.get('Disks', {}).get('Disk', [])
    disk_map = {}
    for d in disks:
        iid = d.get('InstanceId', '')
        size = float(d.get('Size', 0))
        disk_map[iid] = disk_map.get(iid, 0) + size  # 累加多盘
    
    rows = []
    for inst in instances:
        iid = inst['InstanceId']
        rows.append({
            'resource_id': iid,
            'resource_type': 'ecs',
            'instance_name': inst.get('InstanceName', ''),
            'instance_type': inst['InstanceType'],
            'cpu_cores': int(inst['CpuCoreCount']),
            'memory_gb': int(inst['Memory']) / 1024,  # MB → GB
            'disk_gb': disk_map.get(iid, 0),
            'pay_type': inst.get('InstanceChargeType', ''),
            'expire_time': inst.get('ExpiredTime', ''),
            'status': inst.get('Status', ''),
            'vswitch_id': inst.get('VSwitchId', ''),
            'region': region,
        })
    return pd.DataFrame(rows)

def fetch_ecs_metrics(instance_ids: list[str], metric: str, days: int = 7) -> dict:
    """拉取 ECS 监控指标，返回 {instance_id: avg_value}"""
    results = {}
    start = datetime.utcnow() - timedelta(days=days)
    for iid in instance_ids:
        raw = cli(
            f'aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard '
            f'--MetricName {metric} '
            f'--Dimensions "[{{\\"instanceId\\":\\"{iid}\\"}}]" '
            f'--Period 3600 --StartTime "{start.strftime("%Y-%m-%dT%H:%M:%SZ")}" '
            f'--api-version 2019-05-01'
        )
        dps = raw.get('Datapoints', [])
        if dps:
            values = [float(p['Value']) for p in dps]
            results[iid] = np.mean(values)
    return results
```

---

## 3. RDS + Redis 数据采集

```python
def fetch_rds_instances(region: str = 'cn-hangzhou') -> pd.DataFrame:
    raw = cli(f'aliyun rds DescribeDBInstances --RegionId {region} --PageSize 100')
    instances = raw.get('Items', {}).get('DBInstance', [])
    rows = []
    for inst in instances:
        # 查属性（包含 DiskUsed、Memory）
        attr_raw = cli(f'aliyun rds DescribeDatabaseAttribute --DBInstanceId {inst["DBInstanceId"]}')
        attr = attr_raw.get('Items', {}).get('DBInstanceAttribute', [{}])[0]
        rows.append({
            'resource_id': inst['DBInstanceId'],
            'resource_type': 'rds',
            'instance_name': inst.get('DBInstanceDescription', inst['DBInstanceId']),
            'instance_type': inst.get('DBInstanceType', ''),  # 如 mysql.r9i.large
            'engine': inst.get('Engine', ''),
            'cpu_cores': int(attr.get('DBInstanceCPU', 0)),
            'memory_gb': int(attr.get('DBInstanceMemory', 0)) / 1024,  # kB → GB
            'disk_gb': float(attr.get('DiskUsed', 0)),  # GB
            'max_iops': int(attr.get('MaxIOPS', 0)),
            'max_connections': int(attr.get('MaxConnections', 0)),
            'pay_type': inst.get('PayType', ''),
            'expire_time': inst.get('ExpireTime', ''),
            'region': region,
        })
    return pd.DataFrame(rows)
```

---

## 4. K8s 数据采集

```python
def fetch_k8s_clusters(region: str = 'cn-hangzhou') -> list[dict]:
    """获取 K8s 集群列表"""
    raw = cli(f'aliyun cs GET /clusters')
    return raw if isinstance(raw, list) else raw.get('clusters', [])

def fetch_k8s_nodes(cluster_id: str) -> pd.DataFrame:
    """获取 K8s 节点列表（含 allocatable CPU/Memory）"""
    raw = cli(f'aliyun cs GET /clusters/{cluster_id}/nodes')
    nodes = raw if isinstance(raw, list) else raw.get('nodes', [])
    rows = []
    for node in nodes:
        alloc = node.get('allocatable', {})
        rows.append({
            'resource_id': node.get('node_name', node.get('instance_id', '')),
            'resource_type': 'k8s_node',
            'cluster_id': cluster_id,
            'instance_type': node.get('instance_type', ''),
            'cpu_cores': int(alloc.get('cpu', 0)),
            'memory_gb': int(alloc.get('memory', 0)) / 1024,  # Ki → GB
            'cpu_allocatable': int(alloc.get('cpu', 0)),
            'memory_allocatable_gb': int(alloc.get('memory', 0)) / 1024,
            'status': node.get('status', ''),
        })
    return pd.DataFrame(rows)

def collect_all_k8s(region: str = 'cn-hangzhou') -> pd.DataFrame:
    """采集所有 K8s 集群节点"""
    clusters = fetch_k8s_clusters(region)
    all_nodes = []
    for cluster in clusters:
        cid = cluster.get('cluster_id', '')
        if cid:
            all_nodes.append(fetch_k8s_nodes(cid))
    return pd.concat(all_nodes, ignore_index=True) if all_nodes else pd.DataFrame()
```

---

## 5. Tag 采集

```python
RESOURCE_TYPES = [
    'ecs:instance', 'rds:instance', 'kvstore:instance',
    'slb:loadbalancer', 'oss:bucket',
]

def fetch_all_tags(region: str = 'cn-hangzhou') -> list[dict]:
    """一次性拉取所有资源的标签"""
    all_tags = []
    for rt in RESOURCE_TYPES:
        page = 1
        while True:
            raw = cli(
                f'aliyun resourcemanager ListResources '
                f'--ResourceType "{rt}" --RegionId {region} '
                f'--PageSize 100 --PageNumber {page}'
            )
            resources = raw.get('Resources', {}).get('Resource', [])
            for res in resources:
                rid = res.get('ResourceId', '')
                tags = res.get('Tags', {}).get('Tag', [])
                for tag in tags:
                    all_tags.append({
                        'resource_id': rid,
                        'tag_key': tag.get('TagKey', ''),
                        'tag_value': tag.get('TagValue', ''),
                    })
            if len(resources) < 100:
                break
            page += 1
    return all_tags

def tags_to_dataframe(tags: list[dict]) -> pd.DataFrame:
    """标签列表 → 宽表 DataFrame"""
    df = pd.DataFrame(tags)
    # pivot：resource_id 为行，tag_key 为列
    pivot = df.pivot_table(
        index='resource_id',
        columns='tag_key',
        values='tag_value',
        aggfunc='first'
    ).reset_index()
    # 标准化列名
    for col in ['product', 'env', 'project', 'owner', 'cost_center', 'business_line']:
        if col not in pivot.columns:
            pivot[col] = 'unknown'
    return pivot
```

---

## 6. 全量采集 Pipeline

```python
from concurrent.futures import ThreadPoolExecutor

def collect_all(region: str = 'cn-hangzhou', days: int = 7) -> pd.DataFrame:
    """全量采集：并行拉取 → 汇聚 → 标签 join"""
    
    # Step 1: 并行拉取各产品
    with ThreadPoolExecutor(max_workers=6) as ex:
        fut_ecs    = ex.submit(fetch_ecs_instances, region)
        fut_rds    = ex.submit(fetch_rds_instances, region)
        fut_redis  = ex.submit(fetch_redis_instances, region)
        fut_slb    = ex.submit(fetch_slb_loadbalancers, region)
        fut_k8s    = ex.submit(collect_all_k8s, region)
        fut_tags   = ex.submit(fetch_all_tags, region)
        
        df_ecs   = fut_ecs.result()
        df_rds   = fut_rds.result()
        df_redis = fut_redis.result()
        df_slb   = fut_slb.result()
        df_k8s   = fut_k8s.result()
        tags_raw = fut_tags.result()
    
    # Step 2: 合并所有资源
    df_all = pd.concat([df_ecs, df_rds, df_redis, df_slb, df_k8s], ignore_index=True)
    
    # Step 3: Tag join
    tag_df = tags_to_dataframe(tags_raw)
    df_all = df_all.merge(tag_df, on='resource_id', how='left')
    
    # Step 4: 标签富化（Tag → 名称解析 fallback）
    name_filled = df_all['instance_name'].apply(extract_from_name)
    for col in ['product', 'env', 'project']:
        mask = df_all[col].isna() | (df_all[col] == 'unknown')
        df_all.loc[mask, col] = [name_filled[i][col] for i in range(len(df_all)) if mask.iloc[i]]
    
    # Step 5: 估算成本
    df_all = estimate_all_costs(df_all)
    
    return df_all
```
