# API 参考文档

> **目的**: FC Sandbox 全量 API 端点参考（控制面 + 数据面），包含请求/响应格式、参数说明和错误码。

## 1. 端点概述

| 平面 | Base URL | 说明 |
|---|---|---|
| **控制面** | `https://agentrun.{region}.aliyuncs.com/2025-09-10` | 模板管理、Sandbox 生命周期 |
| **数据面** | `https://{account}.agentrun-data.{region}.aliyuncs.com` | 代码执行、文件操作、TTY |

### 必要请求头

| Header | 说明 | 适用平面 |
|---|---|---|
| `Content-Type: application/json` | 请求体类型 | 两者 |
| `X-Acs-Parent-Id: {主账号ID}` | 租户标识 | 两者 |
| `Authorization: ACS3-HMAC-SHA256 ...` | 签名认证 | 两者 |

---

## 2. 控制面 API

### 2.1 模板管理

#### 创建模板

```
POST https://agentrun.{region}.aliyuncs.com/2025-09-10/templates
```

**请求体**:
```json
{
  "templateName": "my-interpreter",
  "description": "用于数据分析的代码解释器",
  "networkConfiguration": {
    "networkMode": "PUBLIC"
  },
  "cpu": 2,
  "memory": 4096
}
```

**响应**:
```json
{
  "templateId": "tpl-xxx",
  "templateName": "my-interpreter",
  "status": "READY",
  "createdAt": "2024-12-02T10:30:00Z"
}
```

#### 删除模板

```
DELETE https://agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| templateName | string | 是 | 模板名称 |

- **幂等**: 是
- **备注**: 删除前会检查是否有 Sandbox 实例依赖该模板

#### 获取模板

```
GET https://agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| templateName | string | 是 | 模板名称 |

**响应**:
```json
{
  "code": "SUCCESS",
  "requestId": "F8A0F5F3-0C3E-4C82-9D4F-5E4B6A7C8D9E",
  "data": {
    "templateId": "996ffd5e-003f-4700-9f24-9e2a1c19019b.schema",
    "templateName": "my-interpreter",
    "templateVersion": "预留",
    "cpu": 2,
    "memory": 4096,
    "status": "READY",
    "templateType": "Browser",
    "templateArn": "acs:agentrun:cn-hangzhou:12345678:templates/xxx",
    "createdAt": "2026-01-15T17:12:59.375168+08:00",
    "lastUpdatedAt": "2026-01-15T17:12:59.375168+08:00",
    "sandboxIdleTimeoutInSeconds": 1800,
    "networkConfiguration": {
      "networkMode": "PUBLIC"
    },
    "containerConfiguration": {
      "image": "registry.cn-hangzhou.aliyuncs.com/my-namespace/agent-runtime:latest",
      "port": 5000
    },
    "diskSize": 10240,
    "description": "模板描述"
  }
}
```

#### 列出模板

```
GET https://agentrun.{region}.aliyuncs.com/2025-09-10/templates
```

**查询参数**:

| 名称 | 类型 | 必填 | 描述 | 示例值 |
|---|---|---|---|---|
| templateType | string | 否 | 模板类型 | Browser |
| status | string | 否 | 状态过滤 | READY |
| templateName | string | 否 | 模板名称（模糊匹配） | temp-abc |
| pageNumber | integer | 否 | 页码 | 1 |
| pageSize | integer | 否 | 页面大小 | 20 |
| workspaceId | string | 否 | 工作空间 ID | aaa |

**响应**:
```json
{
  "code": "SUCCESS",
  "requestId": "C0595DB0-D1EE-55C3-8DDD-790872C7EC2F",
  "data": {
    "pageNumber": 1,
    "pageSize": 10,
    "total": 10,
    "items": [
      {
        "templateId": "996ffd5e-003f-4700-9f24-9e2a1c19019b.schema",
        "templateName": "my-interpreter",
        "status": "READY",
        "templateType": "Browser",
        "cpu": 2,
        "memory": 4096,
        "createdAt": "2026-01-15T17:12:59Z",
        "lastUpdatedAt": "2026-01-15T17:12:59Z"
      }
    ]
  }
}
```

#### 更新模板

