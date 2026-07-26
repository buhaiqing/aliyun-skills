# PLAN: alicloud-aiops-ml Phase 1 — 并行开发计划

**基于**: SPEC.md v0.1  
**目标**: 跑通 AIOps + FinOps ML 全链路（XX项目数据验证）

> **注**：本文档中"XX项目"为代称，指代实际验证用的租户/项目。

---

## 安全约束

**🔴 只读原则**：本模块为 FinOps 巡检分析工具，**全程只读**，禁止任何资源变更操作。

| 约束 | 说明 |
|------|------|
| **只读 API** | 仅调用 `Describe*` / `List*` / `Get*` 类 API |
| **禁止写入** | 禁止 `Create*` / `Update*` / `Delete*` / `Modify*` / `Release*` 等写操作 |
| **本地输出** | 分析结果仅写入本地文件（报告、CSV），不修改云资源 |
| **CLI 白名单** | cli_utils.py 中硬编码只读 API 前缀白名单，调用非只读 API 直接报错 |

---

## 运维约束

### 错误处理

| 错误类型 | 策略 |
|---------|------|
| **API 限流（Throttling）** | 指数退避重试，最多 3 次，初始间隔 1s |
| **凭证失效** | 立即停止，提示用户检查 AK/SK |
| **资源不存在** | 跳过该资源，记录 WARN 日志 |
| **网络超时** | 重试 2 次，间隔 2s |

### 凭证安全

| 约束 | 说明 |
|------|------|
| **环境变量** | 凭证从 `ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET` 读取 |
| **日志掩码** | 输出中 AK/SK 自动替换为 `****` |
| **本地存储** | 不将凭证写入任何本地文件 |

---

## Phase 1 任务分解

### 三条并行 Track

```
Track A：数据采集（5个独立任务，可5人并行）
  ├─ A1: 公共模型 + CLI Wrapper    ← 所有任务的前置
  ├─ A2: ECS 数据采集器
  ├─ A3: RDS/Redis 数据采集器
  ├─ A4: SLB/OSS/K8s 数据采集器
  └─ A5: Tag 标签采集器
        ↓ 汇聚
Track B：特征工程（2个任务，可2人并行）
  ├─ B1: 数据汇聚层（依赖 A2~A5）
  └─ B2: 特征工程（依赖 B1）
        ↓
Track C：ML 模型 + 报告（4个任务，C1/C2/C3 可3人并行）
  ├─ C1: IsolationForest（依赖 B2）
  ├─ C2: XGBoost（依赖 B2）
  ├─ C3: DBSCAN（依赖 B2）
  └─ C4: 报告生成器（依赖 C1+C2+C3）
        ↓
Track D：集成测试（1个任务）
  └─ D1: 全链路验证（依赖 A+B+C）
```

---

## 任务卡清单

### A1：公共数据模型 + CLI Wrapper
```
文件：resource_model.py + cli_utils.py
依赖：无（外部无依赖）
并行：独立（A1 不依赖任何其他任务）
**⚠️ 重要**：A1 是所有其他任务（A2~A5）的实际依赖，A2~A5 的 `import cli_utils` 必须在 A1 完成之后。建议开发顺序：**A1 先完成，再并行 A2~A5**。
输出：
  - Resource 数据类（统一字段定义，含 unit 注释）
  - cli_call(cmd) → JSON，错误处理、超时、凭证掩码
  - **只读保护**：内置 API 白名单，非只读调用直接拒绝
验证：python -c "from resource_model import Resource; print('OK')"
```

### A2：ECS 数据采集器
```
文件：ecs_collector.py
依赖：A1（cli_utils.py）
并行队友：A1完成后 → A3/A4/A5 并行
**⚠️ 实际并行时机**：A1 完成后才可开始开发
**数据来源**：
  - DescribeInstances → 实例规格（Memory=int(MB)÷1024=GB）
  - DescribeDisks → 云盘大小（disk_gb 必须从此获取，DescribeInstances 无此字段）
  - CMS acs_ecs_dashboard → 监控指标（**必须加 --api-version 2019-05-01**）
采集指标：cpu.utilization, memory.usedutilization, disk.read.bytes, disk.write.bytes, disk.read.iops, disk.write.iops, InternetIn.rate, InternetOut.rate
输出：
  - fetch_ecs_instances() → DescribeInstances + DescribeDisks
  - fetch_ecs_metrics(days=7) → CMS DescribeMetricList
验证：python -c "from ecs_collector import fetch_ecs_instances; print(len(fetch_ecs_instances()))"
```

