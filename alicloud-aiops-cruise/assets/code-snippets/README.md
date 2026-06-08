# 阿里云全链路 AIOps 巡检 — Go Code Snippets

> 当 `aliyun` CLI 无法覆盖某些操作（主要是 DAS 数据库自治服务）时，Agent 从本目录动态生成 Go 代码并执行。
>
> **设计原则**：
> - 每个 `.go` 文件是一个独立的可执行零件，Agent 可 `go run` 单独运行
> - 不写大而全的独立巡检脚本（遵循选型 A 原则）
> - Agent 看到 DAS 需要时，动态生成 -> `go run` -> 取结果 -> 继续推理

## 前置条件

- Go 1.21+ (推荐 1.24+)
- 环境变量：
  - `ALIBABA_CLOUD_ACCESS_KEY_ID`
  - `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
  - `ALIBABA_CLOUD_REGION_ID`（DAS 固定为 `cn-shanghai`）

## 使用方式

```bash
cd alicloud-aiops-cruise/assets/code-snippets

# 第一次：拉取依赖
go mod tidy

# 查询 RDS 慢 SQL（替换 InstanceId）
INSTANCE_ID=rm-xxx go run das_slow_query.go

# 查询 RDS 性能洞察
INSTANCE_ID=rm-xxx go run das_performance_insight.go

# Redis 缓存分析（触发分析任务）
INSTANCE_ID=r-xxx NODE_ID=node-0 go run das_cache_analysis.go
```

## Snippet 清单

| 文件 | 用途 | 环境变量 |
|---|---|---|
| `das_slow_query.go` | 查询 RDS MySQL 慢 SQL 统计 + 样本 | `INSTANCE_ID` |
| `das_performance_insight.go` | RDS 性能洞察（等待事件分布） | `INSTANCE_ID` |
| `das_cache_analysis.go` | Redis 缓存分析（大key/热key） | `INSTANCE_ID`, `NODE_ID`(可选) |
| `main.go` | Client 工厂（被以上文件引用） | 自动读取 AK/SK |

## 注意事项

1. DAS 是单区域服务，endpoint 固定为 `das.cn-shanghai.aliyuncs.com`
2. 所有参数从环境变量读取，绝不硬编码
3. 输出为 JSON 格式，Agent 用 jq 解析
4. 所有 snippet 遇到错误立即 `log.Fatalf` 退出