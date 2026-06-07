# Core Concepts — 架构评审与设计核心概念

> 本文档定义 alicloud-arch-advisor 所依赖的核心架构理念，包括 WAF 五支柱模型、通用架构模式、以及三模式方法论。

---

## 1. 阿里云 Well-Architected Framework (WAF)

阿里云 Well-Architected Framework 是阿里云官方发布的云架构最佳实践框架，涵盖五个支柱。alicloud-arch-advisor 的核心评估能力即基于此框架。

### 1.1 五支柱概述

| 支柱 | 关注核心 | 典型检查项 |
|:----:|---------|-----------|
| **Security** | 数据保护、访问控制、合规性 | 安全组规则是否过松、是否启用加密、RAM 策略是否符合最小权限 |
| **Reliability** | 高可用、容错、灾备 | 是否多 AZ 部署、有无自动备份、SLB 健康检查是否配置 |
| **Performance** | 资源效率、响应速度、扩展性 | 实例规格是否匹配负载、存储 IOPS 是否达标、有无自动伸缩 |
| **Cost** | 成本优化、资源利用率、付费模式 | 是否存在闲置资源、是否应使用预留实例、规格是否过度 |
| **Efficiency** | 运维效率、自动化、交付流程 | 是否使用 IaC、CI/CD 流水线、监控告警是否完善 |

### 1.2 支柱间的权衡

架构设计本质上是权衡的艺术。常见冲突包括：

- **Reliability vs Cost**: 多 AZ + 多副本部署提高可靠性但增加成本
- **Performance vs Cost**: 更高规格的实例和 SSD 磁盘提升性能但增加支出
- **Security vs Efficiency**: 严格的访问控制和加密增加运维复杂度

alicloud-arch-advisor 在报告中会标注此类权衡关系，由用户基于业务优先级做决策，而不是替用户选择。

---

## 2. 通用架构模式

alicloud-arch-advisor 识别四种主要架构模式，用于在 Mode A 中进行模式分类，在 Mode C 中作为方案模板的基础。

### 2.1 单节点架构 (Single-Node)

```
[ ECS (单台) ]
      |
[ RDS (单节点) ]
```

**特征**: 所有组件均为单实例部署，无冗余。
**适用**: 开发测试环境、小型个人站点、低流量 MVP。
**WAF 风险**: Reliability 最低，Cost 可控，Security 依赖手动配置。
**典型产品**: 1x ECS + 1x RDS MySQL 基础版 + 1x OSS Bucket。

### 2.2 三层架构 (3-Tier)

```
[ SLB/ALB ] → [ ECS Cluster (多台) ] → [ RDS 高可用 / Redis ]
                                          [ OSS / NAS ]
```

**特征**: 接入层、应用层、数据层分离，每层可以独立扩缩。
**适用**: 标准 Web 应用、企业管理系统、中等流量业务。
**WAF 风险**: Reliability 良好，但需要关注 SLB 健康检查、ECS 伸缩策略、数据库备份。
**典型产品**: ALB + N 台 ECS (Auto Scaling) + RDS MySQL 高可用版 + Redis + OSS。

### 2.3 微服务架构 (Microservice)

```
[ ALB/APIGateway ]
      |
[ Service A (ACK Pod) ] ←→ [ Service B (ACK Pod) ]
      |                           |
[ RDS / PolarDB ]         [ Redis / MongoDB ]
      |
[ MSE / RocketMQ ]   ← 异步消息解耦
```

**特征**: 业务拆分为独立服务，每个服务有自己的数据存储，通过 API 或消息队列通信。
**适用**: 复杂业务系统、大型电商、需要频繁迭代的产品。
**WAF 风险**: 架构复杂度高，需要服务治理( MSE/Sentinel)、可观测性(SLS/ARMS)、CI/CD 流水线。
**典型产品**: ACK + MSE + RocketMQ + PolarDB + SLS + ARMS + Redis。

### 2.4 Serverless 架构

```
[ API Gateway / ALB ]
      |
[ Function Compute ]  →  [ Tablestore / OSS ]
      |
[ SLS (日志) / MNS (消息) ]
```

