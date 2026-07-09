# Well-Architected Assessment — Bailian

## Five-Pillar Assessment

### 1. Security (安全)

| Practice | Implementation | Status |
|----------|----------------|--------|
| **API Key Management** | DASHSCOPE_API_KEY rotated every 90 days | Required |
| **Least Privilege RAM** | Custom policy with minimal bailian:* permissions | Required |
| **VPC Endpoint** | PrivateLink for isolated network access | Recommended |
| **Encryption at Rest** | Automatic for KB embeddings and model artifacts | Built-in |
| **Encryption in Transit** | TLS 1.2+ for all API calls | Built-in |
| **Audit Logging** | ActionTrail for all control plane operations | Required |
| **Prompt Injection Guard** | Input validation and content filtering | Required |

**Minimum RAM Policy:**
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bailian:GetModelInfo",
        "bailian:ListModels",
        "bailian:CreateChatCompletion",
        "bailian:CreateEmbedding"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bailian:CreateAgent",
        "bailian:UpdateAgent",
        "bailian:DeleteAgent"
      ],
      "Resource": "acs:bailian:*:123456789:agent/*",
      "Condition": {
        "StringEquals": {
          "bailian:RequestTag/Environment": "production"
        }
      }
    }
  ]
}
```

### 2. Stability (稳定)

| Practice | Implementation | RTO | RPO |
|----------|----------------|-----|-----|
| **Multi-AZ Deployment** | Bailian automatically multi-AZ | N/A | N/A |
| **Model Fallback** | Primary → Fallback model config | <5s | N/A |
| **Circuit Breaker** | Hystrix pattern for API failures | Instant | N/A |
| **KB Backup** | Weekly OSS snapshot | 1 hour | 7 days |
| **Agent Versioning** | Immutable agent snapshots | 5 min | N/A |
| **Rate Limit Buffer** | 80% of quota as soft limit | N/A | N/A |

**Disaster Recovery Runbook:**

```markdown
## Scenario: Region-wide Bailian Outage

### Detection
- Alert: ErrorRate > 10% for 2 minutes
- Verify: Check status.aliyun.com

### Response
1. Switch to backup region (cn-shanghai)
   ```bash
   export ALIBABA_CLOUD_REGION_ID=cn-shanghai
   ```

2. Verify model availability
   ```bash
   aliyun bailian ListModels --RegionId cn-shanghai
   ```

3. Update application endpoints
   - Update DNS/config to point to cn-shanghai
   - Verify inference works: test query → OK

4. Communicate
   - Post incident notice
   - Update status page

### Recovery
1. Monitor primary region status
2. When restored, gradually shift traffic back
3. Verify no KB/agent drift between regions
```

### 3. Cost (成本)

| Model | Input/1K | Output/1K | Typical Cost/Month |
|-------|----------|-----------|-------------------|
| qwen-turbo | ¥0.002 | ¥0.006 | ¥500 (1M calls) |
| qwen-plus | ¥0.004 | ¥0.012 | ¥1,000 (1M calls) |
| qwen-max | ¥0.02 | ¥0.06 | ¥5,000 (1M calls) |
| text-embedding-v2 | ¥0.0001 | — | ¥50 (10M vectors) |

**Cost Optimization Patterns:**

| Pattern | Savings | Implementation |
|---------|---------|----------------|
| **Model Tiering** | 80% | Turbo for simple, Plus for complex, Max for critical |
| **Response Caching** | 30% | Cache frequent queries in Redis (5min TTL) |
| **Prompt Compression** | 20% | Remove unnecessary context, use summaries |
| **Batch Embeddings** | 40% | Batch up to 100 docs per call |
| **KB Right-Sizing** | 15% | Remove outdated docs, optimize chunk size |

**Idle Resource Detection:**
```bash
# Find unused agents (>30 days no invocations)
aliyun bailian ListAgents | jq '.Agents[] | select(.LastUsed < "'$(date -d "30 days ago" +%Y-%m-%d)'")'

# Find empty knowledge bases
aliyun bailian ListKnowledgeBases | jq '.KnowledgeBases[] | select(.DocumentCount == 0)'

# Find unused prompt templates
aliyun bailian ListPromptTemplates | jq '.Templates[] | select(.UsageCount == 0)'
```

### 4. Efficiency (效率)

**Batch Operations:**

```go
// Batch embedding (max 100 docs)
req := &bailian.CreateEmbeddingRequest{
    Model: tea.String("text-embedding-v2"),
    Input: []*string{
        tea.String("doc1 content"),
        tea.String("doc2 content"),
        // ... up to 100
    },
}
```

**CI/CD Integration:**

```yaml
# .github/workflows/bailian-deploy.yml
name: Deploy Bailian Agent

on:
  push:
    paths:
      - 'agents/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install aliyun CLI
        run: curl -fsSL https://aliyuncli.alicdn.com/install.sh | bash
      
      - name: Configure credentials
        run: |
          aliyun configure set \
            --access-key-id ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }} \
            --access-key-secret ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }} \
            --region cn-hangzhou
      
      - name: Update Agent
        run: |
          aliyun bailian UpdateAgent --body "$(cat agents/support-bot.json)"
```

### 5. Performance (性能)

**Key Metrics:**

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| P50 Latency | <500ms | >800ms |
| P99 Latency | <2000ms | >3000ms |
| Error Rate | <0.1% | >1% |
| Token Throughput | Max quota | >90% of quota |

**Auto-scaling Triggers:**

| Condition | Action |
|-----------|--------|
| RPM > 80% of quota | Request quota increase |
| P99 latency > 2s | Enable response caching |
| KB query latency > 500ms | Optimize embedding model |

**Performance Baselines by Model:**

| Model | P50 Latency | P99 Latency | Best For |
|-------|-------------|-------------|----------|
| qwen-turbo | 300ms | 800ms | High-throughput chat |
| qwen-plus | 500ms | 1500ms | Balanced workloads |
| qwen-max | 800ms | 2500ms | Complex reasoning |

## Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model deprecation | Medium | High | Version pinning + fallback |
| Quota exhaustion | Medium | High | Monitoring + auto-increase |
| Prompt injection | Medium | Critical | Input validation + filtering |
| Data leakage via LLM | Low | Critical | Output filtering + audit |
| Region outage | Low | High | Multi-region fallback |
| Cost overrun | Medium | Medium | Budget alerts + caching |

## Compliance Checklist

- [ ] RAM policies follow least privilege
- [ ] VPC endpoints configured for production
- [ ] ActionTrail enabled for audit
- [ ] Model fallback configured
- [ ] Cost alerts at 80% budget
- [ ] DR runbook tested quarterly
- [ ] PII detection in prompts
- [ ] Output content filtering enabled
