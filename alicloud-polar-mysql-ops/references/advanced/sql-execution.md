# SQL Execution — PolarDB MySQL (Agent Runbook)

> **Read this document first** when the user asks to run SQL, execute a `.sql` file,
> import schema/data, or "在 PolarDB MySQL 集群里执行 SQL".

## TL;DR (Decision Tree)

```
用户要在 PolarDB MySQL 集群里执行 SQL（尤其是一个含多条语句的 .sql 文件）
│
├─ 问：能否用 `aliyun polardb` 直接执行 SQL？
│   └─ ❌ 不能。`aliyun polardb` 是管控面 API（建删集群、节点、账号、备份等），不含执行 SQL。
│
├─ 问：PolarDB 有类似 RDS Data API 的接口吗？
│   └─ ❌ 没有。PolarDB MySQL 当前无 `polardb-data` 类似的 SQL 执行 API。
│
├─ 推荐路径（多语句 .sql 文件、DDL+DML 混合、含存储过程）
│   └─ ✅ 标准 `mysql` 客户端 + 集群 Endpoint 地址（见 §Path A）
│       · 通过 Primary Endpoint 执行写入操作
│       · 通过 Cluster Endpoint 实现读写分离
│       · 通过 Custom Endpoint 连接指定节点组
│
└─ 可选路径（无 mysql 客户端、仅需查询类操作）
    └─ ⚠️ 通过 DMS 或控制台执行（见 §Path B）
        · 适合临时查询、无自动化需求
```

| 需求 | 推荐方式 | Endpoint 类型 |
|------|----------|---------------|
| 执行含多条语句的 `.sql` 文件 | `mysql ... < file.sql` | Primary（写入）或 Cluster（读写分离） |
| 单条查询（只读） | `mysql ... -e "SELECT..."` | Cluster 或 Custom（只读节点） |
| 单条写入（INSERT/UPDATE/DELETE） | `mysql ... -e "..."` | Primary（必须） |
| 管理集群/账号/库（不执行 SQL） | `aliyun polardb ...` | 管控面 API |

---

## PolarDB Endpoint Architecture

PolarDB MySQL 集群提供多种 Endpoint 类型，支持不同的访问场景：

| Endpoint 类型 | 地址标识 | 用途 | SQL 执行建议 |
|---------------|----------|------|--------------|
| **Primary（主地址）** | `pc-xxxx.mysql.polardb.rds.aliyuncs.com` | 连接主节点，所有写入操作 | DDL、INSERT、UPDATE、DELETE |
| **Cluster（集群地址）** | `pc-xxxx-cluster.mysql.polardb.rds.aliyuncs.com` | 读写分离，自动路由 | 混合读写、查询为主 |
| **Custom（自定义地址）** | 用户自定义名称 | 指定节点组（如所有只读节点） | 纯查询、分析任务 |

### Endpoint 选择指南

```
SQL 类型决策树
│
├─ 写入操作（INSERT/UPDATE/DELETE/DDL）
│   └─ ✅ Primary Endpoint（主地址）
│       · 所有写入必须通过主节点
│       · 确保数据一致性
│
├─ 纯查询（SELECT）
│   ├─ 需要读写分离（自动路由）
│   │   └─ ✅ Cluster Endpoint（集群地址）
│   │       · 自动将读请求路由到只读节点
│   │       · 减轻主节点压力
│   │
│   └─ 只读节点专用查询
│   │   └─ ✅ Custom Endpoint（连接只读节点）
│   │       · 指定特定只读节点
│   │       · 适合大数据分析、报表查询
│
└─ 混合操作（事务中含读写）
    └─ ✅ Primary Endpoint
        · 事务内读写需在同一节点
```

---

## Path A — `mysql` 客户端执行 SQL（推荐）

适用：`.sql` 含多条语句、DDL+DML、迁移脚本、初始化 schema、用户明确要"跑 SQL 文件"。

### A.1 前置条件（Agent 检查清单）

| # | 检查项 | 如何验证 |
|---|--------|----------|
| 1 | 集群状态为 Running | `aliyun polardb DescribeDBClusterAttribute --DBClusterId <id>` → `DBClusterStatus` |
| 2 | 执行端能访问集群网络 | 同 VPC 用内网地址；跨 VPC 用云企业网或 NAT |
| 3 | IP 白名单已放行 | `aliyun polardb DescribeDBClusterAccessWhitelist --DBClusterId <id>` |
| 4 | 账号与库已存在 | `DescribeAccounts` / `DescribeDatabases`；或脚本内含 `CREATE` |
| 5 | 本机已安装 `mysql` 客户端 | `mysql --version` |