```
PUT https://agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| templateName | string | 是 | 模板名称 |

**请求参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| clientToken | string | 否 | 幂等令牌 |
| body | UpdateTemplateInput | 是 | 更新参数（结构同创建时的 body） |

**备注**: 支持更新资源配置、网络配置、环境变量等字段，不传的字段保持原值。

#### 停止 TemplateMCP 服务

```
PATCH https://agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}/mcp/stop
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| templateName | string | 是 | 模板名称 |

**注意**: 停止后 MCP 资源将被删除，MCP 端点不可访问。

#### 启用 TemplateMCP 服务

```
PATCH https://agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}/mcp/activate
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| templateName | string | 是 | 模板名称 |

**请求体**:
```json
{
  "enabledTools": [
    "health", "run_code", "list_contexts", "create_context",
    "get_context", "delete_context", "read_file", "write_file",
    "file_system_list", "file_system_stat", "file_system_download",
    "file_system_mkdir", "file_system_move", "file_system_remove",
    "file_system_upload", "process_exec_cmd", "process_tty",
    "process_list", "process_stat", "process_kill"
  ],
  "transport": "streamable-http"
}
```

**注意**: 启用后会自动部署 MCP 服务函数，保证 mcp-session-id 和 SandboxID 的唯一映射。

### 2.2 Sandbox 实例管理

#### 创建 Sandbox

```
POST https://agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes
```

**请求体**:
```json
{
  "templateName": "my-interpreter",
  "sandboxId": "custom-id"  // 可选，自动生成 ULID
}
```

**响应**:
```json
{
  "sandboxId": "01JCED8Z9Y6XQVK8M2NRST5WXY",
  "templateId": "tpl-xxx",
  "templateName": "my-interpreter",
  "templateType": "CodeInterpreter",
  "status": "READY",
  "sandboxIdleTimeoutInSeconds": 3600,
  "createdAt": "2024-12-02T10:30:00Z",
  "lastUpdatedAt": "2024-12-02T10:30:15Z",
  "metadata": {
    "fcSessionDetails": {
      "sessionId": "1234567890abcdef",
      "sessionStatus": "Active",
      "sessionIdleTimeoutInSeconds": 3600
    }
  }
}
```

#### 获取 Sandbox

```
GET https://agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}
```

**路径参数**:

| 名称 | 类型 | 必填 | 描述 |
|---|---|---|---|
| sandboxId | string | 是 | 沙箱 ID |

**响应**:
```json
{
  "code": "SUCCESS",
  "requestId": "F8A0F5F3-0C3E-4C82-9D4F-5E4B6A7C8D9E",
  "data": {
    "sandboxId": "01KAWBP6JQD0J3Z34BP4WMX1KG",
    "templateId": "8d409d30-cac1-445a-95d5-476c47780336.schema",
    "templateName": "my-template",
    "status": "READY",
    "createdAt": "2025-11-26T10:54:17.770719+08:00",
    "lastUpdatedAt": "2025-11-26T10:54:17.770719+08:00",
    "sandboxIdleTimeoutSeconds": 1800,
    "endedAt": "2025-11-26T10:54:17.770719+08:00",
    "sandboxArn": "acs:ram::123456:role/aliyunfcdefaultrole",
    "sandboxIdleTTLInSeconds": 0,
    "metadata": {}
  }
}
```

#### 列出 Sandbox

```
GET https://agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes
```

**查询参数**:

| 名称 | 类型 | 必填 | 描述 | 示例值 |
|---|---|---|---|---|
| templateName | string | 否 | 模板名称过滤 | my-template |
| templateType | string | 否 | 模板类型 | TASK |
| status | string | 否 | 状态过滤 | CREATING |
| maxResults | integer | 否 | 每页结果数 | 1000 |
| nextToken | string | 否 | 分页游标（非空表示有更多） | dnLkmea... |

**响应**:
```json
{
  "code": "SUCCESS",
  "requestId": "55D4BE40-2811-5CFB-8482-E0E98D575B1E",
  "data": {
    "nextToken": "",
    "items": [
      {
        "sandboxId": "01KAWBP6JQD0J3Z34BP4WMX1KG",
        "templateId": "8d409d30-cac1-445a-95d5-476c47780336.schema",
        "templateName": "my-template",
        "status": "READY",
        "createdAt": "2025-11-26T10:54:17.770719+08:00",
        "lastUpdatedAt": "2025-11-26T10:54:17.770719+08:00",
        "sandboxIdleTimeoutSeconds": 1800,
        "endedAt": "2025-11-26T10:54:17.770719+08:00",
        "sandboxArn": "acs:ram::123456:role/aliyunfcdefaultrole",
        "sandboxIdleTTLInSeconds": 0,
        "metadata": {}
      }
    ]
  }
}
```

#### 停止 Sandbox

```
POST https://agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}/stop
```

- **幂等**: 是
- **响应**: 与创建相同，但 `status` 为 `TERMINATED`，增加 `endedAt`

#### 删除 Sandbox

```
DELETE https://agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}
```

- **幂等**: 是
- **行为**: 如果 READY → 先 Stop → 再删除
- **响应**: 返回删除前状态

### 2.3 Sandbox 状态

| 状态 | 说明 |
|---|---|
| `CREATING` | 创建中 |
| `READY` | 就绪，可以使用 |
| `TERMINATED` | 已停止 |

---

## 3. 数据面 API

### 3.1 上下文管理

#### 创建上下文

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/contexts
```