**特征**: 无服务器管理，按用量付费，自动弹性伸缩。
**适用**: 事件驱动型业务、不定时突发流量、低频 API、批处理任务。
**WAF 风险**: 冷启动延时、长任务不适用、厂商锁定风险。
**典型产品**: FC + Tablestore + OSS + API Gateway + SLS + MNS。

---

## 3. 三模式方法论

alicloud-arch-advisor 采用三模式设计，确保对用户意图的精确覆盖。

### 3.1 Mode A — 架构逆向与分析

**输入**: 用户描述的现有系统
**输出**: 架构拓扑 + 组件清单 + 依赖关系 + 风险标识

核心能力：
1. 从用户自然语言描述中提取架构信息
2. 通过 `topo-discovery` 验证实际资源状态
3. 自动识别架构模式（单节点/三层/微服务/Serverless）
4. 标注每个组件的健康状态和潜在风险

适用场景：新接手系统需要了解架构、系统文档缺失需要重建、并购后的技术尽调。

### 3.2 Mode B — WAF 成熟度评估

**输入**: 评估范围（全量或指定支柱）
**输出**: 五支柱评分 + 风险发现清单 + 改进建议

核心能力：
1. 基于实际资源状态（topo-discovery）和巡检结果（advisor-ops）进行客观评估
2. 每个支柱分解为多个检查维度
3. 每个发现项标注严重级别 P0-P3
4. 提供可操作的改进建议，包括预估工作量和影响

评估流程示例（Security 支柱）：
```
1. 安全检查项：
   - 安全组是否过度开放（`0.0.0.0/0` 端口映射）？
   - 是否有未关联安全组的 ECS 实例？
   - RDS 是否开启了 TLS/SSL？
   - OSS Bucket 是否公开可读？
   - RAM 用户是否启用了 MFA？
   - ActionTrail 是否已启用？

2. 数据来源：advisor-ops (DescribeAdvices filter Security) + topo-discovery
3. 评分逻辑：每个检查项通过得 1 分，按通过比例计算支柱得分
```

### 3.3 Mode C — 架构方案推荐

**输入**: 业务需求描述 + 非功能性要求 + 约束
**输出**: 推荐架构方案 + 多方案对比 + 实施路线

核心能力：
1. 根据业务特征匹配合适的架构模式
2. 参考阿里云最佳实践场景模板
3. 对比至少 2 个可行方案（成本、复杂度、WAF 覆盖度）
4. 推荐分阶段实施路线

方案对比示例：

| 维度 | 方案 A: 传统三层 (ALB+ECS+RDS) | 方案 B: 容器化 (ACK+PolarDB) |
|------|:---:|:---:|
| WAF Security | ★★★☆☆ | ★★★★☆ |
| WAF Reliability | ★★★★☆ | ★★★★★ |
| WAF Performance | ★★★☆☆ | ★★★★★ |
| WAF Cost | ★★★★☆ | ★★★☆☆ |
| WAF Efficiency | ★★★☆☆ | ★★★★★ |
| 运维复杂度 | 低 | 中高 |
| 月度成本预估 | ¥3,000 | ¥4,500 |
| 推荐场景 | 快速上线、团队经验有限 | 长期运行、团队有容器经验 |

---

## 4. 数据采集策略

### 4.1 主动采集（通过委托下游 Skill）

| 数据源 Skill | 采集内容 | 模式依赖 |
|-------------|---------|:--------:|
| `alicloud-topo-discovery` | 资源清单、网络拓扑、组件依赖 | A, B, C |
| `alicloud-advisor-ops` | Advisor 巡检结果、成本优化建议 | B (所有支柱) |
| `alicloud-cms-ops` | 资源利用率指标（CPU/内存/IOPS） | B (Performance) |
| `alicloud-billing-ops` | 账单数据、成本趋势 | B (Cost) |

### 4.2 被动采集（用户直接提供）

当 Agent 无法访问实际云环境（无凭证或 Skill 不可用时），采用降级策略：

- **用户描述**: 要求用户提供架构图、配置清单等
- **Confidence 标注**: 报告中标注依赖实际数据源的结论为 `low confidence`
- **局限性说明**: 明确告知用户哪些评估因数据源不可用而无法完成

---

## 5. 参考链接

- [阿里云 Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html)
- [阿里云最佳实践](https://www.alibabacloud.com/zh/solutions)
- [阿里云产品白皮书](https://www.alibabacloud.com/zh/whitepapers)