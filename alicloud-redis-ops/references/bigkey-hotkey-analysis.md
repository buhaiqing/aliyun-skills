# Big Key / Hot Key Analysis — Alibaba Cloud Redis / Tair (KVStore)

大 Key / 热 Key 分析的权威流程。控制面（`r-kvstore`）**没有**直接返回 Key 级分布的 API，
因此采用两条路径：**阿里云 CLI 调用 DAS API（首选，只读、无需改实例配置）** 与
**云助手 redis-cli（兜底，数据面）**。

## 1. 方法选择

| 方法 | 接口 / 命令 | 数据来源 | 适用 | 约束 |
|---|---|---|---|---|
| DAS 实时统计 | `DescribeHotBigKeys` | 当前内存实时数据 | 快速定位当前热 Key / 大 Key | Redis 开源版或 Tair 内存型；需最新小版本 |
| DAS 历史 Top | `DescribeTopHotKeys` / `DescribeTopBigKeys` | 最近 4 天采样 | 复盘一段时间内 Top 100 | 单次窗口 ≤ 3 小时；仅最近 4 天 |
| DAS 离线全量 | `CreateCacheAnalysisJob` + `DescribeCacheAnalysisJob` | Redis 备份文件 | 全量 Key 分布、过期时间、按字节/元素数排序的 Top 500 | 异步任务；10s 轮询，600s 上限；仅 Redis 引擎 |
| 云助手 redis-cli | `--bigkeys` / `--hotkeys` / `MEMORY USAGE` / `OBJECT FREQ` | 实例数据面 | DAS 不可用、自建 Redis、临时排查 | `--hotkeys` 要求 LFU 淘汰策略；扫描产生额外负载 |

**默认路径：阿里云 CLI + DAS API。** 仅当 DAS 未接入实例、权限不足或需要即时 ad-hoc 扫描时，
走云助手数据面路径（见 §4）。

**禁止事项：**

- 不要用 `KEYS *` 做全量扫描（阻塞主线程）；DAS 和 `--bigkeys` 内部基于采样/SCAN。
- 不要为了跑 `--hotkeys` 静默执行 `CONFIG SET maxmemory-policy ...`；这属于
  `CONFIG-MUTATION`，必须走 `ModifyParameter` 并取得用户显式确认。
- 不要用 `MONITOR` 长时间抓包来推断热 Key（高开销、含敏感数据）。

## 2. 判定规则与阈值

### 2.1 DAS 官方判定规则

| 类别 | 规则 | 依据 |
|---|---|---|
| 热 Key | Key 的 QPS > 3000 记为热 Key；`HotKeys` 按 QPS 排序 | DAS `DescribeHotBigKeys` / `DescribeTopHotKeys` |
| 热 Key（流量） | `Category=traffic` 时按入/出流量统计，官方未给固定阈值 | `DescribeTopHotKeys` |
| 大 Key | `list` / `hash` / `set` / `zset` 按**元素数量**排序，Top 3 记为大 Key | DAS `DescribeHotBigKeys` / `DescribeTopBigKeys` |
| 大 Key（离线） | 按占用字节数和元素数分别给出 Top 500（`BigKeys` / `BigKeysOfNum`） | `DescribeCacheAnalysisJob` |

> 注意：`DescribeTopBigKeys.Data.BigKey[].Size` 和 `DescribeHotBigKeys.Data.BigKeys.BigKey[].Size`
> 表示**元素数量**，不是内存字节数；需要字节数请用离线分析的 `Bytes` 字段或 `MEMORY USAGE`。

### 2.2 运维建议阈值（非官方固定值，用于风险分级）

| 类型 | 关注 | 严重 |
|---|---|---|
| `string` | ≥ 10 KB | ≥ 100 KB |
| `hash` / `list` / `set` / `zset` | ≥ 5,000 元素 | ≥ 50,000 元素 |
| 热 Key | QPS ≥ 3,000 | 单 Key 占节点 QPS ≥ 30% 或出现 `CROSSSLOT` / 集群倾斜 |
| 无 TTL 的大 Key | 任意大 Key 且 `ExpirationTimeMillis=0` | 且内存使用率 > 85% |

## 3. 方法一：阿里云 CLI（首选）

本地 `aliyun` CLI 3.3.14 已内置 DAS 2020-01-16 API。使用 **CamelCase API 名**
（`aliyun das DescribeHotBigKeys`）；kebab-case（`describe-hot-big-keys`）需额外安装
`aliyun-cli-das` 插件。所有 DAS CLI 调用优先走
[`alicloud-das-ops/scripts/das-harness-wrapper.sh`](../../alicloud-das-ops/scripts/das-harness-wrapper.sh)
（自修复 + 追踪），wrapper 不可用时退回原生 `aliyun das`；不要裸调绕过 wrapper（GCL §2.4）。