### A3：RDS + Redis 数据采集器
```
文件：db_collector.py
依赖：A1（cli_utils.py）
并行队友：A1完成后 → A2/A4/A5 并行
**⚠️ 实际并行时机**：A1 完成后才可开始开发
**数据来源**：
  - DescribeDBInstances + DescribeDatabaseAttribute → 实例规格
  - Memory单位：DBInstanceMemory=int(kB)÷1024²=GB
  - CMS acs_rds_dashboard → RDS监控指标
  - CMS acs_kvstore_dashboard → Redis监控指标
采集指标：CPUUtilization, MemoryUsage, DiskUsage, QPS, ConnectionUsage, IOPSUsage
输出：
  - fetch_rds_instances() → DescribeDBInstances + DescribeDatabaseAttribute
  - fetch_redis_instances() → r-kvstore DescribeInstances
验证：python -c "from db_collector import fetch_rds_instances; print(len(fetch_rds_instances()))"
```

### A4：SLB + OSS + K8s 数据采集器
```
文件：net_collector.py
依赖：A1（cli_utils.py）
并行队友：A1完成后 → A2/A3/A5 并行
**⚠️ 实际并行时机**：A1 完成后才可开始开发
**⚠️ K8s 数据来源**：K8s node allocatable **不是 CMS 指标**，是 CS API 的结果。调 `aliyun cs GET /clusters/{id}/nodes` 获取节点 allocatable CPU/Memory。
采集指标：
  - SLB: DescribeLoadBalancers + acs_slb_dashboard (TrafficRX, TrafficTX, Qps)
  - OSS: DescribeBuckets + GetBucketStat（存储量，**不是 CMS**）
  - K8s: cs GET /clusters → cs GET /clusters/{id}/nodes
输出：
  - fetch_slb_loadbalancers() → DescribeLoadBalancers
  - fetch_oss_buckets() → DescribeBuckets + GetBucketStat
  - fetch_k8s_clusters() → cs GET /clusters
  - fetch_k8s_nodes(cluster_id) → cs GET /clusters/{id}/nodes
验证：python -c "from net_collector import fetch_slb_loadbalancers; print(len(fetch_slb_loadbalancers()))"
```

### A5：Tag 标签采集器
```
文件：tag_collector.py
依赖：A1（cli_utils.py）
并行队友：A1完成后 → A2/A3/A4 并行
**⚠️ 实际并行时机**：A1 完成后才可开始开发
**⚠️ business_line 不存在于阿里云 Tag**：必须 fallback 到名称解析，仍无则标注 "unknown"
标签来源（优先级）：
  Level 1 → ResourceManager ListResources（最权威）
  Level 2 → 实例名称正则解析（见 tag-enrichment-strategy.md）
  Level 3 → 标注 "unknown"
输出：
  - fetch_all_tags() → ResourceManager ListResources（所有资源类型）
  - tags_to_dataframe(tags) → 宽表 DataFrame（resource_id × tag_key）
  - enrich_resources(df, tags) → DataFrame join 标签 + 名称 fallback
验证：python -c "from tag_collector import fetch_all_tags; tags = fetch_all_tags(); print(len(tags))"
```

---

### B1：数据汇聚层
```
文件：data_pipeline.py
依赖：A2+A3+A4+A5（数据部分）
并行队友：B2
输出：
  - collect_all(region, days=7) → 并行调 A2~A4
  - enrich_with_tags(df, tags) → join A5 的标签
  - to_unified_df() → 统一 DataFrame
验证：python -c "from data_pipeline import collect_all; df = collect_all(); print(df.shape)"
```

