# SPEC: alicloud-aiops-ml — AIOps + FinOps 智能分析引擎

**版本**: v0.1 | **状态**: 设计中 | **Owner**: 待定

---

## 1. 问题陈述 + 与现有 Skill 的关系

**现有 Skill 能力盘点**：
| Skill | FinOps 已有能力 |
|-------|---------------|
| `alicloud-ecs-ops` | cost-visualization.md（成本可视化）、idle-resource-detection.md（闲置检测）、multi-metric-anomaly.md（阈值异常）、predictive-capacity.md（线性回归预测） |
| `alicloud-rds-ops` | 基础生命周期管理，FinOps 能力弱 |
| `alicloud-redis-ops` | 基础生命周期管理，FinOps 能力弱 |
| `alicloud-slb-ops` | monitoring.md 有流量指标，FinOps 能力中等 |
| `alicloud-ack-ops` | finops-idle-detection.md、finops-cost-allocation.md、finops-resource-optimization.md |

**扩展策略**：
- `alicloud-aiops-ml` **独立新建**，不扩展现有 Skill
- 理由：ML 引擎需要跨产品汇聚数据（ECS+RDS+Redis+SLB），现有 Skill 均为单产品，无法承担多产品汇聚的职责
- 委托关系：`alicloud-aiops-ml` 调用 `alicloud-ecs-ops` / `alicloud-rds-ops` / `alicloud-redis-ops` 的数据采集部分（复用已有 CLI 命令），ML 引擎层独立实现
- 长期：若 `alicloud-aiops-ml` 的 ECS 子集分析成熟，可将 IF/DBSCAN 能力反向贡献到 `alicloud-ecs-ops`

**现状**：当前 `alicloud-ecs-ops` 虽有 AIOps 和 FinOps 的单产品能力（多指标异常、闲置检测、容量预测），但存在三个核心缺陷：

**现状**：当前 `alicloud-ecs-ops` 虽有 AIOps 和 FinOps 的单产品能力（多指标异常、闲置检测、容量预测），但存在三个核心缺陷：

1. **数据维度不全**：无 IO 吞吐、网络流量指标；无 RDS/Redis/SLB/K8s/OSS 的关联分析
2. **缺乏分类特征**：无法按产品线、环境、业务线分组分析，导致跨产品误报（如测试环境低利用率被判为异常）
3. **ML 能力空白**：孤立森林/XGBoost/DBSCAN 未落地，仅有阈值规则

**目标**：构建统一的 AIOps + FinOps ML 引擎，覆盖 ECS/RDS/Redis/SLB/K8s/OSS 全产品，支持分类特征编码、多维异常检测、成本预测、费用归因。

---

## 2. 成本归因（费用归因 — df_attr 来源）

df_attr（费用归因 DataFrame）**无需独立采集任务**，从统一 DataFrame 聚合即可：

```python
def compute_cost_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """按 product × env 汇总月费用，无需独立上游任务"""
    attr = df.groupby(['product', 'env']).agg(
        resource_count=('resource_id', 'count'),
        total_monthly_cost=('monthly_cost', 'sum'),
        avg_cpu_util=('cpu_util_avg', 'mean'),
        avg_mem_util=('mem_util_avg', 'mean'),
    ).reset_index()
    attr['cost_ratio'] = attr['total_monthly_cost'] / attr['total_monthly_cost'].sum()
    return attr
```

---

## 3. 成功标准

**月成本估算方案（方案 B — 无需 BSS API）**：
- ECS 月成本 = Σ(实例规格单价 × 数量) + Σ(云盘大小 × 云盘单价/月)
- RDS 月成本 = Σ(实例规格单价 × 数量) + Σ(存储大小 × 存储单价/月)
- Redis 月成本 = Σ(实例规格单价 × 数量)
- SLB 月成本 = 按量付费 Σ(流量 × 单价) 或 包年包月
- 规格单价表预置为 `data/unit_prices.json`（ecs_types.json / rds_types.json / redis_types.json）

