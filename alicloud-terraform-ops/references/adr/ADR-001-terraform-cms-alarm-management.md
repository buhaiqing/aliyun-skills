# ADR-001: Terraform 管理云监控告警体系

> **状态**: Accepted
> **日期**: 2025-01-15
> **决策者**: AI Agent (alicloud-terraform-ops)

---

## 背景

云监控（CloudMonitor Service, CMS）是阿里云基础设施可观测性的核心组件。传统方式通过控制台手动配置告警规则存在以下问题：

| 问题 | 影响 |
|------|------|
| 手动配置无法版本化 | 无法回滚、审计困难 |
| 多环境配置不一致 | dev/prod 告警阈值混乱 |
| 告警联系人分散管理 | 人员变动时漏通知 |
| 无法与 IaC 流程集成 | 基础设施变更不触发告警同步 |

## 决策

**使用 Terraform 管理阿里云云监控告警体系**，包括：
- 告警规则（`alicloud_cms_alarm`）
- 告警联系人组（`alicloud_cms_contact_group`）
- 钉钉 Webhook 通知

## 架构设计

### 资源模型

```
┌─────────────────────────────────────────────────────────────┐
│                    Terraform CMS Module                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐     ┌──────────────────────────┐     │
│  │ contact_group    │     │ alarm_rules              │     │
│  │ (联系人组)        │────▶│ - cpu_alarm             │     │
│  │                  │     │ - memory_alarm           │     │
│  │ - email          │     │ - disk_alarm             │     │
│  │ - sms            │     │ - slb_502_alarm          │     │
│  │ - webhook        │     │ - [resource-specific]     │     │
│  └──────────────────┘     └──────────────────────────┘     │
│           │                         │                       │
│           ▼                         ▼                       │
│  ┌────────────────────────────────────────────────────┐   │
│  │              alicloud_cms_alarm                     │   │
│  │  alarm_actions ← contact_group.id                   │   │
│  │  ok_actions   ← contact_group.id                   │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 模块设计

```
modules/addon-cms-alarm/
├── main.tf         # 资源定义
├── variables.tf    # 输入变量
├── outputs.tf     # 输出
└── versions.tf    # 版本约束
```

### 告警规则类型

| 类型 | 指标 | 适用资源 | 默认阈值 |
|------|------|----------|----------|
| CPU | `cpu_total` | ECS | 80% |
| 内存 | `memory_usedutilization` | ECS | 85% |
| 磁盘 | `diskusage_utilization` | ECS | 85% |
| SLB 502 | `SlbHttpCode_5xx` | SLB | 5% |
| RDS | `CpuUsage`/`DiskUsage` | RDS | 80%/85% |
| Redis | `MemoryUsage`/`QPS` | Redis | 85%/10000 |

## 决策理由

### 为什么用 Terraform 管理 CMS？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Terraform IaC** | 版本化、可复用、多环境一致 | 需要学习 HCL |
| 控制台手动 | 简单直观 | 无法版本化、易出错 |
| SDK/API 脚本 | 灵活 | 无状态管理、无 plan 预览 |
| Ansible | 可复用 | 非声明式、无依赖分析 |

### 为什么告警模块独立？

1. **解耦**: 告警与基础设施独立演进
2. **复用**: 不同项目复用相同告警模板
3. **粒度**: 可单独 apply/destroy 告警
4. **测试**: 告警变更不影响业务资源

## 替代方案考虑

### 方案 A: 嵌入业务模块（Rejected）

```hcl
# 不推荐：告警与 ECS 耦合
module "ecs" {
  source = "../../modules/compute-ecs"
  # ... ECS 配置
}
```

**问题**:
- 告警变更触发 ECS 重建（误报）
- 告警配置难以复用
- 权限耦合

### 方案 B: Terraform Cloud 管理（Rejected）

**问题**:
- 需要 Terraform Cloud 订阅
- 国内访问延迟
- 与现有 OSS Backend 冲突

### 方案 C: 独立 Module（Accepted）

```hcl
# 推荐：告警独立管理
module "ecs" {
  source = "../../modules/compute-ecs"
}

module "cms_alarm" {
  source = "../../modules/addon-cms-alarm"
  alarm_resources = [
    { resource_id = module.ecs.instance_id, resource_type = "acs_ecs", metric_name = "cpu_total" }
  ]
}
```

## 后果

### 正面

- ✅ 告警配置版本化，可审计
- ✅ 多环境告警一致性
- ✅ 支持多环境阈值差异化（dev: 90%, prod: 80%）
- ✅ 告警变更通过 plan 预览
- ✅ 可与 CI/CD 集成

### 负面

- ⚠️ 需要维护告警模板
- ⚠️ 告警模块更新需要 apply
- ⚠️ 联系人变更需要权限（RAM）

### 风险

| 风险 | 缓解措施 |
|------|----------|
| 告警通知风暴 | 配置 `silence_minutes` 静默周期 |
| 联系人失效 | 定期审计联系人组 |
| 阈值误配 | GCL Correctness 检查阈值范围 |
| Terraform 误删告警 | `prevent_destroy = true` |

## 相关文档

- [SPEC-cms-alarm.md](./SPEC-cms-alarm.md) — 详细规格
- [knowledge-cms-alarm.md](./knowledge-cms-alarm.md) — 知识库
- [module-coverage.md](./module-coverage.md) — 模块覆盖矩阵

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2025-01-15 | 1.0 | 初始版本 |
