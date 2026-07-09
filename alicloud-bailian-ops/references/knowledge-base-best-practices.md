# Knowledge Base Best Practices

## Overview

Bailian Knowledge Base provides Retrieval-Augmented Generation (RAG) capabilities:
- **Embedding**: Convert text to vector representations
- **Indexing**: Store and organize document chunks
- **Retrieval**: Semantic search for relevant context

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Document   │────▶│   Chunking   │────▶│  Embedding   │
│   Upload     │     │   Strategy   │     │  (Vector)    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
┌──────────────┐     ┌──────────────┐            │
│   Retrieved  │◀────│   Vector     │◀───────────┘
│   Context    │     │   Search     │
└──────┬───────┘     └──────────────┘
       │
       ▼
┌──────────────┐
│   LLM +      │
│   Generation │
└──────────────┘
```

## Chunking Strategies

### 1. Fixed-Size Chunking

```go
// Best for: General documents, uniform content
req := &bailian.CreateKnowledgeBaseRequest{
    Name:        tea.String("general-docs"),
    ChunkSize:   tea.Int64(500),  // tokens per chunk
    OverlapSize: tea.Int64(50),   // overlap between chunks
}
```

| Chunk Size | Overlap | Best For |
|------------|---------|----------|
| 200 | 20 | Short Q&A, FAQs |
| 500 | 50 | General documents |
| 1000 | 100 | Long-form articles |
| 2000 | 200 | Technical manuals |

### 2. Semantic Chunking

```go
// Best for: Well-structured documents with clear sections
// Uses document structure (headers, paragraphs) instead of fixed size
req := &bailian.CreateKnowledgeBaseRequest{
    Name:          tea.String("structured-docs"),
    ChunkStrategy: tea.String("semantic"),
}
```

**Use when:**
- Content has clear headings/sections
- Preserving context boundaries is critical
- Mixed content types in one document

### 3. Recursive Chunking

```go
// Best for: Code, technical docs with nested structure
req := &bailian.CreateKnowledgeBaseRequest{
    Name:        tea.String("code-docs"),
    ChunkSize:   tea.Int64(1000), // characters (not tokens)
    OverlapSize: tea.Int64(100),
    ChunkBy:     tea.String("characters"),
}
```

**Use when:**
- Source code documentation
- API references
- Structured data (JSON, XML, YAML)

## Document Formats

| Format | Support | Notes |
|--------|---------|-------|
| PDF | ✅ | OCR for scanned PDFs |
| Word (DOCX) | ✅ | Preserves formatting |
| Markdown | ✅ | Best for structured content |
| TXT | ✅ | Plain text |
| HTML | ✅ | Strips tags, keeps content |
| JSON | ⚠️ | Convert to structured text first |
| CSV | ⚠️ | Row-based chunking recommended |

## Embedding Models

| Model | Dimensions | Best For |
|-------|------------|----------|
| text-embedding-v2 | 1536 | General purpose |
| text-embedding-v1 | 1536 | Legacy compatibility |

**Selection Criteria:**
- Use v2 for new projects
- Consistency: Same model for all docs in a KB
- Multilingual: v2 supports Chinese/English mixed

## Indexing Best Practices

### Pre-processing

```bash
# 1. Clean documents before upload
# Remove: Headers, footers, page numbers
# Normalize: Whitespace, encoding (UTF-8)

# 2. Structure with markdown
```markdown
# Product Name

## Feature: Authentication
Authentication supports OAuth 2.0 and SAML...

## Feature: Authorization
Role-based access control...
```

### Upload Strategy

```bash
# Batch upload (max 100 files per batch)
for batch in $(ls docs/*.pdf | xargs -n 100); do
  for file in $batch; do
    aliyun bailian CreateIndex --body "{
      \"KnowledgeBaseId\": \"$KB_ID\",
      \"DocumentUrl\": \"oss://bucket/$file\",
      \"DocumentName\": \"$(basename $file)\",
      \"Metadata\": {\"category\": \"product\", \"version\": \"2.0\"}
    }" &
  done
  wait  # Wait for batch to complete
  sleep 5  # Rate limiting
Done
```

### Metadata Strategy

