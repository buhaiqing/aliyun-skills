---
name: alicloud-bailian-ops
description: >-
  Use when the user needs to deploy, invoke, or manage Alibaba Cloud Bailian (百炼)
  GenAI Service Platform resources — model lifecycle, Agent management, knowledge base
  operations, and Prompt engineering. User mentions Bailian, 百炼, 百炼大模型,
  GenAI platform, model deployment, Agent creation, knowledge base (知识库), 
  Prompt template, or describes LLM/AI scenarios (chatbot, RAG, model fine-tuning) 
  even without explicit naming. Covers model info retrieval (version, input/output 
  pricing, context window), inference endpoints, and multi-turn conversation management.
  NOT for general billing, RAM permissions only, or non-Bailian AI products.
license: MIT
compatibility: >-
  Alibaba Cloud CLI (`aliyun bailian`) with plugin, Go 1.21+ runtime for JIT SDK fallback.
  API: bailian 2023-12-29. Requires ALIBABA_CLOUD_ACCESS_KEY_ID/SECRET and DASHSCOPE_API_KEY
  for model inference.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-08"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "bailian 2023-12-29"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    aliyun bailian supports 2023-12-29 API. Enhanced plugin available via
    'aliyun plugin install --names aliyun-cli-bailian'. SDK package:
    github.com/alibabacloud-go/bailian-20231229/v1/client
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
    - DASHSCOPE_API_KEY
---

# Alibaba Cloud Bailian (百炼) Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/bailian-skillopt-wrapper.sh` for all Bailian CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun bailian` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |

## Overview

Bailian (百炼) is Alibaba Cloud's GenAI Service Platform providing:
- **Model Hub**: Access to Qwen, Llama, and third-party LLMs
- **Agent Framework**: Build autonomous AI agents with tool use
- **Knowledge Base**: RAG (Retrieval-Augmented Generation) with document indexing
- **Prompt Engineering**: Template management and optimization
- **Fine-tuning**: Domain-specific model customization

This skill provides operational runbooks for model deployment, inference, Agent lifecycle, knowledge base management, and Prompt workflows.

### Key Capabilities

| Capability | Description | Primary API |
|------------|-------------|-------------|
| Model Info | Query model specs (version, pricing, context window) | `GetModelInfo` |
| Model Inference | Invoke LLM for chat/completion | `CreateChatCompletion` |
| Agent Management | Create, update, deploy AI agents | `CreateAgent` / `UpdateAgent` |
| Knowledge Base | Document upload, indexing, RAG queries | `CreateIndex` / `Retrieve` |
| Prompt Template | Manage reusable prompt patterns | `CreatePromptTemplate` |
| Fine-tuning | Train custom models | `CreateFineTuneJob` |

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | Explicit SHOULD/SHOULD NOT triggers; delegates billing to `alicloud-billing-ops` |
| 2 | **Structured I/O** | Placeholders: `{{env.*}}` for creds, `{{user.*}}` for model/agent IDs, `{{output.*}}` for API responses |
| 3 | **Explicit Actionable Steps** | Pre-flight → Execute → Validate → Recover for all operations |
| 4 | **Complete Failure Strategies** | ≥10 error codes with retry/backoff guidance; distinguishes auth vs quota vs rate-limit errors |
| 5 | **Absolute Single Responsibility** | Only Bailian GenAI platform; other AI products (PAI, etc.) delegated |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Bailian", "百炼", "百炼大模型", "DashScope", or "灵积"
- Keywords: model deployment, LLM inference, AI Agent, chatbot, 知识库, knowledge base, RAG, Prompt template, fine-tuning, model endpoint, context window, token pricing
- Tasks: query model information, invoke model, create Agent, manage knowledge base, upload documents for RAG, create Prompt templates
- Scenarios: build AI application, create intelligent客服, implement RAG system, fine-tune domain model

### SHOULD NOT Use This Skill When

- Pure billing/account queries → delegate to `alicloud-billing-ops`
- RAM/IAM permission setup only → delegate to `alicloud-ram-ops`
- Non-Bailian AI platforms (PAI-EAS, etc.) → ask for clarification
- Model training data preparation (DataWorks) → delegate to data pipeline tools

### Delegation Rules

