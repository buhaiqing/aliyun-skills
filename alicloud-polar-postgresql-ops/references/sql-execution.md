# SQL Execution

> PolarDB PostgreSQL SQL 执行能力

## Overview

本文档提供在 PolarDB PostgreSQL 集群上执行 SQL 的完整指南，包括 SQL 语句执行和 SQL 文件执行。

## Prerequisites

```bash
# 1. 确认集群状态
aliyun polardb DescribeDBClusterAttribute \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
# 期望: DBClusterStatus = Running

# 2. 确认账户可用
aliyun polardb DescribeAccounts \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 3. 获取连接信息
aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

## Connection Methods

### 1. 公网访问

```bash
# 获取公网端点
ENDPOINT=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=ConnectionString rows=Items[0].AddressItems[0])

# 连接数据库
psql "host=$ENDPOINT port=5432 dbname={{user.db_name}} user={{user.account_name}} password={{user.account_password}} sslmode=require"
```

### 2. 私网访问 (VPC 内)

```bash
# 获取私网端点
ENDPOINT=$(aliyun polardb DescribeDBClusterEndpoints \
  --DBClusterId "{{user.db_cluster_id}}" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=ConnectionString rows=Items[0].AddressItems[?VPCId!=null].ConnectionString)

# 连接数据库
psql "host=$ENDPOINT port=5432 dbname={{user.db_name}} user={{user.account_name}} password={{user.account_password}}"
```

## Execute SQL

### CLI: aliyun polardb ExecuteSQL

```bash
# 执行单条 SQL
aliyun polardb ExecuteSQL \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DatabaseName "{{user.db_name}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --SQL "SELECT version();" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"

# 执行复杂查询
aliyun polardb ExecuteSQL \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DatabaseName "{{user.db_name}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --SQL "SELECT pid, usename, application_name, client_addr, query_start, state, query FROM pg_stat_activity WHERE state = 'active';" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Execute SQL File

```bash
# 执行 SQL 文件
aliyun polardb ExecuteSQLFile \
  --DBClusterId "{{user.db_cluster_id}}" \
  --DatabaseName "{{user.db_name}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --FilePath "/path/to/script.sql" \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Go SDK: ExecuteSQL

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    polardb "github.com/alibabacloud-go/polardb-20220530/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func executeSQL(client *polardb.Client, clusterId, dbName, account, password, sql string) error {
    request := &polardb.ExecuteSQLRequest{
        DBClusterId:     tea.String(clusterId),
        DatabaseName:    tea.String(dbName),
        AccountName:     tea.String(account),
        AccountPassword: tea.String(password),
        SQL:             tea.String(sql),
    }
    
    response, err := client.ExecuteSQL(request)
    if err != nil {
        return err
    }
    
    fmt.Printf("SQL executed successfully\n")
    fmt.Printf("RequestId: %s\n", tea.StringValue(response.Body.RequestId))
    
    return nil
}

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    client, err := polardb.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // 执行查询
    err = executeSQL(client, 
        os.Getenv("DB_CLUSTER_ID"),
        "postgres",
        os.Getenv("DB_ACCOUNT"),
        os.Getenv("DB_PASSWORD"),
        "SELECT version();",
    )
    if err != nil {
        panic(err)
    }
}
```

## Common SQL Operations

### Database Management

```sql
-- 创建数据库
CREATE DATABASE {{user.db_name}} 
    WITH ENCODING = 'UTF8' 
    LC_COLLATE = 'en_US.UTF-8' 
    LC_CTYPE = 'en_US.UTF-8';

-- 删除数据库
DROP DATABASE IF EXISTS {{user.db_name}};

-- 列出所有数据库
SELECT datname FROM pg_database WHERE datistemplate = false;
```

### User Management

```sql
-- 创建用户
CREATE USER {{user.new_account}} WITH PASSWORD '{{user.password}}';

-- 授权
GRANT ALL PRIVILEGES ON DATABASE {{user.db_name}} TO {{user.new_account}};

-- 查看用户
SELECT usename FROM pg_user;

-- 删除用户
DROP USER IF EXISTS {{user.new_account}};
```

### Table Operations

```sql
-- 创建表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_users_username ON users(username);

-- 查看表结构
\d users

-- 删除表
DROP TABLE IF EXISTS users;
```

### Performance Queries

```sql
-- 查看活跃连接
SELECT pid, usename, application_name, client_addr, 
       query_start, state, query
FROM pg_stat_activity
WHERE state = 'active';

-- 查看空闲连接
SELECT pid, usename, state, state_change
FROM pg_stat_activity
WHERE state = 'idle';

-- 查看表统计
SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC;

-- 查看索引使用情况
SELECT schemaname, tablename, indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### System Queries

```sql
-- 查看数据库版本
SELECT version();

-- 查看当前数据库
SELECT current_database();

-- 查看当前用户
SELECT current_user;

-- 查看配置参数
SHOW max_connections;
SHOW shared_buffers;
SHOW work_mem;

-- 查看锁信息
SELECT * FROM pg_locks WHERE NOT granted;
```

## Safety Controls

### SQL 执行安全检查

```bash
#!/bin/bash
# safe-sql-executor.sh

CLUSTER_ID="{{user.db_cluster_id}}"
DB_NAME="{{user.db_name}}"
ACCOUNT="{{user.account_name}}"
PASSWORD="{{user.account_password}}"
REGION="{{env.ALIBABA_CLOUD_REGION_ID}}"

# 危险操作关键词
DANGEROUS_KEYWORDS=("DROP DATABASE" "DROP TABLE" "DELETE FROM" "TRUNCATE" "ALTER USER")

# 检查 SQL 是否包含危险操作
check_sql_safety() {
    local sql="$1"
    for keyword in "${DANGEROUS_KEYWORDS[@]}"; do
        if echo "$sql" | grep -qi "$keyword"; then
            echo "⚠️  WARNING: SQL contains dangerous keyword: $keyword"
            return 1
        fi
    done
    return 0
}

# 执行 SQL
execute_sql() {
    local sql="$1"
    
    echo "Executing SQL: $sql"
    
    # 安全检查
    if ! check_sql_safety "$sql"; then
        read -p "Do you want to proceed? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Aborted."
            return 1
        fi
    fi
    
    # 执行
    aliyun polardb ExecuteSQL \
      --DBClusterId "$CLUSTER_ID" \
      --DatabaseName "$DB_NAME" \
      --AccountName "$ACCOUNT" \
      --AccountPassword "$PASSWORD" \
      --SQL "$sql" \
      --RegionId "$REGION"
}

# 使用示例
execute_sql "SELECT * FROM users LIMIT 10;"
```

## Error Handling

### Common SQL Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `relation does not exist` | 表不存在 | 检查表名或创建表 |
| `column does not exist` | 列不存在 | 检查列名 |
| `permission denied` | 权限不足 | 检查用户权限 |
| `syntax error` | SQL 语法错误 | 修正 SQL 语法 |
| `connection refused` | 连接失败 | 检查集群状态和白名单 |

## Best Practices

1. **Always use parameterized queries** to prevent SQL injection
2. **Test SQL in non-production first**
3. **Use transactions for multi-statement operations**
4. **Limit result sets with `LIMIT`** for large tables
5. **Add comments** for complex queries
6. **Review execution plan** with `EXPLAIN` before running expensive queries
