# Prompt Examples — FC Sandbox Sidecar 开发

本文档提供**自然语言提示词示例**，用户可直接复制或修改后发送给 Agent，触发 `alicloud-sandbox-dev` Skill 进行 Sidecar 开发。

> **使用方式:** 将下面任意一条提示词发给 Agent，Skill 会自动识别场景、收集缺失参数、生成代码并返回结果。  
> **变量约定:** `{变量}` 表示需要用户提供的信息，Agent 会在执行前主动询问补充。  
> **说明:** 本 Skill 是 **API/SDK 开发模式**——Agent 生成 Go/Python 源代码文件，而非执行 CLI 运维命令。

---

## 1. 模板管理开发 (Template Management)

### 1.1 创建模板

```
帮我在 Go Sidecar 里实现 CreateTemplate 功能，模板名叫 "python-data-analyzer"，
4 CPU 8G 内存，网络模式 PUBLIC，idle timeout 设为 1800 秒

```

```
实现一个创建模板的 HTTP handler，让用户能传入 templateName、cpu、memory 参数，
调 CreateTemplate API，记得加请求体校验和错误处理

```

```
帮我写一段 Python 代码来调用创建模板的 API，需要设置 networkConfiguration
为 PRIVATE 模式，指定 vpcId=vpc-123 和 securityGroupId=sg-456

```

### 1.2 查询模板

```
在 Sidecar 里加一个 GET /api/sandbox/v1/templates/{templateName} 端点，
转发到 AgentRun 的 GetTemplate API，要加签名

```

```
实现 ListTemplates 功能，支持按 templateType (Browser/CodeInterpreter) 过滤，
还要支持分页参数 pageNumber 和 pageSize

```

```
帮我做一个查询所有模板的 CLI 工具脚本，用 Go 写，输出格式化表格，
包含 templateName、status、cpu、memory 这几列

```

### 1.3 更新和删除

```
实现 PUT /api/sandbox/v1/templates/{templateName} 端点，
转发 UpdateTemplate API，支持 clientToken 幂等头

```

```
加一个删除模板的 handler，DELETE /api/sandbox/v1/templates/{templateName}，
删除前要检查有没有 Sandbox 实例在用它，有的话先报错返回

```

```
UpdateTemplate 和 CreateTemplate 的请求体结构几乎一样，
帮我把 CreateTemplate 的输入结构体复用作 UpdateTemplate 的

```

---

## 2. Sandbox 实例管理开发 (Instance Management)

### 2.1 创建 Sandbox

```
用 Go 实现创建 Sandbox 端点 POST /api/sandbox/v1/sandboxes，
请求体只要传 templateName 就行，sandboxId 让服务器自动生成

```

```
CreateSandbox 返回的 SandboxId 是 ULID 格式的长字符串，
帮我在返回给用户前封装一下，加上模板名称和状态

```

```
Python 实现创建 Sandbox，要验证 templateName 参数必填，
如果模板不存在返回 400 而不是 500

```

### 2.2 查询 Sandbox

```
实现 GET /api/sandbox/v1/sandboxes/{sandboxId} 来获取单个 Sandbox 详情，
转发到 AgentRun 的 GetSandbox API

```

```
帮我做 ListSandboxes 端点，支持按 templateName、status (CREATING/READY/TERMINATED)
过滤，还要支持 nextToken 分页游标

```

```
查询 Sandbox 列表时，帮我把 metadata 里的 fcSessionDetails 解析出来，
提取 sessionId、sessionStatus、functionName 展示给用户

```

### 2.3 状态变更

```
实现 StopSandbox 功能，POST /api/sandbox/v1/sandboxes/{sandboxId}/stop，
要注意这个 API 是幂等的——如果已经 TERMINATED 了直接返回成功

```

```
帮我对 ListSandboxes 做优化，过滤掉已经 TERMINATED 超过 24 小时的旧记录，
只返回 CREATING 和 READY 的

```

### 2.4 删除 Sandbox

