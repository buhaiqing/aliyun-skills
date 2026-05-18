# FC Sandbox 技能可行性分析与技术方案

> **讨论日期**: 2026-05-18  
> **上下文**: 评估阿里云 Function Compute Sandbox 是否适合开发为新 Skill  
> **文档维护**: 随着技术调研深入持续更新  

---

## 1. Sandbox 生态全景

### 1.1 组件矩阵

| 组件 | 核心能力 | 文档链接 |
|---|---|---|
| **Code Interpreter** | Python/JS 代码执行、文件系统操作、Shell 命令、上下文管理 | [文档](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter) |
| **BrowserTool** | 浏览器自动化沙箱 | [文档](https://help.aliyun.com/zh/functioncompute/fc/sandbox-browsertool) |
| **AIO Sandbox** | 全能型沙箱 | [文档](https://help.aliyun.com/zh/functioncompute/fc/aio-sandbox) |
| **深休眠（文件系统）** | 暂停/恢复会话，仅恢复文件系统 | [文档](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-sleep-file-system-only-recovery) |
| **深休眠（会话）** | 完整暂停与恢复会话 | [文档](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session) |

### 1.2 Code Interpreter 核心能力矩阵

**控制面（资源管理）**：
- 模板创建/管理（`CreateTemplate`、`UpdateTemplate`、`DeleteTemplate`）
- Sandbox 实例生命周期（创建/停止/删除）
- 最长硬生命周期：**固定 6 小时**（不可配置）
- `sandboxIdleTimeoutInSeconds`：**软空闲超时阈值**（可配置，用于在 6 小时内提前回收闲置资源）

**数据面（功能执行）**：
- 🐍 **代码执行**：同步执行 Python/JS，支持上下文隔离
- 📁 **文件系统**：读写/list/move/remove/upload/download，支持最大 100MB 文件
- 🔧 **终端执行**：同步 shell 命令 + WebSocket 交互式 TTY
- 🔄 **进程管理**：列进程/详情查看/强制终止
- ❤️ **健康检查**：`GET /sandboxes/{sandboxId}/health`

### 1.3 标准使用流程

```
1. 创建代码解释器模板（控制面）
   ↓
2. 启动沙箱实例（控制面）
   ↓
3. 创建执行上下文（数据面）
   ↓
4. 执行代码（数据面）
   ↓
5. 文件操作/终端命令（数据面，可选）
   ↓
6. 清理资源（控制面/数据面）
```

---

## 2. Java 容器中的集成方案对比

### 2.1 场景约束

- **运行环境**：Java 应用容器（Spring Boot 微服务）
- **可能无 Python 运行时**
- **AK/SK 安全管理需求**
- **需要与现有 HTTP 客户端共存**（OkHttp / Apache HttpClient / RestTemplate）

### 2.2 方案对比详解

| 维度 | 方案 1：原始 HTTP | 方案 2：通用 SDK | 方案 3：Sidecar |
|---|---|---|---|
| **依赖引入** | 0 额外依赖（只需已有 HTTP 客户端） | `aliyun-java-sdk-core`（2-3 个 jar） | Sidecar 镜像，Java 侧零依赖 |
| **鉴权签名** | 手动实现 ACS3-HMAC-SHA256（~200 行） | SDK 内置 `CredentialProvider` | Sidecar 集中处理 |
| **类型安全** | 无编译期检查 | 编译期 POJO 映射 | 需定义 Client 接口 |
| **重试策略** | 需自行实现（Resilience4j） | SDK 内置重试机制 | Sidecar 统一处理 |
| **WS 支持** | 手动处理握手/帧解析 | SDK 可能支持 | Sidecar 可暴露 gRPC Stream |
| **多语言** | 每种语言重复实现 | 需对应语言 SDK | 业务侧统一 HTTP/gRPC |
| **AK/SK 轮换** | 各 Pod 手动同步 | SDK 自动轮换 | Sidecar 热加载 |
| **新增 Sandbox** | 每语言重新适配 | 等 SDK 更新 | Sidecar 统一适配 |
| **观测性** | 分散埋点 | SDK metrics 有限 | 集中 metrics/tracing |
| **资源开销** | 最小 | 中等（jar 大小） | 中等（额外容器） |
| **适用频率** | 高频场景需封装 | 中高频场景 | 低频也适用 |

---

## 3. 通用 SDK (`aliyun-java-sdk-core`) 集成详解

### 3.1 为什么推荐 CommonRequest 模式？

当阿里云未为某个产品提供专用 SDK 时（AgentRun 当前即如此），`CommonRequest` 是官方推荐的通用调用方式。它的核心价值是：**SDK 自动处理签名、重试、超时，你只需提供 domain/version/action 和参数**。

#### 核心能力

| 能力 | 说明 |
|---|---|
| **自动签名** | SDK 内置 ACS3-HMAC-SHA256 / V1 签名算法，无需手动实现 |
| **凭据管理** | `DefaultProfile` 管理 AK/SK，支持环境变量读取 |
| **自动重试** | 内置指数退避重试策略 |
| **类型安全** | 编译期检查参数，运行时 JSON 解析 |
| **零额外语言** | 纯 Java 实现，无需 Python/Go 运行环境 |

### 3.2 Maven 依赖

```xml
<!-- https://mvnrepository.com/artifact/com.aliyun/aliyun-java-sdk-core -->
<dependency>
    <groupId>com.aliyun</groupId>
    <artifactId>aliyun-java-sdk-core</artifactId>
    <version>4.5.13</version> <!-- 建议使用最新稳定版 -->
</dependency>

<!-- 如果需要自定义 HTTP 客户端（如 OkHttp 替换默认 Apache HttpClient） -->
<dependency>
    <groupId>com.aliyun</groupId>
    <artifactId>aliyun-java-sdk-core</artifactId>
    <version>4.5.13</version>
</dependency>
```

### 3.3 控制面 API 调用示例

```java
import com.aliyun.CommonRequest;
import com.aliyun.CommonResponse;
import com.aliyun.DefaultAcsClient;
import com.aliyun.IAcsClient;
import com.aliyun.exceptions.ClientException;
import com.aliyun.exceptions.ServerException;
import com.aliyun.profile.DefaultProfile;

public class AgentRunControlPlaneDemo {

    // 初始化客户端（建议作为 Spring Bean 单例管理）
    private static IAcsClient initClient() {
        DefaultProfile profile = DefaultProfile.getProfile(
            "cn-hangzhou",
            System.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            System.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"));
        return new DefaultAcsClient(profile);
    }

    /**
     * 创建 Sandbox 模板
     * POST https://agentrun.cn-hangzhou.aliyuncs.com/2025-09-10/templates
     */
    public static String createTemplate(IAcsClient client, String templateName) throws ClientException {
        CommonRequest request = new CommonRequest();
        request.setSysMethod(com.aliyun.http.MethodType.POST);
        request.setSysDomain("agentrun.cn-hangzhou.aliyuncs.com");
        request.setSysVersion("2025-09-10");
        request.setSysAction("CreateTemplate");
        request.putBodyParameter("templateName", templateName);
        request.putBodyParameter("description", "用于数据分析的代码解释器");
        request.putBodyParameter("networkConfiguration.networkMode", "PUBLIC");
        request.putBodyParameter("cpu", "2");
        request.putBodyParameter("memory", "4096");

        try {
            com.aliyun.CommonResponse response = client.getCommonResponse(request);
            // 返回 JSON: {"templateId": "tpl-xxx", ...}
            return response.getData();
        } catch (ServerException e) {
            e.printStackTrace();
            throw e;
        }
    }

    /**
     * 启动 Sandbox 实例
     * POST https://agentrun.cn-hangzhou.aliyuncs.com/2025-09-10/sandboxes
     */
    public static String startSandbox(IAcsClient client, String templateName) throws ClientException {
        CommonRequest request = new CommonRequest();
        request.setSysMethod(com.aliyun.http.MethodType.POST);
        request.setSysDomain("agentrun.cn-hangzhou.aliyuncs.com");
        request.setSysVersion("2025-09-10");
        request.setSysAction("CreateSandbox");
        request.putBodyParameter("templateName", templateName);

        try {
            com.aliyun.CommonResponse response = client.getCommonResponse(request);
            // 返回: {"sandboxId": "01JCED8Z9Y6XQVK8M2NRST5WXY", "status": "READY", ...}
            return response.getData();
        } catch (ServerException e) {
            e.printStackTrace();
        }
    }
}
```

### 3.4 数据面 API 调用示例

数据面 API 使用 RESTful PathPattern，需要设置 `uriPattern`：

```java
/**
 * 数据面：执行代码
 * POST https://{account}.agentrun-data.cn-hangzhou.aliyuncs.com/sandboxes/{sandboxId}/contexts/execute
 */
public static String executeCode(IAcsClient client, String accountId, String sandboxId,
                                  String contextId, String code) throws ClientException {
    CommonRequest request = new CommonRequest();
    request.setSysMethod(com.aliyun.http.MethodType.POST);
    request.setSysDomain(accountId + ".agentrun-data.cn-hangzhou.aliyuncs.com");
    request.setSysVersion("2025-09-10");
    request.setUriPattern("/sandboxes/" + sandboxId + "/contexts/execute");
    
    request.putBodyParameter("contextId", contextId);
    request.putBodyParameter("code", code);
    request.putBodyParameter("timeout", "30");
    request.putBodyParameter("language", "python");

    try {
        com.aliyun.CommonResponse response = client.getCommonResponse(request);
        return response.getData();
    } catch (ServerException e) {
        e.printStackTrace();
    }
}

/**
 * 数据面：健康检查
 * GET /sandboxes/{sandboxId}/health
 */
public static String healthCheck(IAcsClient client, String accountId, String sandboxId) throws ClientException {
    CommonRequest request = new CommonRequest();
    request.setSysMethod(com.aliyun.http.MethodType.GET);
    request.setSysDomain(accountId + ".agentrun-data.cn-hangzhou.aliyuncs.com");
    request.setSysVersion("2025-09-10");
    request.setUriPattern("/sandboxes/" + sandboxId + "/health");

    try {
        com.aliyun.CommonResponse response = client.getCommonResponse(request);
        return response.getData();
        // 预期返回: {"status":"ok","service":"sandbox-code-interpreter",...}
    } catch (ServerException e) {
        e.printStackTrace();
    }
}
```

### 3.5 ⭐ 后台线程同步状态机制设计

这是用户关心的核心——**如何通过后台线程持续监控 Sandbox 实例的生命状态，并在状态变化时通知业务层**。

#### 3.5.1 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                      Java 应用容器                                │
│                                                                 │
│  ┌──────────────────────────────┐                               │
│  │  SandboxStateManager          │  ◄── 后台线程 1               │
│  │  (ScheduledExecutorService)   │  ◄── 后台线程 2               │
│  │                               │  ◄── ...                     │
│  │  - 定时拉取状态 (每 30s)      │                               │
│  │  - 状态缓存 (ConcurrentHashMap)│                              │
│  │  - 状态变更事件发布           │                               │
│  └──────────────┬───────────────┘                               │
│                 │                                               │
│      ╔══════════▼══════════╗                                    │
│      ║  SandboxRegistry     ║  ◄── ConcurrentHashMap<sandboxId, │
│      ║  (状态缓存)           ║       SandboxState>               │
│      ╚══════════╦══════════╝                                    │
│                 │                                               │
│      ╔══════════▼══════════╗                                    │
│      ║  EventPublisher      ║  ◄── Spring ApplicationEvent       │
│      ║  (状态变更通知)       ║     或 CompletableFuture 回调      │
│      ╚══════════╦══════════╝                                    │
│                 │                                               │
│  ┌──────────────▼───────────────┐                               │
│  │  IAcsClient (SDK Client)     │  ◄── 签名/重试由 SDK 自动处理    │
│  │  DefaultAcsClient (单例)     │                                │
│  └──────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.5.2 核心实现代码

```java
import com.aliyun.DefaultAcsClient;
import com.aliyun.CommonRequest;
import com.aliyun.CommonResponse;
import com.aliyun.exceptions.ClientException;
import com.aliyun.exceptions.ServerException;
import org.springframework.stereotype.Service;
import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class SandboxStateManager {

    private final DefaultAcsClient acsClient;
    private final String accountId; // 阿里云主账号 ID
    private final ConcurrentHashMap<String, SandboxState> sandboxRegistry;
    private final ScheduledExecutorService scheduler;
    private final ApplicationEventPublisher eventPublisher;
    
    // 可配置的轮询间隔
    @Value("${sandbox.state.sync.interval:30}")
    private int syncIntervalSeconds;

    public SandboxStateManager(DefaultAcsClient acsClient, 
                                @Value("${sandbox.account-id}") String accountId,
                                ApplicationEventPublisher eventPublisher) {
        this.acsClient = acsClient;
        this.accountId = accountId;
        this.sandboxRegistry = new ConcurrentHashMap<>();
        this.scheduler = Executors.newScheduledThreadPool(
            Runtime.getRuntime().availableProcessors(),
            new ThreadFactoryBuilder().setNameFormat("sandbox-state-sync-%d").build());
        this.eventPublisher = eventPublisher;
    }

    /**
     * Sandbox 状态枚举
     */
    public enum State {
        CREATING, READY, TERMINATED, UNKNOWN
    }

    /**
     * 状态包装类
     */
    @Data
    @AllArgsConstructor
    public static class SandboxState {
        private String sandboxId;
        private String templateName;
        private State currentState;
        private String lastStatus; // 原始 API 返回的状态字符串
        private long lastSyncTimestamp; // 最近同步时间戳
        private long createdAt;
        
        // 状态变更判断
        public boolean isTransitioned(State newState) {
            return this.currentState != newState;
        }
    }

    /**
     * 注册并开始监控一个 Sandbox 实例
     */
    public void startWatching(String sandboxId, String templateName) {
        // 1. 创建初始状态条目
        SandboxState state = new SandboxState(
            sandboxId, templateName, State.CREATING, "CREATING",
            System.currentTimeMillis(), System.currentTimeMillis());
        sandboxRegistry.put(sandboxId, state);

        // 2. 启动定时状态同步任务
        scheduler.scheduleAtFixedRate(
            () -> syncSandboxState(sandboxId),
            0,                    // 初始延迟 0
            syncIntervalSeconds,  // 轮询间隔 (如 30 秒)
            TimeUnit.SECONDS
        );
    }

    /**
     * 核心：定时同步单个 Sandbox 状态
     */
    private void syncSandboxState(String sandboxId) {
        SandboxState currentState = sandboxRegistry.get(sandboxId);
        if (currentState == null) {
            return; // 已被移除
        }

        // 已终止的实例不再轮询
        if (currentState.getCurrentState() == State.TERMINATED) {
            return;
        }

        try {
            // 调用数据面健康检查接口
            String result = healthCheckInternal(accountId, sandboxId);
            
            // 解析状态 (成功代表 READY)
            State newState = State.READY;
            
            // 检查状态是否发生变化
            if (currentState.isTransitioned(newState)) {
                State oldState = currentState.getCurrentState();
                currentState.setCurrentState(newState);
                currentState.setLastSyncTimestamp(System.currentTimeMillis());
                
                // 发布状态变更事件 (Spring Event)
                eventPublisher.publishEvent(
                    new SandboxStateChangedEvent(this, sandboxId, oldState, newState));
            }

        } catch (ServerException e) {
            // 404 = 实例已不存在 → 状态变为 TERMINATED
            if (e.getErrCode().contains("NotFound") || e.getHttpStatus() == 404) {
                handleTermination(sandboxId, "API 404 - 实例不存在");
            } else {
                // 其他错误：不变更状态，记录警告
                log.warn("Sandbox {} 状态同步失败: {}", sandboxId, e.getMessage());
            }
        } catch (ClientException e) {
            log.warn("Sandbox {} SDK 调用异常: {}", sandboxId, e.getMessage());
        } catch (Exception e) {
            log.error("Sandbox {} 同步未知异常", sandboxId, e);
        }
    }

    /**
     * 处理 Sandbox 终止逻辑
     */
    private void handleTermination(String sandboxId, String reason) {
        SandboxState state = sandboxRegistry.get(sandboxId);
        if (state == null) return;
        
        if (state.getCurrentState() != State.TERMINATED) {
            State oldState = state.getCurrentState();
            state.setCurrentState(State.TERMINATED);
            state.setLastStatus(reason);
            state.setLastSyncTimestamp(System.currentTimeMillis());
            
            eventPublisher.publishEvent(
                new SandboxStateChangedEvent(this, sandboxId, oldState, State.TERMINATED));
            
            // 从注册表中移除，停止轮询
            sandboxRegistry.remove(sandboxId);
            log.info("Sandbox {} 已终止并从注册表移除: {}", sandboxId, reason);
        }
    }

    /**
     * Getters
     */
    public SandboxState getSandboxState(String sandboxId) {
        return sandboxRegistry.get(sandboxId);
    }

    public boolean isSandboxReady(String sandboxId) {
        SandboxState state = sandboxRegistry.get(sandboxId);
        return state != null && state.getCurrentState() == State.READY;
    }

    @PreDestroy
    public void shutdown() {
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
        }
    }
}
```

#### 3.5.3 Spring Event 监听器示例

```java
@Component
public class SandboxStateEventListener {

    @EventListener
    public void onSandboxStateChanged(SandboxStateChangedEvent event) {
        log.info("Sandbox 状态变更: {} | {} → {}", 
            event.getSandboxId(), event.getOldState(), event.getNewState());

        switch (event.getNewState()) {
            case READY:
                // Sandbox 就绪 → 更新业务层状态 / 通知前端
                notifyFrontendReady(event.getSandboxId());
                break;
            case TERMINATED:
                // Sandbox 已终止 → 清理相关上下文 / 释放资源
                cleanupSandboxResources(event.getSandboxId());
                break;
        }
    }

    @Async
    public void notifyFrontendReady(String sandboxId) {
        // 通过 WebSocket / SSE 推送给前端
        // ...
    }

    public void cleanupSandboxResources(String sandboxId) {
        // 清理与该 Sandbox 关联的上下文、文件、进程等
        // ...
    }
}

/**
 * 自定义 Spring 事件
 */
@Getter
public class SandboxStateChangedEvent extends ApplicationEvent {
    private final String sandboxId;
    private final State oldState;
    private final State newState;
    private final long timestamp;

    public SandboxStateChangedEvent(Object source, String sandboxId, 
                                     State oldState, State newState) {
        super(source);
        this.sandboxId = sandboxId;
        this.oldState = oldState;
        this.newState = newState;
        this.timestamp = System.currentTimeMillis();
    }
}
```

#### 3.5.4 后台线程同步的最佳实践

| 考量点 | 建议方案 |
|---|---|
| **轮询间隔** | 建议 `30-60 秒`（低频场景）；高频场景可降至 `5-10 秒` |
| **线程数** | `ScheduledThreadPool` 大小 = CPU 核心数即可（非 CPU 密集型）|
| **失败处理** | 不立即移除状态 → 重试 `3 次` → 确认为 `TERMINATED` 后才清理 |
| **内存泄漏** | 已终止实例必须从 `ConcurrentHashMap` 中移除，否则会 OOM |
| **优雅关闭** | `@PreDestroy` 中 shutdown scheduler，避免线程泄漏 |
| **健康检查 vs 控制面 API** | 数据面健康检查更轻量（仅 GET 请求），适合作为轮询源 |
| **状态缓存持久化** | 生产环境建议将状态缓存同步到 Redis，支持跨 Pod 查询 |
| **多实例协调** | 多 Pod 部署时，使用 Redis 锁或分布式调度避免重复轮询 |

#### 3.5.5 生产级状态同步架构（多 Pod + Redis）

```
┌──────────────────┐    ┌──────────────────┐
│  Pod A            │    │  Pod B            │
│  ┌──────────────┐ │    │  ┌──────────────┐ │
│  │ StateSync-1  │ │    │  │ StateSync-2  │ │
│  │ (Leader)     │ │    │  │ (Follower)   │ │
│  └──────┬───────┘ │    │  └──────┬───────┘ │
└─────────┼─────────┘    └─────────┼─────────┘
          │ Redis Lock              │ Redis Lock
          │ (分布式协调)            │ (分布式协调)
          └─────────┬──────────────┘
                    ▼
          ┌───────────────────┐
          │    Redis (K-V)     │
          │  key: sandbox: {id} │
          │  value: {state,    │
          │           ts,      │
          │           pod}     │
          └───────────────────┘
```

**分布式协调伪代码**：

```java
// 使用 Redisson 实现分布式锁
String lockKey = "sandbox:sync:" + sandboxId;
RLock lock = redissonClient.getLock(lockKey);

if (lock.tryLock(10, TimeUnit.SECONDS)) {
    try {
        // 只有获取锁的 Pod 执行状态同步
        syncSandboxState(sandboxId);
    } finally {
        lock.unlock();
    }
}
// 未获取到锁的 Pod 自动跳过
```

---

## 4. 签名鉴权深度分析

### 4.1 为什么原始 HTTP 的签名是最大痛点？

阿里云 ACS3-HMAC-SHA256 签名流程：

```
1. 构建 CanonicalRequest
   ├─ HTTP Method
   ├─ CanonicalURI
   ├─ CanonicalQueryString (排序)
   ├─ CanonicalHeaders (排序 + 小写)
   ├─ SignedHeaders
   └─ HashedPayload (SHA-256)
      ↓
2. 构建 StringToSign
   ├─ Algorithm: "ACS3-HMAC-SHA256"
   ├─ RequestDateTime
   ├─ CredentialScope (Date/Region/Service)
   └─ HashedCanonicalRequest
      ↓
3. 计算 Signature
   └─ HMAC-SHA256(SigningKey, StringToSign)
      ↓
4. 构建 Authorization Header
   └─ "ACS3-HMAC-SHA256 Credential={AccessKeyId}/Scope, SignedHeaders={headers}, Signature={sig}"
```

**关键风险点**：
- 时间戳漂移（服务器时间 vs Pod 时间）
- Body Hash 计算（流式上传时无法预知 body 长度）
- Header 排序规则严格，多/少空格即签名失败
- AK/SK 在内存中明文暴露，需加密存储

### 4.2 签名代码量估算

| 语言 | 签名实现行数 | 是否需第三方库 |
|---|---|---|
| Python | ~150 行 | `hashlib` 内置 |
| Go | ~200 行 | `crypto/hmac` 内置 |
| Java | ~250 行 | 需 `javax.crypto` |

---

## 5. Sidecar 代理模式深度设计

### 5.1 架构概览（完整图）

```
┌────────────────────────────────────────────────────────────────────────┐
│                        K8s Pod / FC Container Pod                      │
│                                                                        │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐  │
│  │  Java 业务容器        │    │  Sidecar 容器 (Go / Python / Rust)   │  │
│  │                      │    │                                      │  │
│  │  ┌────────────────┐  │    │  ┌────────────────────────────────┐ │  │
│  │  │ SandboxClient   │──┼────┼─►│  HTTP/gRPC Listener (localhost)│ │  │
│  │  │ (轻量 Java 封装) │  │    │  │  端口: 8080 / Unix Domain      │ │  │
│  │  └────────────────┘  │    │  └────────────────────────────────┘ │  │
│  │                      │    │                                      │  │
│  │  主业务逻辑           │    │  ┌────────────────────────────────┐ │  │
│  │  - Spring Boot       │    │  │  Auth Manager                   │ │  │
│  │  - AK/SK 无关        │    │  │  ├─ AK/SK 安全存储 (Vault/KMS)  │ │  │
│  │  - 不处理签名        │    │  │  ├─ STS 临时凭证管理            │ │  │
│  │  - 不关心 API 变更   │    │  │  └─ 凭证自动轮换                 │ │  │
│  │                      │    │  └────────────────────────────────┘ │  │
│  │                      │    │                                      │  │
│  │                      │    │  ┌────────────────────────────────┐ │  │
│  │                      │    │  │  Connection Manager             │ │  │
│  │                      │    │  │  ├─ 连接池复用                  │ │  │
│  │                      │    │  │  ├─ 健康检查 & 自动重连         │ │  │
│  │                      │    │  │  └─ 多区域路由                  │ │  │
│  │                      │    │  └────────────────────────────────┘ │  │
│  │                      │    │                                      │  │
│  │                      │    │  ┌────────────────────────────────┐ │  │
│  │                      │    │  │  Protocol Router                │ │  │
│  │                      │    │  │  ├─ Code Interpreter → 路由    │ │  │
│  │                      │    │  │  ├─ BrowserTool → 路由         │ │  │
│  │                      │    │  │  ├─ AIO Sandbox → 路由         │ │  │
│  │                      │    │  │  └─ Deep Hibernation → 路由    │ │  │
│  │                      │    │  └────────────────────────────────┘ │  │
│  │                      │    │                                      │  │
│  │                      │    │  ┌────────────────────────────────┐ │  │
│  │                      │    │  │  Resilience Layer               │ │  │
│  │                      │    │  │  ├─ 令牌桶速率限制              │ │  │
│  │                      │    │  │  ├─ 熔断器 (circuit breaker)    │ │  │
│  │                      │    │  │  └─ 重试策略 (指数退避)         │ │  │
│  │                      │    │  └────────────────────────────────┘ │  │
│  │                      │    │                                      │  │
│  │                      │    │  ┌────────────────────────────────┐ │  │
│  │                      │    │  │  Observability                  │ │  │
│  │                      │    │  │  ├─ Prometheus /metrics        │ │  │
│  │                      │    │  │  ├─ OpenTelemetry tracing       │ │  │
│  │                      │    │  │  └─ 结构化日志                   │ │  │
│  │                      │    │  └────────────────────────────────┘ │  │
│  └──────────────────────┘    └──────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ (HTTPS, 带签名)
                                    ▼
                ┌─────────────────────────────────────────┐
                │  Aliyun AgentRun API                     │
                │  控制面: agentrun.{region}.aliyuncs.com  │
                │  数据面: {account}.agentrun-data....     │
                └─────────────────────────────────────────┘
```

### 5.2 通信协议选型分析

| 协议 | 场景 | 优势 | 劣势 | Java 接入成本 |
|---|---|---|---|---|
| **HTTP/REST** | 控制面、简单调用 | 零学习曲线、调试方便 | JSON 解析开销、无流式 | 极低 |
| **WebSocket** | TTY 交互、长连接 | 全双工、适合终端交互 | 需处理 ping/pong | 低 |
| **gRPC** | 高效调用、多端点 | 强类型、压缩、流式 | 需引入 gRPC-jar | 中 |
| **Unix Domain Socket** | 同主机通信 | 最低延迟、无网络开销 | Java 需 JDK 16+ | 极低 |

**推荐混合方案**：
- **常规 API 调用** → HTTP REST (`http://localhost:8080/api/sandbox/v1/...`)
- **交互式终端** → WebSocket (`ws://localhost:8080/ws/tty/{sandboxId}`)
- **大文件传输** → HTTP Chunked Transfer 或 gRPC Stream

### 5.3 Sidecar 技术实现路径

#### 5.3.1 技术栈选择

| 语言 | 优势 | 劣势 | 适用场景 |
|---|---|---|---|
| **Go** | 静态编译、单二进制、并发强 | 生态不如 Java 丰富 | 推荐作为 Sidecar |
| **Python** | 快速开发、SDK 丰富 | 运行时依赖大、性能较低 | 原型快速验证 |
| **Rust** | 极致性能、安全、零依赖 | 开发成本高 | 极致性能要求时 |

**推荐：Go**
- 单二进制部署（<20MB 镜像）
- 原生并发支持（goroutine）
- `net/http` 库成熟，支持 HTTP/2、WebSocket
- Prometheus 官方 Go Client、OpenTelemetry Go SDK

#### 5.3.2 核心模块设计

```go
// 伪代码架构示意

type SandboxProxy struct {
    auth      *AuthManager      // 鉴权管理
    router    *RequestRouter    // 请求路由
    limiter   *RateLimiter      // 限流器
    breaker   *CircuitBreaker   // 熔断器
    metrics   *PrometheusClient // 观测指标
    logger    *zap.Logger       // 结构化日志
    pool      *ConnectionPool   // 连接池
}

// 鉴权管理器 - 核心职责
type AuthManager struct {
    ak        string           // AccessKey
    sk        string           // SecretKey（内存加密存储）
    token     string           // STS Token（可选）
    region    string           // 区域
    accountID string           // 主账号 ID
    mu        sync.RWMutex     // 并发安全
    ticker    *time.Ticker     // 定期轮换
}

func (a *AuthManager) SignRequest(req *http.Request) error {
    // 1. 构建 CanonicalRequest
    // 2. 计算 StringToSign
    // 3. HMAC-SHA256 签名
    // 4. 设置 Authorization Header
}
```

#### 5.3.3 API 抽象层

Java 侧调用 Sidecar 的接口设计：

```java
// Java 业务侧 - 轻量 Client 接口（不关心签名/区域/认证）
public interface SandboxClient {
    // 模板管理
    Template createTemplate(TemplateSpec spec);
    void deleteTemplate(String templateId);
    
    // Sandbox 实例
    SandboxInstance startSandbox(String templateName);
    void stopSandbox(String sandboxId);
    void deleteSandbox(String sandboxId);
    
    // 代码执行
    ExecutionResult executeCode(String sandboxId, String code, int timeout);
    
    // 文件系统
    FileContent readFile(String sandboxId, String path);
    void writeFile(String sandboxId, String path, String content);
    List<FileSystemEntry> listDirectory(String sandboxId, String path);
    
    // 终端命令
    CommandResult runCommand(String sandboxId, String command);
    
    // TTY 交互（WebSocket）
    TtySession connectTTY(String sandboxId);
}
```

#### 5.3.4 多租户/多区域支持

```yaml
# Sidecar 配置示例
sidecar:
  auth:
    mode: "env"  # env | secret | kms | vault
    regions:
      - name: "cn-hangzhou"
        endpoint: "agentrun.cn-hangzhou.aliyuncs.com"
        dataEndpoint: "{account}.agentrun-data.cn-hangzhou.aliyuncs.com"
    refreshInterval: "5m"
    
  proxy:
    port: 8080
    unixSocket: "/tmp/sandbox-proxy.sock"  # 可选，用于 UDS
    maxConcurrent: 100
    timeout: "30s"
    
  resilience:
    rateLimit:
      enabled: true
      rps: 50  # 每秒最大请求数
    circuitBreaker:
      threshold: 5
      resetTimeout: "10s"
    retry:
      maxAttempts: 3
      backoff: "exponential"
      
  observability:
    metrics:
      enabled: true
      port: 9090  # /metrics 端口
    tracing:
      enabled: true
      endpoint: "otlp-collector:4317"
```

### 5.4 Sidecar 部署模式

| 模式 | 说明 | 优势 | 劣势 | 适用场景 |
|---|---|---|---|---|
| **Pod Sidecar** | 每个 Pod 独立容器 | 资源隔离、独立生命周期 | 每 Pod 额外资源开销 | FC 单实例 |
| **DaemonSet** | 每个 K8s 节点一个实例 | 资源复用、集中管理 | 网络通信成本 | K8s 集群 |
| **Deployment** | 独立服务集群 | 水平扩展、统一监控 | 网络延迟 | 多服务共享 |

**FC 场景下推荐 Pod Sidecar 模式**：
- Function Compute 支持 Sidecar 容器（需确认）
- 每个实例独立签名实例，互不影响
- 资源限额可单独配置 Sidecar

### 5.5 风险与缓解措施

| 风险 | 描述 | 缓解措施 |
|---|---|---|
| **Sidecar 单点故障** | Sidecar 挂掉导致业务无法调用 Sandbox | 实现熔断器，快速失败 |
| **签名缓存不一致** | 多 Sidecar 实例 AK/SK 轮换不同步 | 使用统一 KMS/Vault 源 |
| **性能开销** | 额外网络 hop 延迟 | UDS 通信 + 连接池预热 |
| **资源竞争** | 多 Sidecar 争抢 Sandbox 配额 | Sidecar 间协调限流 |
| **版本升级** | API 变更需更新 Sidecar | 语义化版本 + 向后兼容 |

---

## 6. Skill 设计建议

### 6.1 使用频率评估

- **判断**：非高频场景
- **结论**：定位"按需参考文档"而非"自动化工具链"
- **设计原则**：结构化 API 速查 + 最佳实践指南

### 6.2 Skill 推荐结构

```
aliyun-sandbox/
├── SKILL.md                          # 核心：何时用、流程概览、最佳实践
├── references/
│   ├── signing-guide.md              # 签名鉴权实现指南（多语言）
│   ├── api-code-interpreter.md       # Code Interpreter 全量 API 速查
│   ├── api-browser-tool.md           # BrowserTool 接口文档
│   ├── api-aio-sandbox.md            # AIO Sandbox 接口文档
│   ├── api-deep-hibernation.md       # 深休眠 API
│   └── lifecycle-management.md       # 生命周期管理 & 资源清理
├── examples/
│   ├── java-common-request.java      # Java CommonRequest 调用示例
│   ├── java-raw-http.java            # Java 原始 HTTP + 签名示例
│   └── go-sidecar.go                 # Go Sidecar 骨架示例
└── scripts/
    └── (后续按需添加)
```

### 6.3 Skill 内容要点

- 完整 API 端点列表（控制面 + 数据面）
- 多语言签名实现示例（Java/Go/Python）
- Sidecar 架构设计参考
- 错误处理与重试策略
- 资源管理最佳实践
- 安全注意事项

---

## 7. Sandbox 生命周期详解

### 7.1 核心概念区分

| 概念 | 说明 | 是否可配置 | 文档来源 |
|---|---|---|---|
| **最长硬生命周期** | Sandbox 实例从创建起**最多存活 6 小时**，届时系统强制终止 | ❌ 固定为 6 小时 | [Code Interpreter 文档 > 使用说明](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter) |
| **sandboxIdleTimeoutInSeconds** | 会话进入浅休眠（闲置）状态后，超过此秒数即提前终止 | ✅ 用户可配置，建议 < 21600 | [Code Interpreter 文档 > 使用说明](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter) |

### 7.2 原文引用

> **沙箱模板定义一组沙箱实例的基础配置；沙箱实例则是具体执行代码任务的沙箱环境，一个沙箱实例最长生命周期为 6 小时。此外，通过 `sandboxIdleTimeoutInSeconds` 参数，可以设定一个超时时长。如果会话的浅休眠（原闲置）时间超过该值，它将被提前终止，而无需等待 6 小时的生命周期结束。**
>
> — [阿里云文档：Code Interpreter 代码解释器 > 使用说明](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter)

### 7.3 生命周期状态机

```
┌──────────┐   创建成功    ┌───────┐     idle timeout 到期     ┌────────────┐
│ CREATING  │ ──────────► │ READY │ ────────────────────────► │ TERMINATED │
└──────────┘              └───┬───┘                            └────────────┘
                              │
                    硬生命周期 6 小时到期
                    或主动调用 StopSandbox
                              │
                              ▼
                        ┌────────────┐
                        │ TERMINATED │
                        └────────────┘
```

| 状态 | 说明 |
|---|---|
| `CREATING` | 创建中 |
| `READY` | 就绪，可执行代码/文件操作 |
| `TERMINATED` | 已停止（StopSandbox 或超时触发）|

### 7.4 sandboxIdleTimeoutInSeconds 典型配置

| 场景 | 建议值 | 说明 |
|---|---|---|
| 短期快速分析 | `300`（5 分钟） | 5 分钟不使用即回收 |
| 交互式分析/调试 | `900`（15 分钟） | 适合用户逐步探索数据 |
| 长时间数据处理 | `3600`（1 小时） | 适合复杂 ETL 场景 |
| 最大有效值 | **< 21600**（6 小时） | 超过 6 小时仍会被硬上限截断 |

### 7.5 资源管理最佳实践

1. **必须设置 idle timeout**：防止"僵尸 Sandbox"浪费资源
2. **主动清理**：任务完成后调用 `StopSandbox` + `DeleteSandbox`
3. **监控存储空间**：`507 存储空间不足` 错误 → 清理文件后重试
4. **敏感数据清理**：使用后删除临时文件，避免信息泄露

### 7.6 完整 API 参考文档链接

| 类别 | 文档 | 说明 |
|---|---|---|
| 控制面 API | [AgentRun OpenAPI Explorer](https://next.api.aliyun.com/api/) > AgentRun > 浏览器沙箱 | 模板管理/Sandbox 生命周期 |
| 数据面 API | [Code Interpreter 文档 > 数据面 OpenAPI](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter) | 代码执行/文件系统/TTY/进程管理 |
| 深休眠（文件系统） | [Sandbox 深休眠：仅恢复文件系统](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-sleep-file-system-only-recovery) | 暂停持久化策略 |
| 深休眠（完整会话） | [Sandbox 深休眠：暂停与恢复会话](https://help.aliyun.com/zh/functioncompute/fc/sandbox-deep-hibernation-pause-and-resume-session) | 完整会话挂起/恢复 |
| BrowserTool | [Sandbox BrowserTool](https://help.aliyun.com/zh/functioncompute/fc/sandbox-browsertool) | 浏览器自动化沙箱 |
| AIO Sandbox | [Sandbox AIO](https://help.aliyun.com/zh/functioncompute/fc/aio-sandbox) | 全能沙箱环境 |