| 编号 | 标准 | 验证方式 |
| S1 | 能并行拉取 6 类资源的云监控指标 | 跑通恰货铺子全量数据，无报错 |
| S2 | 能从 ResourceTag API 获取 project/product/env/owner/cost_center 标签 | Tag 数据与 DescribeInstances 数据 join 正确 |
| S3 | 孤立森林输出异常TOP10，按 product 分组，env=production 过滤 | 测试环境不进入异常列表 |
| S4 | XGBoost 输出月费用预测，MAE < 估算费用的 20% | 用规格×单价公式验证（无 BSS API 依赖） |
| S5 | DBSCAN 聚类输出同 product 同业务线实例，按 cost_per_core 排序 | 同产品线聚类，跨产品不聚类 |
| S6 | 输出 Markdown 格式报告，含异常列表 + 优化建议 + 负责人 | 报告可读性达到"直接发给 owner"的标准 |
| S7 | Python 依赖不超过 5 个（pandas/numpy/sklearn/xgboost/pyyaml） | pip list 验证 |

---

## 3. 架构设计

### 3.1 系统架构

```
用户输入（触发词）
    ↓
SKILL.md（解析触发词 → 确定跑哪些模块）
    ↓
aiops_engine.py（统一 ML 引擎）
    ├── DataCollector（数据采集层）
    │   ├── ECS: DescribeInstances + DescribeDisks + CMS DescribeMetricList（**必须加 --api-version 2019-05-01**）
    │   ├── RDS: DescribeDBInstances + DescribeDatabaseAttribute + CMS DescribeMetricList
    │   ├── Redis: DescribeInstances + CMS DescribeMetricList
    │   ├── SLB: DescribeLoadBalancers + DescribeMetricList
    │   ├── K8s: cs DescribeClusterNodes（**不是 CMS**，用 cs API）
    │   └── Tag: ResourceManager ListResources（统一标签）
    │       - 降级策略：若无 business_line 标签 → 从实例名称正则解析 → 仍无则标注 "未知"
    │       - 降级策略：若无 product/env 标签 → 从实例名称或集群名称推导 → 仍无则标注 "未知"
    │
    ├── FeatureEngine（特征工程层）
    │   ├── 标量特征：cpu/mem/disk/iops/net 利用率（归一化）
    │   ├── 派生特征：idle_ratio, cost_per_core, cost_per_gb
    │   └── 类别特征：product/env/business_line Label Encoding
    │
    ├── Models（ML 模型层）
    │   ├── IsolationForest：多维异常检测
    │   ├── XGBoost：月费用预测
    │   └── DBSCAN：同产品线聚类
    │
    └── ReportEngine（报告层）
        ├── Markdown 报告（异常TOP10 + 预测 + 聚类 + 归因）
        └── JSON 结构化输出（供 Agent 下游使用）
```

### 3.2 数据模型

```python
class Resource:
    resource_id: str
    resource_type: str        # ecs / rds / redis / slb / oss / k8s
    product: str              # h6 / crm / iwms / 到家 / 经营助手
    env: str                  # production / int / test
    project: str
    business_line: str         # 业务线（Tag 无此字段，fallback: 从名称解析或标注"未知"）
    owner: str
    cost_center: str
    cpu_cores: int
    memory_gb: float          # ECS Memory=int(MB)÷1024；RDS DBInstanceMemory=int(kB)÷1024²
    disk_gb: float            # 从 DescribeDisks（ECS）或 DescribeDatabaseAttribute（RDS）获取，非 DescribeInstances
    instance_type: str         # ecs.r9i.xlarge / mysql.r9i.large 等
    cpu_util_avg: float       # CPU利用率 %
    mem_util_avg: float       # 内存利用率 %
    disk_util_avg: float      # 磁盘使用率 %
    iops_util_avg: float      # IOPS利用率 %
    net_in_avg: float         # 内网入带宽 Mbps
    net_out_avg: float        # 内网出带宽 Mbps
    idle_ratio: float         # 综合闲置率 = 1 - max(cpu_util_avg, mem_util_avg)
    monthly_cost: float        # 预估月成本（由规格×单价估算表计算）
    # cost_per_core 不作为 IF 特征（它是待预测量的派生量，避免循环依赖）
```

### 3.3 ML 算法设计

#### 3.3.1 孤立森林（IsolationForest）

```python
features = [
    'cpu_util_norm', 'mem_util_norm', 'disk_util_norm',
    'iops_util_norm', 'net_util_norm',
    'cost_per_gb_norm',  # 移除了 cost_per_core（循环依赖：monthly_cost 是待预测量）
    'idle_ratio',
    'product_encoded', 'env_encoded'
]

# 按 product 分组建模（避免跨产品误报）
for product in df['product'].unique():
    subset = df[df['product'] == product]
    clf = IsolationForest(n_estimators=100, contamination=0.05)  # FinOps 场景 5% 更合理
    clf.fit(subset[features])
    subset['anomaly_score'] = clf.decision_function(subset[features])

# 只在 production 环境内判定异常
result = subset[(subset['env'] == 'production') & (subset['anomaly_score'] < 0)]
```

