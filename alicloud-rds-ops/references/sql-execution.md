# SQL Execution — RDS MySQL (Agent Runbook)

> **Read this document first** when the user asks to run SQL, execute a `.sql` file,
> import schema/data, or "用阿里云 CLI 在 RDS 里执行 SQL".

## TL;DR (Decision Tree)

```
用户要在 RDS MySQL 实例里执行 SQL（尤其是一个含多条语句的 .sql 文件）
│
├─ 问：能否用 `aliyun rds` 直接执行？
│   └─ ❌ 不能。`aliyun rds` 是管控面 API（建删实例、账号、备份、参数等），不含执行 SQL。
│
├─ 问：能否用 `aliyun rds-data` 直接传入文件路径？
│   └─ ❌ 不能。只有 `--sql` 字符串参数，没有 `--file` / `--sql-file`。
│
├─ 推荐路径（多语句 .sql 文件、DDL+DML 混合、含存储过程）
│   └─ ✅ 标准 `mysql` 客户端 + 实例连接地址（见 §Path A）
│
└─ 可选路径（仅需 OpenAPI、无法直连 3306、单条或可控拆分）
    └─ ⚠️ `aliyun rds-data` + 插件 `aliyun-cli-rds-data`（见 §Path B）
        · 每次调用一条 `--sql`
        · `batch-execute-statement` 面向批量 INSERT/UPDATE 参数集，不是通用 SQL 文件执行器
```

| 需求 | 推荐方式 | CLI 产品 |
|------|----------|----------|
| 执行含多条语句的 `.sql` 文件 | `mysql ... < file.sql` | 非 `aliyun rds` |
| 单条查询/更新（自动化、无 3306 连通） | `aliyun rds-data execute-statement` | `rds-data` + 插件 |
| 批量 INSERT/UPDATE（同模板多组参数） | `aliyun rds-data batch-execute-statement` | `rds-data` + 插件 |
| 管理实例/账号/库（不执行 SQL） | `aliyun rds ...` | `rds` |

**引擎限制：** RDS Data API（`rds-data`）当前文档标明 **仅 MySQL**。PostgreSQL / SQL Server
请使用 `psql`、`sqlcmd` 等对应客户端，连接信息仍可通过 `aliyun rds DescribeDBInstanceNetInfo` 获取。

---

## Path A — `mysql` 客户端执行 SQL 文件（推荐）

适用：`.sql` 含多条语句、DDL+DML、迁移脚本、初始化 schema、用户明确要"跑 SQL 文件"。

### A.1 前置条件（Agent 检查清单）

| # | 检查项 | 如何验证 |
|---|--------|----------|
| 1 | 实例状态为 Running | `aliyun rds DescribeDBInstances --DBInstanceId <id>` → `DBInstanceStatus` |
| 2 | 执行端能访问实例网络 | 同 VPC 用内网地址；本地/跨网用外网地址 + 白名单 |
| 3 | IP 白名单已放行 | `aliyun rds DescribeDBInstanceIPArrayList --DBInstanceId <id>` |
| 4 | 账号与库已存在 | `DescribeAccounts` / `DescribeDatabases`；或脚本内含 `CREATE` |
| 5 | 本机已安装 `mysql` 客户端 | `mysql --version` |

### A.2 用 `aliyun rds` 获取连接信息（管控面，不执行 SQL）

```bash
# 1) 连接地址与端口
aliyun rds DescribeDBInstanceNetInfo \
  --DBInstanceId "{{user.db_instance_id}}"

# 常用 JSON 路径（验证后再写入 runbook）：
#   $.DBInstanceNetInfo.ConnectionString  — 连接域名
#   $.DBInstanceNetInfo.Port              — 端口，MySQL 通常为 3306

# 2) 若无外网地址，需先在控制台或通过 API 申请（AllocateInstancePublicConnection）
# 3) 将执行机 IP 加入白名单（示例：追加一段 CIDR）
aliyun rds ModifySecurityIps \
  --DBInstanceId "{{user.db_instance_id}}" \
  --SecurityIps "10.0.0.0/8,172.16.0.0/12"
```

### A.3 执行 SQL 文件

```bash
# 变量（由用户或上一步 API 提供）
export RDS_HOST="rm-xxxx.mysql.rds.aliyuncs.com"
export RDS_PORT="3306"
export RDS_USER="dbuser"
export RDS_DB="mydb"
export SQL_FILE="./schema.sql"

# 方式 1：标准输入重定向（最常用，支持文件中多条以 ; 结尾的语句）
mysql -h "$RDS_HOST" -P "$RDS_PORT" -u "$RDS_USER" -p"$RDS_PASS" "$RDS_DB" < "$SQL_FILE"

# 方式 2：交互式 source（适合含 DELIMITER 的存储过程脚本）
mysql -h "$RDS_HOST" -P "$RDS_PORT" -u "$RDS_USER" -p"$RDS_PASS" "$RDS_DB" \
  -e "source $SQL_FILE"

# 方式 3：不指定库名（脚本内自行 USE / CREATE DATABASE）
mysql -h "$RDS_HOST" -P "$RDS_PORT" -u "$RDS_USER" -p"$RDS_PASS" < "$SQL_FILE"
```