| Dependency | Target Skill | Scenario |
|------------|--------------|----------|
| OSS for document storage | `alicloud-oss-ops` | Knowledge base document upload |
| VPC endpoint config | `alicloud-vpc-ops` | Private network access setup |
| Log analysis | `alicloud-sls-ops` | Inference log querying |
| GCL quality gate | `alicloud-gcl-runner-ops` | Command validation for destructive ops |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Alibaba Cloud Access Key | NEVER ask; HALT if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Alibaba Cloud Secret Key | NEVER ask; mask in all output |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Region (e.g., cn-hangzhou) | Use default if skill allows |
| `{{env.DASHSCOPE_API_KEY}}` | Bailian/DashScope API key for inference | NEVER ask; HALT if unset |
| `{{user.model_id}}` | Model identifier (e.g., qwen-turbo) | Ask once; reuse |
| `{{user.agent_id}}` | Agent instance ID | Ask once; reuse |
| `{{user.knowledge_base_id}}` | Knowledge base ID | Ask once; reuse |
| `{{user.prompt_template_id}}` | Prompt template ID | Ask once; reuse |
| `{{output.model_info}}` | Model metadata from GetModelInfo | Parse from API |
| `{{output.endpoint_url}}` | Inference endpoint | Parse from API |
| `{{output.task_id}}` | Async operation task ID | Parse for polling |

> **Security Warning:** `DASHSCOPE_API_KEY` is sensitive — mask as `***` in all logs and output.

## Quick Start

### Prerequisites

```bash
# 1. Install aliyun CLI with bailian plugin
aliyun plugin install --names aliyun-cli-bailian

# 2. Configure credentials
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export DASHSCOPE_API_KEY="{{env.DASHSCOPE_API_KEY}}"

# 3. Verify setup
aliyun bailian GetModelInfo --ModelId "qwen-turbo"
```

### Your First Model Query

```bash
# Get model specifications
aliyun bailian GetModelInfo --ModelId "qwen-turbo"
```

### Your First Inference Call

```bash
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [{"role": "user", "content": "Hello"}]
}'
```

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/bailian-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun bailian ...` 命令在执行时应替换为 `./scripts/bailian-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun bailian` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows

### Operation: Get Model Info

Retrieve detailed model specifications including version, pricing, and context window.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI plugin | `aliyun bailian --help` | No "plugin not found" error | Run `aliyun plugin install --names aliyun-cli-bailian` |
| Credentials | `test -n "$DASHSCOPE_API_KEY"` | Non-empty | HALT — set DASHSCOPE_API_KEY |
| Model exists | ListModels API call | ModelId in response | HALT — invalid model ID |

#### Execution — CLI (Primary)

```bash
# Get model information
aliyun bailian GetModelInfo --ModelId "{{user.model_id}}"

# Response JSON paths:
# $.ModelId -> Model identifier
# $.ModelName -> Human-readable name
# $.Version -> Model version string
# $.ContextWindow -> Maximum context length (tokens)
# $.InputTokenPrice -> Price per 1K input tokens
# $.OutputTokenPrice -> Price per 1K output tokens
# $.MaxInputTokens -> Max input tokens allowed
# $.MaxOutputTokens -> Max output tokens allowed
```

#### Execution — SDK Fallback

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    bailian "github.com/alibabacloud-go/bailian-20231229/v1/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("bailian.aliyuncs.com"),
    }
    
    client, err := bailian.NewClient(config)
    if err != nil { panic(err) }
    
    request := &bailian.GetModelInfoRequest{
        ModelId: tea.String(os.Getenv("MODEL_ID")),
    }
    
    response, err := client.GetModelInfo(request)
    if err != nil { panic(err) }
    
    body := response.Body
    fmt.Printf("Model: %s\n", tea.ToString(body.ModelId))
    fmt.Printf("Version: %s\n", tea.ToString(body.Version))
    fmt.Printf("Context Window: %d tokens\n", tea.Int64Value(body.ContextWindow))
    fmt.Printf("Input Price: %.4f/1K tokens\n", tea.Float64Value(body.InputTokenPrice))
    fmt.Printf("Output Price: %.4f/1K tokens\n", tea.Float64Value(body.OutputTokenPrice))
}
```

#### Post-execution Validation

1. Verify `$.ContextWindow` > 0
2. Verify pricing fields are numeric and non-negative
3. Cross-check with Bailian console if values seem unexpected

#### Common Model IDs

| Model ID | Context Window | Description |
|----------|----------------|-------------|
| qwen-turbo | 8K | Fast, cost-effective |
| qwen-plus | 32K | Balanced performance |
| qwen-max | 32K | Maximum capability |
| qwen-coder | 8K | Code generation |
| llama2-70b-chat | 4K | Llama2 70B |

### Operation: List Models

Enumerate available models with filtering.

#### Execution — CLI

```bash
# List all models
aliyun bailian ListModels

# With filter
aliyun bailian ListModels --ModelType "TextGeneration"

# Response paths:
# $.Models[].ModelId -> Model ID
# $.Models[].ModelName -> Display name
# $.Models[].ModelType -> TextGeneration, Embedding, etc.
# $.Models[].Status -> Available, Unavailable
```

