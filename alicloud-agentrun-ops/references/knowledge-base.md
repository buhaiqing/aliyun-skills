# Knowledge Base — AgentRun Sandbox

> **Purpose**: Consolidated product knowledge for agents — platform positioning, MCP/Skills integration, OSS loading semantics, and operational playbooks.  
> **Sources**: [什么是 AgentRun](https://help.aliyun.com/zh/functioncompute/fc/what-is-agentrun), [动态挂载自定义 Skills](https://help.aliyun.com/zh/functioncompute/fc/dynamically-mount-custom-skills-for-sandboxes), [Sandbox 深休眠](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session), [CreateTemplateInput](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-agentrun-2025-09-10-struct-createtemplateinput), [ActivateTemplateMCP API](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-agentrun-2025-09-10-activatetemplatemcp), [工具市场](https://help.aliyun.com/zh/functioncompute/fc/tool-marketplace), [创建 Skills](https://help.aliyun.com/zh/functioncompute/fc/create-skills).

---

## 1. AgentRun 与 Sandbox 定位

**AgentRun** 是企业级 Agentic AI 的 Serverless 基础设施（开发/部署/运维全生命周期），基于函数计算 FC。

**Sandbox** 是其中的「沙箱即服务」，为 Agent 提供隔离执行环境（代码、浏览器、文件、终端）。

```
AgentRun = Agent 运行时 + Sandbox + 模型治理 + 工具/MCP 生态 + 凭证 + 可观测
```

| 组件 | 职责 |
|------|------|
| AgentRuntime | 智能体运行时（无/低/高代码） |
| **Sandbox** | Code Interpreter / BrowserTool / AIO |
| 模型管理 | 多模型代理、Fallback、限流 |
| 工具管理 | MCP、Function Call、Tool Hub |
| 凭证管理 | API Key、AK/SK 等统一注入 |

**本 Skill 范围**：Sandbox 模板/实例运维、数据面执行、MCP 启停、`enabledTools` 配置；不覆盖 Agent 应用编排或 Tool Hub 安装流程（控制台为主）。

---

## 2. Sandbox 类型速查

| templateType | 名称 | 典型规格（控制台默认） | 主要能力 |
|--------------|------|------------------------|----------|
| `CodeInterpreter` | 代码解释器 | 2C4G | Python/JS 代码、文件、Shell、TTY |
| `Browser` | 浏览器沙箱 | 4C8G | CDP/WebSocket、Puppeteer/Playwright、VNC |
| `AIO` / `AllInOne` | 一体化 | 4C8G | 代码 + 浏览器 + MCP；复合 Agent 首选 |

**硬限制**：单实例最长 **6 小时**；`sandboxIdleTimeoutInSeconds` 为软闲置超时（常见 30min～1h）。

### 2.1 GPU 支持（结论：不支持）

**Sandbox 当前不提供 GPU 运行环境，仅支持 CPU + 内存。**

| 依据 | 说明 |
|------|------|
| 官方规格约束 | [Sandbox 深休眠](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session) 前提：**实例规格仅支持 CPU 实例，不支持 GPU 实例** |
| CreateTemplate API | 仅 `cpu`、`memory`、`diskSize`，无 `gpu` / `gpuMemory` / 加速卡类型字段 |
| 控制台 | Code Interpreter / Browser / AIO 模板资源配置为 CPU+内存（如 2C4G、4C8G） |

**与 AgentRun 其他组件区分**：

| 组件 | GPU |
|------|-----|
| **模型管理 / 模型运行时** | ✅ 支持弹性交付 GPU、FunModel 托管（vLLM 等）— 推理算力在此层 |
| **Sandbox 沙箱** | ❌ CPU 隔离执行环境（代码、浏览器、文件、终端） |
| **FC GPU 函数** | ✅ 函数计算有 GPU 函数能力，但与 **AgentRun Sandbox 模板** 是不同产品线，不能通过 `CreateTemplate` 选 GPU |

**常见需求与替代**：

| 需求 | 建议 |
|------|------|
| Agent 内大模型推理 | 使用 AgentRun **模型代理 / 托管模型**；Sandbox 只做工具与代码执行 |
| 沙箱内 PyTorch/CUDA 本地训练或推理 | **不适用**；考虑 FC GPU 函数、PAI、ECS GPU 等 |
| 沙箱代码需 GPU 算力 | 在 Sandbox 内通过 HTTP 调用外部 GPU 推理 Endpoint |
| 确认是否有路线图/内测 | 公开文档未支持；可向阿里云 **提交工单** 咨询 |

> **Agent 决策一句话**：Sandbox = CPU 沙箱；GPU 在模型运行时或外部服务，不能为 Sandbox 模板「申请 GPU」。

---

## 3. MCP 集成：两条路径（勿混淆）

| 路径 | 启用方式 | MCP 端点 | 暴露内容 |
|------|----------|----------|----------|
| **A. 模板底层 MCP** | `ActivateTemplateMCP` + `enabledTools` | `https://{accountId}.agentrun-data.{region}.aliyuncs.com/templates/{templateName}/mcp` | 沙箱数据面能力（代码/文件/进程） |
| **B. Agent & Skills** | 创建模板时 `enableAgent: true` + 控制台启动 MCP | 同上 | 内置 Agent + 预置 Skills（docx/pdf/浏览器等） |

- 传输协议：`streamable-http`
- MCP 调用时会按 `mcp-session-id` ↔ `sandboxId` 映射，**可自动创建 Sandbox 实例**
- 路径 A 与 B 可叠加：A 管底层 tool，B 管高层 Skill

### 3.1 路径 A：`enabledTools` 完整列表（20 个）

官方 [ActivateTemplateMCP](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-agentrun-2025-09-10-activatetemplatemcp) 枚举：

| Tool | 分组 |
|------|------|
| `health` | 健康 |
| `run_code` | 代码 |
| `list_contexts`, `create_context`, `get_context`, `delete_context` | 上下文 |
| `read_file`, `write_file` | 文件 |
| `file_system_list`, `file_system_stat`, `file_system_download`, `file_system_mkdir`, `file_system_move`, `file_system_remove`, `file_system_upload` | 文件系统 |
| `process_exec_cmd`, `process_tty`, `process_list`, `process_stat`, `process_kill` | 进程 |

> API 响应示例偶现 `execute_code`，以 OpenAPI `enabledTools` 文档为准，推荐使用 `run_code`。

### 3.2 路径 B：内置 Skills（Sandbox Agent & Skills，公测）

| Skill | 适用沙箱 |
|-------|----------|
| `docx`, `pdf`, `pptx`, `xlsx` | 全部 |
| `internal-comms`, `mcp-builder`, `frontend-design`, `filesystem` | 全部 |
| `browseruse-expert` | Browser / AIO |

- 代码解释器：内置 **Coding Agent**
- 浏览器 / AIO：通用 Agent（网页 + 文档 + 文件）

---

## 4. OSS 与 Skill 加载（三层机制）

「自动加载 OSS」在官方文档中指 **新 Sandbox 实例启动时** 完成，**不是** 运行中对 OSS 变更的热感知。

### 4.1 三层分工

| 层级 | 配置 | 作用 | 触发时机 |
|------|------|------|----------|
| **① OSS 挂载（文件系统）** | 模板 `ossConfiguration[]` 或实例 `ossMountConfig` | ossfs 挂到容器路径（如 `/mnt/workspace`） | **实例启动** |
| **② Skill 扫描（语义层）** | `enableAgent: true` + OSS 目录 `skills/` + **环境变量（必配）** + 执行角色 OSS 读权限 + 启动 MCP | Skill Loader 读 `skills/<name>/SKILL.md` | **实例/MCP 就绪时** |
| **③ 仅文件访问** | 仅 ①、无 ② | 可 `ls`/读写挂载目录，Agent **不**自动当 Skill | — |

**调用链（路径 B）**：

```
Agent → MCP Client → MCP Server(Sandbox) → Skill Loader → CLI Engine
```

### 4.2 模板级 OSS 配置（CreateTemplate）

```json
{
  "enableAgent": true,
  "ossConfiguration": [{
    "bucketName": "my-bucket",
    "prefix": "skills",
    "mountPoint": "/mnt/workspace",
    "permission": "READ_ONLY",
    "region": "cn-hangzhou"
  }],
  "executionRoleArn": "acs:ram::...:role/with-oss-read"
}
```

OSS 目录结构：

```
<bucket>/skills/<skill-name>/SKILL.md
                      └── RULES（可选）
```

### 4.3 实例级 OSS 挂载（CreateSandbox）

数据面 `CreateSandbox` 可传 `ossMountConfig`（与模板 `ossConfiguration` 可并存）。详见 [实例级 OSS 挂载](https://help.aliyun.com/zh/functioncompute/fc/sandbox-supports-instance-level-dynamic-mount-of-oss-test-invitation)。

- 实现：ossfs；挂载目录须为 `/home`、`/mnt`、`/data` 子目录
- 同地域最多 **5** 个挂载点；建议内存 ≥ 512MB
- **不同实例间 OSS 视图可能不一致**，勿假定跨实例实时同步

### 4.4 「自动」包含 / 不包含

| ✅ 自动（官方承诺） | ❌ 不包含 |
|---------------------|-----------|
| 新实例启动时挂载 OSS | 运行中实例感知 OSS 新增 Skill |
| 条件满足时 Skill Loader 扫描注册 | 修改 `SKILL.md` 后长活实例自动刷新 |
| 无需把 Skill 打入镜像 | 从工具市场运行时拉取 Skill 到 Sandbox |
| MCP 可按会话创建新实例并重新加载 | 仅重启 MCP、实例未销毁即可靠刷新 Skill 列表 |

### 4.5 OSS 变更后生效 playbook

| 变更 | 是否改模板 OSS 配置 | 如何生效 |
|------|---------------------|----------|
| 同 Bucket、`skills/` 下**新增** Skill | 否 | **新 Sandbox 实例**（Stop/Delete 旧实例，或等闲置超时） |
| 修改已有 `SKILL.md` | 否 | 同上 |
| 换 Bucket / prefix / mountPoint | 是（UpdateTemplate） | 新实例；**运行中实例不继承模板更新** |
| 仅上传 OSS、实例仍在跑 | — | **不会**自动出现在 MCP Skill 列表 |

**推荐发布流程**：`OSS 上传 → 停止/等待旧实例销毁 → 验证新实例 Skill 列表`。

---

## 5. Skill 来源对比（Tool Hub vs OSS vs Agent Runtime）

| 来源 | 安装/配置位置 | Sandbox 内生效方式 | 运行时从 Hub 下载？ |
|------|---------------|-------------------|---------------------|
| **工具市场（Tool Hub）** | 控制台一键安装 →「我的工具」→ 挂到 **Agent** | 经 Agent 编排调用；非 Sandbox 直连市场 API | ❌ |
| **OSS 动态挂载** | 模板 OSS + `enableAgent` + 环境变量 | 实例**启动时** Skill Loader 扫描 | ❌（启动时加载） |
| **控制台创建 Skill** | 工具与 Skills → Markdown/ZIP | Agent 主动加载或 `find_agent_on_skills` | ❌（Agent 侧） |
| **`find_agent_on_skills`** | Agent Runtime 内置 | 用户**明确查询**时搜索账号下 Skill；可「动态安装」到 **Agent** 环境 | ❌ 非 Sandbox MCP 热拉 |

> **「动态挂载」** = 配置化挂载 OSS，替代重做镜像；**≠** OSS 文件变更热更新。

---

## 6. Browser / AIO 端点速查

**CDP（Puppeteer / Playwright）**：

```
wss://{accountId}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/ws/automation?tenantId={accountId}
```

**VNC 实时画面**：`/ws/livestream`  
**AIO 沙箱内本地 CDP**（预装 puppeteer/playwright）：`ws://localhost:5000/ws/automation`

---

## 7. 深休眠与状态

| 状态 | 说明 |
|------|------|
| `CREATING` / `READY` / `TERMINATED` | 常规实例状态 |
| `HIBERNATED` | 深休眠（若启用 Pause/Resume） |

深休眠（完整会话）需白名单 + 自定义容器 + 会话亲和/隔离；暂停期间无 CPU/内存费；Resume 后 WebSocket 等长连接需重建。详见 [core-concepts.md](core-concepts.md) §8。

---

## 8. 官方文档索引

| 主题 | URL |
|------|-----|
| AgentRun 总览 | https://help.aliyun.com/zh/functioncompute/fc/what-is-agentrun |
| 动态挂载自定义 Skills | https://help.aliyun.com/zh/functioncompute/fc/dynamically-mount-custom-skills-for-sandboxes |
| Sandbox Agent & Skills | https://help.aliyun.com/functioncompute/fc/using-sandbox-agent-skills-in-beta |
| 工具市场 | https://help.aliyun.com/zh/functioncompute/fc/tool-marketplace |
| 创建 Skills | https://help.aliyun.com/zh/functioncompute/fc/create-skills |
| ActivateTemplateMCP | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-agentrun-2025-09-10-activatetemplatemcp |
| 实例级 OSS 挂载 | https://help.aliyun.com/zh/functioncompute/fc/sandbox-supports-instance-level-dynamic-mount-of-oss-test-invitation |
| Code Interpreter API | https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter |
| AIO Sandbox | https://help.aliyun.com/zh/functioncompute/fc/aio-sandbox |
| BrowserTool | https://help.aliyun.com/zh/functioncompute/fc/sandbox-browsertool |
| Sandbox 深休眠（含 CPU/GPU 规格说明） | https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session |
| CreateTemplateInput | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-agentrun-2025-09-10-struct-createtemplateinput |

---

## 9. Agent 决策速查

| 用户问题 | 应答要点 |
|----------|----------|
| Sandbox 能申请 GPU 吗？ | **不能**；仅 CPU+内存；推理用模型运行时，算力密集任务用外部 GPU 服务 |
| OSS 加了新 Skill，要不要改配置？ | 路径不变则**不用**；要**新实例** |
| Sandbox 会自动感知 OSS 变化吗？ | **不会**（无热加载文档） |
| MCP 有哪些 tool？ | 路径 A：20 个 `enabledTools`；路径 B：内置 Skills + Agent 工具 |
| 能从 Skill Hub 运行时下载吗？ | **不能**直连；市场装到 Agent，或 OSS 挂载到 Sandbox |
| AIO 和 Code Interpreter 怎么选？ | 仅代码 → CodeInterpreter；爬取+处理 → AIO |
