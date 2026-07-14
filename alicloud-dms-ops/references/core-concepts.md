# DMS Core Concepts

## Architecture

DMS Enterprise is an **AI-powered data security access gateway** providing:

| Capability | Description |
| ------------ | ------------- |
| **Secure Access** | Credential management, intranet-only data access, fine-grained permission control |
| **NL2SQL** | Natural language to SQL conversion for non-technical users |
| **SQL Audit** | Complete SQL execution audit trail for compliance |
| **Multi-Source** | Unified management of 40+ database types |

## Supported Data Sources

### Alibaba Cloud Data Sources

- RDS MySQL, RDS PostgreSQL, RDS MariaDB, RDS SQLServer, PolarDB MySQL
- PolarDB PostgreSQL, ADB MySQL, ADB PostgreSQL, ADB Spark
- Lindorm, TableStore, MaxCompute, EMR, ClickHouse
- AnalyticDB MySQL, AnalyticDB PostgreSQL

### Other Cloud & On-Premise

- MySQL, MariaDB, PostgreSQL, Oracle, SQLServer
- Redis, MongoDB, StarRocks, ClickHouse, SelectDB
- DB2, OceanBase, GaussDB, BigQuery
- Hive, Presto, Trino, Elasticsearch, SAP HANA

## Permission Model (Fine-Grained Permission Control)

| Level | Granularity | Use Case |
| ------- | ------------- | ---------- |
| Instance | Entire instance | DBA-level access |
| Database | Single DB | Schema-level isolation |
| Table | Single table | Team-level access |
| Column | Specific columns | Sensitive data protection |
| Row | Row-level filtering | Data masking / tenant isolation |

## Key DMS Entities

| Entity | Description |
| -------- | ------------- |
| Database | Logical DB registered in DMS (DbId) |
| Owner | User responsible for a database |
| ResourceLocker | SQL task awaiting approval |
| User | DMS user with assigned role |
| Permission | Database-level access grant |
| SensitiveColumn | Column marked as sensitive |
| AuditLog | SQL execution record |

## NL2SQL (Intelligent Query)

DMS NL2SQL engine:

1. Parses natural language question
2. Matches against data table metadata
3. Understands business semantics from knowledge base
4. Generates and executes SQL
5. Returns results in human-readable format

## Limits & Quotas

| Resource | Default Limit | Notes |
| ---------- | -------------- | ------- |
| SQL tasks per user | 100/day | Configurable |
| Concurrent executions | 10 per instance | Per instance |
| Databases per user | 1000 | With ownership |
| Users per enterprise | Unlimited | Role-based |
| Sensitive columns | Unlimited | Per database |

## Resource Relationships

```text
Database → Owner → User → Permission → Database
                    ↓
            SensitiveColumn
                    ↓
               Table → Column
```

## Security Architecture

- **Credential Management**: DB passwords stored in DMS KMS,
  never exposed to users
- **Intranet access**: Data access via DMS agent, data never leaves VPC
- **High-risk SQL Identification**: Rule engine blocks DROP, TRUNCATE,
  DELETE without WHERE,
  etc.
- **Audit trail**: All SQL executions logged with user, time, database, SQL,
  rows affected

## CRUD Classification

| SQL Type | Examples | Approval Required | High-Risk Block |
| ---------- | ---------- | ------------------- | ----------------- |
| Read | `SELECT` | No | No |
| Write | `INSERT`, `UPDATE`, `DELETE` | Yes (CreateResourceLocker) | UPDATE/DELETE without WHERE blocked |
| DDL | `CREATE`, `ALTER`, `DROP` | Yes | `DROP`, `TRUNCATE` blocked by default |
| DCL | `CREATE USER`, `GRANT`, `REVOKE` | Yes + admin whitelist | `CREATE USER`, `DROP USER` blocked by default |
| Procedure | `CALL proc()`, `SELECT fn()` | Depends on rules | May be blocked |

## Database User vs DMS User

| Concept | Managed By | Operations |
| --------- | ----------- | ------------ |
| **DMS User** (logical) | DMS platform | `CreateUser`, `ListUsers` (role: Developer/DBA/Admin) |
| **Database User** (physical) | Target DB | `CREATE USER`, `GRANT`, `REVOKE` via `ExecuteStatement` |

Both layers exist; DMS permissions don't replace DB-level grants. To execute
`CREATE USER` on a target DB via DMS, the connected DB user must have DDL
privilege, and the SQL may need admin whitelist.

## Stored Procedure & Function

- `CALL proc_name(args)` — invokes procedure; OUT/INOUT parameter values may not
  be returned in `ExecuteStatement` response
- `SELECT fn_name(args)` — invokes function; returns scalar value
- Recommended pattern for OUT params: use `SELECT fn()` instead of `CALL proc(?,
  @out)`, or write to temp table and SELECT back
