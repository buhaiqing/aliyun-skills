# Skill 功能矩阵 (Skill Matrix)

> 速览：本仓库共有 **53 个 `alicloud-*` 技能目录**（45 个产品 `-ops` + 8 个元/治理/编排类）。
> 下表按 **能力维度** 标注每个技能能做什么，帮助你快速找到对应技能，而不是逐个翻 `SKILL.md`。
> 完整触发词与参数见各技能目录下的 `SKILL.md`。

## 能力维度说明

| 维度 | 含义 |
| --- | --- |
| 生命周期 | 资源的创建 / 修改 / 删除 / 查询（CRUD） |
| 监控告警 | 指标查询、大盘、告警规则、订阅 |
| 诊断排障 | 故障定位、错误码分析、日志/链路排查 |
| 安全合规 | 访问控制、密钥、审计、合规检查、WAF |
| 治理编排 | 跨产品巡检、架构评审、弹性编排、资源组织 |
| 开发框架 | 技能生成、运行时 Harness、GCL 质量门禁 |

---

## 产品技能 (45 × `-ops`)

| 技能 | 产品 | 生命周期 | 监控告警 | 诊断排障 | 安全合规 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| `ecs-ops` | ECS 云服务器 | ✅ | ✅ | ✅ | ✅ | 实例/磁盘/快照/安全组，含 SecOps 巡检 |
| `rds-ops` | RDS 数据库 | ✅ | ✅ | ✅ | — | MySQL/PG/SQL Server，含告警诊断 |
| `redis-ops` | Redis/Tair | ✅ | ✅ | ✅ | — | 实例，含 redis-cli、智能巡检 |
| `mongodb-ops` | MongoDB | ✅ | ✅ | ✅ | — | ApsaraDB for MongoDB |
| `polar-mysql-ops` | PolarDB MySQL | ✅ | ✅ | ✅ | — | 集群部署/配置/排障 |
| `polar-oracle-ops` | PolarDB Oracle | ✅ | ✅ | ✅ | — | Oracle 兼容集群 |
| `polar-postgresql-ops` | PolarDB PG | ✅ | ✅ | ✅ | — | PostgreSQL 集群（规范命名） |
| `polar-pg-ops` | PolarDB PG | ✅ | ✅ | ✅ | — | PostgreSQL 集群（compact，与上并存） |
| `ack-ops` | ACK Kubernetes | ✅ | ✅ | ✅ | — | 托管 K8s 集群生命周期与排障 |
| `ask-ops` | ASK Serverless K8s | ✅ | ✅ | ✅ | — | 无服务器 K8s |
| `eci-ops` | ECI 弹性容器 | ✅ | — | ✅ | — | 弹性容器实例 |
| `fc-ops` | 函数计算 FC | ✅ | ✅ | ✅ | — | 函数诊断/优化/监控 |
| `alb-ops` | ALB 应用型负载 | ✅ | ✅ | ✅ | — | 负载均衡部署/配置/排障 |
| `slb-ops` | SLB/CLB 负载 | ✅ | ✅ | ✅ | — | 经典负载均衡 |
| `eip-ops` | 弹性公网 IP | ✅ | — | — | — | 分配/绑定/解绑/释放 |
| `nat-ops` | NAT 网关 | ✅ | — | ✅ | — | SNAT/DNAT/FULLNAT 配置 |
| `vpc-ops` | VPC 专有网络 | ✅ | — | — | — | 网络资源全生命周期 |
| `cen-ops` | 云企业网 CEN | ✅ | ✅ | ✅ | — | 跨地域组网 |
| `dns-ops` | 云解析 DNS | ✅ | — | — | — | 公网/私有权威解析 |
| `oss-ops` | 对象存储 OSS | ✅ | — | — | — | 存储桶与对象管理 |
| `nas-ops` | 文件存储 NAS | ✅ | — | — | — | 文件系统创建/挂载/删除 |
| `elasticsearch-ops` | Elasticsearch | ✅ | ✅ | ✅ | — | 部署/配置/排障，含 AIOps |
| `kms-ops` | 密钥管理 KMS | ✅ | ✅ | ✅ | ✅ | 密钥/凭据托管 |
| `ram-ops` | 访问控制 RAM | — | — | — | ✅ | 用户/角色/权限/策略 |
| `sas-ops` | 安全中心 SAS | — | ✅ | ✅ | ✅ | 主机安全、漏洞/基线 |
| `waf-ops` | Web 应用防火墙 | — | — | ✅ | ✅ | 网站防护、规则配置 |
| `cms-ops` | 云监控 CMS | — | ✅ | — | — | 指标/告警/大盘/健康巡检 |
| `das-ops` | 数据库自治 DAS | — | ✅ | ✅ | — | 慢 SQL/性能/连接诊断 |
| `actiontrail-ops` | 操作审计 | — | — | ✅ | ✅ | 账号操作溯源 |
| `billing-ops` | 费用中心 | — | ✅ | — | — | 账单/成本/订单 |
| `sls-ops` | 日志服务 SLS | ✅ | ✅ | ✅ | — | 日志采集/查询/分析 |
| `dts-ops` | 数据传输 DTS | ✅ | ✅ | ✅ | — | 数据迁移/同步 |
| `dms-ops` | 数据管理 DMS | ✅ | — | — | — | 数据库元数据与开发 |
| `pts-ops` | 性能测试 PTS | ✅ | ✅ | ✅ | — | 压测任务创建/运行/分析 |
| `sms-ops` | 短信服务 | ✅ | — | — | — | 单发/批量短信、模板 |
| `voice-ops` | 语音通知 | ✅ | — | — | — | 单发/批量语音通知 |
| `bailian-ops` | 百炼 GenAI | ✅ | — | — | — | 模型/Agent/RAG/Prompt |
| `resourcemanager-ops` | 资源管理 | — | — | — | ✅ | 资源目录/账号/标签策略 |
| `advisor-ops` | 智能顾问 | — | ✅ | ✅ | ✅ | 跨产品健康巡检建议 |
| `terraform-ops` | Terraform/IaC | ✅ | — | ✅ | — | 基础设施创建/销毁 |
| `ess-ops` | 弹性伸缩 ESS | ✅ | ✅ | ✅ | — | 伸缩组/伸缩规则 |
| `agentrun-ops` | AgentRun 沙箱 | ✅ | — | ✅ | — | 沙箱资源/模板/会话 |
| `auto-scaling-orch` | 弹性伸缩编排 | — | ✅ | — | — | 跨产品弹性编排 |
| `arch-advisor` | 架构评审 | — | — | ✅ | ✅ | 架构评审、WAF 评估 |
| `aiops-cruise` | AIOps 巡检 | — | ✅ | ✅ | ✅ | 全链路巡检（多感知 Agent） |
| `topo-discovery` | 拓扑发现 | — | — | ✅ | — | 网络拓扑与资源清单发现 |