### Operation: Create Chat Completion

Invoke LLM for chat or completion tasks.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| API key valid | Test call with minimal request | HTTP 200 | HALT — check DASHSCOPE_API_KEY |
| Model available | GetModelInfo status check | Status=Available | Suggest alternative model |
| Input within limits | Length check vs MaxInputTokens | Input < limit | Truncate or split input |

#### Execution — CLI

```bash
# Simple chat completion
aliyun bailian CreateChatCompletion --body '{
  "model": "{{user.model_id}}",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "{{user.prompt}}"}
  ],
  "temperature": 0.7,
  "max_tokens": 1500
}'

# Response paths:
# $.Choices[0].Message.Content -> Generated text
# $.Choices[0].FinishReason -> stop/length/content_filter
# $.Usage.PromptTokens -> Input token count
# $.Usage.CompletionTokens -> Output token count
# $.Usage.TotalTokens -> Total tokens
```

#### Execution — Streaming (SDK)

```go
// For streaming responses, use SDK with tea.Reader
request := &bailian.CreateChatCompletionRequest{
    Model: tea.String("qwen-turbo"),
    Messages: []*bailian.ChatMessage{
        {Role: tea.String("user"), Content: tea.String("Hello")},
    },
    Stream: tea.Bool(true),
}

response, err := client.CreateChatCompletion(request)
// Handle streaming with response.Body as io.Reader
```

#### Failure Recovery

| Error | Pattern | Action |
|-------|---------|--------|
| InvalidApiKey | 401 Unauthorized | HALT — verify DASHSCOPE_API_KEY |
| ModelNotFound | 404 | Check model ID with ListModels |
| RateLimitExceeded | 429 + Retry-After | Exponential backoff (1s, 2s, 4s) |
| ContextLengthExceeded | 400 | Reduce input or use larger context model |
| ContentFiltered | 200 with filter flag | Warn user; suggest rephrasing |

### Operation: Create Agent

Deploy an autonomous AI agent with tool capabilities.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Name unique | ListAgents + grep | No match | Suggest alternative name |
| Model valid | GetModelInfo | Status=Available | HALT — select valid model |
| Tools available | ListTools API | Tool IDs exist | Filter to available tools |

#### Execution — CLI

```bash
aliyun bailian CreateAgent --body '{
  "AgentName": "{{user.agent_name}}",
  "Description": "{{user.description}}",
  "ModelId": "{{user.model_id}}",
  "Instructions": "{{user.instructions}}",
  "Tools": ["{{user.tool_id_1}}", "{{user.tool_id_2}}"],
  "KnowledgeBaseIds": ["{{user.kb_id}}"]
}'

# Response: $.AgentId -> New agent ID
```

#### Post-execution Validation

```bash
# Verify agent creation
aliyun bailian GetAgent --AgentId "{{output.agent_id}}"

# Poll until Status=Ready
for i in {1..30}; do
  STATUS=$(aliyun bailian GetAgent --AgentId "{{output.agent_id}}" | jq -r '.Status')
  [ "$STATUS" = "Ready" ] && break
  sleep 5
done
```

### Operation: Manage Knowledge Base

Create and populate RAG knowledge bases.

#### Create Knowledge Base

```bash
aliyun bailian CreateKnowledgeBase --body '{
  "Name": "{{user.kb_name}}",
  "Description": "{{user.description}}",
  "EmbeddingModel": "text-embedding-v2",
  "ChunkSize": 500,
  "OverlapSize": 50
}'

# Response: $.KnowledgeBaseId
```

#### Upload Document

```bash
aliyun bailian CreateIndex --body '{
  "KnowledgeBaseId": "{{user.knowledge_base_id}}",
  "DocumentUrl": "{{user.oss_url}}",
  "DocumentName": "{{user.doc_name}}",
  "DocumentType": "pdf"
}'

# Response: $.TaskId for polling
```

#### Query Knowledge Base (RAG)

```bash
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "{{user.knowledge_base_id}}",
  "Query": "{{user.query}}",
  "TopK": 5
}'

# Response paths:
# $.Results[].Content -> Retrieved chunks
# $.Results[].Score -> Relevance score
# $.Results[].Source -> Document source
```

### Operation: Prompt Template Management

Create reusable prompt patterns.

#### Create Template

```bash
aliyun bailian CreatePromptTemplate --body '{
  "TemplateName": "{{user.template_name}}",
  "Content": "{{user.template_content}}",
  "Variables": ["{{user.var_1}}", "{{user.var_2}}"],
  "ModelId": "{{user.model_id}}"
}'

# Response: $.PromptTemplateId
```