### 3.1 预检（MANDATORY）

| 检查项 | 方法 | 通过条件 | 失败处理 |
|---|---|---|---|
| CLI | `aliyun version` | ≥ 3.x，`aliyun help das` 可见目标 API | 安装/升级 CLI；或安装 `aliyun-cli-das` 插件 |
| Wrapper | `test -x ../alicloud-das-ops/scripts/das-harness-wrapper.sh` | 可执行 | 退回原生 `aliyun das` |
| 凭据 | 环境变量 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 非空 | HALT，不向用户索取明文密钥 |
| 引擎与状态 | `./scripts/redis-harness-wrapper.sh describe-instances --InstanceId {{user.instance_id}}` | Redis/Tair，状态 `Normal` | HALT |
| DAS 接入 | `"$DAS_WRAPPER" GetInstanceInspections --InstanceId {{user.instance_id}}` | 已注册（不报 `NotFound`） | 先 `AddHDMInstance`（告知轻微开销） |
| 小版本 | `DescribeInstanceAttribute` + `DescribeEngineVersion` | 最新小版本（Top 接口硬性要求） | 建议 `UpgradeMinorVersion`，需用户确认 |
| 地域/端点 | 固定 `--RegionId cn-shanghai`、`--endpoint das.cn-shanghai.aliyuncs.com` | 可达 | VPC 内改用 `das.vpc-proxy.aliyuncs.com` |
| RAM | `hdm:DescribeHotBigKeys` / `hdm:DescribeTopHotKeys` / `hdm:DescribeTopBigKeys` / `hdm:CreateCacheAnalysisJob` / `hdm:DescribeCacheAnalysisJob` | 已授权 | 委托 `alicloud-ram-ops` |
| 时间窗口 | 用户给定 StartTime/EndTime | 最近 4 天内、窗口 ≤ 3 小时 | 拆分多个窗口 |

### 3.2 通用调用形式

```bash
DAS_WRAPPER=../alicloud-das-ops/scripts/das-harness-wrapper.sh
"$DAS_WRAPPER" DescribeHotBigKeys \
  --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com \
  --InstanceId "{{user.instance_id}}"
# 集群指定分片：追加 --NodeId r-x****-db-0
```

默认输出 JSON（`$.Code=="200"` 且 `$.Success=="true"` 才算成功）。
需要表格输出时可用 CLI 的 `--output cols=... rows=...`，但归一化/聚合建议用下面的脚本。

### 3.3 实时大 Key / 热 Key（默认）

```bash
"$DAS_WRAPPER" DescribeHotBigKeys --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com --InstanceId "{{user.instance_id}}"
```

| 返回字段 | 内容 |
|---|---|
| `$.Data.HotKeys.HotKey[]` | `Key`、`Db`、`KeyType`、`Hot`（QPS 区间）、`Lfu`、`Size`、`NodeId` |
| `$.Data.BigKeys.BigKey[]` | `Key`、`Db`、`KeyType`、`Size`（元素数）、`NodeId` |
| `$.Data.HighTrafficKeys` / `LargeKeys` | 按流量 / 内存排序的补充列表 |
| `$.Data.*Msg` | 非空表示该维度不可用（如 `current version doesn't support`），标注「不支持」而非 0 |

### 3.4 历史 Top Key（4 天内，单次 ≤ 3 小时）

```bash
"$DAS_WRAPPER" DescribeTopBigKeys --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com --InstanceId "{{user.instance_id}}" \
  --StartTime 1764000000000 --EndTime 1764001800000
"$DAS_WRAPPER" DescribeTopHotKeys --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com --InstanceId "{{user.instance_id}}" \
  --StartTime 1764000000000 --EndTime 1764001800000
```

`DescribeTopBigKeys` 返回 `$.Data.BigKey[]`；`DescribeTopHotKeys` 返回 `$.Data.HotKey[]`
（`Key`、`Db`、`KeyType`、`Hot`、`Lfu`、`NodeId`、`Category`、`InBytes`、`OutBytes`）。
时间窗口超过 3 小时必须分片查询后按 `Key` + `NodeId` + `Db` 合并去重。

### 3.5 离线全量分析（字节维度 / 过期时间分布）

```bash
"$DAS_WRAPPER" CreateCacheAnalysisJob --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com --InstanceId "{{user.instance_id}}"
# $.Data.JobId

"$DAS_WRAPPER" DescribeCacheAnalysisJob --RegionId cn-shanghai \
  --endpoint das.cn-shanghai.aliyuncs.com --InstanceId "{{user.instance_id}}" \
  --JobId "{{output.job_id}}"
```