**请求体**:
```json
{
  "language": "python",
  "cwd": "/home/user"  // 可选
}
```

**响应**:
```json
{
  "id": "271f70d5-9065-4403-8ea3-4d541f7d2bb8",
  "language": "python",
  "cwd": "/home/user"
}
```

#### 列出上下文

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/contexts
```

**响应**:
```json
[
  {
    "id": "kernel-12345-67890",
    "language": "python",
    "cwd": "/tmp/sandbox/home/user"
  }
]
```

#### 删除上下文

```
DELETE https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/contexts/{contextId}
```

- **响应**: 204 No Content

### 3.2 代码执行

#### 同步执行代码

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/contexts/execute
```

**请求体**:
```json
{
  "contextId": "kernel-12345-67890",  // 可选，不提供则需 language
  "language": "python",               // 可选，未提供 contextId 时需要
  "code": "print('hello')",
  "timeout": 30
}
```

**响应**:
```json
{
  "results": [
    {
      "type": "stdout",
      "text": "hello"
    },
    {
      "type": "result",
      "text": "None"
    },
    {
      "type": "endOfExecution",
      "status": "ok"
    }
  ],
  "contextId": "kernel-12345-67890"
}
```

### 3.3 文件系统

#### 列出目录

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem?path=/home/user&depth=1
```

**响应**:
```json
{
  "path": "/home/user",
  "entries": [
    {
      "name": "example.txt",
      "type": "file",
      "path": "/tmp/code-interpreter-sandbox/home/user/example.txt",
      "size": 1024,
      "mode": 420,
      "permissions": "-rw-r--r--",
      "owner": "user",
      "group": "group",
      "modifiedTime": "2025-11-15T10:30:00Z"
    }
  ]
}
```

#### 读取文件

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/files?path=/workspace/example.txt
```

**响应**:
```json
{
  "name": "example.txt",
  "type": "file",
  "path": "/workspace/example.txt",
  "size": 1024,
  "content": "Hello, World!",
  "encoding": "utf-8"  // 二进制文件为 "base64"
}
```

#### 写入文件

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/files
```

**请求体**:
```json
{
  "path": "example.txt",
  "content": "Hello, World!",
  "encoding": "utf-8"
}
```

**限制**:
- 不支持隐藏文件（`.` 开头）
- 自动创建父目录
- 默认权限 0644

**响应**:
```json
{
  "path": "/home/user/example.txt",
  "size": 25
}
```

#### 下载文件

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem/download?path=/workspace/file.bin
```

**响应**: 文件二进制流

#### 创建目录

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem/mkdir
```

**请求体**:
```json
{
  "path": "/home/user/testDir"
}
```

**幂等**: 如果已存在，返回 200

#### 移动/重命名

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem/move
```

**请求体**:
```json
{
  "source": "/workspace/old.txt",
  "destination": "/workspace/new.txt"
}
```

**幂等**: 是

#### 删除文件/目录

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem/remove
```

**请求体**:
```json
{
  "path": "/home/user/test_dir"
}
```

**幂等**: 是（不存在返回 200）

#### 上传文件

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/filesystem/upload
Content-Type: multipart/form-data
```

