# Troubleshooting — Bailian

## Error Code Reference

| Error Code | HTTP | Meaning | Agent Action |
|------------|------|---------|--------------|
| InvalidApiKey | 401 | DASHSCOPE_API_KEY invalid or expired | HALT — regenerate API key |
| InvalidAccessKeyId | 403 | ALIBABA_CLOUD_ACCESS_KEY_ID not found | HALT — check credentials |
| InvalidAccessKeySecret | 403 | Access key secret mismatch | HALT — verify secret |
| InvalidParameter | 400 | Request parameter invalid | FIX — align with OpenAPI spec |
| MissingParameter | 400 | Required parameter absent | FIX — add missing field |
| ModelNotFound | 404 | Model ID doesn't exist | FIX — use ListModels to find valid ID |
| ModelUnavailable | 503 | Model temporarily offline | RETRY (3x, 5s) or use fallback model |
| ContextLengthExceeded | 400 | Input exceeds model context | FIX — truncate or use larger context model |
| RateLimitExceeded | 429 | RPM/TPM quota exceeded | BACKOFF (exponential: 1s, 2s, 4s) |
| QuotaExceeded | 403 | Account quota limit reached | HALT — request quota increase |
| InsufficientBalance | 402 | Account balance insufficient | HALT — recharge account |
| ServiceUnavailable | 503 | Temporary service outage | RETRY (3x, 10s) |
| InternalError | 500 | Server-side error | RETRY (3x, 5s) then HALT with RequestId |
| Timeout | 504 | Request timeout | RETRY with reduced complexity |
| ContentFiltered | 200* | Output filtered by safety | WARN user; suggest rephrasing |
| OperationNotSupported | 400 | API not available in region | HALT — use supported region |
| ResourceAlreadyExists | 409 | Name/ID already in use | FIX — use unique identifier |
| ResourceNotFound | 404 | Agent/KB/Template not found | FIX — verify ID or create first |
| OperationConflict | 409 | Concurrent operation in progress | WAIT (10s) then RETRY |

## Diagnostic Order

### 1. Authentication Issues

```bash
# Check if API key is set
test -n "$DASHSCOPE_API_KEY" && echo "✅ DASHSCOPE_API_KEY set" || echo "❌ DASHSCOPE_API_KEY missing"

# Verify key validity
aliyun bailian ListModels
# Expected: JSON list of models
# Error 401: Invalid key
```

### 2. Model Availability

```bash
# Check model status
aliyun bailian GetModelInfo --ModelId "qwen-turbo" | jq '.Status'
# Expected: "Available"

# List available models
aliyun bailian ListModels | jq '.Models[] | select(.Status == "Available") | .ModelId'
```

### 3. Rate Limiting

```bash
# Monitor rate limit headers (if available)
aliyun bailian CreateChatCompletion --body '...' -v 2>&1 | grep -i rate

# Implement backoff in scripts
for attempt in 1 2 3; do
  response=$(aliyun bailian CreateChatCompletion --body '...' 2>&1)
  if echo "$response" | grep -q "RateLimitExceeded"; then
    sleep $((2 ** attempt))
    continue
  fi
  echo "$response"
  break
done
```

### 4. Context Length Issues

```bash
# Check model limits
aliyun bailian GetModelInfo --ModelId "qwen-turbo" | jq '{input: .MaxInputTokens, output: .MaxOutputTokens, total: .ContextWindow}'

# Estimate token count (approximate: ~4 chars = 1 token)
echo "Your input text" | wc -c | awk '{print "Approx tokens:", int($1/4)}'
```

## Common Issue Patterns

### Issue: "Model not found" Error

**Symptoms:**
```
Error: ModelNotFound — The specified model ID does not exist
```

**Diagnosis:**
```bash
# List valid model IDs
aliyun bailian ListModels | jq '.Models[].ModelId'

# Common correct IDs:
# - qwen-turbo
# - qwen-plus
# - qwen-max
# - qwen-coder
# - text-embedding-v2
```