**安全提示：** 生产环境优先 `-p` 交互输入或从环境变量读取密码，避免在 shell 历史里明文
`--password=xxx`。Agent 不得将用户密码写入日志或提交到版本库。

### A.4 常见失败与处理

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `ERROR 2003 (HY000): Can't connect` | 白名单/网络/VPC | 检查 `ModifySecurityIps`、安全组、是否误用内网地址 |
| `Access denied` | 账号密码或权限 | `DescribeAccounts`；确认对目标库有 DDL/DML 权限 |
| 部分语句成功、后续失败 | 脚本未包事务 | 大变更前备份；考虑 `mysql` 单事务模式或拆分文件 |
| 存储过程报错 | 文件含 `DELIMITER` | 用 `source` 或 `mysql` 交互模式，不要简单按 `;` 拆行 |

---

## Path B — RDS Data API（`aliyun rds-data`）

适用：执行机 **无法直连 3306**，但已开通 Data API；或只需 **单条/少量** SQL 的自动化。
**不适用：** 把任意 `.sql` 文件"一键上传执行"——CLI 无文件参数，且批量接口语义有限。

### B.1 安装插件（必须）

内置 `aliyun rds-data` 在 3.3.x 上 **没有** 可用的 `ExecuteStatement` API 名；
必须安装官方插件（命令为 **kebab-case**，不是 CamelCase）：

```bash
aliyun plugin install --names aliyun-cli-rds-data
aliyun rds-data --help   # 应看到 execute-statement、batch-execute-statement 等
```

| 错误调用 | 正确调用 |
|----------|----------|
| `aliyun rds-data ExecuteStatement` | `aliyun rds-data execute-statement` |
| `aliyun rds-data BatchExecuteStatement` | `aliyun rds-data batch-execute-statement` |

### B.2 开通凭证（管控面 `aliyun rds`）

```bash
# 查询已有 Data API 凭证
aliyun rds DescribeSecrets \
  --RegionId "{{user.region}}" \
  --Engine MySQL \
  --PageNumber 1 \
  --PageSize 20 \
  --DbInstanceId "{{user.db_instance_id}}"

# 若无凭证，创建（需数据库账号密码；仅 MySQL）
aliyun rds CreateSecret \
  --RegionId "{{user.region}}" \
  --DbInstanceId "{{user.db_instance_id}}" \
  --Engine MySQL \
  --Username "{{user.account_name}}" \
  --Password "{{user.account_password}}" \
  --ResourceGroupId "<从 DescribeDBInstanceAttribute 获取>"
```

从 `DescribeSecrets` 响应取 `SecretArn`（格式示例）：

`acs:rds:cn-hangzhou:123456789012:rds-db-credentials/mysecret-123456`

### B.3 构造 ResourceArn

```bash
# 获取主账号 ID（用于拼 ARN）
aliyun sts GetCallerIdentity
# AccountId → 填入下方 {{account_id}}

export RESOURCE_ARN="acs:rds:{{user.region}}:{{account_id}}:dbinstance/{{user.db_instance_id}}"
export SECRET_ARN="<从 DescribeSecrets 的 SecretArn>"
export DATABASE="{{user.db_name}}"
```

### B.4 执行单条 SQL

```bash
aliyun rds-data execute-statement \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database "$DATABASE" \
  --sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"
```

可选：查询结果 JSON 化 `--format-records-as JSON`；超时后继续执行
`--continue-after-timeout true`（见 `execute-statement --help`）。

### B.5 事务（多条 SQL 需要原子性时）

```bash
TXN=$(aliyun rds-data begin-transaction \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database "$DATABASE" \
  --output cols=transactionId rows=transactionId)

aliyun rds-data execute-statement \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database "$DATABASE" \
  --transaction-id "$TXN" \
  --sql "INSERT INTO t (c) VALUES (1)"

aliyun rds-data execute-statement \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database "$DATABASE" \
  --transaction-id "$TXN" \
  --sql "UPDATE t SET c = 2 WHERE c = 1"

aliyun rds-data commit-transaction \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --transaction-id "$TXN"
# 失败时：rollback-transaction
```

### B.6 从 `.sql` 文件执行（Agent 自行拆分，慎用）

CLI **没有** `--sql-file`。若必须用 Data API 跑文件：

