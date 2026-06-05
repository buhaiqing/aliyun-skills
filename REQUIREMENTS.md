# Aliyun Skills — 需求开发文档

> 本文档是 [README_CN.md](README_CN.md)（中文） / [README.md](README.md)（English）的配套需求开发文档，详细描述本项目所有阿里云运维 Agent Skills 的功能需求、架构设计、技术规范与开发指南。

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [产品级 Skill 需求详情](#3-产品级-skill-需求详情)
   - 3.1 [alicloud-ecs-ops — 云服务器 ECS](#31-alicloud-ecs-ops--云服务器-ecs)
   - 3.2 [alicloud-rds-ops — 云数据库 RDS](#32-alicloud-rds-ops--云数据库-rds)
   - 3.3 [alicloud-redis-ops — 云数据库 Redis/Tair](#33-alicloud-redis-ops--云数据库-redistair)
   - 3.4 [alicloud-ack-ops — 容器服务 ACK](#34-alicloud-ack-ops--容器服务-ack)
   - 3.5 [alicloud-slb-ops — 负载均衡 SLB/CLB](#35-alicloud-slb-ops--负载均衡-slbclb)
   - 3.6 [alicloud-ram-ops — 访问控制 RAM](#36-alicloud-ram-ops--访问控制-ram)
   - 3.7 [alicloud-cms-ops — 云监控 CMS](#37-alicloud-cms-ops--云监控-cms)
    - 3.8 [alicloud-das-ops — 数据库自治服务 DAS](#38-alicloud-das-ops--数据库自治服务-das)
    - 3.9 [alicloud-kms-ops — 密钥管理服务 KMS](#39-alicloud-kms-ops--密钥管理服务-kms)
    - 3.10 [alicloud-topo-discovery — 网络拓扑与资源清单](#310-alicloud-topo-discovery--网络拓扑与资源清单)
  4. [Meta Skill — Skill 生成器](#4-meta-skill--skill-生成器)
5. [跨技能协同协议](#5-跨技能协同协议)
6. [技术规范](#6-技术规范)
7. [开发与贡献指南](#7-开发与贡献指南)

---

## 1. 项目概述

### 1.1 项目定位

本项目是阿里云（Alibaba Cloud）运维 **Agent Skills Farm**，一套 **Meta Skill（元技能）体系**——将运维知识转化为结构化的、AI Agent 可解析、可执行、可验证的声明式规范。

### 1.2 核心价值

| 特性 | 说明 |
|------|------|
| 占位符机制 | `{{env.*}}`（环境变量）、`{{user.*}}`（用户输入）、`{{output.*}}`（输出捕获），实现人机双通道 |
| 职责委托 | `SHOULD/SHOULD NOT Use` 定义边界，跨产品操作自动委派 |
| 生成器 | 基于 OpenAPI 规范自动生成 Skill 框架模板，支持人工审核和完善 |
| CLI-first 执行 | 优先使用 `aliyun` CLI（静态 Go 二进制），CLI 不支持时 JIT 构建 Go SDK 脚本 |
| 安全机制 | 凭证隔离（`{{env.*}}` 不暴露）、操作安全门（删除/恢复需确认） |
| 跨平台设计 | 基于标准 Markdown + OpenSpec，支持多种 Agent 框架接入 |

### 1.3 项目结构

```
aliyun-skills/
├── README.md                              # 项目总览
├── REQUIREMENTS.md                         # 需求开发文档（本文档）
├── pyproject.toml                          # Python 项目配置
├── go.mod                                  # Go 模块配置（可选）
├── .env.example                           # 环境变量示例
├── alicloud-jit-setup.sh                  # JIT Go SDK 一键部署脚本
│
├── alicloud-skill-generator/              # [Meta Skill] Skill 生成器
│   ├── SKILL.md
│   ├── assets/
│   └── references/                        # 模板、治理、AIOPs 最佳实践等
│
├── alicloud-ecs-ops/                      # [产品 Skill] 云服务器 ECS
├── alicloud-rds-ops/                      # [产品 Skill] 云数据库 RDS
├── alicloud-redis-ops/                    # [产品 Skill] 云数据库 Redis/Tair
├── alicloud-ack-ops/                      # [产品 Skill] 容器服务 ACK
├── alicloud-slb-ops/                      # [产品 Skill] 负载均衡 SLB/CLB
├── alicloud-ram-ops/                      # [产品 Skill] 访问控制 RAM
├── alicloud-cms-ops/                      # [产品 Skill] 云监控 CMS
└── alicloud-das-ops/                      # [产品 Skill] 数据库自治服务 DAS
└── alicloud-topo-discovery/              # [发现类 Skill] 网络拓扑与资源清单
```

### 1.4 每个 Skill 的标准目录结构

```
alicloud-<product>-ops/
├── SKILL.md                               # Skill 主文件（声明式规范 + 执行流程）
├── references/
│   ├── cli-usage.md                       # CLI 使用指南
│   ├── api-sdk-usage.md                   # API/SDK 使用指南
│   ├── core-concepts.md                   # 核心概念
│   ├── integration.md                     # 集成指南
│   ├── monitoring.md                      # 监控指标
│   └── troubleshooting.md                 # 故障排查
└── assets/
    └── example-config.yaml                # 示例配置
```

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Runtime                           │
│   (Harness AI Agent / Claude Code / Cursor / 兼容 Runtime)  │
└──────────────────┬──────────────────────────────────────────┘
                   │ 加载 Skill
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  aliyun-skills 仓库                          │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           alicloud-skill-generator                   │   │
│   │              (Meta Skill - 生成器)                    │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│   │ ECS  │ │ RDS  │ │Redis │ │ ACK  │ │ SLB  │ │ RAM  │  │
│   │ ops  │ │ ops  │ │ ops  │ │ ops  │ │ ops  │ │ ops  │  │
│   └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
│   ┌──────┐ ┌──────┐                                       │
│   │ CMS  │ │ DAS  │                                       │
│   │ ops  │ │ ops  │                                       │
│   └──────┘ └──────┘                                       │
└─────────────────────────────────────────────────────────────┘
                   │ 执行路径
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    执行引擎                                  │
│                                                             │
│   ┌─────────────────┐    ┌──────────────────────────────┐   │
│   │  aliyun CLI      │◄───│  JIT Go SDK (go run 回退)   │   │
│   │  (Go 静态二进制)  │    │  (动态生成脚本)             │   │
│   └─────────────────┘    └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  Alibaba Cloud OpenAPI                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 执行路径策略

每种 Skill 根据 `metadata.cli_applicability` 声明其执行路径策略：

| 策略 | 说明 | 适用产品 |
|------|------|----------|
| **cli-first** | CLI 是主要执行路径，JIT Go SDK 仅作为边缘操作回退 | ECS, SLB |
| **dual-path** | 每种操作同时提供 CLI 和 SDK 两种路径 | RDS, Redis, ACK, RAM, CMS |
| **sdk-only** | CLI 不支持，全部操作走 JIT Go SDK | DAS |

### 2.3 凭证安全架构

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  Agent Runtime│───►│ 环境变量          │───►│ 阿里云 OpenAPI│
│  上下文       │    │ ALIBABA_CLOUD_   │    │              │
│              │    │ ACCESS_KEY_ID/    │    │               │
│              │    │ ACCESS_KEY_SECRET │    │               │
│              │    │ REGION_ID         │    │               │
└──────────────┘    └──────────────────┘    └──────────────┘
```

**安全规则：**
- `{{env.*}}` 变量由运行时环境提供，Agent **绝不**向用户索要
- 任何输出中 **必须遮盖** `access_key_secret` 等敏感字段值
- `{{output.access_key_secret}}` 仅展示一次，**绝不**记录到日志

### 2.4 操作安全门

所有**破坏性操作**（删除实例/用户/策略、重置密码等）必须执行安全检查：

```
操作请求
   │
   ▼
┌─────────────────────┐
│  安全门触发           │
│  - 确认资源标识       │
│  - 确认操作影响范围    │
│  - 征求用户确认       │
└─────────┬───────────┘
          │ 用户确认
          ▼
┌─────────────────────┐
│  执行操作             │
│  - 带上客户端令牌      │
│  - 幂等重试           │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  验证结果             │
│  - 状态轮询           │
│  - 响应校验           │
└─────────────────────┘
```

---

## 3. 产品级 Skill 需求详情

### 3.1 alicloud-ecs-ops — 云服务器 ECS

| 元数据 | 值 |
|--------|------|
| **版本** | 2.1.0 |
| **API 版本** | ECS 2014-05-26 |
| **执行策略** | cli-first |
| **CLI 产品名** | `ecs` |

#### 3.1.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 实例生命周期 | CreateInstance, StartInstance, StopInstance, RebootInstance, DeleteInstance, DescribeInstances | P0 |
| 批量创建 | RunInstances（批量创建 + 自动命名） | P0 |
| 实例属性 | ModifyInstanceAttribute（重命名、重置密码、修改描述） | P0 |
| 云盘管理 | CreateDisk, AttachDisk, DetachDisk, DeleteDisk, DescribeDisks, ResizeDisk | P0 |
| 镜像管理 | CreateImage, DescribeImages, DeleteImage, CopyImage, ShareImage | P0 |
| 快照管理 | CreateSnapshot, DescribeSnapshots, DeleteSnapshot | P0 |
| 安全组 | CreateSecurityGroup, DescribeSecurityGroups, DeleteSecurityGroup, AuthorizeSecurityGroup, RevokeSecurityGroup | P0 |
| 系统盘更换 | ReplaceSystemDisk（需 Stopped 状态） | P1 |
| 标签管理 | TagResources, UntagResources, ListTagResources | P1 |
| 云助手 | RunCommand, InvokeCommand, SendFile, StopInvocation, DescribeInvocationResults, DescribeSendFileResults, DescribeCloudAssistantStatus | P1 |

#### 3.1.2 状态轮询需求

| 操作 | 轮询间隔 | 最大等待 |
|------|----------|----------|
| CreateInstance → Running | 5s | 300s |
| StartInstance → Running | 5s | 120s |
| StopInstance → Stopped | 5s | 120s |
| CreateSnapshot → accomplished | 10s | 600s |
| RunInstances → Running | 5s | 300s |

#### 3.1.3 引用文档

- [references/cli-usage.md](alicloud-ecs-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-ecs-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-ecs-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-ecs-ops/references/monitoring.md)
- [references/integration.md](alicloud-ecs-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-ecs-ops/references/troubleshooting.md)
- [references/prompt-examples.md](alicloud-ecs-ops/references/prompt-examples.md)

---

### 3.2 alicloud-rds-ops — 云数据库 RDS

| 元数据 | 值 |
|--------|------|
| **版本** | 2.0.0 |
| **API 版本** | RDS 2014-08-15 |
| **执行策略** | dual-path |
| **CLI 产品名** | `rds` |

#### 3.2.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 实例生命周期 | CreateDBInstance, DescribeDBInstances, ModifyDBInstanceSpec, RestartDBInstance, DeleteDBInstance | P0 |
| 数据库管理 | CreateDatabase, DescribeDatabases, DeleteDatabase | P0 |
| 账号管理 | CreateAccount, DescribeAccounts, GrantAccountPrivilege, RevokeAccountPrivilege, DeleteAccount, ResetAccountPassword | P0 |
| 备份管理 | CreateBackup, DescribeBackups, RestoreDBInstance, DeleteBackup | P0 |
| 性能监控 | DescribeDBInstancePerformance, DescribeResourceUsage | P0 |
| 慢查询日志 | DescribeSlowLogs, DescribeSlowLogRecords | P0 |
| 参数管理 | DescribeParameters, ModifyParameters | P1 |
| 安全白名单 | DescribeDBInstanceIPArrayList, ModifySecurityIps | P0 |
| 只读实例 | CreateReadOnlyDBInstance, DescribeReadDBInstances | P1 |
| 高可用配置 | DescribeDBInstanceHAConfig, ModifyDBInstanceHAConfig | P1 |
| 升级操作 | UpgradeDBInstanceEngineVersion, UpgradeDBInstanceKernelVersion | P1 |
| 迁移可用区 | MigrateToOtherZone | P2 |

#### 3.2.2 支持的数据库引擎

- MySQL（5.6 / 5.7 / 8.0）
- PostgreSQL（10 / 11 / 12 / 13 / 14 / 15）
- SQL Server（2008r2 / 2012 / 2016 / 2017 / 2019）
- MariaDB（10.3）

#### 3.2.3 状态轮询需求

| 操作 | 轮询间隔 | 最大等待 |
|------|----------|----------|
| CreateDBInstance → Running | 10s | 600s |
| RestartDBInstance → Running | 10s | 300s |
| CreateBackup → Success | 10s | 600s |
| CreateAccount → Available | 5s | 120s |

#### 3.2.4 引用文档

- [references/cli-usage.md](alicloud-rds-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-rds-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-rds-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-rds-ops/references/monitoring.md)
- [references/integration.md](alicloud-rds-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-rds-ops/references/troubleshooting.md)
- [references/alert-diagnosis.md](alicloud-rds-ops/references/alert-diagnosis.md)

---

### 3.3 alicloud-redis-ops — 云数据库 Redis/Tair

| 元数据 | 值 |
|--------|------|
| **版本** | 1.0.0 |
| **API 版本** | R-kvstore 2015-01-01 |
| **执行策略** | dual-path |
| **CLI 产品名** | `r-kvstore` |

#### 3.3.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 实例生命周期 | CreateInstance, DescribeInstances, DescribeInstanceAttribute, ModifyInstanceSpec, RestartInstance, DeleteInstance | P0 |
| 账号管理 | CreateAccount, DescribeAccounts, ResetAccountPassword, DeleteAccount | P0 |
| 备份管理 | CreateBackup, DescribeBackups, RestoreInstance, DeleteBackup | P0 |
| 白名单管理 | DescribeSecurityIps, ModifySecurityIps | P0 |
| 参数管理 | DescribeParameters, ModifyInstanceConfig | P0 |
| 性能监控 | DescribeMonitorItems, DescribeHistoryMonitorValues, DescribeIntranetAttribute | P0 |
| 慢查询 | DescribeSlowLogs | P0 |
| 网络管理 | ModifyIntranetBandwidth, FlushInstance | P1 |
| SSL/TLS | ModifyInstanceSSL | P1 |
| 版本升级 | UpgradeMinorVersion | P1 |
| 维护时间 | ModifyInstanceMaintainTime | P1 |
| 大 Key/热 Key 分析 | 通过 Redis 原生命令或控制台功能 | P2 |

#### 3.3.2 状态轮询需求

| 操作 | 轮询间隔 | 最大等待 |
|------|----------|----------|
| CreateInstance → Normal | 10s | 600s |
| RestartInstance → Normal | 10s | 300s |
| ModifyInstanceSpec → Normal | 10s | 600s |
| CreateAccount → Available | 5s | 120s |

#### 3.3.3 引用文档

- [references/cli-usage.md](alicloud-redis-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-redis-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-redis-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-redis-ops/references/monitoring.md)
- [references/integration.md](alicloud-redis-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-redis-ops/references/troubleshooting.md)
- [references/prompts.md](alicloud-redis-ops/references/prompts.md)
- [references/ci-compatibility.md](alicloud-redis-ops/references/ci-compatibility.md)
- [scripts/preflight-check.sh](alicloud-redis-ops/scripts/preflight-check.sh)
- [scripts/sdk-fallback.go](alicloud-redis-ops/scripts/sdk-fallback.go)

---

### 3.4 alicloud-ack-ops — 容器服务 ACK

| 元数据 | 值 |
|--------|------|
| **版本** | 2.0.0 |
| **API 版本** | CS-2015-12-15 |
| **执行策略** | dual-path |
| **CLI 产品名** | `cs` |

#### 3.4.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 集群生命周期 | CreateCluster, DescribeClusters, DescribeClusterDetail, DeleteCluster | P0 |
| 节点池管理 | CreateNodePool, DescribeNodePools, ModifyNodePool, DeleteNodePool | P0 |
| 集群扩缩容 | ScaleOutCluster, ScaleInCluster | P0 |
| 集群升级 | UpgradeCluster | P0 |
| KubeConfig | DescribeClusterUserKubeconfig | P0 |
| 节点管理 | DescribeClusterNodes, RemoveClusterNodes | P1 |
| 插件管理 | DescribeAddons, InstallAddon, UninstallAddon, UpgradeAddon | P1 |
| 集群监控 | DescribeClusterLogs | P1 |

#### 3.4.2 集群类型支持

- **ManagedKubernetes** — 标准托管版
- **ASK** — Serverless Kubernetes
- **EdgeKubernetes** — 边缘容器
- **Sandboxed-Container** — 安全沙箱

#### 3.4.3 状态轮询需求（长时间操作）

| 操作 | 轮询间隔 | 最大等待 |
|------|----------|----------|
| CreateCluster → running | 30s | 1800s (30min) |
| UpgradeCluster → running | 30s | 3600s (60min) |
| ScaleOutCluster → running | 30s | 1800s (30min) |
| DeleteCluster → absent/404 | 30s | 1800s (30min) |

#### 3.4.4 引用文档

- [references/cli-usage.md](alicloud-ack-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-ack-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-ack-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-ack-ops/references/monitoring.md)
- [references/integration.md](alicloud-ack-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-ack-ops/references/troubleshooting.md)

---

### 3.5 alicloud-slb-ops — 负载均衡 SLB/CLB

| 元数据 | 值 |
|--------|------|
| **版本** | 1.0.0 |
| **API 版本** | SLB 2014-05-15 |
| **执行策略** | cli-first |
| **CLI 产品名** | `slb` |

#### 3.5.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 实例生命周期 | CreateLoadBalancer, DescribeLoadBalancers, DescribeLoadBalancerAttribute, SetLoadBalancerStatus, DeleteLoadBalancer | P0 |
| 监听器管理 | CreateLoadBalancerTCPListener, CreateLoadBalancerUDPListener, CreateLoadBalancerHTTPListener, CreateLoadBalancerHTTPSListener, DescribeLoadBalancerListeners, DeleteLoadBalancerListener | P0 |
| 虚拟服务器组 | CreateVServerGroup, DescribeVServerGroups, DescribeVServerGroupAttribute, SetVServerGroupAttribute, DeleteVServerGroup | P0 |
| 后端服务器 | AddBackendServers, RemoveBackendServers, SetBackendServers, DescribeHealthStatus | P0 |
| 证书管理 | UploadServerCertificate, DescribeServerCertificates, DeleteServerCertificate, UploadCACertificate, DescribeCACertificates | P1 |
| 访问控制 ACL | CreateAccessControlList, DescribeAccessControlLists, AddAccessControlListEntry, RemoveAccessControlListEntry, DeleteAccessControlList | P1 |
| 转发规则 | CreateRules, DescribeRules, SetRule, DeleteRules | P1 |
| 域名扩展 | CreateDomainExtension, DescribeDomainExtensions, DeleteDomainExtension | P2 |

#### 3.5.2 支持的监听协议

- TCP（四层）
- UDP（四层）
- HTTP（七层）
- HTTPS（七层，需配置证书）

#### 3.5.3 引用文档

- [references/cli-usage.md](alicloud-slb-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-slb-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-slb-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-slb-ops/references/monitoring.md)
- [references/integration.md](alicloud-slb-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-slb-ops/references/troubleshooting.md)
- [references/prompt-examples.md](alicloud-slb-ops/references/prompt-examples.md)
- [assets/listener-config-examples/](alicloud-slb-ops/assets/listener-config-examples/)
- [assets/ram-policy.json](alicloud-slb-ops/assets/ram-policy.json)
- [assets/slb-instance-template.json](alicloud-slb-ops/assets/slb-instance-template.json)

---

### 3.6 alicloud-ram-ops — 访问控制 RAM

| 元数据 | 值 |
|--------|------|
| **版本** | 2.0.0 |
| **API 版本** | Ram/2015-05-01 |
| **执行策略** | dual-path |
| **CLI 产品名** | `ram` |

#### 3.6.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| RAM 用户 | CreateUser, GetUser, UpdateUser, ListUsers, DeleteUser | P0 |
| 用户组 | CreateGroup, GetGroup, ListGroups, AddUserToGroup, RemoveUserFromGroup, DeleteGroup | P0 |
| RAM 角色 | CreateRole, GetRole, ListRoles, UpdateRole, DeleteRole | P0 |
| 自定义策略 | CreatePolicy, GetPolicy, ListPolicies, CreatePolicyVersion, DeletePolicy, DeletePolicyVersion | P0 |
| 策略授权 | AttachPolicyToUser, DetachPolicyFromUser, AttachPolicyToGroup, DetachPolicyFromGroup, AttachPolicyToRole, DetachPolicyFromRole, ListEntitiesForPolicy | P0 |
| 访问密钥 | CreateAccessKey, ListAccessKeys, UpdateAccessKey, DeleteAccessKey | P0 |
| 登录配置 | CreateLoginProfile, GetLoginProfile, UpdateLoginProfile, DeleteLoginProfile | P0 |
| 多因素认证 MFA | CreateVirtualMFADevice, ListVirtualMFADevices, BindMFADevice, UnbindMFADevice, DeleteVirtualMFADevice | P1 |
| STS 临时凭证 | AssumeRole, GetCallerIdentity | P0 |
| 密码策略 | SetPasswordPolicy, GetPasswordPolicy | P1 |
| 权限审计 | 分析已附加策略、识别过度授权的身份、未使用访问密钥 | P1 |

#### 3.6.2 安全约束

RAM 是全局服务，大多数 API 使用 `cn-hangzhou` 作为默认区域。破坏性操作（删除用户/AK/角色、分离策略）必须有明确的安全确认门。

#### 3.6.3 引用文档

- [references/cli-usage.md](alicloud-ram-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-ram-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-ram-ops/references/core-concepts.md)
- [references/integration.md](alicloud-ram-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-ram-ops/references/troubleshooting.md)
- [references/policy-examples.md](alicloud-ram-ops/references/policy-examples.md)

---

### 3.7 alicloud-cms-ops — 云监控 CMS

| 元数据 | 值 |
|--------|------|
| **版本** | 2.0.0 |
| **API 版本** | Cms/2019-01-01 (RPC) + Cms/2024-03-30 (ROA) |
| **执行策略** | dual-path |
| **CLI 产品名** | `cms` |

#### 3.7.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 指标查询 | DescribeMetricList, DescribeMetricLast, DescribeMetricData, DescribeMetricTop | P0 |
| 告警规则 | PutMetricAlarm, DescribeMetricAlarmList, DescribeMetricAlarm, EnableMetricAlarm, DisableMetricAlarm, DeleteMetricAlarm | P0 |
| 监控分组 | CreateMonitorGroup, DescribeMonitorGroups, DeleteMonitorGroup, PutMonitorGroupDynamicRule | P0 |
| 告警联系人 | PutContact, DescribeContacts, DeleteContact | P0 |
| 告警联系组 | PutContactGroup, DescribeContactGroups, DeleteContactGroup | P0 |
| 自定义监控 | PutCustomMetric, DescribeCustomMetricList | P1 |
| 事件监控 | PutEvent, DescribeEventMonitorAttribute, DescribeEventRuleList | P1 |
| 站点监控 | CreateSiteMonitor, DescribeSiteMonitorList, DeleteSiteMonitor | P1 |
| 云产品监控大盘 | DescribeMonitoringAgentAccessKey, CreateMonitorGroupInstances | P1 |
| 日志监控 | PutLogMonitor, DescribeLogMonitorList, DeleteLogMonitor | P2 |

#### 3.7.2 常见产品 Namespace

| 产品 | Namespace |
|------|-----------|
| ECS | `acs_ecs_dashboard` |
| RDS | `acs_rds_dashboard` |
| SLB | `acs_slb_dashboard` |
| OSS | `acs_oss_dashboard` |
| Redis | `acs_kvstore_dashboard` |
| MongoDB | `acs_mongodb_dashboard` |
| PolarDB | `acs_polardb_dashboard` |
| Kubernetes | `acs_k8s_dashboard` |

#### 3.7.3 限频限制

- DescribeMetricList / DescribeMetricLast / DescribeMetricData / DescribeMetricTop：**100 万次/月** 免费额度
- **50 次/秒** 每 API 每账号

#### 3.7.4 异常检测与自愈框架

CMS Skill 内置了 **4 层异常检测框架**，用于 CLI 安装问题的诊断与自愈：

| 层级 | 名称 | 检测内容 |
|------|------|----------|
| Level 1 | 环境检测层 | OS 兼容性、Shell 类型、包管理器、架构兼容、PATH 可写 |
| Level 2 | 依赖检测层 | Go 运行时、SDK 包解析、版本冲突、构建工具、Go Mod Cache |
| Level 3 | 网络检测层 | DNS 解析、CMS 端点、CLI 下载源、Go Proxy、代理检测 |
| Level 4 | 权限检测层 | Credential 存在性/有效性、RAM 策略、二进制权限、磁盘写入权限 |

#### 3.7.5 引用文档

- [references/cli-usage.md](alicloud-cms-ops/references/cli-usage.md)
- [references/api-sdk-usage.md](alicloud-cms-ops/references/api-sdk-usage.md)
- [references/core-concepts.md](alicloud-cms-ops/references/core-concepts.md)
- [references/monitoring.md](alicloud-cms-ops/references/monitoring.md)
- [references/integration.md](alicloud-cms-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-cms-ops/references/troubleshooting.md)
- [references/cli-install-diagnosis.md](alicloud-cms-ops/references/cli-install-diagnosis.md)
- [references/knowledge-base.md](alicloud-cms-ops/references/knowledge-base.md)
- [references/observability.md](alicloud-cms-ops/references/observability.md)
- [references/prompts.md](alicloud-cms-ops/references/prompts.md)

---

### 3.8 alicloud-das-ops — 数据库自治服务 DAS

| 元数据 | 值 |
|--------|------|
| **版本** | 1.0.0 |
| **API 版本** | DAS/2020-01-16 |
| **执行策略** | sdk-only（CLI 不支持 DAS） |
| **端点** | `das.cn-shanghai.aliyuncs.com`（公有）/ `das.vpc-proxy.aliyuncs.com`（VPC） |
| **SDK 包** | `github.com/alibabacloud-go/das-20200116/v5/client` |

#### 3.8.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 实例接入 | AddHDMInstance, GetHDMInstance, GetEndpointSwitchTask | P0 |
| 巡检评分 | GetInstanceInspections, DescribeDiagnosticReportList | P0 |
| SQL 诊断 | CreateDiagnosticReport, DescribeDiagnosticReportList, GetQueryOptimizeData, GetQueryOptimizeExecErrorStats | P0 |
| 缓存分析 | CreateCacheAnalysisJob, DescribeCacheAnalysisJob, DescribeCacheAnalysisJobs | P0 |
| 死锁分析 | CreateLatestDeadLockAnalysis, DescribeLatestDeadLockAnalysis | P1 |
| 会话管理 | GetRunningSqlConcurrencyControlRules, CreateKillInstanceSessionTask, GetKillInstanceSessionTaskResult | P1 |
| 空间分析 | GetSpaceSummary, GetSpaceUsageStatistic | P0 |
| SQL 限流 | CreateSqlLimitTask, GetSqlLimitTaskStatus, GetRunningSqlConcurrencyControlRules | P1 |
| 自动弹性伸缩 | SetAutoScalingConfig, DescribeAutoScalingConfig, DescribeAutoScalingHistory | P1 |
| 事件订阅 | SetEventSubscription, DescribeEventSubscribe, GetAutonomousNotifyEventsInRange | P1 |
| SQL 洞察 | DescribeSqlLogStatistic, DescribeSqlLogRecords, DescribeSqlLogTasks | P1 |
| 性能洞察 | GetPfsSqlSamples, DescribeTopHotKeys, DescribeHotKeys | P1 |
| 索引诊断 | GetQueryOptimizeExecErrorStats | P1 |

#### 3.8.2 DAS 标准响应结构

所有 DAS API 遵循统一的五元素响应封装：

```json
{
  "Code": 200,
  "Message": "Successful",
  "RequestId": "B6D17591-...",
  "Data": { ... },
  "Success": true
}
```

> **注意：** `Code == 200` 不总是代表业务成功，必须检查 `Success == true`。

#### 3.8.3 引用文档

- [references/prompt-templates.md](alicloud-das-ops/references/prompt-templates.md)
- [references/integration.md](alicloud-das-ops/references/integration.md)
- [references/troubleshooting.md](alicloud-das-ops/references/troubleshooting.md)
- [references/cross-skill-collaboration.md](alicloud-das-ops/references/cross-skill-collaboration.md)
- [references/governance-and-adversarial-review.md](alicloud-das-ops/references/governance-and-adversarial-review.md)
- [assets/das-alert-thresholds.yaml](alicloud-das-ops/assets/das-alert-thresholds.yaml)
- [assets/das-fault-pattern-library.yaml](alicloud-das-ops/assets/das-fault-pattern-library.yaml)
- [assets/das-log-analysis-patterns.yaml](alicloud-das-ops/assets/das-log-analysis-patterns.yaml)

### 3.9 alicloud-kms-ops — 密钥管理服务 KMS

| 元数据 | 值 |
|--------|------|
| **版本** | 1.0.0 |
| **API 版本** | KMS 2016-01-20 |
| **执行策略** | dual-path |
| **CLI 产品名** | `kms` |
| **Go SDK 包** | `github.com/alibabacloud-go/kms-20160120/v3/client` |
| **端点** | `kms.aliyuncs.com`（公有）/ `kms.{region}.aliyuncs.com`（区域） |

#### 3.9.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|----------|----------|--------|
| 服务管理 | DescribeRegions, OpenKmsService, DescribeAccountKmsStatus | P0 |
| 密钥生命周期 | CreateKey, DescribeKey, ListKeys, EnableKey, DisableKey, UpdateKeyDescription | P0 |
| 密钥删除 | ScheduleKeyDeletion, CancelKeyDeletion, SetDeletionProtection | P0 |
| 别名管理 | CreateAlias, UpdateAlias, DeleteAlias, ListAliases, ListAliasesByKeyId | P0 |
| 密码学操作 | Encrypt, Decrypt, GenerateDataKey, GenerateDataKeyWithoutPlaintext | P0 |
| 非对称操作 | AsymmetricSign, AsymmetricVerify, AsymmetricEncrypt, AsymmetricDecrypt, GetPublicKey | P1 |
| 密钥版本 | CreateKeyVersion, DescribeKeyVersion, ListKeyVersions, UpdateRotationPolicy | P1 |
| BYOK | GetParametersForImport, ImportKeyMaterial, DeleteKeyMaterial | P1 |
| Secret 管理 | CreateSecret, DescribeSecret, ListSecrets, UpdateSecret | P0 |
| Secret 值操作 | GetSecretValue, PutSecretValue, ListSecretVersionIds, UpdateSecretVersionStage | P0 |
| Secret 轮 | RotateSecret, UpdateSecretRotationPolicy, GetRandomPassword | P1 |
| Secret 删除/恢复 | DeleteSecret, RestoreSecret | P0 |
| 标签管理 | TagResource, UntagResource, ListResourceTags, TagResources, UntagResources, ListTagResources | P1 |
| KMS 实例管理 | ListKmsInstances, GetKmsInstance, ConnectKmsInstance, UpdateKmsInstanceBindVpc | P1 |
| 应用管理 | CreateApplicationAccessPoint, DeleteApplicationAccessPoint, DescribeApplicationAccessPoint, ListApplicationAccessPoints | P2 |
| 网络规则 | CreateNetworkRule, DeleteNetworkRule, DescribeNetworkRule, ListNetworkRules, UpdateNetworkRule | P2 |

#### 3.9.2 支持的密钥类型

| KeySpec | 算法 | 用途 | 最大明文 |
|---------|------|------|----------|
| `Aliyun_AES_256` | AES-256 | ENCRYPT/DECRYPT | 4096 bytes |
| `Aliyun_SM4` | SM4（国密） | ENCRYPT/DECRYPT | 4096 bytes |
| `RSA_2048` | RSA-2048 | SIGN/VERIFY; AsymmetricEncrypt/Decrypt | N/A |
| `EC_P256` | ECDSA P-256 | SIGN/VERIFY | N/A |
| `EC_P256K` | ECDSA P-256K | SIGN/VERIFY | N/A |
| `EC_SM2` | SM2（国密） | SIGN/VERIFY | N/A |

#### 3.9.3 密钥状态

| 状态 | 描述 | 可转换到 |
|------|------|----------|
| `Enabled` | 密钥处于启用状态，可用于密码运算 | Disabled, PendingDeletion |
| `Disabled` | 密钥存在但不可使用 | Enabled, PendingDeletion |
| `PendingDeletion` | 已进入预定删除状态（7–30 天等待期） | Enabled（通过 CancelKeyDeletion） |
| `PendingImport` | 等待导入外部密钥材料（BYOK） | Enabled（导入后） |

#### 3.9.4 状态轮询需求

| 操作 | 轮询间隔 | 最大等待 |
|------|----------|----------|
| EnableKey → Enabled | 2s | 15s |
| DisableKey → Disabled | 2s | 15s |
| ScheduleKeyDeletion → PendingDeletion | N/A（异步） | N/A |
| CancelKeyDeletion → Enabled | N/A（异步） | N/A |
| CreateKey → Enabled | 2s | 30s |
| CreateSecret → Available | 2s | 30s |

#### 3.9.5 引用文档

- [references/core-concepts.md](alicloud-kms-ops/references/core-concepts.md)
- [references/api-sdk-usage.md](alicloud-kms-ops/references/api-sdk-usage.md)
- [references/cli-usage.md](alicloud-kms-ops/references/cli-usage.md)
- [references/troubleshooting.md](alicloud-kms-ops/references/troubleshooting.md)
- [references/monitoring.md](alicloud-kms-ops/references/monitoring.md)
- [references/integration.md](alicloud-kms-ops/references/integration.md)
- [references/well-architected-assessment.md](alicloud-kms-ops/references/well-architected-assessment.md)
- [references/enhanced-self-healing-framework.md](alicloud-kms-ops/references/enhanced-self-healing-framework.md)
- [assets/example-config.yaml](alicloud-kms-ops/assets/example-config.yaml)

---

### 3.10 alicloud-topo-discovery — 网络拓扑与资源清单

| 元数据 | 值 |
|--------|------|
| **版本** | 1.0.0 |
| **API 版本** | Cross-Product (VPC/ECS/RDS/SLB/ACK) |
| **执行策略** | cli-only (仅只读) |
| **产品名** | `multi` |

#### 3.9.1 功能需求

| 功能模块 | 操作列表 | 优先级 |
|---------|----------|--------|
| 安全门 | Read-Only 预检 (正则拦截 Create/Delete/Modify 等) | P0 |
| 并行采集 | DescribeVpcs, DescribeVSwitches, DescribeLoadBalancers, DescribeEipAddresses, DescribeNatGateways | P0 |
| 简报模式 | VPC + VSwitch + SLB/EIP + 资源数量统计 | P0 |
| 详细模式 | 简报 + 完整 ECS/RDS/ACK/安全组清单表 | P0 |
| 拓扑视图 | ASCII 树形结构 + Mermaid 可选 | P0 |
| 多文档模式 | 支持单文件 report.md 或多文件拆分 (topology/inventory/summary) | P1 |
| 模板引擎 | 基于 templates/ 独立 .md 模板 + 变量替换 | P1 |

#### 3.9.2 安全约束

**绝对只读 (Read-Only Only):**
- 仅允许 `Describe*`, `List*`, `Get*` API
- 自动拦截所有写操作前缀 (Create/Delete/Modify/Update/Associate 等)
- 不修改/创建/删除/绑定任何云资源
- AK/Secret 输出严格掩码

#### 3.9.3 引用文档

- [references/safety-gate.md](alicloud-topo-discovery/references/safety-gate.md)
- [references/execution-commands.md](alicloud-topo-discovery/references/execution-commands.md)
- [scripts/topo-scan.sh](alicloud-topo-discovery/scripts/topo-scan.sh)
- [scripts/topo-render.py](alicloud-topo-discovery/scripts/topo-render.py)
- [templates/vpc-topology.md](alicloud-topo-discovery/templates/vpc-topology.md)

---

## 4. Meta Skill — Skill 生成器

### 4.1 alicloud-skill-generator 概述

| 元数据 | 值 |
|--------|------|
| **类型** | meta-skill（元技能） |
| **版本** | 2.0.0 |
| **用途** | 生成新的产品级运维 Skill 或扩展现有 Skill |
| **技术栈** | `aliyun` CLI + Alibaba Cloud Go SDK + JIT `go run` |

### 4.2 功能需求

| 功能 | 说明 |
|------|------|
| 新 Skill 脚手架 | 从模板创建标准目录结构（SKILL.md + references/* + assets/*） |
| OpenAPI 对齐 | 基于 OpenAPI/Swagger 规范生成操作列表、请求/响应字段、错误映射 |
| CLI 支持验证 | 自动检测 `aliyun help <product>` 确认 CLI 支持情况 |
| 占位符注入 | 生成标准化的 `{{env.*}}` / `{{user.*}}` / `{{output.*}}` 占位符表 |
| 执行路径决策 | 根据 CLI 支持情况设置 `cli_applicability`：cli-first / dual-path / sdk-only |
| 安全策略注入 | 强制加入凭证遮盖规则和操作安全门 |
| 治理审查 | 引用治理文档，确保符合 P0/P1 质量门禁 |
| 优化分析 | 三维优化框架：Prompt 质量 + 成本效率 + 用户体验 |

### 4.3 生成流程

```
Step 0: 环境准备（aliyun CLI + Go runtime）
Step 1: 收集产品信息（产品名、API 版本、文档 URL、OpenAPI 规范）
Step 2: 创建目录结构
Step 3: 生成 SKILL.md（触发条件、占位符、API 响应表、状态轮询、执行流程）
Step 4: 生成 reference 文档（CLI、API、核心概念、集成、监控、故障排查）
Step 5: 生成 assets/ 示例配置
Step 6: 治理审查与对抗性评审
Step 7: 提交 PR
```

### 4.4 引用文档

- [references/alicloud-skill-template.md](alicloud-skill-generator/references/alicloud-skill-template.md)
- [references/aiops-best-practices.md](alicloud-skill-generator/references/aiops-best-practices.md)
- [references/enhanced-self-healing-framework.md](alicloud-skill-generator/references/enhanced-self-healing-framework.md)
- [references/governance-and-adversarial-review.md](alicloud-skill-generator/references/governance-and-adversarial-review.md)
- [references/optimization-analysis.md](alicloud-skill-generator/references/optimization-analysis.md)
- [references/prompt-library.md](alicloud-skill-generator/references/prompt-library.md)
- [references/user-experience-spec.md](alicloud-skill-generator/references/user-experience-spec.md)

---

## 5. 跨技能协同协议

### 5.1 协同触发条件

| 触发场景 | 源 Skill | 目标 Skill | 传递数据 |
|----------|----------|------------|----------|
| DAS 实例未找到 | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | instance_id, engine |
| 连通性诊断失败 | alicloud-das-ops | alicloud-vpc-ops | instance_id, src_ip, failure_reason |
| 实例状态异常 | alicloud-das-ops | alicloud-rds-ops / alicloud-polar-mysql-ops / alicloud-polar-pg-ops / alicloud-polar-oracle-ops | instance_id, status, engine |
| 余额不足 | alicloud-das-ops | alicloud-billing-ops | instance_id, feature_name |
| RAM 权限不足 | 任意 Skill | alicloud-ram-ops | instance_id, required_permission |
| 创建 ECS 需 VPC | alicloud-ecs-ops | alicloud-vpc-ops | vpc_id, vswitch_id |
| 创建 RDS 需 VPC | alicloud-rds-ops | alicloud-vpc-ops | vpc_id, vswitch_id |
| SLB 添加后端 | alicloud-slb-ops | alicloud-ecs-ops | backend_server_id |

### 5.2 上下文传递格式

```json
{
  "source_skill": "alicloud-*-ops",
  "target_skill": "alicloud-*-ops",
  "trigger_reason": "具体触发原因",
  "context": {
    "instance_id": "",
    "engine": "",
    "region_id": "",
    "failure_reason": ""
  },
  "expected_outcome": "期望修复结果",
  "callback_api": "验证 API"
}
```

### 5.3 协同最佳实践

1. **上下文完整性**：委托时必须包含基础信息及诊断关键数据
2. **避免循环委托**：目标 Skill 不应将问题重新委托回源 Skill
3. **结果验证**：源 Skill 收到修复结果后必须重新验证
4. **错误处理**：所有尝试方案均失败时建议人工介入
5. **安全传递**：上下文中不得包含 AccessKey Secret 等敏感信息

---

## 6. 技术规范

### 6.1 元数据规范

每个 Skill 的 `SKILL.md` 必须包含标准化的 YAML 前置元数据：

```yaml
---
name: alicloud-<product>-ops
description: >-
  Use when ...
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime ...
metadata:
  author: alicloud
  version: "x.y.z"
  last_updated: "YYYY-MM-DD"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "<Product> <API-Version> / <API-Doc-URL>"
  cli_applicability: cli-first | dual-path | sdk-only
  cli_support_evidence: "Confirmed via `aliyun help <product>` ..."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---
```

### 6.2 占位符规范

| 类别 | 模式 | 来源 | Agent 行为 |
|------|------|------|-----------|
| 环境变量 | `{{env.*}}` | 运行时环境 | 永不向用户索要，未设置时直接失败 |
| 用户输入 | `{{user.*}}` | 用户交互或推理 | 缺失时向用户询问一次，后续复用 |
| 输出捕获 | `{{output.*}}` | 前一步 API 响应 | 从 JSON 响应中按 XPath 解析 |

### 6.3 凭证安全规范

所有执行路径必须遵守以下遮盖规则：

| 执行路径 | 安全模式 | 不安全模式 |
|----------|----------|------------|
| 控制台输出 | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | 原始凭证值 |
| 错误消息 | `Error: API call failed (credential omitted)` | 包含原始凭证的错误 |
| 日志文件 | `[INFO] Credentials: Secret=***` | 明文凭证 |
| 验证 | `test -n "$var" && echo "Secret is set"` | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| JIT Go SDK | `os.Getenv(...)` 读取安全；永不打印 Config 结构体 | `fmt.Printf("Config: %+v", config)` |
| 调试模式 | `Debug mode may expose credentials (use with caution)` | 调试输出中未遮盖的凭证 |

### 6.4 SKILL.md 文档结构规范

```
┌─────────────────────────────────┐
│  YAML Frontmatter (元数据)       │
├─────────────────────────────────┤
│  Overview (概述)                 │
├─────────────────────────────────┤
│  Trigger & Scope (触发与范围)     │
│  ├── SHOULD Use                   │
│  ├── SHOULD NOT Use               │
│  └── Delegation Rules             │
├─────────────────────────────────┤
│  Variable Convention (变量约定)   │
├─────────────────────────────────┤
│  Security Warning (安全警告)      │
├─────────────────────────────────┤
│  API and Response Conventions    │
│  ├── Response Field Table        │
│  ├── Expected State Transitions  │
│  └── Polling Strategy            │
├─────────────────────────────────┤
│  Execution Flows (执行流程)       │
│  ├── Pre-flight Checks           │
│  ├── Execute (CLI / SDK)         │
│  ├── Validate                    │
│  └── Recover                     │
├─────────────────────────────────┤
│  Changelog (变更历史)             │
└─────────────────────────────────┘
```

### 6.5 执行流程规范

每个操作必须包含四个阶段：

```
Pre-flight → Execute → Validate → Recover
```

| 阶段 | 说明 |
|------|------|
| **Pre-flight** | CLI 存在性、凭证检查、资源存在性、配额检查 |
| **Execute** | CLI 命令（主要）或 JIT Go SDK 脚本（回退） |
| **Validate** | 响应校验 + 状态轮询直到目标状态 |
| **Recover** | 错误分类、重试逻辑、降级策略 |

### 6.6 Go 版本兼容性

| 场景 | 最低 Go 版本 | 说明 |
|------|-------------|------|
| Agent Runtime 最小要求 | Go 1.21+ | SDK 包编译兼容 |
| JIT 下载推荐 | Go 1.24+ | 更快的编译速度和更好的依赖管理 |
| JIT 下载脚本 | 自动下载 Go 1.24.0 | 跨平台支持 macOS/Linux/Windows |

---

## 7. 开发与贡献指南

### 7.1 开发环境要求

- `aliyun` CLI（官方 Go 静态二进制）
- Go 1.21+（JIT Go SDK 回退路径）
- `markdownlint-cli2`（Markdown 格式校验）
- curl / wget（网络下载）
- Python 3.10+（可选，用于 pyproject.toml 中的工具）

### 7.2 初始化开发环境

```bash
# 1. 安装 aliyun CLI
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# 2. 配置凭证
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_ak_id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_ak_secret"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# 3. 安装格式检查工具
pip install markdownlint-cli2
```

### 7.3 JIT 部署脚本

提供 [alicloud-jit-setup.sh](alicloud-jit-setup.sh) 一键部署脚本，自动完成：
- aliyun CLI 安装检测与自动安装
- Go Runtime 检测与自动安装
- Go SDK 包下载与编译
- SDK 脚本生成与执行

```bash
# 基本用法
./alicloud-jit-setup.sh ecs DescribeRegions

# 指定产品、操作和凭据文件
./alicloud-jit-setup.sh rds DescribeDBInstances .env
```

### 7.4 新增产品 Skill 流程

```bash
# 1. 使用生成器创建新 Skill
# 在 Agent Runtime 中加载 alicloud-skill-generator
# 提供提示词，例如：
# "生成阿里云 <产品名> 的 Skill，核心功能：<操作列表>"

# 2. 生成后的目录结构
alicloud-<product>-ops/
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

# 3. 格式验证
npx markdownlint-cli2 "alicloud-*/SKILL.md"
```

### 7.5 质量标准（P0/P1）

| 级别 | 必须包含 |
|------|----------|
| **P0** | YAML Frontmatter、Trigger & Scope（SHOULD/SHOULD NOT）、占位符表、安全警告、响应字段表、状态轮询表、至少 3 个操作的完整执行流程（Pre-flight → Execute → Validate → Recover） |
| **P1** | 更多操作的执行流程、故障排查决策树、监控指标表、集成指南 |

### 7.6 版本管理

- 版本号遵循语义化版本（SemVer）：`主版本.次版本.修订`
- 每次变更必须在 SKILL.md 末尾的 Changelog 表中记录
- Changelog 格式：
  ```
  | Version | Date | Changes |
  |---------|------|---------|
  | x.y.z   | YYYY-MM-DD | 变更描述 |
  ```