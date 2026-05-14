# aliyun-skills

阿里云相关的Agent Skills

## 概述

本项目是阿里云（Alibaba Cloud）运维 Agent Skills 集合，提供云产品的自动化运维、监控和管理能力。

## 核心价值

**Skills Farm 是一套 Meta Skill（元技能）体系**——将运维知识转化为结构化的、AI Agent 可解析、可执行、可验证的声明式规范。

### 关键特性

| 特性 | 说明 |
|------|------|
| **占位符机制** | `{{env.*}}`（环境变量）、`{{user.*}}`（用户输入）、`{{output.*}}`（输出捕获），实现人机双通道 |
| **职责委托** | `SHOULD/SHOULD NOT Use` 定义边界，跨产品操作自动委派 |
| **生成器** | 基于 OpenAPI 规范自动生成 Skill 框架模板，支持人工审核和完善 |
| **CLI-first 执行** | 优先使用 `aliyun` CLI（静态 Go 二进制），CLI 不支持时 JIT 构建 Go SDK 脚本 |
| **安全机制** | 凭证隔离（`{{env.*}}` 不暴露）、操作安全门（删除/恢复需确认） |
| **跨平台设计** | 基于标准 Markdown + OpenSpec，支持多种 Agent 框架接入 |

## 项目结构

```
aliyun-skills/
├── README.md                          # 本文件
├── go.mod                              # Go 模块配置（可选）
├── .env.example                       # 环境变量示例
├── .gitignore                         # Git 排除规则
├── alicloud-skill-generator/          # Skill 生成器（Meta Skill）
│   ├── SKILL.md
│   ├── assets/
│   └── references/
│       ├── alicloud-skill-template.md   # Skill 模板
│       └── governance-and-adversarial-review.md
└── alicloud-<product>-ops/            # 产品级运维 Skill（待生成）
    ├── SKILL.md
    ├── references/
    └── assets/
```

## 快速开始

### 1. 安装 aliyun CLI

```bash
# 官方一键安装（自动检测 OS + 架构）
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

### 2. 配置凭证

```bash
# 方式一：环境变量（推荐）
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# 方式二：交互式配置
aliyun configure
```

### 3. 生成新 Skill

在 Agent Runtime 中引用生成器，然后提供提示词：

> "生成阿里云 ECS 的 Skill，名称 alicloud-ecs-ops，核心功能：实例生命周期管理、磁盘、快照"

**生成结构**：
```
alicloud-ecs-ops/
├── SKILL.md
├── references/
│   ├── cli-usage.md
│   ├── api-sdk-usage.md
│   ├── core-concepts.md
│   ├── integration.md
│   ├── monitoring.md
│   └── troubleshooting.md
└── assets/
    └── example-config.yaml
```

## 阿里云 CLI 行为特征

### 正确 CLI 调用模式

```bash
# RPC 风格 API（大部分产品）
aliyun <product> <OperationName> --RegionId cn-hangzhou --Param1 value1

# 示例
aliyun ecs DescribeInstances --RegionId cn-hangzhou
aliyun rds DescribeDBInstances --RegionId cn-hangzhou

# JMESPath 字段提取
aliyun ecs DescribeInstances --output cols=InstanceId,Status rows=Instances.Instance[]

# 轮询等待
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300
```

## aliyun CLI 安装

**官方一键安装（自动检测 OS + 架构）：**
```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

`install.sh` 自动处理：
- **macOS**: 下载 `universal` 包（Intel + Apple Silicon 通吃）
- **Linux AMD64**: `aliyun-cli-linux-latest-amd64.tgz`
- **Linux ARM64**: `aliyun-cli-linux-latest-arm64.tgz`
- 安装到 `/usr/local/bin/aliyun`

**其他方式：**
```bash
# macOS Homebrew
brew install aliyun-cli
```

## 凭证配置

**环境变量（Agent 执行推荐）：**
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

**交互式配置：**
```bash
aliyun configure
```

**配置文件：**
```json
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "YOUR_AK",
      "access_key_secret": "YOUR_SECRET",
      "region_id": "cn-hangzhou"
    }
  ]
}
```

## Skill 编写要点

- CLI 示例：用 `bash`，JSON 用 `json`，YAML 用 `yaml`
- 表格展示：产品列表、监控指标、告警阈值
- 凭证配置见上方环境变量章节

## 验证

```bash
# 检查 Markdown 格式
npx markdownlint-cli2 "alicloud-*/SKILL.md"
```

验证：CLI 命令可执行、链接有效、示例正确。

## 参考资源

- [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud SDK for Go](https://github.com/alibabacloud-go)
- [Agent Skills OpenSpec](https://agentskills.io/specification)
- [阿里云帮助文档](https://help.aliyun.com)

## 常见问题

| Q | A |
|---|---|
| Skill 和 MCP Server 关系？ | Skill 是文档，MCP 是执行服务 |
| 一个 Skill 覆盖多产品？ | 建议单一职责，通过 Reference 互相引用 |
| 如何更新 Skill？ | 修改后更新 version 和变更历史 |

---

参考 `alicloud-skill-generator/SKILL.md` 了解生成器的完整使用说明。