### A.2 用 `aliyun polardb` 获取 Endpoint 信息

```bash
# 1) 获取集群所有 Endpoint
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 输出结构（关键路径）：
# $.EndItems.Endpoint[].DBEndpointId      — Endpoint ID（如 primary、cluster）
# $.EndItems.Endpoint[].DBEndpointType    — 类型：Primary、Cluster、Custom
# $.EndItems.Endpoint[].Address[].ConnectionString — 连接域名
# $.EndItems.Endpoint[].Address[].Port    — 端口（通常 3306）

# 2) 解析 Primary Endpoint（用于写入）
PRIMARY_HOST=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --output cols=ConnectionString rows='EndItems.Endpoint[?DBEndpointType==`Primary`].Address[0]')

# 3) 解析 Cluster Endpoint（用于读写分离）
CLUSTER_HOST=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --output cols=ConnectionString rows='EndItems.Endpoint[?DBEndpointType==`Cluster`].Address[0]')

# 4) 查看白名单配置
aliyun polardb DescribeDBClusterAccessWhitelist \
  --DBClusterId "{{user.db_cluster_id}}"
```

### A.3 执行 SQL 文件

#### 通过 Primary Endpoint 执行（写入操作）

```bash
# 变量（由用户或上一步 API 提供）
export POLAR_HOST="pc-xxxx.mysql.polardb.rds.aliyuncs.com"  # Primary Endpoint
export POLAR_PORT="3306"
export POLAR_USER="dbuser"
export POLAR_PASS=""  # ⚠️ 密码来源说明：
                      # - {{user.account_password}}：用户直接提供
                      # - 环境变量：POLAR_DB_PASSWORD（推荐安全实践）
                      # - Secrets Manager：通过 API 获取（生产环境推荐）
                      # Agent 必须在执行前明确询问或验证密码存在
export POLAR_DB="mydb"
export SQL_FILE="./schema.sql"

# 方式 1：标准输入重定向（最常用）
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" < "$SQL_FILE"

# 方式 2：交互式 source（适合含 DELIMITER 的存储过程）
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" \
  -e "source $SQL_FILE"

# 方式 3：不指定库名（脚本内自行 USE / CREATE DATABASE）
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" < "$SQL_FILE"
```

#### 通过 Cluster Endpoint 执行（读写分离）

```bash
# 使用集群地址，自动实现读写分离
export POLAR_CLUSTER_HOST="pc-xxxx-cluster.mysql.polardb.rds.aliyuncs.com"

# 查询类操作会自动路由到只读节点
mysql -h "$POLAR_CLUSTER_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" \
  -e "SELECT COUNT(*) FROM large_table WHERE created_at > '2024-01-01'"
```

#### 通过 Custom Endpoint 执行（指定只读节点）

```bash
# 假设有自定义只读 Endpoint：custom-reader
export POLAR_CUSTOM_HOST="pc-xxxx-custom-reader.mysql.polardb.rds.aliyuncs.com"

# 适合大数据分析、报表查询等重负载只读任务
mysql -h "$POLAR_CUSTOM_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" \
  -e "SELECT /*+ PARALLEL(4) */ * FROM orders WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'"
```

**安全提示：** 生产环境优先 `-p` 交互输入或从环境变量读取密码，避免在 shell 历史里明文
`--password=xxx`。Agent 不得将用户密码写入日志或提交到版本库。

### A.4 单条 SQL 执行

```bash
# 写入操作（通过 Primary Endpoint）
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" \
  -e "INSERT INTO users (id, name) VALUES (1, 'alice')"

# 查询操作（通过 Cluster Endpoint，利用读写分离）
mysql -h "$POLAR_CLUSTER_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" \
  -e "SELECT * FROM users WHERE id = 1"

# DDL 操作（通过 Primary Endpoint）
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" "$POLAR_DB" \
  -e "CREATE TABLE IF NOT EXISTS orders (id INT PRIMARY KEY, amount DECIMAL(10,2))"
```