### B2：特征工程
```
文件：feature_engine.py
依赖：B1
并行队友：B1
输出：
  - normalize_scalar_features(df) → cpu_util_norm, mem_util_norm 等
  - compute_derived_features(df) → idle_ratio, cost_per_core, cost_per_gb
  - encode_categorical(df) → product_encoded, env_encoded
验证：python -c "from feature_engine import build_features; df = build_features(); print([c for c in df.columns if '_norm' in c or '_encoded' in c])"
```

---

### C1：IsolationForest 孤立森林
```
文件：iforest_detector.py
依赖：B2
并行队友：C2/C3
输出：
  - detect(df, by_product=True, contamination=0.1)
  - 输出：anomaly_score, is_anomaly, top_features
关键设计：
  - 按 product 分组建模（避免跨产品误报）
  - 只对 env=production 判定异常
  - 输出偏离最大的特征名（可解释性）
验证：python -c "from iforest_detector import detect; df = detect(); print(df[df.is_anomaly].head())"
```

### C2：XGBoost 成本预测
```
文件：xgboost_predictor.py
依赖：B2
并行队友：C1/C3
输出：
  - predict_monthly_cost(df)
  - predict_with_confidence(df) → 预测值 ±20% 置信区间
  - evaluate(pred, actual) → MAE < 20%
特征：cpu_cores, memory_gb, disk_gb, *_util_avg, product_encoded, is_prepaid, days_until_expire
验证：python -c "from xgboost_predictor import predict; df = predict(); print(df[['resource_id','predicted_cost']].head())"
```

### C3：DBSCAN 聚类
```
文件：dbscan_cluster.py
依赖：B2
并行队友：C1/C2
输出：
  - cluster(df, by=['product','business_line'])
  - 只对 env=production 聚类
  - cluster_id=-1 为离群点（同业务但规格差异大）
验证：python -c "from dbscan_cluster import cluster; df = cluster(); print(df[df.cluster_id==-1][['resource_id','product','cost_per_core']].head())"
```

### C4：Markdown 报告生成器
```
文件：report_generator.py
依赖：C1+C2+C3
并行队友：无（顺序）
输出：
  - generate_markdown(df_if, df_xgb, df_dbscan, df_attr)
  - generate_json(df_if, df_xgb, df_dbscan, df_attr)
报告节：
  - 执行摘要（资源总数 / 异常数 / 月费用预测 / 预估节省）
  - 异常TOP10（instance / product / env / anomaly_score / top_features）
  - 费用预测（按 product 汇总 / 置信区间）
  - 同产品线离群点（cluster_id=-1 实例列表）
  - 费用归因（by product × by env）
  - 优化建议（含优先级：P0/P1/P2）
验证：python -c "from report_generator import generate; print(generate(...))" # 输出非空
```

---

### D1：集成测试（XX项目全量验证）
```
文件：test_integration.py
依赖：A+B+C 全部
输出：test_full_pipeline() + test_target_project()
通过标准：
  ✓ 全链路跑通，无报错
  ✓ 测试环境（env=int/test）不进入异常列表
  ✓ 资源总数 = 实际总数（ECS+RDS+Redis+SLB）
  ✓ 执行时间：50实例 < 60秒
  ✓ 报告包含所有6个章节
验证：python -m pytest test_integration.py -v
```

---

## 依赖关系图（含实际并行时机）

```
Phase 1（A1先行，A2~A5 等待 A1 完成后再并行）：
A1 ─┬─→ A2 ─┐
    ├─→ A3 ─┤
    ├─→ A4 ──┼──→ B1 ──→ B2 ──┬──→ C1 ─┐
    └─→ A5 ─┘                 ├──→ C2 ─┼──→ C4 ──→ D1
                               └──→ C3 ─┘

实际并行度：
  A1 期间：A1 独立开发（1人）
  A2~A5 期间：4人并行（等待 A1 完成，约1~2人日）
  B1 期间：1人（必须等 A2~A5 完成）
  B2 期间：1人（等 B1）
  C1/C2/C3 期间：3人并行（等 B2）
  C4 期间：1人（等 C1+C2+C3）
  D1 期间：1人（等全部）

Critical Path = A1(1日) + A2~A5(2日) + B1(1日) + B2(1日) + C1/C2/C3(1日) + C4(0.5日) + D1(1日) = 7.5人日
```