1. 读取本地 `schema.sql` 内容；
2. **仅对简单脚本**（无 `DELIMITER`、无复杂字符串转义）按 `;` 拆成多条语句；
3. 对每条非空语句调用 `execute-statement`（或包在 §B.5 事务中）；
4. 任一条失败则停止并 `rollback-transaction`（若已开事务）。

```bash
# 示例：极简拆分（不处理存储过程/字符串内分号——生产脚本请用 Path A）
SQL_FILE="./schema.sql"
while IFS= read -r -d ';' stmt; do
  stmt=$(echo "$stmt" | sed '/^\s*$/d;/^\s*--/d')
  [ -z "$stmt" ] && continue
  aliyun rds-data execute-statement \
    --region "{{user.region}}" \
    --resource-arn "$RESOURCE_ARN" \
    --secret-arn "$SECRET_ARN" \
    --database "$DATABASE" \
    --sql "$stmt" || exit 1
done < <(tr '\n' ' ' < "$SQL_FILE" | sed 's/;/;\n/g')
```

**Agent 规则：** 若文件含 `DELIMITER`、`CREATE PROCEDURE`、事件或复杂转义 → **强制 Path A**，
不要自动拆分。

### B.7 `batch-execute-statement` 的正确用途

```bash
# 同一 INSERT 模板 + 多组参数（非“执行整个 .sql 文件”）
aliyun rds-data batch-execute-statement \
  --region "{{user.region}}" \
  --resource-arn "$RESOURCE_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database "$DATABASE" \
  --sql "INSERT INTO users (id, name) VALUES (:id, :name)" \
  --parameter-sets '[[1,"alice"],[2,"bob"]]'
```

官方说明：该 API **通常用于 INSERT/UPDATE 批量**，不是通用 SQL 脚本运行器。

---

## Path C — DMS / 控制台（补充）

用户仅需一次性导入、无自动化要求时，可引导 [DMS 登录实例](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/step-2-connect-to-an-apsaradb-rds-for-mysql-instance)
执行 SQL 或导入。此路径 **不经过** `aliyun` CLI 执行 SQL。

---

## Agent 标准工作流（复制执行）

### 场景 1：用户给了一个 `.sql` 文件要在 RDS MySQL 执行

1. 确认引擎为 **MySQL**（`DescribeDBInstanceAttribute` → `Engine`）。
2. `DescribeDBInstanceNetInfo` 取 `ConnectionString` + `Port`。
3. 确认执行机网络 + `ModifySecurityIps`（如需）。
4. 确认 `mysql` 客户端可用。
5. 执行：`mysql -h ... -P ... -u ... -p ... < file.sql`（§A.3）。
6. 检查退出码；失败时抓取 `mysql` stderr，勿声称成功。

### 场景 2：用户坚持"只用阿里云 CLI"、且无法直连 3306

1. `aliyun plugin install --names aliyun-cli-rds-data`。
2. `DescribeSecrets` / `CreateSecret` 准备 `secret-arn`。
3. `GetCallerIdentity` + 实例 ID 拼 `resource-arn`。
4. 评估 SQL 文件复杂度 → 简单则 §B.6 拆分 + `execute-statement`；复杂则告知必须用 Path A 或 DMS。
5. 需要原子性 → §B.5 事务包裹。

### 场景 3：用户问 `aliyun rds` 能否执行 SQL 文件

直接回答：**不能**。`aliyun rds` 只管实例；执行 SQL 见本文 Path A/B。

---

## CLI 覆盖对照（写入记忆，避免幻觉）

| 操作 | `aliyun rds` | `aliyun rds-data`（+插件） | `mysql` 客户端 |
|------|:------------:|:--------------------------:|:--------------:|
| 创建实例/账号/库 | ✅ | ❌ | ❌ |
| 查询慢日志/SQL 审计记录 | ✅（已执行过的 SQL） | ❌ | ❌ |
| 执行单条 SQL | ❌ | ✅ `--sql "..."` | ✅ `-e "..."` |
| 执行多语句 `.sql` 文件 | ❌ | ⚠️ 无文件参数，需自行拆分 | ✅ `< file.sql` |
| 批量参数化 INSERT | ❌ | ✅ `batch-execute-statement` | ✅ |
| 需 RAM + 网络 | AK/SK | AK/SK + Data API 凭证 | 数据库账号密码 |

---

## 参考链接

- [RDS 与阿里云 CLI 集成示例](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/alibaba-cloud-cli-integration-example)（管控面）
- [连接 RDS MySQL 实例](https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/step-2-connect-to-an-apsaradb-rds-for-mysql-instance)（`mysql` 客户端）
- [DescribeSecrets - Data API 凭证](https://help.aliyun.com/document_detail/446624.html)
- [RDS Data API OpenAPI](https://api.aliyun.com/api/rds-data/2022-03-30)（ExecuteStatement / BatchExecuteStatement）