---

## 元 / 框架技能 (8 个)

| 技能 | 类别 | 作用 |
| --- | --- | --- |
| `skill-generator` | 开发框架 | 从 OpenAPI spec 生成/更新 `alicloud-*-ops` 骨架 |
| `runtime-harness-ops` | 开发框架 | Runtime Harness：Langfuse 追踪、Prometheus 指标 |
| `skillopt-ops` | 开发框架 | Runtime Harness 旧版兼容别名 |
| `gcl-runner-ops` | 开发框架 | GCL 对抗式质量门禁 + 记忆/反思/策略 |
| `sandbox-dev` | 开发框架 | FC Sandbox Sidecar 代理开发 |
| `aiyun-skills` | 预留 | 迁移占位目录，当前为空壳 |

---

## 使用提示

- **找技能**：先按产品/维度定位，再打开对应目录的 `SKILL.md` 看触发词。
- **跨产品任务**：优先用编排/治理类（如 `auto-scaling-orch`、`arch-advisor`、`aiops-cruise`、`advisor-ops`），它们会自动委托下游产品技能。
- **安全红线**：所有 `Delete*` / `Release*` / `Flush*` 等破坏性操作都需你在会话中显式确认，技能不会静默执行。
- **统一命名**：用户面向提示词示例为 `references/prompt-examples.md`；GCL 内部模板为 `references/prompt-templates.md`。
