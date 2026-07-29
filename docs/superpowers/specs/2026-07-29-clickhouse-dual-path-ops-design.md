# SPEC: alicloud-clickhouse-ops — Dual-Path (Enterprise CLI + Classic SDK) Design

## What & Why

**What**: 为阿里云云数据库 ClickHouse 版（ApsaraDB for ClickHouse）创建产品运维 Skill。

**Why**: ClickHouse 是实时分析数据库，目前在 `aliyun-skills` 仓库中完全缺失（仅 DMS skill 中作为数据源列出）。用户需要自动化管理 ClickHouse 集群生命周期、账户、备份、监控等操作。

## Product Context

| 项 | 值 |
|---|---|
| 产品名 | 云数据库 ClickHouse 版 (ApsaraDB for ClickHouse) |
| API 版本 | 企业版: `2023-05-22`，经典版: `2019-11-11` |
| CLI 支持 | ✅ `aliyun clickhouse`（企业版），需 plugin `aliyun-cli-clickhouse` |
| Go SDK | `github.com/alibabacloud-go/clickhouse-20191111` |
| CLI Applicability | `dual-path`（企业版 CLI, 经典版 SDK） |
| 主资源 | DBInstance（ClickHouse 集群） |

## Success Criteria

- [ ] `alicloud-clickhouse-ops/` 目录创建，包含 `SKILL.md` + `references/` + `assets/`
- [ ] 覆盖 ClickHouse 企业版集群的完整生命周期管理（创建、查询、修改、释放、启停、重启、升配）
- [ ] 覆盖账户管理、白名单、备份策略、慢查询监控
- [ ] 遵循 aliyun-skills 仓库规范：P0/P1 checklist, token efficiency, GCL readiness

## Scope Boundaries

| In Scope | Out of Scope |
|----------|-------------|
| 企业版集群管理 (CreateDBInstance, DescribeDBInstances, ModifyDBInstanceClass, DeleteDBInstance, StartDBInstance, StopDBInstance, RestartDBInstance) | 经典版集群（仅 SDK 覆盖，可后续扩展） |
| 账户管理 (CreateAccount, DeleteAccount, DescribeAccounts, ModifyAccountAuthority, ResetAccountPassword) | 数据面操作（如 INSERT/SELECT 查询） |
| 数据库管理 (CreateDB, DeleteDB) | 内核参数调优 |
| 安全白名单 (ModifySecurityIPList, DescribeSecurityIPList) | 跨产品编排 |
| 备份策略 (CreateBackupPolicy, ModifyBackupPolicy, DescribeBackups) | |
| 慢查询监控 (DescribeSlowLogRecords, DescribeSlowLogTrend) | |
| 配置管理 (ModifyDBInstanceConfig, DescribeDBInstanceConfig) | |
| 连接管理 (CreateEndpoint, DescribeEndpoints, ModifyDBInstanceConnectionString) | |

## Key Decisions (recorded)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI applicability | `dual-path` | 企业版 CLI 全支持；经典版需 SDK fallback |
| 模板来源 | `alicloud-elasticsearch-ops` | 同为数据类产品，结构最接近 |
| API 版本 | 优先 `2023-05-22`（企业版） | CLI 原生支持，操作覆盖更全 |
