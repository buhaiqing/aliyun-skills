# 成本估算模型（方案 B）— 内置规格单价表

> 无需 BSS API，无需历史账单。直接用规格×单价估算月成本，精度 ±15%。
> Agent 直接使用本文件的估算逻辑，无需外部搜索。

---

## 1. 成本估算公式

```
ECS 月成本 = 规格单价 × 数量 + 云盘成本
           = Σ(instance_type_price_per_month) + Σ(disk_size_gb × disk_price_per_gb_per_month)

RDS 月成本 = 规格单价 + 存储成本
           = instance_type_price_per_month + storage_gb × storage_price_per_gb_per_month

Redis 月成本 = 规格单价（纯内存，无存储）
             = instance_type_price_per_month

SLB 月成本 = 带宽成本 + 流量成本（按量付费）
           = bandwidth_mbps × bandwidth_price_per_mbps + traffic_gb × traffic_price_per_gb
```

---

## 2. ECS 规格单价表（cn-hangzhou，按量付费，月估算）

| 实例族 | 规格 | vCPU | 内存(GB) | 月单价(元) |
|--------|------|------|---------|-----------|
| c9i | c9i.large | 2 | 4 | 144 |
| c9i | c9i.xlarge | 4 | 8 | 288 |
| c9i | c9i.2xlarge | 8 | 16 | 576 |
| g9i | g9i.large | 2 | 8 | 211 |
| g9i | g9i.xlarge | 4 | 16 | 422 |
| g9i | g9i.2xlarge | 8 | 32 | 844 |
| g9i | g9i.4xlarge | 16 | 64 | 1688 |
| r9i | r9i.large | 2 | 16 | 422 |
| r9i | r9i.xlarge | 4 | 32 | 844 |
| r9i | r9i.2xlarge | 8 | 64 | 1688 |
| g8ise | g8ise.8xlarge | 32 | 128 | 3388 |
| u1 | u1.large | 2 | 8 | 187 |
| u1 | u1.xlarge | 4 | 16 | 374 |
| u1 | u1.2xlarge | 8 | 32 | 748 |

**云盘单价（高效云盘）**：`0.35 元/GB/月`
**SSD 云盘**：`1.0 元/GB/月`

---

## 3. RDS MySQL 规格单价表（cn-hangzhou，按量付费，月估算）

| 规格族 | 规格 | vCPU | 内存(GB) | 月单价(元) | 存储单价(元/GB/月) |
|--------|------|------|---------|-----------|-----------------|
| r9i | mysql.r9i.large | 2 | 16 | 422 | 0.48 |
| r9i | mysql.r9i.xlarge | 4 | 32 | 844 | 0.48 |
| r9i | mysql.r9i.2xlarge | 8 | 64 | 1688 | 0.48 |
| r9i | mysql.r9i.4xlarge | 16 | 128 | 3376 | 0.48 |
| msql.xlarge | msql.xlarge | 4 | 16 | 580 | 0.48 |

---

## 4. RDS PostgreSQL 规格单价表（cn-hangzhou，按量付费）

| 规格族 | 规格 | vCPU | 内存(GB) | 月单价(元) | 存储单价 |
|--------|------|------|---------|-----------|---------|
| pg.r9i.large | pg.r9i.large | 2 | 16 | 499 | 0.48 |
| pg.r9i.xlarge | pg.r9i.xlarge | 4 | 32 | 998 | 0.48 |

---

## 5. Redis 规格单价表（cn-hangzhou，内存型，按量付费）

| 规格族 | 规格 | 内存(GB) | 月单价(元) |
|--------|------|---------|-----------|
| redis.master.middle.default | redis.master.middle.default.2g | 2 | 156 |
| redis.master.middle.default | redis.master.middle.default.4g | 4 | 312 |
| redis.master.middle.default | redis.master.middle.default.8g | 8 | 624 |
| redis.master.large.default | redis.master.large.default.16g | 16 | 1248 |
| redis.master.large.default | redis.master.large.default.32g | 32 | 2496 |

---

## 6. SLB 成本估算

| 类型 | 计费方式 | 公式 |
|------|---------|------|
| 公网 SLA | 包年包月 | `bandwidth_mbps × 58 元/Mbps/月` |
| 公网 SLB | 按量付费 | `流量(GB) × 0.8 元/GB` |
| 内网 SLB | 免费 | `0` |

---

## 7. 估算实现代码

