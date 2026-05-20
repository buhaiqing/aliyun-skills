# JIT SDK 预编译缓存架构设计

> **Purpose:** 解决 JIT SDK 冷启动延迟问题，将启动时间从 45s 优化至 <500ms
> **Version:** 1.0.0
> **Last Updated:** 2026-05-20
> **Status:** P0 - 高优先级

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [问题分析](#2-问题分析)
3. [架构设计](#3-架构设计)
4. [缓存策略](#4-缓存策略)
5. [增量构建](#5-增量构建)
6. [实现路线图](#6-实现路线图)
7. [度量与验证](#7-度量与验证)

---

## 1. 执行摘要

### 1.1 目标指标

| 指标 | 当前值 | 目标值 | 优化幅度 |
|------|--------|--------|----------|
| 首次 JIT 构建 | ~45s | <500ms | **99%** |
| Go 依赖下载 | ~30s | 0s (预下载) | **100%** |
| 编译时间 | ~15s | <3s | **80%** |

### 1.2 核心策略

```yaml
预编译缓存方案:
  - 按产品预编译常用 SDK 操作
  - 缓存位置: ~/.cache/aliyun-skills/
  - Go build -buildmode=archive 复用
  - 增量构建支持
```

---

## 2. 问题分析

### 2.1 当前瓶颈

```
JIT SDK 冷启动流程:
  1. 解析产品/操作 → 查找 SDK 版本
  2. go mod init → 初始化模块 (2s)
  3. go get sdk → 下载依赖 (30s)
  4. go build → 编译代码 (15s)
  5. 执行操作 → 调用 API
```

### 2.2 根因分析

| 阶段 | 耗时 | 根因 | 优化方向 |
|------|------|------|----------|
| 依赖下载 | 30s | 每次从 proxy 下载 | 预编译二进制 |
| 编译 | 15s | 无增量构建 | archive 复用 |
| 初始化 | 2s | 重复创建 go.mod | 缓存模板 |

---

## 3. 架构设计

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Skill 调用层                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  SDK 缓存管理器                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  缓存查找     │  │  缓存更新     │  │  过期清理     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
           ┌────────────────┼────────────────┐
           ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ 预编译二进制  │ │ 源码缓存     │ │ 依赖镜像     │
    │ .bin/        │ │ .src/        │ │ .pkg/        │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 3.2 缓存目录结构

```
~/.cache/aliyun-skills/
├── bin/                              # 预编译二进制
│   ├── ecs-20200430-
│   │   ├── DescribeInstances
│   │   ├── StartInstance
│   │   └── StopInstance
│   ├── rds-20140815-
│   │   ├── DescribeDBInstances
│   │   └── DescribeSlowLogs
│   ├── cms-20190101-
│   │   ├── DescribeMetricList
│   │   └── DescribeMetricData
│   └── das-20200116-
│       ├── CreateDiagnosticReport
│       └── GetDasSQLLogHotKeys
├── src/                              # 源码模板
│   ├── templates/
│   │   ├── main.go.tpl
│   │   ├── client.go.tpl
│   │   └── request.go.tpl
│   └── generated/
│       └── {product}-{operation}-{timestamp}.go
├── pkg/                              # 依赖包缓存
│   ├── go-mod-cache/                 # GOPROXY 本地缓存
│   └── archive/
│       ├── ecs-20200430.a
│       ├── rds-20140815.a
│       └── cms-20190101.a
└── meta/                             # 元数据
    ├── versions.json                 # SDK 版本映射
    ├── checksums.json                # 校验和
    └── access.log                    # 访问日志
```

### 3.3 缓存键设计

```go
// 缓存键格式
CacheKey = "{product}-{api_version}-{operation}"

// 示例
cacheKey := "ecs-20200430-DescribeInstances"
cacheKey := "rds-20140815-DescribeDBInstances"
```

### 3.4 版本管理

```json
// ~/.cache/aliyun-skills/meta/versions.json
{
  "sdk_versions": {
    "ecs-20200430": {
      "version": "v1.0.0",
      "go_module": "github.com/aliyun/alibaba-cloud-sdk-go/services/ecs",
      "last_updated": "2026-05-20T10:00:00Z",
      "checksum": "sha256:abc123..."
    },
    "rds-20140815": {
      "version": "v1.0.0",
      "go_module": "github.com/aliyun/alibaba-cloud-sdk-go/services/rds",
      "last_updated": "2026-05-20T10:00:00Z",
      "checksum": "sha256:def456..."
    }
  },
  "binary_versions": {
    "ecs-20200430-DescribeInstances": {
      "built_at": "2026-05-20T10:00:00Z",
      "go_version": "1.21.0",
      "size_bytes": 15240000,
      "checksum": "sha256:xyz789..."
    }
  }
}
```

---

## 4. 缓存策略

### 4.1 预编译触发策略

```yaml
预编译时机:
  安装时:
    - Skill 首次安装
    - SDK 版本更新
  后台时:
    - 系统空闲时段
    - 定时任务 (每日凌晨)
  按需时:
    - 首次调用 (异步预编译下一个常用操作)

预编译优先级:
  P0: 核心产品核心操作 (ECS DescribeInstances, RDS DescribeDBInstances)
  P1: 常用诊断操作 (CMS DescribeMetricList, DAS CreateDiagnosticReport)
  P2: 低频操作 (按需编译)
```

### 4.2 缓存生命周期

```yaml
缓存策略:
  TTL:
    - 预编译二进制: 30天
    - 源码模板: 7天
    - 依赖包: 90天
  
  清理策略:
    - LRU: 最近最少使用
    - 容量上限: 1GB (可配置)
    - 手动清理: skill cache clean 命令
```

### 4.3 缓存命中率优化

```
热点操作识别:
  ┌────────────────────────┬─────────────┬──────────────┐
  │ 操作                   │ 日调用频次  │ 预编译状态   │
  ├────────────────────────┼─────────────┼──────────────┤
  │ DescribeInstances      │ 1000+       │ 已预编译   │
  │ DescribeMetricList     │ 800+        │ 已预编译   │
  │ DescribeDBInstances    │ 600+        │ 已预编译   │
  │ CreateDiagnosticReport │ 200+        │ 已预编译   │
  │ DescribeSlowLogs       │ 100+        │ 按需编译   │
  │ RestartInstance        │ 50+         │ 按需编译   │
  └────────────────────────┴─────────────┴──────────────┘
```

---

## 5. 增量构建

### 5.1 Go Buildmode=Archive 方案

```go
// 1. 生成通用 client 包
// file: pkg/client/client.go
package client

import (
    "github.com/aliyun/alibaba-cloud-sdk-go/sdk"
    "github.com/aliyun/alibaba-cloud-sdk-go/sdk/auth/credentials"
)

type AliyunClient struct {
    *sdk.Client
}

func NewClient(regionId string, accessKeyId string, accessKeySecret string) (*AliyunClient, error) {
    client, err := sdk.NewClientWithOptions(
        regionId,
        nil, // sdk.WithTimeout(time.Second * 30),
        credentials.NewAccessKeyCredential(accessKeyId, accessKeySecret),
    )
    if err != nil {
        return nil, err
    }
    return &AliyunClient{client}, nil
}
```

```bash
# 2. 编译为 archive
# 通用 client 库 (所有产品共享)
go build -buildmode=archive -o ~/.cache/aliyun-skills/pkg/archive/common-client.a \
  ./pkg/client/

# 产品特定 archive
go build -buildmode=archive -o ~/.cache/aliyun-skills/pkg/archive/ecs-20200430.a \
  github.com/aliyun/alibaba-cloud-sdk-go/services/ecs
```

### 5.2 增量编译流程

```
增量构建流程:
  1. 检查 archive 缓存
     └─> 存在 → 直接使用
     └─> 不存在 → 编译并缓存
  
  2. 生成操作代码
     └─> 基于模板生成 {operation}.go
  
  3. 链接编译
     └─> go build -o {output} -linkshared {operation}.go {archive}.a
  
  4. 执行
     └─> 直接运行预编译二进制
```

### 5.3 Makefile 模板

```makefile
# ~/.cache/aliyun-skills/build/Makefile

CACHE_DIR := $(HOME)/.cache/aliyun-skills
ARCHIVE_DIR := $(CACHE_DIR)/pkg/archive
BIN_DIR := $(CACHE_DIR)/bin

# SDK 版本映射
ECS_VERSION := 20200430
RDS_VERSION := 20140815
CMS_VERSION := 20190101
DAS_VERSION := 20200116

# 预编译目标
.PHONY: all clean ecs rds cms das

all: ecs rds cms das

# ECS Archive
ecs:
	mkdir -p $(ARCHIVE_DIR)/ecs-$(ECS_VERSION)
	go build -buildmode=archive \
	  -o $(ARCHIVE_DIR)/ecs-$(ECS_VERSION).a \
	  github.com/aliyun/alibaba-cloud-sdk-go/services/ecs

# RDS Archive  
rds:
	mkdir -p $(ARCHIVE_DIR)/rds-$(RDS_VERSION)
	go build -buildmode=archive \
	  -o $(ARCHIVE_DIR)/rds-$(RDS_VERSION).a \
	  github.com/aliyun/alibaba-cloud-sdk-go/services/rds

# CMS Archive
cms:
	mkdir -p $(ARCHIVE_DIR)/cms-$(CMS_VERSION)
	go build -buildmode=archive \
	  -o $(ARCHIVE_DIR)/cms-$(CMS_VERSION).a \
	  github.com/aliyun/alibaba-cloud-sdk-go/services/cms

# DAS Archive
das:
	mkdir -p $(ARCHIVE_DIR)/das-$(DAS_VERSION)
	go build -buildmode=archive \
	  -o $(ARCHIVE_DIR)/das-$(DAS_VERSION).a \
	  github.com/aliyun/alibaba-cloud-sdk-go/services/das

# 清理
clean:
	rm -rf $(ARCHIVE_DIR)/*
	rm -rf $(BIN_DIR)/*

# 安装依赖
init:
	go env -w GOPROXY=https://goproxy.cn,direct
	go env -w GOMODCACHE=$(CACHE_DIR)/pkg/go-mod-cache
```

---

## 6. 实现路线图

### 6.1 Sprint 1 (Week 1)

| 任务 | 工时 | 产出 |
|------|------|------|
| 缓存目录结构设计 | 4h | 目录结构文档 |
| 版本管理 JSON Schema | 2h | versions.json 定义 |
| 预编译 Makefile 实现 | 4h | Makefile + 构建脚本 |
| 基础缓存管理器 | 6h | cache_manager.go |

### 6.2 Sprint 2 (Week 2)

| 任务 | 工时 | 产出 |
|------|------|------|
| 增量构建支持 | 6h | archive 链接实现 |
| 热点操作识别 | 4h | 调用统计模块 |
| 缓存清理策略 | 4h | cache_cleaner.go |
| 集成测试 | 6h | 性能测试报告 |

### 6.3 Sprint 3 (Week 3)

| 任务 | 工时 | 产出 |
|------|------|------|
| 安装时预编译 | 4h | install hook |
| 后台预编译任务 | 6h | cron scheduler |
| 监控与告警 | 4h | metrics exporter |
| 文档完善 | 6h | 使用指南 |

---

## 7. 度量与验证

### 7.1 性能指标

| 指标 | 基准值 | 目标值 | 验证方法 |
|------|--------|--------|----------|
| 冷启动时间 | 45s | <500ms | time go run vs 预编译 |
| 缓存命中率 | 0% | >80% | 访问日志统计 |
| 预编译成功率 | N/A | >95% | 构建日志统计 |
| 磁盘占用 | N/A | <1GB | du -sh 检查 |

### 7.2 测试用例

```bash
# 测试 1: 冷启动对比
echo "=== 原生 JIT 启动 ==="
time aliyun ecs DescribeInstances --RegionId cn-hangzhou

echo "=== 预编译缓存启动 ==="
time aliyun-cache ecs DescribeInstances --RegionId cn-hangzhou

# 测试 2: 缓存命中率
curl http://localhost:9090/metrics | grep cache_hit_rate

# 测试 3: 缓存清理
aliyun-skill cache clean --older-than 30d
du -sh ~/.cache/aliyun-skills/
```

### 7.3 监控 Dashboard

```yaml
监控指标:
  - sdk_cache_hit_rate         # 缓存命中率
  - sdk_cache_miss_count       # 缓存未命中次数
  - sdk_compile_duration       # 编译耗时
  - sdk_cache_size_bytes       # 缓存大小
  - sdk_precompile_queue_size  # 预编译队列大小
```

---

## 附录 A: 相关文档

- [optimization-analysis-enhanced.md](optimization-analysis-enhanced.md) - 三维优化分析
- [execution-environment.md](execution-environment.md) - 执行环境规范

---

*文档版本: v1.0.0 | 最后更新: 2026-05-20*
