# Go 实现 Sidecar 代理应用

> **目的**: 如何用 Go 实现 FC Sandbox Sidecar 代理应用。本文档提供完整的代码示例和实现指南。

## 1. 项目结构

```
sandbox-sidecar/
├── cmd/
│   └── sidecar/
│       └── main.go              # 入口
├── internal/
│   ├── auth/
│   │   ├── signer.go            # ACS3-HMAC-256 签名
│   │   └── credential.go        # 凭据管理
│   ├── config/
│   │   └── config.go            # 配置加载
│   ├── handler/
│   │   ├── control_plane.go     # 控制面路由
│   │   ├── data_plane.go        # 数据面路由
│   │   └── proxy.go             # 代理核心
│   ├── middleware/
│   │   ├── logging.go           # 日志中间件
│   │   ├── ratelimit.go         # 限流中间件
│   │   └── recovery.go          # 错误恢复中间件
│   ├── model/
│   │   └── types.go             # 数据结构定义
│   └── server/
│       └── server.go            # HTTP 服务器
├── go.mod
├── go.sum
└── config.yaml                  # 配置文件
```

## 2. 初始化项目

```bash
mkdir sandbox-sidecar && cd sandbox-sidecar
go mod init sandbox-sidecar

# 安装依赖
go get go.uber.org/zap
go get gopkg.in/yaml.v3
go get github.com/prometheus/client_golang/prometheus
go get github.com/prometheus/client_golang/prometheus/promhttp
```

**go.mod**:
```go
module sandbox-sidecar

go 1.21

require (
	github.com/prometheus/client_golang v1.19.0
	go.uber.org/zap v1.27.0
	gopkg.in/yaml.v3 v3.0.1
)
```

## 3. 核心实现

### 3.1 配置加载 (`internal/config/config.go`)

```go
package config

import (
	"os"
	"strings"
	"time"
)

// Config Sidecar 应用配置
type Config struct {
	Server   ServerConfig   `yaml:"server"`
	Auth     AuthConfig     `yaml:"auth"`
	Resilience ResilienceConfig `yaml:"resilience"`
}

type ServerConfig struct {
	Port         int           `yaml:"port"`
	ReadTimeout  time.Duration `yaml:"read_timeout"`
	WriteTimeout time.Duration `yaml:"write_timeout"`
}

type AuthConfig struct {
	Region         string `yaml:"region"`
	AccountID      string `yaml:"account_id"`
	AccessKeyID     string `yaml:"-"`
	AccessKeySecret string `yaml:"-"`
	ControlEndpoint string `yaml:"control_endpoint"`
	DataEndpoint   string `yaml:"data_endpoint"`
}

type ResilienceConfig struct {
	RateLimitRPS int `yaml:"rate_limit_rps"`
	MaxRetries   int `yaml:"max_retries"`
}

// Load 从环境变量加载配置（支持未来扩展 YAML 加载）
func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Port:         8080,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
		},
		Auth: AuthConfig{
			Region:         getOr("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"),
			AccountID:      getOr("ALIBABA_CLOUD_ACCOUNT_ID", ""),
			AccessKeyID:     getOr("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
			AccessKeySecret: getOr("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
			ControlEndpoint: "agentrun.{region}.aliyuncs.com",
			DataEndpoint:   "{account}.agentrun-data.{region}.aliyuncs.com",
		},
		Resilience: ResilienceConfig{
			RateLimitRPS: 50,
			MaxRetries:   3,
		},
	}

	// 替换模板变量
	cfg.Auth.ControlEndpoint = replace(cfg.Auth.ControlEndpoint, cfg.Auth)
	cfg.Auth.DataEndpoint = replace(cfg.Auth.DataEndpoint, cfg.Auth)

	return cfg, nil
}

func getOr(env, fallback string) string {
	if v := os.Getenv(env); v != "" {
		return v
	}
	return fallback
}

func replace(template string, auth AuthConfig) string {
	r := template
	r = strings.ReplaceAll(r, "{region}", auth.Region)
	r = strings.ReplaceAll(r, "{account}", auth.AccountID)
	return r
}
```

### 3.2 ACS3-HMAC-256 签名 (`internal/auth/signer.go`)

