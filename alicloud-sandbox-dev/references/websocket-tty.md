# WebSocket TTY 交互实现

> **目的**: 如何为 FC Sandbox Sidecar 实现 WebSocket 交互式终端功能。

## 1. 背景

Sandbox 支持通过 WebSocket 进行交互式终端操作（TTY），允许用户在沙箱内执行交互式 shell 命令、系统管理、调试等。这是 Sidecar 最复杂的通信需求。

### 端点

```
GET {account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/processes/tty?protocol=json&tenantId={accountID}
```

### 连接要求

| 要求 | 值 |
|---|---|
| `Connection` | `Upgrade` |
| `Upgrade` | `websocket` |
| `Sec-WebSocket-Key` | Base64 编码的随机 16 字节 |
| `Sec-WebSocket-Version` | `13` |

## 2. Go 实现

### 2.1 使用 gorilla/websocket

```go
// internal/handler/websocket.go
package handler

import (
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // 生产环境应限制来源
	},
}

// HandleWebSocket 代理 WebSocket TTY 连接
func HandleWebSocket(w http.ResponseWriter, r *http.Request, targetURL, accountID string, logger *zap.Logger) {
	// 1. 验证 tenantId 参数，确保租户隔离
	tenantID := r.URL.Query().Get("tenantId")
	if tenantID == "" || tenantID != accountID {
		logger.Warn("websocket unauthorized: invalid tenantId",
			zap.String("tenantId", tenantID),
			zap.String("expected", accountID))
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	// 2. 升级客户端连接
	clientConn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		logger.Error("websocket upgrade failed", zap.Error(err))
		return
	}
	defer clientConn.Close()

	// 3. 连接到上游 Sandbox WebSocket 端点
	serverConn, _, err := websocket.Dial(targetURL, nil)
	if err != nil {
		logger.Error("upstream websocket connect failed", zap.Error(err))
		clientConn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseInternalServerErr, "connect upstream failed"))
		return
	}
	defer serverConn.Close()

	// 4. 双向代理
	var wg sync.WaitGroup
	wg.Add(2)

	// 客户端 → 上游
	go func() {
		defer wg.Done()
		for {
			msgType, msg, err := clientConn.ReadMessage()
			if err != nil {
				return
			}
			if err := serverConn.WriteMessage(msgType, msg); err != nil {
				return
			}
		}
	}()

	// 上游 → 客户端
	go func() {
		defer wg.Done()
		for {
			msgType, msg, err := serverConn.ReadMessage()
			if err != nil {
				return
			}
			if err := clientConn.WriteMessage(msgType, msg); err != nil {
				return
			}
		}
	}()

	wg.Wait()
}
```

### 2.2 TTY 消息格式（JSON 模式）

业务侧通过 Sidecar 发送/接收的 JSON 消息：

| 消息类型 | 方向 | 字段 | 说明 |
|---|---|---|---|
| `input` | 业务 → Sandbox | `{type: "input", data: "ls -la\n"}` | 发送击键/命令 |
| `output` | Sandbox → 业务 | `{type: "output", data: "total 24...", stream: "stdout"}` | 接收终端输出 |
| `resize` | 业务 → Sandbox | `{type: "resize", rows: 24, cols: 80}` | 调整终端尺寸 |
| `status` | Sandbox → 业务 | `{type: "status", message: "..."}` | 终端状态变更 |
| `ping`/`pong` | 双向 | `{type: "ping"}` / `{type: "pong"}` | 心跳保活 |
| `connectionEstablished` | Sandbox → 业务 | `{type: "connectionEstablished", sessionId: "..."}` | 连接确认 |
| `timeoutWarning` | Sandbox → 业务 | `{type: "timeoutWarning", seconds: 30}` | 超时警告 |
| `connectionClosing` | Sandbox → 业务 | `{type: "connectionClosing"}` | 连接关闭通知 |

### 2.3 心跳保活实现

```go
// 客户端（业务侧）需要每 30 秒发送 ping
go func() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		msg := websocket.FormatCloseMessage(websocket.CloseNormalClosure, "")
		clientConn.WriteControl(websocket.PingMessage, nil, time.Now().Add(10*time.Second))
	}
}()

// 服务器 90 秒无心跳发送警告，120 秒超时关闭
```

## 3. Python 实现

### 3.1 使用 websockets 库