`CreateCacheAnalysisJob` 可选 `--BackupSetId`（不传则系统自动备份）、`--NodeId`、`--Separators`。
`$.Data.TaskState` 终态：`FINISHED` / `FAILED`（中间态 `BACKUP`、`ANALYZING`；
部分旧文档写 `SUCCESS`，轮询时两者都当作成功终态）。10s 轮询，最多 600s。

| 字段 | 内容 |
|---|---|
| `$.Data.BigKeys.KeyInfo[]` | 按字节降序，`Key`、`Type`、`Bytes`、`Count`、`Db`、`Encoding`、`ExpirationTimeMillis`、`NodeId` |
| `$.Data.BigKeysOfNum.KeyInfo[]` | 按元素数降序，字段同上 |
| `$.Data.UnexBigKeysOfBytes` / `UnexBigKeysOfNum` | 永不过期 Key 分布 |
| `$.Data.KeyPrefixes.Prefix[]` | `Prefix`、`KeyNum`、`Type`、`Bytes`、`Count` |
| `$.Data.ExpiryKeysLevelCount.ExpiryLevel[]` | `Level`（0=不过期，1=已过期，2~8=各时长档）、`TotalKeys`、`TotalBytes`、`AnalysisTs` |

`AnalysisTs` / `ExpirationTimeMillis` 为 Unix **毫秒**，展示时转 ISO 8601；
`ExpirationTimeMillis=0` 表示不过期。

### 3.6 一键脚本（推荐）

[`scripts/analyze-bigkeys-hotkeys.sh`](../scripts/analyze-bigkeys-hotkeys.sh) 封装了
CLI 调用、离线轮询、字段归一化和统一 JSON 输出：

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"   # 实际值来自环境，勿写入命令行历史

cd /path/to/aliyun-skills
./alicloud-redis-ops/scripts/analyze-bigkeys-hotkeys.sh r-bp1xxx                # 实时（默认）
./alicloud-redis-ops/scripts/analyze-bigkeys-hotkeys.sh r-bp1xxx top \
  --start-ms 1764000000000 --end-ms 1764001800000                              # 历史 Top
./alicloud-redis-ops/scripts/analyze-bigkeys-hotkeys.sh r-bp1xxx offline \
  --poll-interval 10 --max-wait 600                                            # 离线全量