#### 3.3.2 XGBoost 成本预测

```python
features = [
    'cpu_cores', 'memory_gb', 'disk_gb',
    'cpu_util_avg', 'mem_util_avg', 'iops_util_avg',
    'net_in_avg', 'net_out_avg',
    'product_encoded', 'env_encoded',
    'is_prepaid', 'days_until_expire'
]
model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5)
model.fit(X_train, y_train)  # y = monthly_cost
```

#### 3.3.3 DBSCAN 聚类

```python
# 先按 product + business_line 分组，再对 production 环境聚类
for (product, business_line), group in df.groupby(['product', 'business_line']):
    group = group[group['env'] == 'production']
    if len(group) < 3:
        continue  # DBSCAN 要求 min_samples，样本不足跳过
    clustering_features = ['cost_per_gb', 'idle_ratio', 'cpu_util_norm']
    X = StandardScaler().fit_transform(group[clustering_features])
    # 使用 k-dist 图确定 eps：取第 min_samples 个最近邻距离的分位数
    # 或直接使用 eps=1.0（StandardScaler 后数据在 ~[-2,2]，1.0 覆盖约 60-70% 点）
    clustering = DBSCAN(eps=1.0, min_samples=3)
    group['cluster'] = clustering.fit_predict(X)
    # cluster = -1 的为离群点（同业务但规格差异大）
```

---

## 4. 文件结构

```
alicloud-aiops-ml/
├── SKILL.md                              # 入口：触发词 + 变量 + 执行流
├── aiops_engine.py                        # 核心引擎（~300行，不拆分）
└── references/
    ├── data-pipeline.md                    # 数据采集：各产品 API + Tag 汇聚
    ├── feature-engineering.md              # 特征工程：编码规则 + 派生指标
    ├── isolation-forest.md                 # 孤立森林：特征 + 分组 + 阈值
    ├── xgboost-cost-prediction.md         # XGBoost：特征 + 训练 + 验证
    ├── dbscan-clustering.md               # DBSCAN：分组逻辑 + 离群点判定
    ├── cost-attribution.md                # 费用归因：by product × by env
    └── report-template.md                 # 报告模板：Markdown + JSON 格式
```

---

## 5. 触发词设计

| 用户输入 | 解析为 | 含义 |
|---------|--------|------|
| "AIOps分析" | AIOps_all | 跑全部模块 |
| "异常检测" | IF_only | 只跑孤立森林 |
| "FinOps分析" | FinOps_all | 跑 IF + XGBoost + 归因 |
| "成本预测" | XGBoost_only | 只跑 XGBoost |
| "同业务线比对" | DBSCAN_only | 只跑 DBSCAN |
| "哪台ECS最浪费" | IF_top10 | IF 异常TOP10 |
| "下月账单预估" | XGBoost_predict | 月费用预测 |
| "资源利用率" | FinOps_all | 全量 |
| "帮我做个巡检" | AIOps_all | 全量 |
| "孤立森林" | IF_only | 只跑 IF |

---

## 6. 非功能需求

| 维度 | 要求 |
|------|------|
| **性能** | 全量分析（50个实例）< 60秒；单模块 < 15秒 |
| **依赖** | pip install pandas numpy scikit-learn xgboost pyyaml（5个） |
| **凭证** | 复用 `ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET` |
| **错误处理** | 单产品 API 失败不影响其他产品；记录失败产品到 `failed_products` |
| **可解释性** | 每个异常实例必须输出：哪些特征偏离最大 |

---

## 7. 验证计划

| 阶段 | 验证数据 | 通过标准 |
|------|---------|---------|
| 数据管道 | 恰货铺子 40台 ECS + 9个 RDS + 9个 Redis | 全部拉取成功，DataFrame 行数 = 资源总数 |
| 标签汇聚 | ResourceTag ListResources | 每个资源至少含 product + env 标签 |
| 孤立森林 | 手动标注的 5 个已知异常实例 | 全部被检出，且不在 test 环境 |
| XGBoost | 用规格×单价公式验证 | 预测误差 < 20% |
| DBSCAN | 同产品线 vs 跨产品线 | 同产品聚类内，跨产品不聚类 |
