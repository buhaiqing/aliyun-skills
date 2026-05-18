# Core Concepts — AgentRun Sandbox

> **Purpose**: Fundamental architecture, resource types, and operational limits.

## 1. Service Architecture

### 1.1 Two-Plane Design

| Plane | Base URL | Purpose | Authentication |
|---|---|---|---|
| **Control Plane** | `agentrun.{region}.aliyuncs.com/2025-09-10` | Template & Sandbox lifecycle | ACS3-HMAC-SHA256 |
| **Data Plane** | `{account}.agentrun-data.{region}.aliyuncs.com` | Code execution, files, TTY | ACS3-HMAC-SHA256 |

**关键区别**:
- Control Plane: 管理资源 CRUD（模板、沙箱实例）
- Data Plane: 沙箱内操作（执行代码、读写文件、终端交互）

### 1.2 Request Headers (Both Planes)

| Header | Required | Description |
|---|---|---|
| `Content-Type: application/json` | Yes | Request body format |
| `X-Acs-Parent-Id: {主账号ID}` | Yes | Tenant identifier |
| `Authorization: ACS3-HMAC-SHA256 ...` | Yes | Signed authentication |
| `X-Acs-Date: {ISO8601}` | Yes | Request timestamp |
| `X-Acs-Content-Sha256: {hex}` | Yes | Body SHA-256 hash |

---

## 2. Resource Types

### 2.1 Template (模板)

**定义**: 沙箱实例的蓝图，定义资源配置和环境参数。

| Attribute | Type | Description | Constraints |
|---|---|---|---|
| `templateName` | string | Unique identifier | 1-64 chars, alphanumeric/hyphen/underscore |
| `templateId` | string | System-generated ID | UUID format |
| `cpu` | integer | CPU cores | 1-8 |
| `memory` | integer | Memory (MB) | 1024-16384 |
| `diskSize` | integer | Disk size (MB) | 1024-102400 |
| `sandboxIdleTimeoutInSeconds` | integer | Idle timeout | 60-21600 (推荐 < 21600) |
| `networkMode` | string | Network mode | `PUBLIC` \| `PRIVATE` |
| `templateType` | string | Sandbox type | `Browser` \| `CodeInterpreter` \| `AIO` |
| `status` | enum | Template status | `CREATING` \| `READY` \| `DELETING` |

**状态机**:
```
CREATING ──► READY ──► DELETING ──► (deleted)
```

**网络模式**:
- `PUBLIC`: 公网访问，适合简单场景
- `PRIVATE`: VPC 网络隔离，需指定 `vpcId` 和 `securityGroupId`

### 2.2 Sandbox (沙箱实例)

**定义**: 基于 Template 创建的独立执行环境，最长生命周期 6 小时。

| Attribute | Type | Description |
|---|---|---|
| `sandboxId` | string | Instance ID (ULID format, 26 chars) |
| `templateId` | string | Associated template ID |
| `templateName` | string | Template name |
| `status` | enum | `CREATING` \| `READY` \| `TERMINATED` |
| `createdAt` | timestamp | Creation time |
| `endedAt` | timestamp | Termination time (only when TERMINATED) |
| `metadata.fcSessionDetails` | object | FC session info |

**状态机**:
```
CREATING ──► READY ──(idle timeout / 6h hard limit / StopSandbox)──► TERMINATED
```

**生命周期约束**:
| Constraint | Value | Configurable |
|---|---|---|
| Maximum hard lifecycle | **6 hours** | ❌ No |
| Idle timeout | User-defined | ✅ Yes (60-21600 seconds) |

### 2.3 Context (执行上下文)

**定义**: 沙箱内的代码执行环境，支持持久化变量和状态。

| Attribute | Type | Description |
|---|---|---|
| `id` | string | Context ID (UUID) |
| `language` | string | `python` \| `nodejs` \| `go` |
| `cwd` | string | Working directory |

**使用场景**:
- 多次代码执行共享状态
- 保持变量、导入模块、文件系统变更

---

## 3. Sandbox Types

### 3.1 Code Interpreter (代码解释器)

**用途**: 执行 Python/Node.js/Go 代码，处理数据分析、文件操作。

**Capabilities**:
- 代码执行 (同步)
- 文件读写、上传下载
- 终端命令执行
- WebSocket TTY 交互

**典型场景**: AI Agent 代码执行、数据分析、自动化脚本

### 3.2 BrowserTool (浏览器工具)

**用途**: 网页自动化、截图、数据提取。

**Capabilities**:
- 浏览器控制 (Playwright-like)
- 网页截图
- DOM 操作
- 网络请求拦截

**典型场景**: Web scraping, UI testing, 截图生成

### 3.3 AIO Sandbox (All-In-One)

**用途**: 综合沙箱，支持代码执行 + 浏览器 + MCP 服务。

**Capabilities**:
- Code Interpreter 功能
- BrowserTool 功能
- MCP 服务集成

**典型场景**: 复杂 AI Agent 应用、多模态任务

---

## 4. MCP Service Integration

### 4.1 MCP (Model Context Protocol)

**定义**: 为 AI Agent 提供标准化工具接口的服务层。