```

脚本输出即 §5 的统一 schema（stdout 为 JSON，进度日志走 stderr）；
不会修改实例配置或数据，`offline` 模式只创建分析任务。

## 4. 方法二：云助手 redis-cli（兜底）

复用 [redis-cli-execution.md](./redis-cli-execution.md) 的「合并执行」脚本
（幂等安装 redis-cli + `REDISCLI_AUTH` + 网络检查 + 命令执行），仅替换命令：

```bash
export REGION="{{user.region}}"
export ECS_ID="{{user.ecs_instance_id}}"
export REDIS_HOST="{{user.redis_host}}"     # 由 describe-instance-attribute 获取
export REDIS_PORT="{{user.redis_port|6379}}"
export REDIS_PASSWORD="{{user.redis_password|}}"
export REDIS_COMMAND="--bigkeys -i 0.1"     # 大 Key：-i 限制每次 SCAN 的间隔（秒）
# 或
export REDIS_COMMAND="--hotkeys"             # 热 Key：仅 LFU 策略下有效
```

- 控制面取连接地址必须走 wrapper：
  `./scripts/redis-harness-wrapper.sh describe-instance-attribute --InstanceId {{user.instance_id}}`。
- 集群实例加 `-c`（例如 `--bigkeys -i 0.1 -c`）；云助手 `--Timeout` 建议 ≥ 300s。
- `--hotkeys` 前置检查：`INFO stats` / `CONFIG GET maxmemory-policy`；若非 `allkeys-lfu`
  或 `volatile-lfu`，**停止并提示用户**，不得自动修改。可通过 DAS CLI 路径绕过此限制。
- 需要精确定位单个 Key 时，用 `MEMORY USAGE <key>`、`STRLEN`、`HLEN`/`LLEN`/`SCARD`/`ZCARD`、
  `OBJECT ENCODING`，均为只读；`OBJECT FREQ` 同样要求 LFU。
- 数据面命令按 [rubric.md §1.2.1](./rubric.md) 分类：`--bigkeys` / `--hotkeys` /
  `MEMORY USAGE` 等为 `READ-ONLY`；`--hotkeys` 不修改数据，但**开启 LFU 的
  `CONFIG SET` 为 `CONFIG-MUTATION`**，必须单独获得确认。

## 5. 统一输出格式

`analyze-bigkeys-hotkeys.sh` 直接输出以下 schema；手动执行 CLI 时按相同结构汇总：

```json
{
  "analysis_type": "bigkey_hotkey",
  "resource_type": "redis",
  "resource_id": "r-bp1zxszhcgatnx****",
  "source": "DescribeHotBigKeys",
  "analysis_time": "2026-11-25T10:00:00Z",
  "dimensions": [
    {"name": "大Key", "status": "warning", "count": 2, "max_bytes": 153600},
    {"name": "热Key", "status": "critical", "count": 1, "max_qps": "~12000"}
  ],
  "big_keys": [
    {"key": "cache:report:2026", "type": "hash", "bytes": 153600, "elements": 82000,
     "db": 0, "node_id": "r-x****-db-0", "ttl": 0}
  ],
  "hot_keys": [
    {"key": "seckill:sku:1001", "type": "string", "qps": "10000~12000",
     "db": 0, "node_id": "r-x****-db-0", "lfu": 253, "category": "qps"}
  ],
  "requests": [{"api": "DescribeHotBigKeys", "request_id": "B6D17591-****"}],
  "recommendations": [
    "cache:report:2026 为 82,000 元素的 hash 且无 TTL，建议按业务维度拆分并设置过期时间",
    "seckill:sku:1001 QPS 超 3,000，建议本地缓存或读写分离"
  ]
}
```

展示给用户的字段必须脱敏：只输出 Key 名称（业务方确认后），不输出任何
AccessKey、`REDISCLI_AUTH` 或 `AccountPassword`； trace 中同样禁止出现。

## 6. 治理建议（按分析结果触发，仅建议不自动执行）

| 发现 | 建议 | 风险提示 |
|---|---|---|
| 大 Key（string ≥ 10KB） | 压缩、拆分、缩短 TTL | 改数据结构需业务侧配合 |
| 大 Key（容器元素多） | 按前缀/时间分片，使用 `HSCAN`/`SSCAN` 分批读取 | 禁止 `HGETALL` 一次性取回 |
| 无 TTL 大 Key | 设置 `EXPIRE` 或 `EXPIREAT` | 写操作，需用户确认具体 Key |
| 清理大 Key | 使用 `UNLINK` 而非 `DEL`，低峰期执行 | 属于 `WRITE-KEY`/`DESTRUCTIVE-MASS`，按 GCL 规则确认 |
| 热 Key（QPS 高） | 应用侧本地缓存、读写分离、加只读实例、Key 打散 | 扩容/变配走 `ModifyInstanceSpec` |
| 热 Key（流量高） | 压缩 Value、缩短 Key、使用 Tair 数据类型 | 结合 `InBytes`/`OutBytes` 判断 |
| 内存持续高 + 大 Key 多 | 评估 `ModifyInstanceSpec` 或分片架构 | 需用户确认，变配有短暂连接中断 |

## 7. Failure Recovery

| 错误 / 现象 | 处理 |
|---|---|
| `NoPermission` (403) | 检查 `hdm:*` RAM 授权，委托 `alicloud-ram-ops` |
| `InvalidParams` (400) | 校验 InstanceId、时间窗口（≤3h、近 4 天）、时间戳单位（毫秒） |
| `current version doesn't support` | 升级小版本（`UpgradeMinorVersion`，需确认）或改用离线分析 / redis-cli |
| 实例未接入 DAS | `AddHDMInstance` 后重试，提前告知轻微开销 |
| 离线任务 `FAILED` | 读 `$.Data.Message` / `errorMessage`；确认备份可用后重试 |
| 轮询超过 600s | 脚本退出并打印 JobId，让用户后续查询，不返回伪造结果 |
| `--hotkeys` 无输出 | 检查 LFU 策略；不要自动 `CONFIG SET` |
| 云助手退出码 20/21/22/30/40 | 按 [redis-cli-execution.md](./redis-cli-execution.md) 的退出码全表处理 |

## 8. 参考

- [DAS 集成](../../alicloud-das-ops/references/integration.md) — DAS 地域/端点/SDK 约束
- [DAS API 映射](../../alicloud-das-ops/references/api-doc-mapping.md) — `CreateCacheAnalysisJob` 等 API 文档
- [一键分析脚本](../scripts/analyze-bigkeys-hotkeys.sh) — CLI 调用 + 轮询 + 归一化输出
- [redis-cli 数据面执行](./redis-cli-execution.md) — 云助手合并脚本、退出码、诊断日志
- [GCL Rubric](./rubric.md) — 数据面命令分类与凭证脱敏门禁
- [监控与告警](./monitoring.md) — 内存/QPS/延迟指标关联分析