```python
import pandas as pd
import json

# === 规格单价 lookup（简化版，实际从 data/unit_prices.json 加载）===
UNIT_PRICES = {
    'ecs': {
        'c9i.large': 144, 'c9i.xlarge': 288, 'c9i.2xlarge': 576,
        'g9i.large': 211, 'g9i.xlarge': 422, 'g9i.2xlarge': 844, 'g9i.4xlarge': 1688,
        'r9i.large': 422, 'r9i.xlarge': 844, 'r9i.2xlarge': 1688,
        'g8ise.8xlarge': 3388,
        'u1.large': 187, 'u1.xlarge': 374, 'u1.2xlarge': 748,
    },
    'rds_mysql': {
        'mysql.r9i.large': 422, 'mysql.r9i.xlarge': 844, 'mysql.r9i.2xlarge': 1688,
    },
    'redis': {
        'redis.master.middle.default.2g': 156, 'redis.master.middle.default.4g': 312,
        'redis.master.middle.default.8g': 624, 'redis.master.large.default.16g': 1248,
    }
}

DISK_PRICE_PER_GB = 0.35    # 高效云盘 元/GB/月
STORAGE_PRICE_PER_GB = 0.48  # RDS 存储 元/GB/月

def estimate_ecs_cost(row: dict) -> float:
    """估算单台 ECS 月成本"""
    inst_price = UNIT_PRICES['ecs'].get(row['instance_type'], 500)  # 未知规格默认 500
    disk_price = row.get('disk_gb', 0) * DISK_PRICE_PER_GB
    return inst_price + disk_price

def estimate_rds_cost(row: dict) -> float:
    """估算单台 RDS 月成本"""
    inst_price = UNIT_PRICES['rds_mysql'].get(row['instance_type'], 500)
    storage_price = row.get('disk_gb', 0) * STORAGE_PRICE_PER_GB
    return inst_price + storage_price

def estimate_redis_cost(row: dict) -> float:
    """估算单台 Redis 月成本"""
    # Redis 按内存大小定价
    mem = row.get('memory_gb', 0)
    if mem <= 2: return 156
    if mem <= 4: return 312
    if mem <= 8: return 624
    if mem <= 16: return 1248
    if mem <= 32: return 2496
    return 5000

def estimate_slb_cost(row: dict) -> float:
    """估算单台 SLB 月成本（按量付费默认估算）"""
    if row.get('pay_type') == 'PayOnDemand':
        # 按量付费默认估算 500 元/月（实际按流量计费）
        return 500
    # 包年包月：bandwidth × 58
    bw = row.get('bandwidth_mbps', 0)
    return bw * 58

def estimate_all_costs(df: pd.DataFrame) -> pd.DataFrame:
    """批量估算所有资源月成本"""
    df = df.copy()
    
    # 按 resource_type 分发估算器
    mask_ecs   = df['resource_type'] == 'ecs'
    mask_rds   = df['resource_type'] == 'rds'
    mask_redis = df['resource_type'] == 'redis'
    mask_slb   = df['resource_type'] == 'slb'
    
    df.loc[mask_ecs,   'monthly_cost'] = df.loc[mask_ecs].apply(estimate_ecs_cost, axis=1)
    df.loc[mask_rds,   'monthly_cost'] = df.loc[mask_rds].apply(estimate_rds_cost, axis=1)
    df.loc[mask_redis, 'monthly_cost'] = df.loc[mask_redis].apply(estimate_redis_cost, axis=1)
    df.loc[mask_slb,   'monthly_cost'] = df.loc[mask_slb].apply(estimate_slb_cost, axis=1)
    
    return df
```

---

## 8. 包年 vs 按量成本差异

| 计费方式 | 成本特征 | IF/ML 中的处理 |
|---------|---------|--------------|
| 包年包月 | 一次性付清，月均成本低 | `is_prepaid=1`，monthly_cost 用均摊值 |
| 按量付费 | 实时计费，成本 = 规格单价 | `is_prepaid=0` |

**包年包月月均折扣**（参考）：
- 1 年付：月均 × 0.9
- 2 年付：月均 × 0.8
- 3 年付：月均 × 0.7

**恰货铺子实际情况**：所有资源均为"预付费"（Prepaid），到期日 2029-03-31。需在 cost 估算中说明：预付费已一次性付清，估算月成本仅用于利用率对比，不反映实际月度支出。
