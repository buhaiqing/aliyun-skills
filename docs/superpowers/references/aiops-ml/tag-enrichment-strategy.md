# 标签富化策略 — Tag Enrichment Strategy

> 阿里云 ResourceTag API 可能缺失部分标签。本文件定义降级策略，让 Agent 在 Tag 为空时仍能完成分析。

---

## 1. 标签优先级（3 级 fallback）

```
Level 1: Tag API（最权威）
  └─ ResourceManager ListResources → 拿到 product / env / project / owner / cost_center

Level 2: 实例名称解析（次优先）
  └─ 如果 Tag 缺失，从实例名称按正则提取

Level 3: 标注"未知"（兜底）
  └─ 如果名称也无规律，标注为 "unknown"
```

---

## 2. 标签来源字段

| 标签字段 | Tag API 键 | 名称正则（fallback） | 示例 |
|---------|-----------|--------------------|------|
| `product` | `product` | `-(h6\|crm\|iwms\|mas\|sop\|sos\|erp\|pos\|到家\|经营助手\|门店运营\|到家prd)-` | `qhpz-iwms-web-01` → `iwms` |
| `env` | `env` | `-(prd\|int\|test\|uat)-` 或 `-([0-9]+)$`（数字结尾=测试环境） | `qhpz-h6-prd-01` → `production` |
| `project` | `project` | 取前缀第一段 | `qhpz-h6-web-01` → `qhpz` |
| `owner` | `owner` | 无名称规律，**必须从 Tag 获取**，Tag 无则标注 `unknown` | — |
| `cost_center` | `cost_center` | 无名称规律，**必须从 Tag 获取**，Tag 无则标注 `unknown` | — |
| `business_line` | `business_line`（不存在） | 无名称规律，**无法推断**，直接标注 `unknown` | — |

---

## 3. 名称正则模式库

```python
import re

def extract_from_name(resource_name: str) -> dict:
    """从实例名称富化标签（fallback when Tag is empty）"""
    name = resource_name.lower()
    
    # product 识别
    product_map = {
        'iwms': 'iwms',
        'h6': 'h6',
        'crm': 'crm',
        'mas': 'mas',
        'sop': 'sop',
        'sos': 'sos',
        'erp': 'erp',
        'pos': 'pos',
        '到家': '到家',
        '经营助手': '经营助手',
        '门店运营': '门店运营',
    }
    product = 'unknown'
    for key, val in product_map.items():
        if key in name:
            product = val
            break
    
    # env 识别
    if '-prd' in name or '-pro' in name or '-prod' in name:
        env = 'production'
    elif '-int' in name:
        env = 'int'
    elif '-test' in name or '-uat' in name:
        env = 'test'
    elif re.search(r'-[0-9]+$', name):  # 数字结尾
        env = 'test'
    else:
        env = 'unknown'
    
    # project：取第一段（-分隔）
    parts = resource_name.split('-')
    project = parts[0] if parts else 'unknown'
    
    return {
        'product': product,
        'env': env,
        'project': project,
        'owner': 'unknown',          # 必须从 Tag
        'cost_center': 'unknown',     # 必须从 Tag
        'business_line': 'unknown',   # 无法推断
    }
```

---

## 4. Tag API 调用模式

```bash
# 一次性拉取某 region 所有 ECS 实例的标签
aliyun resourcemanager ListResources \
  --ResourceType "ecs:instance" \
  --RegionId cn-hangzhou \
  --PageSize 100

# 按 product 标签过滤
aliyun resourcemanager ListTagResources \
  --Tag '[{"TagKey":"product","TagValue":"iwms"}]' \
  --ResourceType "ecs:instance" \
  --RegionId cn-hangzhou

# 批量处理：遍历所有资源类型
for rt in "ecs:instance" "rds:instance" "kvstore:instance" "slb:loadbalancer"; do
  aliyun resourcemanager ListResources \
    --ResourceType "$rt" \
    --RegionId cn-hangzhou \
    --PageSize 100
done
```

---

## 5. Tag → DataFrame Join

```python
import pandas as pd

def enrich_with_tags(df: pd.DataFrame, tags: list[dict]) -> pd.DataFrame:
    """将 Tag 数据 join 到资源 DataFrame"""
    # tags 格式：[{resource_id: "i-xxx", product: "iwms", env: "production", ...}, ...]
    tag_df = pd.DataFrame(tags)
    
    # 重命名列以匹配 Resource 数据类
    tag_df = tag_df.rename(columns={'resource_id': 'resource_id'})
    
    # left join（保留无 Tag 的资源）
    df = df.merge(tag_df, on='resource_id', how='left', suffixes=('', '_tag'))
    
    # Tag 字段后缀清理
    for col in ['product', 'env', 'project', 'owner', 'cost_center', 'business_line']:
        if f'{col}_tag' in df.columns:
            df[col] = df[f'{col}_tag'].fillna(df[col])  # 优先用 Tag，fallback 到名称解析
    
    # 用名称解析填充 Tag 为空的字段
    name_filled = df['instance_name'].apply(extract_from_name)
    name_df = pd.DataFrame(name_filled.tolist())
    
    for col in ['product', 'env', 'project']:
        mask = df[col].isna() | (df[col] == 'unknown')
        df.loc[mask, col] = name_df.loc[mask, col]
    
    return df
```

---

## 6. 已知恰货铺子命名规律

```
qhpz-{product}-{role}-{N}
示例：
  qhpz-iwms-web-01    → product=iwms, role=web, N=01
  qhpz-h6-api-02      → product=h6, role=api, N=02
  qhpz-erp-web-03     → product=erp, role=web, N=03
  qhpz-iwms-int-web-01 → product=iwms, env=int, role=web, N=01
```

**注意**：`qhpz` = "恰货铺子"缩写，统一前缀。