---

## 文件最终结构

```
alicloud-aiops-ml/
├── aiops_engine.py                    # 入口脚本（import 各模块，main()）
├── resource_model.py                 # A1: 统一数据类
├── cli_utils.py                      # A1: CLI 通用封装
├── ecs_collector.py                  # A2: ECS 采集
├── db_collector.py                   # A3: RDS+Redis 采集
├── net_collector.py                  # A4: SLB+OSS+K8s 采集
├── tag_collector.py                   # A5: Tag 采集
├── data_pipeline.py                  # B1: 数据汇聚
├── feature_engine.py                 # B2: 特征工程
├── iforest_detector.py              # C1: 孤立森林
├── xgboost_predictor.py             # C2: XGBoost
├── dbscan_cluster.py                # C3: DBSCAN
├── report_generator.py               # C4: 报告生成
├── test_integration.py               # D1: 集成测试
└── references/
    ├── api-capability-matrix.md
    ├── finops-data-pipeline.md
    ├── tag-enrichment-strategy.md
    ├── cost-model-reference.md
    ├── feature-engineering.md        # B2: 特征工程
    ├── isolation-forest.md           # C1: 孤立森林
    ├── xgboost-cost-prediction.md   # C2: XGBoost
    ├── dbscan-clustering.md        # C3: DBSCAN
    └── report-template.md            # C4: 报告模板
```

---

## 接口契约（关键：统一 DataFrame 列名）

各任务 DataFrame 输出必须遵循以下列名规范：

| 列名 | 类型 | 来源 | 说明 |
|------|------|------|------|
| resource_id | str | 各采集器 | ECS InstanceId / RDS DBInstanceId / Redis InstanceId |
| resource_type | str | 各采集器 | ecs / rds / redis / slb / oss / k8s_node |
| instance_name | str | 各采集器 | 实例名称 |
| instance_type | str | 各采集器 | 规格名（如 g9i.2xlarge） |
| product | str | Tag join + 名称解析 | 产品线标识（如 app-x / service-y）/ unknown |
| env | str | Tag join + 名称解析 | production / int / test / unknown |
| owner | str | Tag（必须） | 负责人，无则 unknown |
| cpu_cores | int | 各采集器 | 核心数 |
| memory_gb | float | 各采集器 | 内存（已换算为 GB） |
| disk_gb | float | DescribeDisks/RDS属性 | 云盘/存储大小（GB） |
| cpu_util_avg | float | CMS | 7天 CPU 利用率均值（%） |
| mem_util_avg | float | CMS | 7天 内存利用率均值（%） |
| disk_util_avg | float | CMS | 磁盘使用率（%） |
| iops_util_avg | float | CMS | IOPS 使用率（%） |
| net_in_avg | float | CMS | 内网入带宽均值（Mbps） |
| net_out_avg | float | CMS | 内网出带宽均值（Mbps） |
| monthly_cost | float | 规格×单价估算 | 月成本（元） |
| is_prepaid | int | DescribeInstances | 1=包年包月，0=按量 |
| days_until_expire | int | 到期日计算 | 距到期天数 |

---

## 工时估算

| Phase | 任务 | 工时 | 前置依赖 |
|-------|------|------|---------|
| Phase 1 | A1 公共模型+CLI | 1人日 | 无 |
| | A2~A5 采集器 | 2人日 | A1 |
| Phase 2 | B1 数据汇聚 | 1人日 | A2~A5 |
| | B2 特征工程 | 1人日 | B1 |
| Phase 3 | C1/C2/C3 ML模型 | 1人日 | B2 |
| | C4 报告生成 | 0.5人日 | C1~C3 |
| Phase 4 | D1 集成测试 | 1人日 | A+B+C |
| **合计** | | **7.5人日** | |