```
实现 DeleteSandbox 端点，DELETE /api/sandbox/v1/sandboxes/{sandboxId}，
删除前要先调用 StopSandbox，如果已经是 TERMINATED 状态直接删除

```

```
帮我清理所有 TERMINATED 超过 6 小时的沙箱实例，逐个调用 DeleteSandbox 释放资源

```

---

## 3. 数据面功能开发 (Data Plane)

### 3.1 代码执行

```
实现 POST /api/sandbox/v1/sandboxes/{sandboxId}/execute 来执行代码，
转发到 /contexts/execute，超时设 30 秒

```

```
执行代码时需要先创建上下文（context），然后才能执行。
帮我实现一个先 POST /contexts 创建 python 上下文，再 POST /contexts/execute 执行代码的流程

```

```
帮我封装一个 executeCode(sandboxId, code, language) 函数，
自动处理：创建上下文 → 执行代码 → 返回结果 → 清理上下文

```

### 3.2 文件系统操作

```
实现文件读写功能：
GET /api/sandbox/v1/sandboxes/{sandboxId}/files?path=xxx 读取文件
POST /api/sandbox/v1/sandboxes/{sandboxId}/files 写入文件

```

```
帮我实现批量文件操作：一次请求能读多个文件，
用 Python 的 asyncio.gather 并发请求 AgentRun 的 files API

```

```
上传大文件到沙箱（最大 100MB），实现 multipart/form-data 上传端点，
还要自动创建父目录、设置文件权限为 644

```

### 3.3 终端命令

```
实现同步命令执行 POST /api/sandbox/v1/sandboxes/{sandboxId}/cmd，
转发到 /processes/cmd，返回 exitCode、stdout、stderr

```

```
实现 WebSocket TTY 交互端点 WS /ws/tty/{sandboxId}，
代理到 AgentRun 的 processes/tty WebSocket 端点，支持 JSON 消息格式

```

```
TTY 代理要加心跳机制：客户端每 30 秒发 ping，
服务器 120 秒无心跳则断开连接，帮我实现这个

```

---

## 4. 认证和签名开发 (Auth & Signing)

### 4.1 ACS3-HMAC-SHA256 签名

```
帮我实现 ACS3-HMAC-SHA256 签名函数，
要处理 CanonicalRequest 构建、StringToSign 生成、SigningKey 派生

```

```
签名的时候 header 的排序和值有空格会影响结果，
帮我加一个校验函数，确保签名前的规范化请求和期望一致

```

```
Python 版签名实现中，body hash 计算后如果内容是二进制文件要用 base64 编码，
帮我处理这个边界情况

```

### 4.2 凭据管理

```
实现 CredentialManager，支持 AK/SK 加载和 STS 临时凭据自动轮换，
轮换触发条件设为凭据到期前 5 分钟

```

```
AK/SK 从环境变量读取，帮我加一层 AES-GCM 加密，
Sidecar 启动时解密存内存中，不暴露原始明文

```

---

## 5. Sidecar 核心组件开发

### 5.1 路由和代理

```
实现 RequestRouter，区分控制面和控制面路由：
POST /api/sandbox/v1/templates/* → control plane
POST /api/sandbox/v1/sandboxes/*/execute → data plane

```

```
帮我把 Sidecar 的监听端口从 8080 改为 9090，
同时 Prometheus metrics 端点改为 /metrics/prom

```

```
支持 Unix Domain Socket 模式，Sidecar 监听 unix:///tmp/sandbox.sock，
让 Java 业务侧通过 UDS 调用，跳过 TCP 网络栈

```

### 5.2 弹性机制

```
实现令牌桶速率限制器，控制面 API 限流 50 RPS，
数据面 API 限流 100 RPS，超了返回 429

```

```
加熔断器：如果上游 AgentRun API 连续 5 次 5xx 错误，
熔断 10 秒后尝试半开恢复，帮我实现完整的状态机

```

---