```json
{
  "DocumentName": "api-reference.pdf",
  "Metadata": {
    "product": "bailian",
    "version": "1.0.0",
    "category": "api",
    "language": "zh-CN",
    "last_updated": "2026-06-01"
  }
}
```

**Benefits:**
- Filter retrieval by product/version
- Boost recent documents
- Language-specific routing

## Retrieval Optimization

### Query Strategies

```bash
# Basic retrieval
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "kb-xxx",
  "Query": "how to authenticate",
  "TopK": 5
}'

# With threshold
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "kb-xxx",
  "Query": "how to authenticate",
  "TopK": 5,
  "ScoreThreshold": 0.7
}'

# With metadata filter
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "kb-xxx",
  "Query": "how to authenticate",
  "Filter": "product = 'bailian' AND version = '1.0.0'"
}'
```

### Re-ranking

```go
// Retrieve more than needed, then re-rank
req := &bailian.RetrieveRequest{
    KnowledgeBaseId: tea.String("kb-xxx"),
    Query:           tea.String(query),
    TopK:            tea.Int64(20), // Retrieve 20
}

resp, _ := client.Retrieve(req)

// Re-rank by:
// 1. Recency (if time-sensitive)
// 2. Source authority
// 3. Query-specific keywords
// 4. Diversity (avoid duplicate content)

// Take top 5 after re-ranking
```

## RAG Pipeline Patterns

### Pattern 1: Direct RAG

```
User Query ──▶ Retrieve ──▶ LLM ──▶ Response
                    │
                    ▼
              [Context]
```

**Use when:** Simple Q&A, factual retrieval

### Pattern 2: Multi-Step RAG

```
User Query ──▶ Analyze ──▶ Sub-queries ──▶ Parallel Retrieve ──▶ Merge ──▶ LLM
                                              │                    │
                                              ▼                    ▼
                                         [Context A]          [Context B]
```

**Use when:** Complex questions requiring multiple sources

### Pattern 3: HyDE (Hypothetical Document Embedding)

```
User Query ──▶ LLM ──▶ Hypothetical Answer ──▶ Embed ──▶ Retrieve ──▶ LLM
                │                                               │
                ▼                                               ▼
           [Generated]                                    [Actual]
```

**Use when:** Query is vague or abstract

## Evaluation

### Retrieval Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recall@K | >0.8 | % of relevant docs in top K |
| Precision@K | >0.7 | % of top K that are relevant |
| MRR | >0.6 | Mean reciprocal rank |
| NDCG | >0.7 | Normalized discounted CG |

### Test Set Creation

```json
[
  {
    "query": "how to reset password",
    "relevant_docs": ["auth-guide.pdf", "faq.md"],
    "expected_answer_contains": ["settings", "password", "reset"]
  }
]
```

### A/B Testing

```bash
# Test chunk size impact
# Variant A: 500 tokens
# Variant B: 1000 tokens

# Measure:
# - Retrieval latency
# - Answer relevance (human eval)
# - Token consumption
```

## Maintenance

### Regular Tasks

| Task | Frequency | Command |
|------|-----------|---------|
| Index health check | Weekly | ListIndexes + check status |
| Orphaned doc cleanup | Monthly | Find docs with no references |
| Version update | Per release | Re-index updated docs |
| Performance review | Monthly | Check retrieval latency |

### Health Check Script

```bash
#!/bin/bash
KB_ID="kb-xxx"

echo "=== KB Health Check ==="

# Check total documents
TOTAL=$(aliyun bailian ListIndexes --KnowledgeBaseId "$KB_ID" | jq '.TotalCount')
echo "Total documents: $TOTAL"

# Check failed indexes
FAILED=$(aliyun bailian ListIndexes --KnowledgeBaseId "$KB_ID" | jq '[.Indexes[] | select(.Status == "Failed")] | length')
echo "Failed indexes: $FAILED"

# Check KB size
SIZE=$(aliyun bailian GetKnowledgeBase --KnowledgeBaseId "$KB_ID" | jq '.StorageSizeMB')
echo "Storage: ${SIZE}MB"

# Alert if issues
if [ "$FAILED" -gt 0 ]; then
  echo "⚠️ WARNING: $FAILED failed indexes detected"
fi
```