```go
package auth

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"time"
)

// Signer 阿里云 ACS3-HMAC-SHA256 签名器
type Signer struct {
	accessKeyID     string
	accessKeySecret string
	region          string
	service         string // "agentrun"
}

func NewSigner(ak, sk, region, service string) *Signer {
	return &Signer{
		accessKeyID:     ak,
		accessKeySecret: sk,
		region:          region,
		service:         service,
	}
}

// Sign 对 HTTP 请求进行签名
func (s *Signer) Sign(req *http.Request, body []byte) error {
	now := time.Now().UTC()
	dateTime := now.Format("20060102T150405Z")
	date := now.Format("20060102")

	// 1. 计算 Body Hash
	bodyHash := sha256.Sum256(body)
	bodyHashHex := hex.EncodeToString(bodyHash[:])

	// 2. 构建 CanonicalRequest
	canonicalURI := req.URL.Path
	canonicalQueryString := req.URL.Query().Encode()
	if canonicalQueryString == "" {
		canonicalQueryString = ""
	}

	headers := map[string]string{
		"host":            req.Host,
		"content-type":    req.Header.Get("Content-Type"),
		"x-acs-content-sha256": bodyHashHex,
		"x-acs-date":      dateTime,
	}

	// 排序 header keys
	var keys []string
	for k := range headers {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var canonicalHeaders strings.Builder
	var signedHeaders strings.Builder
	for i, k := range keys {
		canonicalHeaders.WriteString(k + ":" + strings.TrimSpace(headers[k]) + "\n")
		if i > 0 {
			signedHeaders.WriteString(";")
		}
		signedHeaders.WriteString(k)
	}

	httpMethod := req.Method
	canonicalRequest := fmt.Sprintf("%s\n%s\n%s\n%s\n%s\n%s",
		httpMethod,
		canonicalURI,
		canonicalQueryString,
		canonicalHeaders.String(),
		signedHeaders.String(),
		bodyHashHex,
	)

	// 3. 计算 CanonicalRequest Hash
	crHash := sha256.Sum256([]byte(canonicalRequest))
	crHashHex := hex.EncodeToString(crHash[:])

	// 4. 构建 StringToSign
	credentialScope := fmt.Sprintf("%s/%s/%s/aliyun_v4_request",
		date, s.region, s.service)
	stringToSign := fmt.Sprintf("ACS3-HMAC-SHA256\n%s\n%s\n%s",
		dateTime, credentialScope, crHashHex)

	// 5. 计算签名
	signingKey := s.deriveSigningKey(s.accessKeySecret, date, s.region, s.service)
	signature := hmacSHA256(signingKey, stringToSign)
	signatureHex := hex.EncodeToString(signature)

	// 6. 构建 Authorization Header
	authorization := fmt.Sprintf(
		"ACS3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s",
		s.accessKeyID, credentialScope, signedHeaders.String(), signatureHex,
	)

	req.Header.Set("Authorization", authorization)
	req.Header.Set("X-Acs-Date", dateTime)
	req.Header.Set("X-Acs-Content-Sha256", bodyHashHex)

	// 重新设置 Body（因为可能已经被读取过）
	req.Body = io.NopCloser(bytes.NewBuffer(body))

	return nil
}

// deriveSigningKey 派生签名密钥
func (s *Signer) deriveSigningKey(secret, date, region, service string) []byte {
	kSecret := []byte("ACS3" + secret)
	kDate := hmacSHA256(kSecret, date)
	kRegion := hmacSHA256(kDate, region)
	kService := hmacSHA256(kRegion, service)
	return hmacSHA256(kService, "aliyun_v4_request")
}

func hmacSHA256(key []byte, data string) []byte {
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(data))
	return mac.Sum(nil)
}
```

### 3.3 凭据管理 (`internal/auth/credential.go`)