## 6. 可观测性和部署 (Observability & Deployment)

### 6.1 Prometheus 指标

```
帮我加这些 Prometheus 指标：
- sandbox_sidecar_proxy_requests_total (counter, by method/status)
- sandbox_sidecar_proxy_duration_seconds (histogram)
- sandbox_sidecar_websocket_connections (gauge)

```

```
把代理延迟直方图的 bucket 配置调优一下，
关注 0.1s-10s 范围，设为 [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

```

### 6.2 OpenTelemetry 链路

```
集成 OpenTelemetry tracing，给 /api/sandbox/v1/sandboxes 路径下的所有端点
加 trace span，记录 sandboxId、templateName、execution time

```

```
帮我配置 OTLP exporter 发送 trace 到 Jaeger collector (endpoint: jaeger-collector:14250)

```

---

## 7. 完整 Sidecar 项目创建

### 7.1 初始化项目

```
给我一个完整的 Go Sidecar 项目骨架，包括 go.mod、main.go、
handler/、auth/、config/、middleware/ 目录结构，能直接编译运行

```

```
创建 Python Sidecar 项目，用 FastAPI 框架，
需要 requirements.txt、Dockerfile、docker-compose.yml 用于本地调试

```

### 7.2 功能集成

```
做一个最小可用的 Go Sidecar，实现：
1. CreateTemplate + ListTemplates
2. CreateSandbox + GetSandbox
3. 执行代码的 executeCode 函数
不需要 WebSocket TTY 和 MCP

```

```
帮我把 Go Sidecar 里的文件操作扩展一下，
添加 createDirectory、moveFile、deleteFile 功能，
都转发到对应的 data plane API

```

### 7.3 集成到业务

```
帮我写一个 Java 业务侧的 RestClient 代码，
调用 Sidecar 的 /api/sandbox/v1/templates 和 /api/sandbox/v1/sandboxes
要加重试、超时、错误处理

```

```
Sidecar 部署到 FC 自定义容器，帮我写 serverless-devs 的 s.yaml 配置，
环境变量从密钥管理服务注入 CPU 0.5 Core 256MB 内存够用

```

---

## 8. MCP 功能开发 (Advanced)

### 8.1 MCP 服务管理

```
实现 StopTemplateMCP 端点，PATCH /api/sandbox/v1/templates/{templateName}/mcp/stop，
停止 MCP 服务后返回模板更新后的状态

```

```
激活 MCP 服务，PATCH /api/sandbox/v1/templates/{templateName}/mcp/activate，
请求体里启用 run_code、list_contexts、read_file、write_file、process_tty 几个工具

```

```
ActivateTemplateMCP 时支持自定义 enabledTools 列表，
帮我实现一个 UI 让用户选择要启用哪些工具 (health/run_code/exec_cmd/tty等)

```

---

## 使用提示

- 复制任意提示词后发送，Agent 会加载 `alicloud-sandbox-dev` Skill 开始开发
- 包含 `{变量}` 的地方，Agent 会主动向你询问具体信息
- 如需更精确的开发控制，可加上目标语言：`用 Go 实现` 或 `用 Python 实现`
- 开发过程中如需修改已有文件，可直接告诉 Agent 修改哪个模块

## Skill 开发优势

| 优势 | 说明 |
|---|---|
| **AK/SK 隔离** | Java 业务侧无需持有云凭据，Sidecar 集中管理 |
| **签名复杂度屏蔽** | 业务方不用实现 200+ 行 ACS3 签名逻辑 |
| **多语言支持** | 业务侧可用任意语言调用 Sidecar HTTP/gRPC 端点 |
| **凭证轮换透明** | STS 凭据自动刷新，业务侧无感知 |
| **可观测性** | 集中注入 metrics/tracing，业务应用零改造 |
| **弹性保护** | 限流/熔断策略在 Sidecar 层统一控制 |
| **API 版本隔离** | AgentRun API 升级只需改 Sidecar，业务代码不变 |