**表单字段**:
| 字段 | 说明 |
|---|---|
| `file` | 文件内容（最大 100MB） |
| `path` | 目标路径（可选） |
| `current_path` | 当前目录（可选） |

### 3.4 终端执行

#### 同步执行命令

```
POST https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes/cmd
```

**请求体**:
```json
{
  "command": "ls -la /home/user",
  "cwd": "/tmp/code-interpreter-sandbox/home/user"
}
```

**硬超时**: 30 秒（数据面网关强制）

**响应**:
```json
{
  "executionId": "tty_exec_001",
  "status": "completed",
  "result": {
    "exitCode": 0,
    "stdout": "total 24\ndrwxr-xr-x 3 user user 4096 Jan 15 10:30 .",
    "stderr": "",
    "cwd": "/tmp/sandbox/home/user",
    "executionTimeMs": 150
  },
  "executionTimeMs": 150
}
```

### 3.5 WebSocket TTY

```
GET wss://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes/tty?protocol=json&tenantId={accountID}
```

详见 [websocket-tty.md](websocket-tty.md)。

### 3.6 进程管理

#### 列出进程

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes
```

**响应**:
```json
{
  "items": [
    {
      "processId": 12345,
      "status": "running",
      "command": "python script.py",
      "tag": "my-process",
      "createdAt": "2025-11-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

#### 获取进程详情

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes/{pid}
```

**响应**:
```json
{
  "processId": 12345,
  "status": "running",
  "command": "python script.py",
  "working_dir": "/tmp/sandbox/home/user",
  "environment": {
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp/sandbox/home/user"
  },
  "resourceUsage": {
    "cpuPercent": 10.5,
    "memoryMb": 128.0
  }
}
```

#### 强制停止进程

```
DELETE https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes/{pid}
```

**行为**: SIGTERM → 失败则 SIGKILL

**响应**:
```json
{
  "pid": 12345,
  "stopped": true,
  "stopped_at": "2025-11-15T10:35:00Z",
  "message": "Process stopped successfully"
}
```

### 3.7 健康检查

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/health
```

**响应**:
```json
{
  "status": "ok",
  "service": "sandbox-code-interpreter",
  "version": "v1",
  "timestamp": "2025-11-15T09:45:01.068104+08:00",
  "uptime": 1142269582541
}
```

---

## 4. 错误码

### 4.1 通用错误格式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述信息",
    "details": {}
  }
}
```

### 4.2 状态码与错误处理

| 状态码 | 错误说明 | 处理建议 |
|---|---|---|
| **400** | 请求参数错误 | 检查请求参数格式和必需字段 |
| **401** | 未授权访问 | 检查签名和凭证 |
| **404** | 资源未找到 | 确认资源 ID 和路径正确 |
| **409** | 资源冲突 | 文件已存在或状态冲突 |
| **413** | 文件过大 | 文件超过 100MB 限制 |
| **500** | 内部服务器错误 | 联系技术支持 |
| **507** | 存储间不足 | 清理文件后重试 |

### 4.3 重试策略

| 错误类型 | 策略 |
|---|---|
| **5xx 服务器错误** | 指数退避重试（最大 3 次） |
| **429 限流错误** | 等待后重试 |
| **507 存储空间不足** | 清理后重试 |
| **403 签名错误** | **不重试**，修复签名逻辑 |

---

## 5. API 文档链接汇总

| 类别 | 文档 |
|---|---|
| 控制面 API | [AgentRun OpenAPI Explorer](https://next.api.aliyun.com/api/) > AgentRun > 浏览器沙箱 |
| 数据面 API | [Code Interpreter 文档](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter) |
| 生命周期 | [FC Sandbox](https://help.aliyun.com/zh/functioncompute/fc/sandbox-function) |
| 深休眠（文件系统） | [仅恢复文件系统](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-sleep-file-system-only-recovery) |
| 深休眠（会话） | [暂停与恢复会话](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session) |
| BrowserTool | [Sandbox BrowserTool](https://help.aliyun.com/zh/functioncompute/fc/sandbox-browsertool) |
| AIO Sandbox | [Sandbox AIO](https://help.aliyun.com/zh/functioncompute/fc/aio-sandbox) |
