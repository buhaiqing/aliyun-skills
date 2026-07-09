# Integration — Bailian SDK & Environment

## Environment Setup

### Prerequisites

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Go | 1.21 | 1.24+ |
| aliyun CLI | 3.0.0 | Latest + bailian plugin |

### Credential Requirements

| Variable | Source | Required For |
|----------|--------|--------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Environment/config | All API calls |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Environment/config | All API calls |
| `ALIBABA_CLOUD_REGION_ID` | Environment/config | Regional endpoints |
| `DASHSCOPE_API_KEY` | Environment | Model inference |

### Install CLI with Bailian Plugin

```bash
# Install aliyun CLI
curl -fsSL https://aliyuncli.alicdn.com/install.sh | bash

# Install bailian plugin
aliyun plugin install --names aliyun-cli-bailian

# Verify
aliyun bailian ListModels
```

## Go SDK Integration

### Package Installation

```bash
# Initialize module
go mod init my-bailian-app

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea/tea
go get github.com/alibabacloud-go/bailian-20231229/v1/client
```

### Client Factory Pattern

```go
package bailian

import (
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    bailian "github.com/alibabacloud-go/bailian-20231229/v1/client"
)

// Config holds Bailian configuration
type Config struct {
    AccessKeyId     string
    AccessKeySecret string
    Endpoint        string
}

// NewClient creates a Bailian client
func NewClient(cfg *Config) (*bailian.Client, error) {
    if cfg.Endpoint == "" {
        cfg.Endpoint = "bailian.aliyuncs.com"
    }
    
    openCfg := &openapi.Config{
        AccessKeyId:     tea.String(cfg.AccessKeyId),
        AccessKeySecret: tea.String(cfg.AccessKeySecret),
        Endpoint:        tea.String(cfg.Endpoint),
    }
    
    return bailian.NewClient(openCfg)
}

// ClientFromEnv creates client from environment variables
func ClientFromEnv() (*bailian.Client, error) {
    return NewClient(&Config{
        AccessKeyId:     os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        AccessKeySecret: os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    })
}
```

### Inference Client (DashScope API Key)

```go
package bailian

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "os"
)

// InferenceClient for model calls
type InferenceClient struct {
    APIKey   string
    BaseURL  string
    HTTPClient *http.Client
}

// NewInferenceClient creates inference client
func NewInferenceClient() *InferenceClient {
    return &InferenceClient{
        APIKey:   os.Getenv("DASHSCOPE_API_KEY"),
        BaseURL:  "https://dashscope.aliyuncs.com/api/v1",
        HTTPClient: &http.Client{},
    }
}

// ChatCompletionRequest represents the request body
type ChatCompletionRequest struct {
    Model       string      `json:"model"`
    Messages    []Message   `json:"messages"`
    Temperature float64     `json:"temperature,omitempty"`
    MaxTokens   int         `json:"max_tokens,omitempty"`
    Stream      bool        `json:"stream,omitempty"`
}

type Message struct {
    Role    string `json:"role"`
    Content string `json:"content"`
}

// ChatCompletion calls the chat API
func (c *InferenceClient) ChatCompletion(req *ChatCompletionRequest) (*ChatCompletionResponse, error) {
    body, _ := json.Marshal(req)
    
    httpReq, err := http.NewRequest("POST", 
        c.BaseURL+"/services/aigc/text-generation/generation",
        bytes.NewBuffer(body))
    if err != nil {
        return nil, err
    }
    
    httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)
    httpReq.Header.Set("Content-Type", "application/json")
    
    resp, err := c.HTTPClient.Do(httpReq)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    respBody, _ := io.ReadAll(resp.Body)
    
    var result ChatCompletionResponse
    if err := json.Unmarshal(respBody, &result); err != nil {
        return nil, fmt.Errorf("parse error: %w, body: %s", err, string(respBody))
    }
    
    return &result, nil
}
```

## SDK Operation Examples

### Get Model Info

```go
client, _ := ClientFromEnv()

req := &bailian.GetModelInfoRequest{
    ModelId: tea.String("qwen-turbo"),
}

resp, err := client.GetModelInfo(req)
if err != nil {
    panic(err)
}

fmt.Printf("Model: %s\n", tea.ToString(resp.Body.ModelId))
fmt.Printf("Context: %d tokens\n", tea.Int64Value(resp.Body.ContextWindow))
fmt.Printf("Price: %.4f/1K in, %.4f/1K out\n",
    tea.Float64Value(resp.Body.InputTokenPrice),
    tea.Float64Value(resp.Body.OutputTokenPrice))
```

### Create Chat Completion