#### Use Template

```bash
aliyun bailian CreateChatCompletion --body '{
  "model": "{{user.model_id}}",
  "prompt_template_id": "{{user.prompt_template_id}}",
  "variables": {
    "{{user.var_1}}": "{{user.value_1}}",
    "{{user.var_2}}": "{{user.value_2}}"
  }
}'
```

### Operation: Fine-tuning Job

Train custom models on domain data.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Training data ready | OSS file exists | HTTP 200 HEAD | HALT — upload training data |
| Base model valid | Supports fine-tuning | Model metadata | Select fine-tunable model |
| Quota available | GetQuota | Training quota > 0 | HALT — request quota increase |

#### Create Fine-tune Job

```bash
aliyun bailian CreateFineTuneJob --body '{
  "BaseModelId": "{{user.base_model_id}}",
  "TrainingDataUrl": "{{user.training_data_url}}",
  "ValidationDataUrl": "{{user.validation_data_url}}",
  "HyperParameters": {
    "Epochs": 3,
    "LearningRate": 0.0001,
    "BatchSize": 4
  },
  "OutputModelName": "{{user.output_model_name}}"
}'

# Response: $.JobId
```

#### Monitor Training

```bash
# Poll job status
aliyun bailian GetFineTuneJob --JobId "{{output.task_id}}"

# States: Pending -> Running -> Succeeded/Failed/Cancelled
# Response: $.Status, $.Progress (0-100), $.Metrics
```

## Failure Recovery (All Operations)

| Error Code | Meaning | Max Retries | Backoff | Action |
|------------|---------|-------------|---------|--------|
| InvalidApiKey | Authentication failed | 0 | — | HALT — fix DASHSCOPE_API_KEY |
| InvalidParameter | Bad request format | 1 | — | Fix parameters per OpenAPI |
| ModelNotFound | Invalid model ID | 0 | — | Use ListModels to find valid ID |
| RateLimitExceeded | Too many requests | 3 | 1s,2s,4s | Exponential backoff |
| QuotaExceeded | Account limit reached | 0 | — | HALT — request quota increase |
| ContextLengthExceeded | Input too long | 0 | — | Truncate or use larger context model |
| ServiceUnavailable | Temporary outage | 3 | 2s,4s,8s | Retry with backoff |
| InternalError | Server error | 3 | 2s,4s,8s | Retry; HALT if persists |
| Timeout | Request timeout | 2 | 5s,10s | Retry with reduced complexity |

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Bailian architecture, model types, limits
- [API & SDK Usage](references/api-sdk-usage.md) — Operation map, request/response schemas
- [CLI Usage](references/cli-usage.md) — aliyun bailian commands with plugin
- [Troubleshooting](references/troubleshooting.md) — Error codes, diagnostics
- [Monitoring](references/monitoring.md) — Metrics, logging, observability
- [Integration](references/integration.md) — SDK setup, credential rules
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar review
- [Knowledge Base Best Practices](references/knowledge-base-best-practices.md) — RAG optimization
- [Agent Design Patterns](references/agent-design-patterns.md) — Agent architecture guide
- [Prompt Engineering Guide](references/prompt-engineering-guide.md) — Template patterns

## Quality Gate (GCL)

This skill implements **Generator-Critic-Loop (GCL)** quality gate for destructive operations.

### Classification

| Level | max_iter | Rationale |
|-------|:--------:|-----------|
| **required** | 2 | Agent/KB deletion is irreversible; Prompt template deletion affects production |

### GCL Files

| File | Purpose |
|------|---------|
| [references/rubric.md](references/rubric.md) | Scoring dimensions, per-op Safety sub-rules, worked examples |
| [references/prompt-templates.md](references/prompt-templates.md) | G/C/H/O prompt templates, loop control logic |

### Destructive Operations Covered

| Operation | Safety Sub-Rules |
|-----------|-----------------|
| `DeleteAgent` | S1.1-S1.4: Confirmation, existence check, session check, prod warning |
| `DeleteKnowledgeBase` | S2.1-S2.4: Confirmation, existence, doc count log, backup check |
| `DeletePromptTemplate` | S3.1-S3.3: Confirmation, usage check, version archive suggestion |
| `CancelFineTuneJob` | S4.1-S4.2: Cancellable status check, running-job extra confirm |

### Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-08 | Initial skill — model info, inference, Agent, KB, Prompt ops |
| 1.0.0 | 2026-06-08 | GCL v1.0.0 — rubric + prompt templates for destructive ops |