**Resolution:**
- Use exact model ID from ListModels
- Check for typos (case-sensitive)
- Verify model is Available in your region

### Issue: Context Length Exceeded

**Symptoms:**
```
Error: ContextLengthExceeded — Input length exceeds maximum context
```

**Resolution:**
```bash
# Option 1: Truncate input
# Option 2: Use larger context model
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-plus",  # 32K context vs 8K
  "messages": [...]
}'
```

### Issue: Rate Limiting During Batch Processing

**Symptoms:**
```
Error: RateLimitExceeded — Too many requests
```

**Resolution:**
```bash
# Implement token bucket pacing
#!/bin/bash
MAX_RPM=60
INTERVAL=$((60 / MAX_RPM))

for item in "${items[@]}"; do
  aliyun bailian CreateChatCompletion --body "..."
  sleep $INTERVAL
done
```

### Issue: Knowledge Base Retrieval Returns Empty

**Symptoms:**
RAG query returns no results or low relevance.

**Diagnosis:**
```bash
# Check KB status
aliyun bailian GetKnowledgeBase --KnowledgeBaseId "kb-xxx" | jq '.Status'
# Expected: "Active"

# Check document count
aliyun bailian ListIndexes --KnowledgeBaseId "kb-xxx" | jq '.TotalCount'

# Test retrieval with debug
aliyun bailian Retrieve --body '{
  "KnowledgeBaseId": "kb-xxx",
  "Query": "test query",
  "TopK": 10,
  "ScoreThreshold": 0.0  # Remove threshold to see all results
}' | jq '.Results[] | {score: .Score, content: .Content[:100]}'
```

**Resolution:**
- Ensure documents are indexed (Status=Completed)
- Lower ScoreThreshold if set too high
- Check query relevance to document content
- Verify embedding model compatibility

### Issue: Agent Not Responding as Expected

**Diagnosis:**
```bash
# Check agent configuration
aliyun bailian GetAgent --AgentId "agent-xxx" | jq '{
  status: .Status,
  model: .ModelId,
  tools: .Tools,
  instructions_length: (.Instructions | length)
}'

# Test agent directly
aliyun bailian InvokeAgent --body '{
  "AgentId": "agent-xxx",
  "Query": "Hello",
  "EnableDebug": true
}' | jq '.DebugInfo'
```

## Multi-Round Diagnosis Flow

### Scenario: Inference Latency Too High

**Round 1 — Baseline:**
```bash
# Measure base latency
time aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "messages": [{"role": "user", "content": "Hi"}],
  "max_tokens": 100
}'
```

**Round 2 — Isolate Variables:**
| Variable | Test | Result |
|----------|------|--------|
| Model | Try qwen-turbo vs qwen-max | Compare latencies |
| Input size | Vary prompt length | Check linearity |
| Output size | Vary max_tokens | Check correlation |
| Region | Test cn-hangzhou vs cn-shanghai | Compare latencies |

**Round 3 — Root Cause:**
- If model-dependent: Switch to faster model (qwen-turbo)
- If input-dependent: Implement prompt compression
- If region-dependent: Use lowest-latency region
- If consistent: Contact support with RequestId

## Log Analysis

### Enable Debug Output

```bash
# Set CLI debug mode
export ALIYUN_CLI_DEBUG=1
aliyun bailian CreateChatCompletion --body '...'
```

### Key Log Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| `RequestId: xxx` | Unique request identifier | Include in support tickets |
| `Latency: xxxms` | End-to-end latency | Monitor for SLAs |
| `TokenUsage: {in: X, out: Y}` | Token consumption | Track costs |
| `CacheHit: true` | Response served from cache | Normal for repeated queries |

## Escalation Checklist

Before escalating to Alibaba Cloud support:

- [ ] RequestId captured from error response
- [ ] Model ID verified with ListModels
- [ ] Region confirmed as supported
- [ ] Quota status checked (not exceeded)
- [ ] Retry with exponential backoff attempted
- [ ] Alternative model tested
- [ ] Issue reproducible with minimal request