```go
req := &bailian.CreateChatCompletionRequest{
    Model: tea.String("qwen-turbo"),
    Messages: []*bailian.ChatMessage{
        {Role: tea.String("system"), Content: tea.String("You are helpful.")},
        {Role: tea.String("user"), Content: tea.String("Hello")},
    },
    Temperature: tea.Float64(0.7),
    MaxTokens:   tea.Int64(1500),
}

resp, err := client.CreateChatCompletion(req)
if err != nil {
    panic(err)
}

fmt.Println(tea.ToString(resp.Body.Choices[0].Message.Content))
fmt.Printf("Tokens: %d in, %d out\n",
    tea.Int64Value(resp.Body.Usage.PromptTokens),
    tea.Int64Value(resp.Body.Usage.CompletionTokens))
```

### Create Agent

```go
req := &bailian.CreateAgentRequest{
    AgentName:    tea.String("support-bot"),
    Description:  tea.String("Customer support agent"),
    ModelId:      tea.String("qwen-turbo"),
    Instructions: tea.String("You help customers with product questions."),
    Tools:        []*string{tea.String("search-docs"), tea.String("create-ticket")},
}

resp, err := client.CreateAgent(req)
if err != nil {
    panic(err)
}

agentId := tea.ToString(resp.Body.AgentId)
fmt.Printf("Created agent: %s\n", agentId)
```

### Knowledge Base Operations

```go
// Create KB
kbReq := &bailian.CreateKnowledgeBaseRequest{
    Name:           tea.String("product-docs"),
    Description:    tea.String("Product documentation"),
    EmbeddingModel: tea.String("text-embedding-v2"),
    ChunkSize:      tea.Int64(500),
    OverlapSize:    tea.Int64(50),
}

kbResp, _ := client.CreateKnowledgeBase(kbReq)
kbId := tea.ToString(kbResp.Body.KnowledgeBaseId)

// Index document
idxReq := &bailian.CreateIndexRequest{
    KnowledgeBaseId: tea.String(kbId),
    DocumentUrl:     tea.String("oss://bucket/doc.pdf"),
    DocumentName:    tea.String("manual.pdf"),
    DocumentType:    tea.String("pdf"),
}

_, _ = client.CreateIndex(idxReq)

// Retrieve
retrieveReq := &bailian.RetrieveRequest{
    KnowledgeBaseId: tea.String(kbId),
    Query:           tea.String("How do I reset password?"),
    TopK:            tea.Int64(5),
}

retrieveResp, _ := client.Retrieve(retrieveReq)
for _, r := range retrieveResp.Body.Results {
    fmt.Printf("[%.2f] %s\n", tea.Float64Value(r.Score), tea.ToString(r.Content))
}
```

## Error Handling Pattern

```go
import (
    "errors"
    "github.com/alibabacloud-go/tea/tea"
)

// BailianError represents API errors
type BailianError struct {
    Code    string
    Message string
    RequestId string
}

func (e *BailianError) Error() string {
    return fmt.Sprintf("[%s] %s (RequestId: %s)", e.Code, e.Message, e.RequestId)
}

// HandleError converts SDK error to BailianError
func HandleError(err error) *BailianError {
    var sdkErr *tea.SDKError
    if errors.As(err, &sdkErr) {
        return &BailianError{
            Code:      tea.ToString(sdkErr.Code),
            Message:   tea.ToString(sdkErr.Message),
            RequestId: tea.ToString(sdkErr.Data["RequestId"]),
        }
    }
    return &BailianError{Code: "Unknown", Message: err.Error()}
}

// IsRetryable determines if error is retryable
func IsRetryable(code string) bool {
    retryable := map[string]bool{
        "ServiceUnavailable": true,
        "InternalError":      true,
        "Timeout":            true,
        "RateLimitExceeded":  true,
    }
    return retryable[code]
}

// Usage
resp, err := client.CreateChatCompletion(req)
if err != nil {
    bErr := HandleError(err)
    if IsRetryable(bErr.Code) {
        // Retry with backoff
    } else {
        // HALT
        panic(bErr)
    }
}
```

## Testing

```go
// client_test.go
package bailian

import (
    "testing"
)

func TestClientFromEnv(t *testing.T) {
    // Set test env
    t.Setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "test-ak")
    t.Setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "test-sk")
    
    client, err := ClientFromEnv()
    if err != nil {
        t.Fatalf("ClientFromEnv failed: %v", err)
    }
    
    if client == nil {
        t.Fatal("Client is nil")
    }
}
```

## Cross-Skill Delegation Matrix

| When Bailian Needs... | Delegate To | Method |
|-----------------------|-------------|--------|
| OSS document storage | `alicloud-oss-ops` | Generate presigned URL |
| VPC endpoint config | `alicloud-vpc-ops` | Create VPC endpoint |
| Log analysis | `alicloud-sls-ops` | Query inference logs |
| Metrics/alarms | `alicloud-cms-ops` | Create dashboards |
| GCL validation | `alicloud-gcl-runner-ops` | Run quality gate |