**Enabled Tools**:
| Tool | Description |
|---|---|
| `health` | 健康检查 |
| `run_code` | 执行代码 |
| `list_contexts` | 列出上下文 |
| `create_context` | 创建上下文 |
| `read_file` | 读取文件 |
| `write_file` | 写入文件 |
| `file_system_*` | 文件系统操作 |
| `process_exec_cmd` | 执行命令 |
| `process_tty` | WebSocket TTY |

### 4.2 MCP Activation

**ActivateTemplateMCP**:
```json
{
  "enabledTools": ["health", "run_code", "read_file", "write_file"],
  "transport": "streamable-http"
}
```

**StopTemplateMCP**: 停止 MCP 服务，删除相关资源

---

## 5. Operational Limits

### 5.1 Resource Limits

| Resource | Limit | Notes |
|---|---|---|
| Sandbox max lifecycle | 6 hours | Hard limit,不可配置 |
| Idle timeout max | 21600 seconds (6h) | 推荐 < 21600 |
| Code execution timeout | 30 seconds | Data plane gateway limit |
| File upload max | 100 MB | Per file |
| Disk size max | 100 GB | Template configurable |

### 5.2 Rate Limits

| API | Rate Limit | Notes |
|---|---|---|
| CreateTemplate | 10/region/account | Per minute |
| CreateSandbox | 50/template | Per minute |
| ExecuteCode | 100/sandbox | Per minute |

### 5.3 Quota Management

**查看配额**: 通过 RAM 控制台或 OpenAPI `GetQuota`

**申请提额**: 提交工单，说明业务场景和预估用量

---

## 6. Security Model

### 6.1 Authentication

**ACS3-HMAC-SHA256 Signing**:
1. Build Canonical Request
2. Generate StringToSign
3. Derive Signing Key (HMAC chain)
4. Calculate Signature
5. Build Authorization Header

详见 [api-signing.md](api-signing.md)

### 6.2 Authorization (RAM)

**Required Permissions**:
| Action | RAM Policy Action |
|---|---|
| CreateTemplate | `fc:CreateTemplate` |
| GetTemplate | `fc:GetTemplate` |
| DeleteTemplate | `fc:DeleteTemplate` |
| CreateSandbox | `fc:CreateSandbox` |
| StopSandbox | `fc:StopSandbox` |
| ExecuteCode | `fc:ExecuteSandboxCode` |

### 6.3 Network Isolation

**PRIVATE Network Mode**:
- 沙箱实例在指定 VPC 内运行
- 需配置 `vpcId` 和 `securityGroupId`
- 适合访问内部服务、数据库

---

## 7. Observability

### 7.1 Logging

**控制面日志**: ActionTrail 记录所有 API 调用

**数据面日志**: Sandbox 内 stdout/stderr 通过 ExecuteCode 返回

### 7.2 Metrics

| Metric | Description | Source |
|---|---|
| `SandboxCount` | Active sandbox count | Control plane |
| `ExecutionTime` | Code execution duration | Data plane |
| `ResourceUsage` | CPU/Memory usage | Health check |

### 7.3 Health Check

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/health
```

**Response**:
```json
{
  "status": "ok",
  "service": "sandbox-code-interpreter",
  "version": "v1",
  "timestamp": "2025-11-15T09:45:01Z",
  "uptime": 1142269582541
}
```

---

## 8. Deep Hibernation (深休眠)

### 8.1 概念

**定义**: 暂停沙箱会话，释放计算资源，保留文件系统状态。

**用途**: 长时间空闲场景，节省成本。

### 8.2 操作

**Pause Session**: 暂停会话，保留文件系统
**Resume Session**: 恢复会话，重新分配计算资源

**文件系统恢复**: 仅恢复文件系统，不恢复执行环境

详见官方文档:
- [仅恢复文件系统](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-sleep-file-system-only-recovery)
- [暂停与恢复会话](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session)

---

## 9. Best Practices

### 9.1 Template Design

1. **资源配额**: 按 CPU/memory 合理配置，避免浪费
2. **Idle Timeout**: 根据业务场景设置，推荐 1800-3600 seconds
3. **Network Mode**: PRIVATE 用于访问内部服务
4. **Template Type**: 根据场景选择 CodeInterpreter/BrowserTool/AIO

### 9.2 Sandbox Management

1. **主动停止**: 任务完成后调用 StopSandbox 释放资源
2. **定期清理**: 清理 TERMINATED 超过 6 小时的沙箱
3. **健康检查**: 执行代码前检查 sandbox health

### 9.3 Error Handling

1. **签名失败**: 不重试，检查签名逻辑
2. **5xx 错误**: 指数退避重试 (max 3)
3. **429 限流**: 等待后重试
4. **507 存储不足**: 清理文件后重试

---

## 10. API Documentation Links

| Category | URL |
|---|---|
| AgentRun Overview | https://help.aliyun.com/zh/functioncompute/fc/sandbox-function |
| Code Interpreter | https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter |
| BrowserTool | https://help.aliyun.com/zh/functioncompute/fc/sandbox-browsertool |
| AIO Sandbox | https://help.aliyun.com/zh/functioncompute/fc/aio-sandbox |
| Deep Hibernation | https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session |
| OpenAPI Explorer | https://next.api.aliyun.com/api/ > AgentRun |