```python
import asyncio
import websockets

async def proxy_websocket(client_websocket, target_url, headers):
    """代理 WebSocket TTY 连接"""
    # 连接上游
    async with websockets.connect(target_url, extra_headers=headers) as server_websocket:
        # 双向代理
        async def client_to_server():
            try:
                async for message in client_websocket:
                    await server_websocket.send(message)
            except websockets.ConnectionClosed:
                pass

        async def server_to_client():
            try:
                async for message in server_websocket:
                    await client_websocket.send(message)
            except websockets.ConnectionClosed:
                pass

        await asyncio.gather(
            client_to_server(),
            server_to_client(),
        )

# FastAPI WebSocket 端点
from fastapi import WebSocket

@app.websocket("/ws/tty/{sandbox_id}")
async def tty_websocket(websocket: WebSocket, sandbox_id: str):
    await websocket.accept()
    
    target = f"wss://{settings.data_endpoint}/sandboxes/{sandbox_id}/processes/tty?protocol=json&tenantId={settings.account_id}"
    
    # 注意：websockets.connect 与 FastAPI WebSocket 不完全兼容
    # 方案：使用 httpx WS 支持或裸 TCP + WebSocket 帧处理
    await proxy_websocket(websocket, target, {"X-Acs-Parent-Id": settings.account_id})
```

### 3.2 FastAPI + httpx-ws 完整实现

```python
# 使用 httpx-ws 库实现完整的 WebSocket 代理
# 安装: pip install httpx-ws
from fastapi import WebSocket, WebSocketDisconnect
import httpx
from httpx_ws import aconnect_ws, WebSocketDisconnect as HttpxWsDisconnect
import asyncio

@app.websocket("/ws/tty/{sandbox_id}")
async def tty_ws(websocket: WebSocket, sandbox_id: str):
    await websocket.accept()
    
    target = f"wss://{settings.data_endpoint}/sandboxes/{sandbox_id}/processes/tty"
    params = {
        "protocol": "json",
        "tenantId": settings.account_id
    }
    headers = {
        "X-Acs-Parent-Id": settings.account_id,
        "Content-Type": "application/json"
    }
    
    try:
        async with aconnect_ws(
            target,
            httpx.AsyncClient(),
            params=params,
            additional_headers=headers
        ) as upstream_ws:
            async def forward_client():
                """客户端 -> 上游"""
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream_ws.send_text(data)
                except WebSocketDisconnect:
                    pass

            async def forward_upstream():
                """上游 -> 客户端"""
                try:
                    while True:
                        data = await upstream_ws.receive_text()
                        await websocket.send_text(data)
                except HttpxWsDisconnect:
                    pass

            # 并发运行两个方向的数据转发
            await asyncio.gather(
                forward_client(),
                forward_upstream(),
            )
    except Exception as e:
        # 清理连接
        try:
            await websocket.close()
        except:
            pass
```

## 4. 心跳保活机制

| 参数 | 值 | 说明 |
|---|---|---|
| 客户端 ping 间隔 | **30 秒** | 必须每 30 秒发一次 ping |
| 服务器超时警告 | **90 秒** | 无心跳 90 秒后发警告 |
| 服务器断开 | **120 秒** | 无心跳 120 秒后强制关闭 |
| 断连后果 | **TTY 进程销毁** | 所有正在运行的命令立即停止 |

### 缓解措施

```bash
# 在上游 TTY 中使用 screen/tmux 创建持久会话
# 即使 WebSocket 断开，屏幕会话仍存活
screen -S sandbox-session
# 重连后: screen -r sandbox-session
```

## 5. 文本模式 vs JSON 模式

| 模式 | 参数 | 说明 | 性能 |
|---|---|---|---|
| **JSON** | `?protocol=json` | 结构化消息，易于调试 | 中 |
| **Text** | `?protocol=text` | 直接终端输出（含 ANSI），xterm.js 兼容 | 高 |

**推荐**: 使用 JSON 模式进行开发和调试，生产环境如果需要低延迟可切换到 text 模式。

## 6. 安全注意事项

1. **WebSocket 连接不经过签名**：WS 握手使用 `Sec-WebSocket-Key` 而非 ACS3 签名
2. **tenantId 参数替代签名**：通过 `tenantId={accountID}` 进行租户识别
3. **敏感命令过滤**：如需限制，可在 Sidecar 中拦截 `input` 消息并过滤危险命令
4. **连接限制**：每个 Sandbox 的 TTY 连接数应有限制，防止资源耗尽
