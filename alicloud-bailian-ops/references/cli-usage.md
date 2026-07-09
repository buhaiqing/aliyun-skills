# CLI Usage — Bailian (`aliyun bailian`)

## Plugin Installation

Bailian CLI requires the official plugin for enhanced features:

```bash
# Install plugin
aliyun plugin install --names aliyun-cli-bailian

# Verify installation
aliyun bailian --help

# Update plugin
aliyun plugin update aliyun-cli-bailian
```

## CLI Conventions

- **Output**: JSON by default — no `--output json` needed
- **JMESPath**: Use `--output cols=...,rows=...` for tabular output
- **Body parameter**: Complex objects use `--body '{...}'` as JSON string
- **Pagination**: Use `--NextToken` and `--MaxResults` for list operations

## Command Map

### Model Commands

```bash
# List all available models
aliyun bailian ListModels

# Get model specifications
aliyun bailian GetModelInfo --ModelId "qwen-turbo"

# Filter by model type
aliyun bailian ListModels --ModelType "TextGeneration"

# Extract specific fields
aliyun bailian ListModels \
  --output cols=ModelId,Status rows=Models[].{ModelId,Status}
```

### Inference Commands

```bash
# Chat completion (simple)
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [{"role": "user", "content": "Hello"}]
}'

# Chat completion (full parameters)
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing"}
  ],
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 0.95,
  "frequency_penalty": 0.0,
  "presence_penalty": 0.0,
  "stream": false
}'

# Extract response content
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [{"role": "user", "content": "Hi"}]
}' --output cols=Content rows=Choices[0].Message.Content

# Get token usage
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [{"role": "user", "content": "Test"}]
}' --output cols=Input,Output,Total rows=Usage.{Input:PromptTokens,Output:CompletionTokens,Total:TotalTokens}

# Create embeddings
aliyun bailian CreateEmbedding --body '{
  "model": "text-embedding-v2",
  "input": "This is a sample text"
}'
```

### Agent Commands

```bash
# Create agent
aliyun bailian CreateAgent --body '{
  "AgentName": "customer-service-bot",
  "Description": "Handles customer inquiries",
  "ModelId": "qwen-turbo",
  "Instructions": "You are a helpful customer service representative.",
  "Tools": ["search-knowledge-base", "create-ticket"]
}'

# Get agent details
aliyun bailian GetAgent --AgentId "agent-xxx"

# List all agents
aliyun bailian ListAgents

# Update agent
aliyun bailian UpdateAgent --body '{
  "AgentId": "agent-xxx",
  "Instructions": "Updated instructions..."
}'

# Delete agent (DESTRUCTIVE)
aliyun bailian DeleteAgent --AgentId "agent-xxx"

# Invoke agent
aliyun bailian InvokeAgent --body '{
  "AgentId": "agent-xxx",
  "Query": "What are your business hours?"
}'
```

### Knowledge Base Commands

```bash
# Create knowledge base
aliyun bailian CreateKnowledgeBase --body '{
  "Name": "product-docs",
  "Description": "Product documentation",
  "EmbeddingModel": "text-embedding-v2",
  "ChunkSize": 500,
  "OverlapSize": 50
}'

# List knowledge bases
aliyun bailian ListKnowledgeBases

# Get KB details
aliyun bailian GetKnowledgeBase --KnowledgeBaseId "kb-xxx"

# Delete KB (DESTRUCTIVE)
aliyun bailian DeleteKnowledgeBase --KnowledgeBaseId "kb-xxx"

# Index document (from OSS)
aliyun bailian CreateIndex --body '{
  "KnowledgeBaseId": "kb-xxx",
  "DocumentUrl": "oss://bucket/path/doc.pdf",
  "DocumentName": "user-manual.pdf",
  "DocumentType": "pdf"
}'

# Query knowledge base (RAG)
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "kb-xxx",
  "Query": "How do I reset my password?",
  "TopK": 5,
  "ScoreThreshold": 0.7
}'
```

### Prompt Template Commands

```bash
# Create template
aliyun bailian CreatePromptTemplate --body '{
  "TemplateName": "code-review",
  "Content": "Review this {{language}} code:\n\n{{code}}",
  "Variables": ["language", "code"],
  "ModelId": "qwen-coder"
}'

# List templates
aliyun bailian ListPromptTemplates

# Get template
aliyun bailian GetPromptTemplate --PromptTemplateId "pt-xxx"

# Update template
aliyun bailian UpdatePromptTemplate --body '{
  "PromptTemplateId": "pt-xxx",
  "Content": "Updated template..."
}'

# Delete template (DESTRUCTIVE)
aliyun bailian DeletePromptTemplate --PromptTemplateId "pt-xxx"
```

### Fine-tuning Commands

```bash
# Create fine-tune job
aliyun bailian CreateFineTuneJob --body '{
  "BaseModelId": "qwen-turbo",
  "TrainingDataUrl": "oss://bucket/training.jsonl",
  "ValidationDataUrl": "oss://bucket/validation.jsonl",
  "HyperParameters": {
    "Epochs": 3,
    "LearningRate": 0.0001,
    "BatchSize": 4,
    "WarmupSteps": 100
  },
  "OutputModelName": "my-custom-model"
}'

# Get job status
aliyun bailian GetFineTuneJob --JobId "ft-xxx"

# List jobs
aliyun bailian ListFineTuneJobs --MaxResults 20

# Cancel job
aliyun bailian CancelFineTuneJob --JobId "ft-xxx"
```

## CLI vs SDK Coverage Gap

| Operation | CLI | SDK | Notes |
|-----------|-----|-----|-------|
| ListModels | ✅ | ✅ | Full support |
| GetModelInfo | ✅ | ✅ | Full support |
| CreateChatCompletion | ✅ | ✅ | Full support |
| Streaming responses | ⚠️ | ✅ | CLI limited; use SDK for streaming |
| CreateAgent | ✅ | ✅ | Full support |
| Agent memory management | ❌ | ✅ | SDK only |
| Knowledge base | ✅ | ✅ | Full support |
| Document parsing config | ❌ | ✅ | Advanced options SDK only |
| Prompt templates | ✅ | ✅ | Full support |
| Fine-tuning | ✅ | ✅ | Full support |
| Custom metrics | ❌ | ✅ | SDK only |

## Credential Configuration

```bash
# Method 1: Environment variables (recommended)
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-sk"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Method 2: Config file
aliyun configure

# Method 3: Command-line flags
aliyun bailian ListModels --access-key-id "xxx" --access-key-secret "xxx"
```

## JMESPath Examples

```bash
# Extract model IDs only
aliyun bailian ListModels --output cols=ModelId rows=Models[].ModelId

# Filter by status
aliyun bailian ListModels | jq '.Models[] | select(.Status == "Available")'

# Get total token usage from completion
aliyun bailian CreateChatCompletion --body '...' | jq '.Usage.TotalTokens'

# List agent names and IDs
aliyun bailian ListAgents --output cols=Name,ID rows=Agents[].{Name:AgentName,ID:AgentId}
```
