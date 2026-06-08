# Bailian Core Concepts

## Architecture Overview

Bailian (百炼) GenAI Service Platform provides a unified interface for:
- **Foundation Models**: Qwen series, Llama, and third-party LLMs
- **Agent Framework**: Autonomous AI with tool use and memory
- **Knowledge Base**: Vector storage with semantic search (RAG)
- **Prompt Management**: Template versioning and A/B testing

```
┌─────────────────────────────────────────────────────────────┐
│                    Bailian Platform                         │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  Model Hub  │   Agents    │  Knowledge  │     Prompts       │
│             │             │    Base     │                   │
├─────────────┼─────────────┼─────────────┼───────────────────┤
│ qwen-turbo  │  ReAct      │  Embedding  │   Templates       │
│ qwen-plus   │  Planning   │  Indexing   │   Variables       │
│ qwen-max    │  Tools      │  Retrieval  │   Versioning      │
│ llama2-70b  │  Memory     │  Chunking   │   A/B Test        │
└─────────────┴─────────────┴─────────────┴───────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Unified API     │
                    │  (bailian 2023-   │
                    │    12-29)         │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Inference        │
                    │  Endpoints        │
                    └───────────────────┘
```

## Model Types

| Type | Description | Use Cases | Examples |
|------|-------------|-----------|----------|
| **Text Generation** | General LLM inference | Chat, completion, summarization | qwen-turbo, qwen-plus, qwen-max |
| **Code Generation** | Programming-focused | Code completion, review, generation | qwen-coder |
| **Embeddings** | Vector representations | RAG, semantic search, clustering | text-embedding-v2 |
| **Multimodal** | Text + vision | Image understanding, OCR | qwen-vl |

## Model Specifications (Key Fields)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| ModelId | string | Unique identifier | `qwen-turbo` |
| Version | string | Model version | `1.0.0` |
| ContextWindow | int64 | Max total tokens (input+output) | 8192 |
| MaxInputTokens | int64 | Maximum input tokens | 6144 |
| MaxOutputTokens | int64 | Maximum output tokens | 2048 |
| InputTokenPrice | float64 | Price per 1K input tokens (CNY) | 0.002 |
| OutputTokenPrice | float64 | Price per 1K output tokens (CNY) | 0.006 |

## Regional Availability

| Region | Model Hub | Agents | Knowledge Base | Fine-tuning |
|--------|:---------:|:------:|:--------------:|:-----------:|
| cn-hangzhou | ✅ | ✅ | ✅ | ✅ |
| cn-shanghai | ✅ | ✅ | ✅ | ✅ |
| cn-beijing | ✅ | ✅ | ❌ | ❌ |
| ap-southeast-1 | ✅ | ✅ | ❌ | ❌ |

## Quota and Limits

### Account Quotas (Default)

| Resource | Default Limit | Request Increase |
|----------|---------------|------------------|
| RPM (Requests Per Minute) | 60 | Submit ticket |
| TPM (Tokens Per Minute) | 100,000 | Submit ticket |
| Concurrent fine-tune jobs | 2 | Submit ticket |
| Knowledge bases per account | 10 | Submit ticket |
| Documents per KB | 10,000 | Submit ticket |
| Agents per account | 20 | Submit ticket |

### Model-Specific Limits

| Model | RPM | TPM | Context |
|-------|-----|-----|---------|
| qwen-turbo | 60 | 100K | 8K |
| qwen-plus | 30 | 60K | 32K |
| qwen-max | 10 | 20K | 32K |
| text-embedding-v2 | 300 | 300K | 2K |

## Knowledge Base Chunking Strategies

| Strategy | Chunk Size | Overlap | Best For |
|----------|------------|---------|----------|
| Fixed | 500 tokens | 50 tokens | General documents |
| Semantic | Dynamic | 0 | Well-structured content |
| Recursive | 1000 chars | 100 chars | Code, technical docs |

## Agent Architecture

### ReAct Pattern
```
User Query → Agent → Thought → Action (Tool) → Observation → ... → Final Answer
```

### Memory Types
| Type | Scope | Duration | Storage |
|------|-------|----------|---------|
| Short-term | Single session | Session | In-memory |
| Long-term | Cross-session | Persistent | Knowledge base |
| Working | Current task | Task completion | Context window |

## SPOF Analysis

| Component | Risk | Mitigation |
|-----------|------|------------|
| API endpoint | Regional outage | Multi-region fallback |
| Model availability | Model deprecation | Version pinning + fallback models |
| Knowledge base | Index corruption | Regular backup + versioning |
| Rate limiting | Throttling | Exponential backoff + caching |
