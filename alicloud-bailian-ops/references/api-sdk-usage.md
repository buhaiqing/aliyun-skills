# API & SDK Usage — Bailian

## OpenAPI Spec

- **Product**: bailian
- **Version**: 2023-12-29
- **Base Path**: `/`
- **Endpoint**: `bailian.aliyuncs.com`
- **Protocol**: HTTPS only
- **Auth**: HMAC-SHA1 (AccessKey) + Bearer token (DashScope API key)

## Go SDK Package

```
github.com/alibabacloud-go/bailian-20231229/v1/client
```

## Operation Map

### Model Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| List models | ListModels | `client.ListModels()` | `aliyun bailian ListModels` |
| Get model info | GetModelInfo | `client.GetModelInfo()` | `aliyun bailian GetModelInfo` |

### Inference Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| Chat completion | CreateChatCompletion | `client.CreateChatCompletion()` | `aliyun bailian CreateChatCompletion` |
| Embeddings | CreateEmbedding | `client.CreateEmbedding()` | `aliyun bailian CreateEmbedding` |

### Agent Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| Create agent | CreateAgent | `client.CreateAgent()` | `aliyun bailian CreateAgent` |
| Get agent | GetAgent | `client.GetAgent()` | `aliyun bailian GetAgent` |
| Update agent | UpdateAgent | `client.UpdateAgent()` | `aliyun bailian UpdateAgent` |
| Delete agent | DeleteAgent | `client.DeleteAgent()` | `aliyun bailian DeleteAgent` |
| List agents | ListAgents | `client.ListAgents()` | `aliyun bailian ListAgents` |
| Invoke agent | InvokeAgent | `client.InvokeAgent()` | `aliyun bailian InvokeAgent` |

### Knowledge Base Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| Create KB | CreateKnowledgeBase | `client.CreateKnowledgeBase()` | `aliyun bailian CreateKnowledgeBase` |
| Get KB | GetKnowledgeBase | `client.GetKnowledgeBase()` | `aliyun bailian GetKnowledgeBase` |
| Delete KB | DeleteKnowledgeBase | `client.DeleteKnowledgeBase()` | `aliyun bailian DeleteKnowledgeBase` |
| List KBs | ListKnowledgeBases | `client.ListKnowledgeBases()` | `aliyun bailian ListKnowledgeBases` |
| Create index | CreateIndex | `client.CreateIndex()` | `aliyun bailian CreateIndex` |
| Retrieve | Retrieve | `client.Retrieve()` | `aliyun bailian Retrieve` |

### Prompt Template Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| Create template | CreatePromptTemplate | `client.CreatePromptTemplate()` | `aliyun bailian CreatePromptTemplate` |
| Get template | GetPromptTemplate | `client.GetPromptTemplate()` | `aliyun bailian GetPromptTemplate` |
| Update template | UpdatePromptTemplate | `client.UpdatePromptTemplate()` | `aliyun bailian UpdatePromptTemplate` |
| Delete template | DeletePromptTemplate | `client.DeletePromptTemplate()` | `aliyun bailian DeletePromptTemplate` |
| List templates | ListPromptTemplates | `client.ListPromptTemplates()` | `aliyun bailian ListPromptTemplates` |

### Fine-tuning Operations

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| Create job | CreateFineTuneJob | `client.CreateFineTuneJob()` | `aliyun bailian CreateFineTuneJob` |
| Get job | GetFineTuneJob | `client.GetFineTuneJob()` | `aliyun bailian GetFineTuneJob` |
| Cancel job | CancelFineTuneJob | `client.CancelFineTuneJob()` | `aliyun bailian CancelFineTuneJob` |
| List jobs | ListFineTuneJobs | `client.ListFineTuneJobs()` | `aliyun bailian ListFineTuneJobs` |

## Request/Response Examples

### GetModelInfo

**Request:**
```json
{
  "ModelId": "qwen-turbo"
}
```

**Response Fields:**
| Field | JSON Path | Type |
|-------|-----------|------|
| ModelId | $.ModelId | string |
| ModelName | $.ModelName | string |
| Version | $.Version | string |
| ContextWindow | $.ContextWindow | int64 |
| MaxInputTokens | $.MaxInputTokens | int64 |
| MaxOutputTokens | $.MaxOutputTokens | int64 |
| InputTokenPrice | $.InputTokenPrice | float64 |
| OutputTokenPrice | $.OutputTokenPrice | float64 |
| Status | $.Status | string |

### CreateChatCompletion

**Request:**
```json
{
  "model": "qwen-turbo",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"}
  ],
  "temperature": 0.7,
  "max_tokens": 1500,
  "top_p": 0.95,
  "stream": false
}
```

**Response Fields:**
| Field | JSON Path | Type |
|-------|-----------|------|
| Content | $.Choices[0].Message.Content | string |
| FinishReason | $.Choices[0].FinishReason | string |
| PromptTokens | $.Usage.PromptTokens | int64 |
| CompletionTokens | $.Usage.CompletionTokens | int64 |
| TotalTokens | $.Usage.TotalTokens | int64 |

### Pagination Patterns

**List operations** use `NextToken` pagination:

```json
// Request
{
  "MaxResults": 50,
  "NextToken": "eyJ0b2tlbiI6ICJ2YWx1ZSJ9"
}

// Response
{
  "Items": [...],
  "NextToken": "eyJuZXh0IjogInBhZ2UifQ=="
}
```

Continue until `NextToken` is empty/null.

## Async Operations

Fine-tune jobs are async with polling:

| State | Description | Terminal? |
|-------|-------------|-----------|
| Pending | Queued, waiting for resources | No |
| Running | Actively training | No |
| Succeeded | Completed successfully | Yes |
| Failed | Error during training | Yes |
| Cancelled | User cancelled | Yes |

**Polling:** 10s interval, max 3600s (1 hour) for typical jobs.