```go
package auth

import (
	"sync"
	"time"
)

// CredentialManager 凭据管理器（支持 AK/SK 和 STS）
type CredentialManager struct {
	mu            sync.RWMutex
	accessKeyID    string
	accessKeySecret string
	stsToken       string // 可选 STS Token
	expireAt       time.Time
}

func NewCredentialManager(ak, sk string) *CredentialManager {
	return &CredentialManager{
		accessKeyID:    ak,
		accessKeySecret: sk,
	}
}

// GetCredentials 获取当前凭据
func (cm *CredentialManager) GetCredentials() (ak, sk, token string) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.accessKeyID, cm.accessKeySecret, cm.stsToken
}

// UpdateSTS 更新 STS 临时凭据
func (cm *CredentialManager) UpdateSTS(ak, sk, token string, ttl time.Duration) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.accessKeyID = ak
	cm.accessKeySecret = sk
	cm.stsToken = token
	cm.expireAt = time.Now().Add(ttl)
}

// ShouldRotate 是否应该轮换凭据
func (cm *CredentialManager) ShouldRotate() bool {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	if cm.expireAt.IsZero() {
		return false // 固定 AK/SK，无需轮换
	}
	return time.Now().Add(5 * time.Minute).After(cm.expireAt)
}
```

### 3.4 HTTP 服务器与路由 (`internal/server/server.go`)

```go
package server

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"sandbox-sidecar/internal/auth"
	"sandbox-sidecar/internal/config"
	"sandbox-sidecar/internal/handler"
	"sandbox-sidecar/internal/model"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// Server HTTP 服务器
type Server struct {
	cfg    *config.Config
	logger *zap.Logger
	signer *auth.Signer
	router *http.ServeMux
	srv    *http.Server
}

func New(cfg *config.Config, logger *zap.Logger) *Server {
	signer := auth.NewSigner(
		cfg.Auth.AccessKeyID,
		cfg.Auth.AccessKeySecret,
		cfg.Auth.Region,
		"agentrun",
	)

	s := &Server{
		cfg:    cfg,
		logger: logger,
		signer: signer,
		router: http.NewServeMux(),
	}

	s.setupRoutes()
	return s
}

func (s *Server) setupRoutes() {
	// API 路由组 - 简化抽象层
	// 业务侧调用这些端点，Sidecar 自动处理签名和路由

	// ===== 模板管理 =====
	s.router.HandleFunc("POST /api/sandbox/v1/templates",
		s.controlPlaneHandler("CreateTemplate", "POST", "/2025-09-10/templates"))
	s.router.HandleFunc("DELETE /api/sandbox/v1/templates/{id}",
		s.controlPlaneHandler("DeleteTemplate", "DELETE", "/2025-09-10/templates"))

	// ===== Sandbox 实例管理 =====
	s.router.HandleFunc("POST /api/sandbox/v1/sandboxes",
		s.controlPlaneHandler("CreateSandbox", "POST", "/2025-09-10/sandboxes"))
	s.router.HandleFunc("POST /api/sandbox/v1/sandboxes/{id}/stop",
		s.controlPlaneHandler("StopSandbox", "POST", "/2025-09-10/sandboxes"))
	s.router.HandleFunc("DELETE /api/sandbox/v1/sandboxes/{id}",
		s.controlPlaneHandler("DeleteSandbox", "DELETE", "/2025-09-10/sandboxes"))

	// ===== 数据面 =====
	s.router.HandleFunc("POST /api/sandbox/v1/sandboxes/{id}/execute",
		s.dataPlaneHandler())
	s.router.HandleFunc("GET /api/sandbox/v1/sandboxes/{id}/health",
		s.dataPlaneHandler())
	s.router.HandleFunc("GET /api/sandbox/v1/sandboxes/{id}/files",
		s.dataPlaneHandler())
	s.router.HandleFunc("POST /api/sandbox/v1/sandboxes/{id}/files",
		s.dataPlaneHandler())
	s.router.HandleFunc("GET /api/sandbox/v1/sandboxes/{id}/filesystem",
		s.dataPlaneHandler())

	// ===== 健康与观测 =====
	s.router.HandleFunc("/healthz", s.healthzHandler())
	s.router.Handle("/metrics", promhttp.Handler())
}

// controlPlaneHandler 控制面请求代理
func (s *Server) controlPlaneHandler(action, method, path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()

		// 构建控制面请求
		endpoint := s.cfg.Auth.ControlEndpoint
		targetURL := "https://" + endpoint + path

		// 替换路径参数
		targetURL = handler.ReplacePathParams(targetURL, r, path)

		req, err := http.NewRequestWithContext(ctx, method, targetURL, r.Body)
		if err != nil {
			s.jsonError(w, http.StatusInternalServerError, err.Error())
			return
		}

		// 设置必要的头
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Acs-Parent-Id", s.cfg.Auth.AccountID)

		// 读取 Body 用于签名
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			s.jsonError(w, http.StatusBadRequest, "failed to read request body: "+err.Error())
			return
		}
		if len(bodyBytes) > 0 {
			req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		}

		// 签名
		if err := s.signer.Sign(req, bodyBytes); err != nil {
			s.jsonError(w, http.StatusInternalServerError, "sign error: "+err.Error())
			return
		}

		// 发送请求
		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			s.jsonError(w, http.StatusBadGateway, err.Error())
			return
		}
		defer resp.Body.Close()

		// 转发响应
		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

// dataPlaneHandler 数据面请求代理
func (s *Server) dataPlaneHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()

		// 构建数据面 URL
		endpoint := s.cfg.Auth.DataEndpoint
		route := r.URL.Path                        // /api/sandbox/v1/sandboxes/{id}/xxx
		route = strings.TrimPrefix(route, "/api/sandbox/v1") // /sandboxes/{id}/xxx
		targetURL := "https://" + endpoint + route

		// 处理 WebSocket 升级
		if strings.HasPrefix(r.Header.Get("Upgrade"), "websocket") {
			handler.HandleWebSocket(w, r, targetURL, s.cfg.Auth.AccountID)
			return
		}

		req, err := http.NewRequestWithContext(ctx, r.Method, targetURL, r.Body)
		if err != nil {
			s.jsonError(w, http.StatusInternalServerError, err.Error())
			return
		}

		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))
		req.Header.Set("X-Acs-Parent-Id", s.cfg.Auth.AccountID)

		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			s.jsonError(w, http.StatusBadRequest, "failed to read request body: "+err.Error())
			return
		}
		if len(bodyBytes) > 0 {
			req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		}

		if err := s.signer.Sign(req, bodyBytes); err != nil {
			s.jsonError(w, http.StatusInternalServerError, "sign error: "+err.Error())
			return
		}

		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			s.jsonError(w, http.StatusBadGateway, err.Error())
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

func (s *Server) healthzHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"service": "sandbox-sidecar",
		})
	}
}

func (s *Server) jsonError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// Start 启动服务器并处理优雅关闭
func (s *Server) Start() error {
	addr := fmt.Sprintf(":%d", s.cfg.Server.Port)
	s.srv = &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  time.Duration(s.cfg.Server.ReadTimeout) * time.Millisecond,
		WriteTimeout: time.Duration(s.cfg.Server.WriteTimeout) * time.Millisecond,
	}

	// 优雅关闭
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
		<-sigChan
		s.logger.Info("shutting down...")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := s.srv.Shutdown(ctx); err != nil {
			s.logger.Error("shutdown error", zap.Error(err))
		}
	}()

	s.logger.Info("sidecar server starting", zap.String("addr", addr))
	return s.srv.ListenAndServe()
}
```

