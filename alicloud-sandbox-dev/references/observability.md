# 观测性实现指南

> **目的**: 如何为 FC Sandbox Sidecar 添加 Prometheus 指标和 OpenTelemetry 链路追踪。

## 1. 架构总览

```
Sidecar ──► /metrics (Prometheus 抓取)
        ──► OTLP Exporter ──► Collector ──► Jaeger/Tempo
        ──► Structured Logs ──► Loki/ELK
```

## 2. Prometheus 指标

### 2.1 定义指标

```go
// internal/metrics/metrics.go
package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// responseWriter 包裹 http.ResponseWriter 以捕获状态码
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

var (
	// HTTP 请求指标
	HTTPRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "sandbox_sidecar_http_request_duration_seconds",
			Help:    "HTTP 请求延迟分布",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "endpoint", "status_code"},
	)

	HTTPRequestTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "sandbox_sidecar_http_requests_total",
			Help: "HTTP 请求总数",
		},
		[]string{"method", "endpoint", "status_code"},
	)

	// Sandbox 实例指标
	SandboxCount = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "sandbox_sidecar_active_sandboxes",
			Help: "当前活跃的 Sandbox 实例数",
		},
		[]string{"status", "template_name"},
	)

	// 签名指标
	SigningErrors = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "sandbox_sidecar_signing_errors_total",
			Help: "签名失败次数",
		},
		[]string{"error_type"},
	)

	// 代理指标
	UpstreamRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "sandbox_sidecar_upstream_duration_seconds",
			Help:    "上游 API 请求延迟",
			Buckets: []float64{0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0},
		},
		[]string{"plane", "method"}, // plane: "control" | "data"
	)

	// WebSocket 指标
	WebSocketConnections = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "sandbox_sidecar_websocket_connections",
			Help: "当前 WebSocket 连接数",
		},
	)
)

// MetricsMiddleware 返回 Prometheus 中间件
func MetricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		// 包裹 ResponseWriter 以捕获状态码
		rw := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(rw, r)
		
		metrics.HTTPRequestDuration.
			WithLabelValues(r.Method, r.URL.Path, strconv.Itoa(rw.statusCode)).
			Observe(time.Since(start).Seconds())
		metrics.HTTPRequestTotal.
			WithLabelValues(r.Method, r.URL.Path, strconv.Itoa(rw.statusCode)).
			Inc()
	})
}

// RegisterMetrics 注册指标端点
func RegisterMetrics(mux *http.ServeMux) {
    mux.Handle("/metrics", promhttp.Handler())
}
```

### 2.2 Go 指标使用示例

```go
// 在 handler 中记录上游延迟
func (s *Server) proxyRequest(...) {
    start := time.Now()
    resp, err := client.Do(req)
    duration := time.Since(start)
    
    plane := "data" // 或 "control"
    metrics.UpstreamRequestDuration.
        WithLabelValues(plane, method).
        Observe(duration.Seconds())
    
    if err != nil {
        metrics.SigningErrors.WithLabelValues("upstream_error").Inc()
    }
}

// WebSocket 连接计数
func HandleWebSocket(...) {
    metrics.WebsocketConnections.Inc()
    defer metrics.WebsocketConnections.Dec()
    // ...
}
```

### 2.3 Python (FastAPI) 指标

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
import time

# 指标定义
http_request_duration = Histogram(
    'sandbox_sidecar_http_request_duration_seconds',
    'HTTP 请求延迟分布',
    labelnames=['method', 'endpoint', 'status_code']
)

http_request_total = Counter(
    'sandbox_sidecar_http_requests_total',
    'HTTP 请求总数',
    labelnames=['method', 'endpoint', 'status_code']
)

active_sandboxes = Gauge(
    'sandbox_sidecar_active_sandboxes',
    '当前活跃的 Sandbox 实例数',
    labelnames=['status', 'template_name']
)

websocket_connections = Gauge(
    'sandbox_sidecar_websocket_connections',
    '当前 WebSocket 连接数'
)

# 中间件
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        http_request_duration.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).observe(duration)
        http_request_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()
        return response
```

## 3. OpenTelemetry 链路追踪

### 3.1 Go OTel 设置

```go
// internal/otel/otel.go
package otel

import (
	"context"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func InitTracer(ctx context.Context, endpoint string) (*sdktrace.TracerProvider, error) {
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(), // 生产环境应使用 TLS
	)
	if err != nil {
		return nil, err
	}

	resource := resource.NewWithAttributes(
		semconv.SchemaURL,
		semconv.ServiceNameKey.String("sandbox-sidecar"),
		semconv.ServiceVersionKey.String("1.0.0"),
	)

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)

	return tp, nil
}
```

### 3.2 使用 Tracer

```go
import "go.opentelemetry.io/otel"

func (s *Server) controlPlaneHandler(...) {
    ctx, span := otel.Tracer("sandbox-sidecar").Start(r.Context(), "controlPlane.proxy")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("sandbox.action", action),
        attribute.String("http.method", method),
    )
    
    // ... 代理逻辑
    span.SetStatus(codes.OK, "") // 或 codes.Error
}
```

### 3.3 Python OTel 设置

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def setup_otel(endpoint="otlp-collector:4317"):
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)
```

## 4. 结构化日志

### 4.1 Go (zap)

```go
// main.go
logger, _ := zap.NewProduction(
    zap.AddStacktrace(zapcore.ErrorLevel),
    zap.AddCaller(),
)
logger.Info("sidecar started",
    zap.Int("port", cfg.Server.Port),
    zap.String("region", cfg.Auth.Region),
    zap.String("account_id", cfg.Auth.AccountID),
)
```

### 4.2 Python (structlog)

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.BytesLoggerFactory(),
)

logger = structlog.get_logger()
logger.info("sidecar started", port=8080, region="cn-hangzhou")
```

## 5. 关键指标清单

| 指标名称 | 类型 | 说明 | 告警建议 |
|---|---|---|---|
| `sandbox_sidecar_http_request_duration_seconds` | Histogram | Sidecar HTTP 请求延迟 | P99 > 5s 告警 |
| `sandbox_sidecar_http_requests_total` | Counter | HTTP 请求总数 | 用于容量规划 |
| `sandbox_sidecar_upstream_duration_seconds` | Histogram | 上游 API 延迟 | P99 > 10s 告警 |
| `sandbox_sidecar_active_sandboxes` | Gauge | 活跃 Sandbox 数 | > 50 告警 |
| `sandbox_sidecar_signing_errors_total` | Counter | 签名失败次数 | > 5/min 告警 |
| `sandbox_sidecar_websocket_connections` | Gauge | WebSocket 连接数 | > 100 告警 |

## 6. Grafana Dashboard 示例

```json
{
  "panels": [
    {
      "title": "HTTP 请求延迟 (P50/P95/P99)",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(sandbox_sidecar_http_request_duration_seconds_bucket[5m]))"
        }
      ]
    },
    {
      "title": "上游 API 错误率",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(http_request_total{status_code=~\"5..\"}[5m]) / rate(http_request_total[5m])"
        }
      ]
    },
    {
      "title": "活跃 Sandbox 实例",
      "type": "graph",
      "targets": [
        {
          "expr": "sandbox_sidecar_active_sandboxes",
          "legendFormat": "{{status}} - {{template_name}}"
        }
      ]
    }
  ]
}
```