### A.5 常见失败与处理

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `ERROR 2003 (HY000): Can't connect` | 白名单/网络/VPC | 检查白名单配置、VPC 网络连通性 |
| `Access denied` | 账号密码或权限 | `DescribeAccounts`；确认对目标库有权限 |
| 部分语句成功、后续失败 | 脚本未包事务 | 大变更前备份；考虑事务模式或拆分文件 |
| 存储过程报错 | 文件含 `DELIMITER` | 用 `source` 或 `mysql` 交互模式 |
| 写入操作用 Cluster Endpoint 报错 | 读写分离限制 | 确保写入操作使用 Primary Endpoint |

---

## Path B — DMS / 控制台（补充）

用户仅需一次性导入、无自动化要求时，可引导 [DMS 登录 PolarDB 集群](https://help.aliyun.com/zh/polardb/polardb-for-mysql/step-2-connect-to-an-apsaradb-polardb-for-mysql-cluster)
执行 SQL 或导入。此路径 **不经过** `aliyun` CLI 执行 SQL。

### DMS 使用场景

| 场景 | DMS 功能 | 适用性 |
|------|----------|--------|
| 临时查询 | SQL 窗口 | ✅ 适合快速查询验证 |
| 数据导入 | 数据导入向导 | ✅ CSV、SQL 文件导入 |
| 表结构修改 | 表设计器 | ✅ 可视化 DDL 操作 |
| 执行历史查询 | SQL 审计 | ✅ 查看历史执行记录 |

---

## 安全控制机制

### 危险 SQL 识别

Agent 执行 SQL 前必须进行安全检查：

| 危险等级 | SQL 类型 | 关键词示例 | Agent 动作 |
|----------|----------|------------|------------|
| **🔴 高危** | 数据删除 | `DROP`, `TRUNCATE`, `DELETE FROM` (无 WHERE) | **必须用户确认** |
| **🟠 中危** | 数据修改 | `UPDATE` (无 WHERE), `ALTER TABLE DROP` | **必须用户确认** |
| **🟡 低危** | 结构变更 | `CREATE`, `ALTER TABLE ADD` | 建议用户确认 |
| **🟢 安全** | 数据查询 | `SELECT`, `SHOW`, `DESCRIBE` | 可直接执行 |

### 安全检查流程

```
SQL 安全检查流程
│
├─ 1. 解析 SQL 类型
│   ├─ 提取首条语句关键词（忽略注释）
│   └─ 匹配危险等级表
│
├─ 2. 危险等级判定
│   ├─ 🔴 高危 → HALT，显示完整 SQL，请求用户确认
│   ├─ 🟠 中危 → HALT，显示完整 SQL，请求用户确认
│   ├─ 🟡 低危 → 提示用户，可选确认
│   └─ 🟢 安全 → 继续执行
│
├─ 3. 用户确认机制
│   ├─ 显示：SQL 内容、影响范围预估
│   ├─ 选项：确认执行 / 取消 / 修改后执行
│   └─ 记录：用户确认时间、方式
│
└─ 4. 执行结果脱敏
    ├─ 不显示敏感数据（密码字段、个人信息）
    ├─ 显示执行状态和影响行数
    └─ 错误信息不包含完整 SQL 内容
```

### 用户确认模板

```
⚠️ 危险 SQL 检测

即将执行高危操作：
────────────────────────────────────
SQL 类型：DROP TABLE
目标对象：users_backup
影响范围：永久删除表及所有数据
────────────────────────────────────

请确认：
[1] 确认执行
[2] 取消操作
[3] 查看完整 SQL 内容

输入选项：
```

---

## 操作：ExecuteSQL

执行单条 SQL 语句。

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 集群状态 | `DescribeDBClusterAttribute` | `Running` | HALT; 等待集群恢复 |
| Endpoint 可用 | `DescribeDBClusterEndpoints` | Primary 或 Cluster endpoint 存在 | HALT; 检查集群配置 |
| 白名单 | `DescribeDBClusterAccessWhitelist` | 执行机 IP 在白名单 | 提示添加白名单 |
| 账号权限 | `DescribeAccounts` + `DescribeDatabases` | 账号对库有相应权限 | HALT; 检查账号权限 |
| SQL 安全检查 | 解析 SQL 类型 | 非高危或已确认 | 高危 → 用户确认 |

### Execution Flow

```bash
# 1. 获取 Endpoint
ENDPOINT_INFO=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}")

# 2. 根据 SQL 类型选择 Endpoint
# 写入类 → Primary Endpoint
# 查询类 → Cluster Endpoint（推荐）或 Primary

# 3. 执行 SQL
mysql -h "$POLAR_HOST" -P "$POLAR_PORT" -u "$POLAR_USER" -p"$POLAR_PASS" \
  -e "{{user.sql_statement}}" "{{user.db_name}}"
```

### Post-execution Validation

1. 检查退出码 `$?`
2. 查询类：返回结果行数 > 0 或明确空结果
3. 写入类：返回 `Query OK, N rows affected`
4. DDL 类：返回 `Query OK, 0 rows affected`

### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `ERROR 2003 (HY000)` | 检查白名单、VPC 网络、Endpoint 地址 |
| `Access denied for user` | 检查账号权限、密码正确性 |
| `Unknown database` | 确认库名或创建库 |
| `Table doesn't exist` | 确认表名或检查 DDL 是否执行 |
| `Syntax error` | 显示错误位置，建议修正 SQL |

---

## 操作：ExecuteSQLFile

执行 `.sql` 文件（含多条语句）。

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| 文件存在 | `test -f "{{user.sql_file}}"` | 文件可读 | HALT; 确认文件路径 |
| 文件大小 | `wc -l "{{user.sql_file}}"` | 可执行大小 | 超大文件提示拆分 |
| 文件内容安全 | 扫描所有 SQL 语句 | 无高危或已确认 | 高危 → 用户确认 |

### Execution Flow

```bash
# 1. 扫描文件危险语句
grep -iE "DROP|TRUNCATE|DELETE FROM" "{{user.sql_file}}" | head -20
# 发现高危语句 → HALT 并请求用户确认

# 2. 获取 Primary Endpoint（写入文件默认用主地址）
POLAR_HOST=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --output cols=ConnectionString rows='EndItems.Endpoint[?DBEndpointType==`Primary`].Address[0]')

# 3. 执行 SQL 文件
mysql -h "$POLAR_HOST" -P "3306" -u "{{user.account_name}}" -p"$POLAR_PASS" \
  "{{user.db_name}}" < "{{user.sql_file}}"

# 4. 检查执行结果
if [ $? -eq 0 ]; then
  echo "✅ SQL 文件执行成功"
else
  echo "❌ SQL 文件执行失败，请检查错误信息"
fi
```

### 安全扫描脚本

```bash
# 扫描文件中的危险 SQL（简化版）
scan_sql_file() {
  local file="$1"
  local dangerous=0
  
  # 检测高危语句
  if grep -qiE "^\s*(DROP|TRUNCATE)" "$file"; then
    echo "🔴 高危：发现 DROP/TRUNCATE 语句"
    dangerous=1
  fi
  
  # 检测无 WHERE 的 DELETE/UPDATE
  if grep -qiE "DELETE FROM.*;$" "$file" | grep -qv "WHERE"; then
    echo "🟠 中危：发现无 WHERE 的 DELETE 语句"
    dangerous=1
  fi
  
  if grep -qiE "UPDATE.*;$" "$file" | grep -qv "WHERE"; then
    echo "🟠 中危：发现无 WHERE 的 UPDATE 语句"
    dangerous=1
  fi
  
  return $dangerous
}
```

> **⚠️ 简化版局限性说明：**
> - 此脚本基于正则匹配，可能遗漏以下复杂场景：
>   - 存储过程内嵌的危险 SQL（`CREATE PROCEDURE` 内含 `DROP`）
>   - 动态 SQL 拼接（字符串内含危险关键词）
>   - 多行 SQL 语句（跨行的 `DELETE FROM`）
>   - 注释混淆（危险关键词被注释包裹）
> - **生产环境建议**：使用专业 SQL 解析器（如 `sqlparse` Python 库）进行 AST 级别分析
> - **复杂文件处理**：含存储过程、触发器、事件调度器的 SQL 文件，建议人工审核后再执行
```

---

## 操作：DescribeSlowQueryLogs

查询 PolarDB 慢查询日志。

> **注意：** PolarDB 慢查询日志通过管控面 API 获取，不直接执行 SQL。

### PolarDB 与 DAS 边界划分

| 功能 | 本 Skill (PolarDB) | DAS Skill |
|------|---------------------|-----------|
| **慢日志统计查询** | ✅ `DescribeSlowLogRecords` | — |
| **慢 SQL 执行文本** | ✅ 返回统计数据 | — |
| **慢 SQL 诊断分析** | — | ✅ 根因分析、执行计划 |
| **SQL 优化建议** | — | ✅ 自动优化推荐 |
| **锁等待分析** | — | ✅ 死锁诊断 |
| **SQL 自动限流** | — | ✅ 智能限流策略 |

> **Agent 决策规则**：
> - 用户请求 "查询慢 SQL"、"慢日志统计" → **本 Skill**（统计数据获取）
> - 用户请求 "诊断慢 SQL"、"优化 SQL"、"分析 SQL 性能" → **委托 DAS**（深度诊断）

### API 路径

PolarDB 慢查询相关操作：

| 操作 | API | 说明 |
|------|-----|------|
| 查询慢 SQL 统计 | `DescribeSlowLogRecords` | 获取慢 SQL 统计数据（次数、时间） |
| 慢 SQL 详情 | `DescribeSlowLogs` | 完整慢 SQL 文本 |

> **深度诊断需求**（SQL 优化建议、执行计划分析、锁分析）→ 委托至 `alicloud-das-ops` skill

### PolarDB CLI 获取慢查询统计

```bash
# 查询指定时间段的慢 SQL 记录
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId "{{user.db_cluster_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --DBName "{{user.db_name}}" \
  --SortBy "TotalQueryTimes"

# 输出字段
# $.Items.SlowLogRecord[].SQLText      — SQL 文本
# $.Items.SlowLogRecord[].ExecutionTime — 执行时间（秒）
# $.Items.SlowLogRecord[].TotalQueryTimes — 累计执行次数
```

### 深度慢查询分析

对于需要深度慢查询诊断（SQL 优化建议、执行计划分析、锁等待分析），委托至：

> **Delegate to:** `alicloud-das-ops` — 提供 SQL 自动优化、智能诊断能力

---

## Agent 标准工作流

### 场景 1：用户给了一个 `.sql` 文件要在 PolarDB MySQL 集群执行

1. 确认集群状态为 `Running`。
2. `DescribeDBClusterEndpoints` 获取 Primary Endpoint 连接地址。
3. 确认执行机网络连通 + 白名单配置。
4. 扫描 SQL 文件安全等级 → 高危则请求用户确认。
5. 确认 `mysql` 客户端可用。
6. 执行：`mysql -h ... -P ... -u ... -p ... < file.sql`。
7. 检查退出码；失败时抓取 `mysql` stderr。

### 场景 2：用户要执行单条 SQL

1. 确认集群状态。
2. 根据 SQL 类型选择 Endpoint：
   - 写入类 → Primary Endpoint
   - 查询类 → Cluster Endpoint
3. SQL 安全检查 → 高危则请求确认。
4. 执行单条 SQL。
5. 返回执行结果或错误信息。

### 场景 3：用户只读查询大数据

1. 确认集群有只读节点（`DescribeDBNodes` 检查 Role=Reader）。
2. 使用 Cluster Endpoint 或 Custom Endpoint（只读节点）。
3. 查询类 SQL 可直接执行。
4. 建议大数据查询启用 Parallel Query。

### 场景 4：用户问 `aliyun polardb` 能否执行 SQL 文件

直接回答：**不能**。`aliyun polardb` 只管集群；执行 SQL 见本文 Path A。

---

## CLI 覆盖对照（写入记忆，避免幻觉）

| 操作 | `aliyun polardb` | `mysql` 客户端 | DAS 委托 |
|------|:----------------:|:--------------:|:--------:|
| 创建集群/账号/库 | ✅ | ❌ | ❌ |
| 查询慢日志统计 | ✅ `DescribeSlowLogRecords` | ❌ | ✅ |
| 执行单条 SQL | ❌ | ✅ `-e "..."` | ❌ |
| 执行多语句 `.sql` 文件 | ❌ | ✅ `< file.sql` | ❌ |
| SQL 优化建议 | ❌ | ❌ | ✅ `alicloud-das-ops` |
| 需要 RAM + 网络 | AK/SK | 数据库账号密码 | AK/SK |

---

## 参考链接

- [PolarDB MySQL 连接集群](https://help.aliyun.com/zh/polardb/polardb-for-mysql/step-2-connect-to-an-apsaradb-polardb-for-mysql-cluster)
- [DescribeDBClusterEndpoints API](https://help.aliyun.com/document_detail/203584.html)
- [PolarDB 读写分离](https://help.aliyun.com/zh/polardb/polardb-for-mysql/user-guide/cluster-endpoints)
- [DAS 慢 SQL 诊断](https://help.aliyun.com/zh/das/)

---

## 提示词示例 (Prompt Examples)

> 以下提示词示例帮助 AI Agent 理解用户意图并正确执行 SQL 相关操作。

### 场景 1：执行 SQL 文件

**用户提示词：**
```
在 PolarDB 集群 pc-bp123456 里执行 schema.sql 文件，数据库是 mydb，账号是 admin
```

**Agent 解析：**
- 操作类型：ExecuteSQLFile
- 目标集群：pc-bp123456
- 目标数据库：mydb
- 账号：admin
- SQL 文件：schema.sql（用户需提供完整路径或文件内容）

**执行步骤：**
1. 获取 Primary Endpoint 地址
2. 扫描 SQL 文件安全等级
3. 执行 `mysql -h <endpoint> -u admin -p <mydb> < schema.sql`

---

### 场景 2：单条 SQL 查询

**用户提示词：**
```
查询 PolarDB 集群 pc-bp123456 的 orders 表，统计2024年订单总数
```

**Agent 解析：**
- 操作类型：ExecuteSQL（查询）
- 目标集群：pc-bp123456
- SQL 类型：SELECT（安全，可直接执行）
- 推荐 Endpoint：Cluster（利用读写分离）

**执行 SQL：**
```sql
SELECT COUNT(*) AS total_orders 
FROM orders 
WHERE YEAR(order_date) = 2024;
```

---

### 场景 3：单条 SQL 写入

**用户提示词：**
```
在 PolarDB 集群 pc-bp123456 的 users 表插入一条记录：id=100, name='张三'
```

**Agent 解析：**
- 操作类型：ExecuteSQL（写入）
- 目标集群：pc-bp123456
- SQL 类型：INSERT（需确认目标表存在）
- 必须使用：Primary Endpoint

**执行 SQL：**
```sql
INSERT INTO users (id, name) VALUES (100, '张三');
```

---

### 场景 4：危险 SQL 执行

**用户提示词：**
```
删除 PolarDB 集群 pc-bp123456 里 test_db 数据库的 logs_backup 表
```

**Agent 解析：**
- 操作类型：ExecuteSQL（DDL）
- 目标集群：pc-bp123456
- SQL 类型：DROP TABLE（🔴 **高危**）
- 安全检查：**必须用户确认**

**Agent 回复模板：**
```
⚠️ 危险 SQL 检测

即将执行高危操作：
────────────────────────────────────
SQL 类型：DROP TABLE
目标对象：logs_backup（数据库：test_db）
影响范围：永久删除表及所有数据，不可恢复
────────────────────────────────────

请确认是否执行：
[1] 确认执行
[2] 取消操作
[3] 先创建备份再执行

请输入您的选择：
```

---

### 场景 5：慢查询分析

**用户提示词：**
```
分析 PolarDB 集群 pc-bp123456 最近7天的慢查询情况
```

**Agent 解析：**
- 操作类型：DescribeSlowQueryLogs
- 目标集群：pc-bp123456
- 时间范围：最近7天
- 可用 API：`DescribeSlowLogRecords`

**执行命令：**
```bash
# 步骤1：获取慢查询统计概览
aliyun polardb DescribeSlowLogs \
  --DBClusterId pc-bp123456 \
  --StartTime "2024-01-01T00:00Z" \
  --EndTime "2024-01-07T23:59Z"

# 步骤2：获取详细慢查询记录（用于 Top N 分析）
aliyun polardb DescribeSlowLogRecords \
  --DBClusterId pc-bp123456 \
  --StartTime "2024-01-01T00:00Z" \
  --EndTime "2024-01-07T23:59Z" \
  --PageSize 100
```

**深度分析流程：**

对于需要深度慢查询诊断（执行计划分析、索引优化建议、SQL 改写建议），委托至：
> **Delegate to:** `alicloud-das-ops` — 提供 SQL 自动优化、智能诊断能力

本 Skill 提供的**轻量级分析能力**：
1. **Top N 慢查询识别** — 基于 `DescribeSlowLogRecords` 数据统计
2. **慢查询趋势分析** — 对比时间段内的慢查询数量变化
3. **初步索引建议** — 基于 SQL 模式的简单规则建议

**轻量级 vs 深度诊断边界：**

| 能力 | 本 Skill (轻量级) | DAS Skill (深度) |
|------|------------------|------------------|
| 慢日志统计查询 | ✅ DescribeSlowLogs/Records | ✅ 更细粒度分析 |
| Top N 识别 | ✅ 基于频次/时间排序 | ✅ 智能聚类 |
| 趋势分析 | ✅ 时间窗口对比 | ✅ 预测性分析 |
| 执行计划分析 | ❌ | ✅ EXPLAIN 分析 |
| 索引优化建议 | ⚠️ 简单规则建议 | ✅ AI 优化建议 |
| SQL 改写建议 | ❌ | ✅ 自动改写 |
| 锁等待分析 | ❌ | ✅ 死锁诊断 |

---

### 场景 6：大数据只读查询

**用户提示词：**
```
在 PolarDB 集群 pc-bp123456 执行一个大数据分析查询，统计2024年各月销售金额，
数据量很大，请使用只读节点避免影响主库性能
```

**Agent 解析：**
- 操作类型：ExecuteSQL（大数据查询）
- 目标集群：pc-bp123456
- SQL 类型：SELECT（聚合查询）
- Endpoint 选择：Cluster 或 Custom（只读节点）
- 优化建议：启用 Parallel Query

**执行 SQL：**
```sql
SELECT /*+ PARALLEL(4) */
  MONTH(sale_date) AS month,
  SUM(amount) AS total_sales
FROM sales_records
WHERE YEAR(sale_date) = 2024
GROUP BY MONTH(sale_date)
ORDER BY month;
```

---

### 场景 7：获取 Endpoint 信息

**用户提示词：**
```
获取 PolarDB 集群 pc-bp123456 的连接地址，我要用 mysql 客户端连接
```

**Agent 解析：**
- 操作类型：DescribeDBClusterEndpoints
- 目标集群：pc-bp123456
- 用户需求：获取连接地址

**执行命令：**
```bash
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId pc-bp123456
```

**返回信息：**
| Endpoint 类型 | 连接地址 | 用途建议 |
|---------------|----------|----------|
| Primary | `pc-bp123456.mysql.polardb.rds.aliyuncs.com` | 写入操作 |
| Cluster | `pc-bp123456-cluster.mysql.polardb.rds.aliyuncs.com` | 读写分离 |

---

### 场景 8：批量数据导入

**用户提示词：**
```
向 PolarDB 集群 pc-bp123456 的 products 表导入 products.sql 文件，
文件包含5000条 INSERT 语句
```

**Agent 解析：**
- 操作类型：ExecuteSQLFile
- 目标集群：pc-bp123456
- 目标表：products
- 文件内容：批量 INSERT（中危，需确认文件内容）
- 推荐方式：使用 Primary Endpoint + mysql 客户端

**安全检查：**
```
检测到批量写入操作（5000条 INSERT）
请确认：
- 文件来源可信？
- 目标表 products 已存在？
- 是否需要事务包裹（失败时回滚）？
```

---

### Agent 提示词理解规则

当用户发送 SQL 执行相关请求时，Agent 应按以下流程解析：

| 用户关键词 | Agent 理解 | 推荐操作 |
|------------|------------|----------|
| "执行 SQL"、"跑 SQL" | ExecuteSQL 或 ExecuteSQLFile | 确认是单条还是文件 |
| "导入数据"、"导入 SQL" | ExecuteSQLFile | 检查文件安全性 |
| "查询"、"统计" | ExecuteSQL（SELECT） | 使用 Cluster Endpoint |
| "插入"、"更新"、"删除" | ExecuteSQL（写入） | 使用 Primary Endpoint + 安全检查 |
| "慢查询"、"慢 SQL" | DescribeSlowQueryLogs | API 查询慢日志 |
| "连接地址"、"endpoint" | DescribeDBClusterEndpoints | 返回连接信息 |
| "DROP"、"TRUNCATE" | 危险 SQL 检测 | **必须用户确认** |

---

## Reference

- [Slow Query Analysis Workflow](slow-query-analysis.md) — 详细的慢查询分析工作流文档，包含 Top N 识别、趋势分析、索引优化建议