### 3.5 入口 (`cmd/sidecar/main.go`)

```go
package main

import (
	"os"

	"sandbox-sidecar/internal/config"
	"sandbox-sidecar/internal/server"

	"go.uber.org/zap"
)

func main() {
	// 初始化日志
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	logger.Info("starting sandbox sidecar")

	// 加载配置
	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("load config", zap.Error(err))
	}

	// 启动服务器
	srv := server.New(cfg, logger)
	if err := srv.Start(); err != nil {
		logger.Fatal("server error", zap.Error(err))
		os.Exit(1)
	}
}
```

## 4. 构建与运行

```bash
# 编译
go build -o sandbox-sidecar ./cmd/sidecar

# 运行
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-sk"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export ALIBABA_CLOUD_ACCOUNT_ID="your-account-id"

./sandbox-sidecar
```

## 5. 关键实现要点

| 模块 | 要点 |
|---|---|
| **签名** | Body 必须先读取再签名，然后重新设置 io.NopCloser |
| **时间同步** | 签名时间与服务器时间偏差不能超过 15 分钟 |
| **请求体** | 控制面用 `putBodyParameter`，数据面用 `uriPattern` |
| **超时** | 数据面网关硬超时 30 秒，客户端超时设置应 < 30s |
| **WebSocket** | 需要单独处理 Upgrade 握手，代理 ws 帧 |
| **多区域** | 模板变量 `{region}` 和 `{account}` 在启动时替换 |
| **优雅关闭** | 使用 signal.Notify + server.Shutdown，等待在飞行请求完成 |
