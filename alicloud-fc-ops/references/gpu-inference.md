# GPU Inference — vLLM & Batch Workloads

> **Purpose**: Agent playbook for deploying and operating LLM inference (vLLM) and batch workloads on FC GPU functions.  
> **Sources**: [Creating a GPU function](https://help.aliyun.com/zh/functioncompute/fc/user-guide/creating-a-gpu-function/), [Quasi-real-time inference](https://help.aliyun.com/zh/functioncompute/fc-3-0/user-guide/quasi-real-time-inference-scenarios), [vLLM on Function AI](https://help.aliyun.com/zh/functioncompute/fc-3-0/create-a-model-service-using-the-vllm-inference-engine), [LLM indicator monitoring](https://help.aliyun.com/zh/functioncompute/fc/user-guide/llm-indicator-monitoring)

---

## 1. Capability Summary

| Question | Answer |
|----------|--------|
| Does FC provide serverless GPU? | **Yes** — **GPU function** type (not regular CPU runtimes) |
| Runtime | **`custom-container` only**, with GPU-capable base images |
| vLLM support | **Yes** — managed via **Function AI Model Service**, or self-hosted in a GPU function container |
| Batch inference | **Yes** — combine vLLM continuous batching (in-process) with FC elastic scaling (cross-instance) |

> **Agent one-liner**: GPU = `custom-container` GPU function; vLLM batching happens **inside** the container; FC scales **instances**; set FC **instance concurrency** based on whether the engine batches internally.

---

## 2. Deployment Paths (Choose One)

| Path | Best for | You manage | FC manages |
|------|----------|------------|------------|
| **A. Function AI Model Service** | Quick LLM deploy, preset/custom models, ops-light | Model source, RAM role, GPU spec choice | vLLM engine, NAS auto-config, scaling, endpoint |
| **B. GPU Function (DIY container)** | Custom vLLM flags, ComfyUI/RAG/TensorRT, full control | Image, HTTP server, startup command, warmup | Instance lifecycle, elastic/resident pools |

**Do not confuse with**:

| Product | GPU |
|---------|-----|
| FC **GPU function** / Function AI Model Service | ✅ |
| FC **CPU function** (python/nodejs/…) | ❌ |
| AgentRun **Sandbox** | ❌ CPU only — call external GPU endpoint from sandbox |

---

## 3. vLLM on FC

### 3.1 Why vLLM fits FC

vLLM targets high-throughput LLM serving with:

- **Continuous batching** — new requests join the GPU batch without waiting for the whole batch to finish
- **PagedAttention** — efficient KV cache; higher concurrent sequences per GPU

On FC, one GPU instance typically runs **one vLLM process**; continuous batching multiplexes **many client requests onto that process**. FC then scales **additional GPU instances** when instance-level capacity is exceeded.

### 3.2 Path A — Function AI (managed vLLM)

1. Create a **Function AI project** → **Model Service** → deploy type **framework-based**
2. Select **vLLM** as inference framework; preset model (ModelScope) or custom (OSS / ModelScope ID)
3. Enable **NAS** (auto-config recommended) for model weight caching across cold starts
4. Pick **GPU spec** (VRAM / vCPU / memory shown in console); use **second-level snapshots** when offered
5. Attach RAM role with OSS/NAS/ACR read permissions

Post-deploy: use service **API Endpoint** + credentials from console; monitor via Function AI + FC LLM metrics.

Official walkthrough: [Create a model service using vLLM](https://help.aliyun.com/zh/functioncompute/fc-3-0/create-a-model-service-using-the-vllm-inference-engine).

### 3.3 Path B — GPU Function (self-managed vLLM image)

**Requirements** (same as any GPU function):

| Requirement | Detail |
|-------------|--------|
| Image | Custom container with **HTTP server** (e.g. vLLM OpenAI-compatible API on port `8000` or `9000`) |
| Listen port | Must match console **listen port** |
| Image size | ≤ **15 GB** uncompressed |
| Model weights | Mount **NAS** or **OSS** — ephemeral disk is lost on instance recycle |
| Warmup | Enable **Initializer** (shell command or code hook) to load model before first request |

**Example startup pattern** (illustrative — tune per model/GPU):

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /mnt/nas/models/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 64 \
  --max-model-len 8192
```

**Production-oriented vLLM flags** (adjust per card and model size):

| Flag / setting | Guidance |
|----------------|----------|
| `--gpu-memory-utilization` | ~**0.85–0.90**; leave headroom for traffic spikes |
| `--max-num-seqs` | Start **32–128** on large GPUs (e.g. Ada 48GB); lower if OOM |
| `--max-model-len` | Set to real SLA max, not model max — improves batching |
| Client `max_tokens` | Cap per request (**256–512** for chat APIs) to improve batch efficiency |
| Prefix caching | Enable when many requests share system prompts |

### 3.4 Instance type for vLLM

| Pattern | Instance type | `min instances` | Notes |
|---------|---------------|-----------------|-------|
| Dev / sparse traffic | **Elastic** | `0` | Lowest cost; accept **10–30s** cold start (model + image) |
| Production chat API | **Elastic** | **≥ 1** | Reduces cold start; still scales out on spikes |
| Stable high QPS | **Resident** (prepaid pool) | Per pool allocation | Predictable cost/latency; no elastic↔resident switch after create |
| Mixed traffic | **Hybrid** (where available) | Baseline resident + elastic burst | Peak/off-peak cost balance |

**Important**: Elastic and resident instance types **cannot be switched** after function creation.

---

## 4. Batch Inference Scenarios

### 4.1 Scenario matrix

| Scenario | Traffic shape | Processing time | Cold start tolerance | FC pattern |
|----------|---------------|-----------------|----------------------|------------|
| **Quasi-real-time** | Sparse (few–10⁴ calls/day) | Seconds–minutes | High | Elastic GPU, `min instances=0`, pay per GB·s |
| **Online chat / API** | Steady or bursty | Sub-second–tens of seconds | Low | `min instances≥1`, LLM metrics, optional resident pool |
| **Offline batch scoring** | Large job, many prompts | Minutes–hours | High | **Async invoke** + OSS input/output; timeout up to **86400s** |
| **Throughput saturation** | Sustained high QPS | Per-token | Low | Multiple GPU instances; capacity plan on **tokens/sec** not raw QPS |

Official quasi-real-time guide: [GPU quasi-real-time inference](https://help.aliyun.com/zh/functioncompute/fc-3-0/user-guide/quasi-real-time-inference-scenarios). Low daily GPU utilization (e.g. &lt;12h/day) often sees large savings vs always-on ECS GPU.

### 4.2 Two layers of “batching”

```
Client requests
      │
      ▼
┌─────────────────────────────────────┐
│  FC: scale GPU instances (elastic)   │  ← cross-instance parallelism
└─────────────────────────────────────┘
      │ per instance
      ▼
┌─────────────────────────────────────┐
│  vLLM: continuous batching           │  ← in-process request multiplexing
│  (PagedAttention / max-num-seqs)     │
└─────────────────────────────────────┘
```

| Layer | Knob | When to change |
|-------|------|----------------|
| **vLLM (in-container)** | `--max-num-seqs`, `--max-model-len`, client `max_tokens` | GPU under-utilized or OOM; tune first |
| **FC instance concurrency** | Per-instance concurrent invocations | See §4.3 |
| **FC provisioned / min instances** | Warm capacity | TTFT / cold-start SLA |

### 4.3 FC instance concurrency vs vLLM

Per [quasi-real-time inference](https://help.aliyun.com/zh/functioncompute/fc-3-0/user-guide/quasi-real-time-inference-scenarios):

| Application type | Recommended FC instance concurrency |
|------------------|-------------------------------------|
| **Compute-intensive, no in-engine batching** | **Default 1** |
| **Engine supports request batch aggregation** (vLLM, SGLang, etc.) | **Keep 1** — let vLLM continuous batching handle multiplexing; scale **instance count** instead |
| **Legacy single-request handlers** (one request = one full GPU forward) | Raise concurrency only if the process is explicitly multi-request safe |

> **Anti-pattern**: Setting high FC instance concurrency **and** running one vLLM server per instance without tuning — can cause GPU OOM or duplicate model loads. Prefer **one vLLM process per GPU instance**, concurrency **1**, scale horizontally.

### 4.4 Offline batch job pattern

For large batch scoring (not interactive chat):

1. **Input**: Upload prompt file(s) to **OSS**; trigger via OSS / EventBridge / async HTTP
2. **Function**: GPU function reads batch from OSS, runs vLLM generate in chunks, writes results to OSS
3. **Config**: `timeout` → max (**86400s**); mount OSS + sufficient NAS if model not in image
4. **Reliability**: **Async invoke** + `maximumRetryAttempts` + **DLQ** (`destination.onFailure`)
5. **Cost**: No provisioned instances; accept cold start on first batch after idle

See `assets/example-config.yaml` → `gpu_vllm_batch`.

---

## 5. Cold Start & Warmup

| Phase | Typical duration | Mitigation |
|-------|------------------|------------|
| Image pull + container start | Seconds | Smaller image; ACR same-region |
| Model load to GPU | Seconds–minutes | **Initializer** warmup; **NAS**-cached weights |
| First inference (JIT/compile) | Variable | Warmup request in Initializer |
| **End-to-end** (common models) | **~10–30s** | `min instances≥1`; resident pool for strict SLA |

Configure **Instance warmup (Initializer)** in GPU function console: run model load script before traffic.

---

## 6. Observability (LLM Metrics)

| Requirement | Detail |
|-------------|--------|
| Scope | **GPU functions only** |
| Engines | **vLLM** (metrics on by default), **SGLang** (`--enable-metrics`) |
| Log config | **Custom** log config required — auto log config **cannot** enable LLM metrics |

**Key metrics** (optimize batching and capacity):

| Metric | Use |
|--------|-----|
| Token Throughput (tokens/sec) | Primary capacity signal (not raw QPS) |
| Time to First Token (TTFT) | User-perceived latency |
| Queue Time | Backpressure — scale instances or tune `max-num-seqs` |
| Prefill / Decode Time | Bottleneck analysis |
| Requests Status (Running/Waiting) | Saturation |

Docs: [LLM indicator monitoring](https://help.aliyun.com/zh/functioncompute/fc/user-guide/llm-indicator-monitoring), [Prometheus integration](https://help.aliyun.com/zh/functioncompute/fc/user-guide/integrating-prometheus-metric-monitoring-for-llm-inference-service-in-function-compute).

**Alerting suggestions**:

| Signal | Threshold idea | Action |
|--------|----------------|--------|
| Queue Time p99 | Sustained high | Scale `min instances` or max instances |
| TTFT p99 | Above SLA | Warmup / resident instances / smaller model |
| Token throughput flat, CPU/GPU low | Under-batched | Increase `--max-num-seqs` if VRAM allows |
| OOM / function errors | Spike | Lower `--gpu-memory-utilization` or `--max-num-seqs` |

---

## 7. Quotas & Limits (GPU-specific)

| Limit | Typical value | Notes |
|-------|---------------|-------|
| GPU cards per account per region | **30** (default) | [Quota center](https://quotas.console.aliyun.com/products/fc/quotas) — request increase if needed |
| Instance types after create | **No switch** | Elastic ↔ resident immutable |
| GPU card families | Ada, Ada.2, Ada.3, Hopper, Xpu.1, … | Region-dependent availability |
| Example Ada spec | 48 GB VRAM, 8 vCPU, 64 GB RAM | See [creating GPU function](https://help.aliyun.com/zh/functioncompute/fc/user-guide/creating-a-gpu-function/) |

CPU function limits (128 MB–3072 MB memory, etc.) in [core-concepts.md](core-concepts.md) **do not apply** to GPU function sizing — use GPU console specs.

---

## 8. Agent Decision Flow

```
User needs LLM inference on FC?
├─ Quick deploy, standard OpenAI API, minimal ops
│   └─► Function AI Model Service + vLLM (Path A)
├─ Custom image / ComfyUI / RAG / fine-grained vLLM flags
│   └─► GPU Function + custom-container (Path B)
├─ Sparse traffic, cost-sensitive, tolerates cold start
│   └─► Elastic GPU, min=0, NAS for weights (quasi-real-time)
├─ Production API, strict TTFT
│   └─► min instances≥1 or resident pool + LLM metrics + Initializer
└─ Large offline scoring
    └─► Async + OSS batch + long timeout, no provisioned
```

---

## 9. Related Ops in This Skill

| Task | Where |
|------|-------|
| GPU execution flows (agent steps) | [SKILL.md § GPU Function Operations](../SKILL.md#operation-gpu-function-vllm--batch) |
| CLI command index | [cli-usage.md § GPU](cli-usage.md#gpu-functions-vllm--batch) |
| SDK operation map | [api-sdk-usage.md § GPU](api-sdk-usage.md#gpu-functions) |
| Async + DLQ for batch jobs | [core-concepts.md](core-concepts.md) AsyncConfig |
| Generic cold start | [core-concepts.md](core-concepts.md#cold-start-mechanics) |
| OOM / timeout faults | [knowledge-base.md](knowledge-base.md) |
| Example YAML | [assets/example-config.yaml](../assets/example-config.yaml) |

---

## 10. CLI / API / SDK by Scenario

All paths use **FC 3.0 ROA** (`FC/2023-03-30`), endpoint `https://fcv3.<region>.aliyuncs.com`.

| Scenario | Primary APIs | CLI (`aliyun fc-open`) | SDK (`github.com/alibabacloud-go/fc-20230330/v4`) |
|----------|--------------|------------------------|---------------------------------------------------|
| **A. Function AI + vLLM** | Function AI control plane (not `fc-open`) | Console / Serverless Devs | Out of `fc-open` scope — see §10.1 |
| **B1. Online vLLM GPU function** | CreateFunction, PutScalingConfig, CreateTrigger | §10.2–10.4 | §10.8 |
| **B2. Quasi-real-time (sparse)** | Same + `minInstances: 0` | §10.3 | `PutScalingConfig` |
| **B3. Offline batch** | CreateFunction, PutAsyncInvokeConfig, InvokeFunction (Async) or OSS trigger | §10.5–10.6 | §10.8 |
| **Ops / tune** | UpdateFunction, GetFunction, GetScalingConfig | §10.7 | Same methods |

### 10.1 Path A — Function AI Model Service (vLLM)

**Not exposed via `aliyun fc-open`.** Use:

| Method | When |
|--------|------|
| [Function AI 控制台](https://cap.console.aliyun.com/) | Create project → Model Service → framework **vLLM** |
| [Serverless Devs](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/install-serverless-devs-and-docker) | IaC deploy of model services (product-specific templates) |

Post-deploy inference uses the **service Endpoint + API key** from the console (OpenAI-compatible), not `POST .../invocations` on a hand-built GPU function.

**This skill (`alicloud-fc-ops`)** covers Path B GPU functions via `fc-open` / Go SDK. For Function AI-only tasks, use console docs or a dedicated Function AI skill when available.

### 10.2 Create GPU Function (custom-container + vLLM)

**API**: `POST /2023-03-30/functions` (`CreateFunction`, `fc:CreateFunction`)

**CLI** (replace placeholders; image must exist in ACR same region):

```bash
aliyun fc-open POST /2023-03-30/functions --body "$(cat <<'EOF'
{
  "functionName": "vllm-qwen-online",
  "runtime": "custom-container",
  "handler": "index.handler",
  "cpu": 8,
  "memorySize": 65536,
  "diskSize": 512,
  "timeout": 600,
  "instanceConcurrency": 1,
  "role": "acs:ram::{{account_id}}:role/fc-gpu-exec",
  "internetAccess": true,
  "gpuConfig": {
    "gpuType": "fc.gpu.ada.1",
    "gpuMemorySize": 49152
  },
  "customContainerConfig": {
    "image": "registry.{{region}}.aliyuncs.com/{{namespace}}/vllm-qwen:latest",
    "port": 8000,
    "command": [
      "python3", "-m", "vllm.entrypoints.openai.api_server",
      "--model", "/mnt/nas/models/Qwen2.5-7B-Instruct",
      "--host", "0.0.0.0", "--port", "8000",
      "--gpu-memory-utilization", "0.90",
      "--max-num-seqs", "64"
    ]
  },
  "instanceLifecycleConfig": {
    "initializer": {
      "handler": "index.initializer",
      "timeout": 300
    }
  },
  "nasConfig": {
    "userId": 0,
    "groupId": 0,
    "mountPoints": [{
      "serverAddr": "{{nas_mount_target}}",
      "mountDir": "/mnt/nas",
      "enableTls": false
    }]
  },
  "logConfig": {
    "project": "{{sls_project}}",
    "logstore": "{{sls_logstore}}",
    "enableLlmMetrics": true,
    "enableRequestMetrics": true,
    "enableInstanceMetrics": true
  }
}
EOF
)"
```

| Field | Notes |
|-------|-------|
| `gpuConfig.gpuType` | e.g. `fc.gpu.ada.1`, `fc.gpu.ampere.1`, `fc.gpu.tesla.1` — region/catalog dependent |
| `gpuConfig.gpuMemorySize` | MB, multiple of **1024** (e.g. `49152` ≈ 48 GB) |
| `cpu` / `memorySize` | Required with GPU; ratio CPU:memory(GB) between **1:1** and **1:4** |
| `customContainerConfig` | Mutually exclusive with `code` — use ACR image + `port` for HTTP |
| `instanceConcurrency` | **1** for vLLM (see §4.3) |
| `logConfig.enableLlmMetrics` | Requires **custom** log project/logstore (not `auto`) |

**Validate**:

```bash
aliyun fc-open GET /2023-03-30/functions/vllm-qwen-online | jq '{state, runtime, gpuConfig, instanceConcurrency}'
```

### 10.3 Elastic scaling — `minInstances` (online vs quasi-real-time)

**API**: `PUT /2023-03-30/functions/{functionName}/scaling-config?qualifier=LATEST` (`PutScalingConfig`)

**Online API** (`minInstances ≥ 1`, lower cold start):

```bash
aliyun fc-open PUT "/2023-03-30/functions/vllm-qwen-online/scaling-config?qualifier=LATEST" \
  --body '{"minInstances": 1, "enableOnDemandScaling": true}'
```

**Quasi-real-time** (sparse traffic, scale to zero):

```bash
aliyun fc-open PUT "/2023-03-30/functions/vllm-qwen-online/scaling-config?qualifier=LATEST" \
  --body '{"minInstances": 0, "enableOnDemandScaling": true}'
```

**Resident pool** (prepaid GPU pool — set at create time in console; tune via API):

```bash
aliyun fc-open PUT "/2023-03-30/functions/vllm-qwen-online/scaling-config?qualifier=LATEST" \
  --body '{
    "minInstances": 2,
    "residentPoolId": "fc-pool-xxxxxxxx",
    "enableOnDemandScaling": false
  }'
```

**Inspect**:

```bash
aliyun fc-open GET "/2023-03-30/functions/vllm-qwen-online/scaling-config?qualifier=LATEST"
aliyun fc-open GET /2023-03-30/scaling-configs
```

### 10.4 HTTP trigger — OpenAI-compatible `/v1/chat/completions`

vLLM serving is **HTTP-first**; prefer HTTP trigger over raw `InvokeFunction` event JSON.

**API**: `POST /2023-03-30/functions/{functionName}/triggers` (`CreateTrigger`)

```bash
aliyun fc-open POST /2023-03-30/functions/vllm-qwen-online/triggers --body "$(cat <<'EOF'
{
  "triggerName": "http-vllm",
  "triggerType": "http",
  "triggerConfig": {
    "authType": "anonymous",
    "methods": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
  }
}
EOF
)"
```

**Get public URL** (from trigger response or console):

```bash
aliyun fc-open GET /2023-03-30/functions/vllm-qwen-online/triggers/http-vllm \
  | jq -r '.httpTrigger.urlInternet // .triggerConfig'
```

**Test inference** (after function ACTIVE):

```bash
curl -sS "${HTTP_TRIGGER_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 128
  }'
```

### 10.5 Offline batch — async invoke + DLQ

**API**: `PUT /2023-03-30/functions/{functionName}/async-invoke-config` (`PutAsyncInvokeConfig`)

```bash
aliyun fc-open PUT /2023-03-30/functions/vllm-batch-scorer/async-invoke-config \
  --body "$(cat <<'EOF'
{
  "maxAsyncEventAgeInSeconds": 86400,
  "maximumRetryAttempts": 2,
  "destinationConfig": {
    "onFailure": {
      "destination": "acs:fc:{{region}}:{{account_id}}:services/{{service}}/functions/{{dlq_function}}/invocations"
    }
  }
}
EOF
)"
```

**Submit batch job** (one event per job; function reads `oss://bucket/batch-jobs/input/...`):

```bash
aliyun fc-open POST /2023-03-30/functions/vllm-batch-scorer/invocations \
  --header "x-fc-invocation-type=Async" \
  --body '{
    "inputPrefix": "oss://my-bucket/batch-jobs/input/job-20260519/",
    "outputPrefix": "oss://my-bucket/batch-jobs/output/job-20260519/"
  }'
```

**Poll async tasks**:

```bash
aliyun fc-open GET "/2023-03-30/functions/vllm-batch-scorer/async-invocations"
```

GPU batch function create: same as §10.2 with `timeout: 86400`, `minInstances: 0`, mount `ossMountConfig` for input/output paths.

### 10.6 OSS trigger — event-driven batch

**API**: `CreateTrigger` with `triggerType: oss`

```bash
aliyun fc-open POST /2023-03-30/functions/vllm-batch-scorer/triggers --body "$(cat <<'EOF'
{
  "triggerName": "oss-batch-input",
  "triggerType": "oss",
  "invocationRole": "acs:ram::{{account_id}}:role/fc-oss-trigger",
  "triggerConfig": {
    "bucketName": "my-batch-bucket",
    "events": ["oss:ObjectCreated:PutObject"],
    "filter": {
      "key": {"prefix": "batch-jobs/input/"}
    }
  }
}
EOF
)"
```

Function code/container must parse OSS event payload and write results under `batch-jobs/output/`.

### 10.7 Day-2 operations

| Goal | CLI |
|------|-----|
| Update image / vLLM flags | `aliyun fc-open PUT /2023-03-30/functions/{name} --body '{"customContainerConfig":{...}}'` |
| Enable LLM metrics later | `PUT` function with `logConfig.enableLlmMetrics: true` (custom log config required) |
| Concurrency cap (account protection) | `PUT /2023-03-30/functions/{name}/concurrency-config --body '{"reservedConcurrency": 10}'` |
| Delete function | `DELETE /2023-03-30/functions/{name}` |
| List GPU functions | `GET /2023-03-30/functions` then filter `.gpuConfig != null` in `jq` |

```bash
aliyun fc-open GET /2023-03-30/functions | jq '[.functions[] | select(.gpuConfig != null) | {functionName, gpuConfig, state}]'
```

### 10.8 Go SDK (representative)

```go
// Create GPU function — same body fields as §10.2 CLI JSON
resp, err := fcClient.CreateFunction(&client.CreateFunctionRequest{
    FunctionName: tea.String("vllm-qwen-online"),
    Runtime:      tea.String("custom-container"),
    Handler:      tea.String("index.handler"),
    Cpu:          tea.Float32(8),
    MemorySize:   tea.Int32(65536),
    DiskSize:     tea.Int32(512),
    Timeout:      tea.Int32(600),
    InstanceConcurrency: tea.Int32(1),
    Role:         tea.String(os.Getenv("FC_RAM_ROLE_ARN")),
    GpuConfig: &client.GPUConfig{
        GpuType:       tea.String("fc.gpu.ada.1"),
        GpuMemorySize: tea.Int32(49152),
    },
    CustomContainerConfig: &client.CustomContainerConfig{
        Image: tea.String(os.Getenv("FC_IMAGE")),
        Port:  tea.Int32(8000),
        Command: []*string{
            tea.String("python3"), tea.String("-m"), tea.String("vllm.entrypoints.openai.api_server"),
            // ...
        },
    },
    LogConfig: &client.LogConfig{
        Project:            tea.String(os.Getenv("SLS_PROJECT")),
        Logstore:           tea.String(os.Getenv("SLS_LOGSTORE")),
        EnableLlmMetrics:   tea.Bool(true),
        EnableRequestMetrics: tea.Bool(true),
    },
})

// Scaling
_, err = fcClient.PutScalingConfig(tea.String("vllm-qwen-online"), &client.PutScalingConfigRequest{
    Qualifier: tea.String("LATEST"),
    MinInstances: tea.Int64(1),
    EnableOnDemandScaling: tea.Bool(true),
})

// Async batch invoke
_, err = fcClient.InvokeFunction(tea.String("vllm-batch-scorer"), &client.InvokeFunctionRequest{
    Body: []byte(`{"inputPrefix":"oss://..."}`),
    XFcInvocationType: tea.String("Async"),
})
```

Struct names may vary slightly by SDK version — generate from [CreateFunctionInput](https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-struct-createfunctioninput).

### 10.9 RAM actions (minimum for agents)

| Action | Use |
|--------|-----|
| `fc:CreateFunction` / `fc:UpdateFunction` / `fc:GetFunction` / `fc:ListFunctions` | GPU function lifecycle |
| `fc:PutScalingConfig` / `fc:GetScalingConfig` | `minInstances`, resident pool |
| `fc:CreateTrigger` / `fc:GetTrigger` | HTTP / OSS triggers |
| `fc:InvokeFunction` | Sync test or async batch submit |
| `fc:PutAsyncInvokeConfig` | Batch retry + DLQ |
| `ram:PassRole` | Attach execution / trigger roles |

---

## 11. Official Links

## 12. Quick Reference — GPU Execution Blocks (from SKILL.md)

### Pre-flight (GPU-specific)

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| GPU quota | [Quota center](https://quotas.console.aliyun.com/products/fc/quotas) | Cards available in region | HALT; request quota |
| ACR image | Image in same region as function | Pullable by FC | HALT; push image |
| NAS/OSS for weights | Mount config valid | Model path reachable from container | HALT; fix mount |
| SLS for LLM metrics | Custom `project` + `logstore` | Not `auto` if `enableLlmMetrics` | Use custom logConfig |

### Execution — Create GPU function (CLI excerpt)

Full body: [§10.2](#102-create-gpu-function-custom-container--vllm).

```bash
aliyun fc-open POST /2023-03-30/functions --body "$(cat <<EOF
{
  "functionName": "{{user.function_name}}",
  "runtime": "custom-container",
  "handler": "index.handler",
  "cpu": 8,
  "memorySize": 65536,
  "diskSize": 512,
  "timeout": {{user.timeout|default:600}},
  "instanceConcurrency": 1,
  "role": "{{user.ram_role_arn}}",
  "gpuConfig": {
    "gpuType": "{{user.gpu_type|default:fc.gpu.ada.1}}",
    "gpuMemorySize": {{user.gpu_memory_mb|default:49152}}
  },
  "customContainerConfig": {
    "image": "{{user.acr_image}}",
    "port": {{user.listen_port|default:8000}},
    "command": {{user.container_command}}
  },
  "logConfig": {
    "project": "{{user.sls_project}}",
    "logstore": "{{user.sls_logstore}}",
    "enableLlmMetrics": true
  }
}
EOF
)"
```

### Execution — Scaling + HTTP inference

```bash
# Warm capacity (online API)
aliyun fc-open PUT "/2023-03-30/functions/{{user.function_name}}/scaling-config?qualifier=LATEST" \
  --body '{"minInstances": {{user.min_instances|default:1}}, "enableOnDemandScaling": true}'

# HTTP trigger
aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/triggers --body "$(cat <<EOF
{
  "triggerName": "http-vllm",
  "triggerType": "http",
  "triggerConfig": {"authType": "anonymous", "methods": ["GET","POST","PUT","DELETE","HEAD","OPTIONS"]}
}
EOF
)"

# Test (after ACTIVE) — use urlInternet from GetTrigger
curl -sS "{{user.http_trigger_url}}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"{{user.model_name}}","messages":[{"role":"user","content":"ping"}],"max_tokens":32}'
```

### Execution — Async batch job

```bash
aliyun fc-open PUT /2023-03-30/functions/{{user.function_name}}/async-invoke-config \
  --body '{"maxAsyncEventAgeInSeconds": 86400, "maximumRetryAttempts": 2}'

aliyun fc-open POST /2023-03-30/functions/{{user.function_name}}/invocations \
  --header "x-fc-invocation-type=Async" \
  --body '{{user.batch_payload}}'
```

### Post-execution Validation

1. `GetFunction` → `state == ACTIVE`, `gpuConfig` present
2. `GetScalingConfig` → `minInstances` matches intent
3. For HTTP: `GetTrigger` → call `/v1/chat/completions`, check TTFT in LLM metrics
4. For async batch: `GET .../async-invocations` until terminal state

### Failure Recovery (GPU)

| Error | Agent Action |
|-------|--------------|
| GPU quota exceeded | HALT; quota ticket or reduce `minInstances` |
| Image pull failed | Verify ACR ACL, same region, image size ≤ 15 GB |
| CUDA OOM in logs | Lower vLLM `--max-num-seqs`; see [knowledge-base.md](knowledge-base.md) FC-GPU-001 |
| Cold start SLA miss | Raise `minInstances`; enable Initializer; see FC-GPU-002 |

## 13. Official Links

| Topic | URL |
|-------|-----|
| Create GPU function | https://help.aliyun.com/zh/functioncompute/fc/user-guide/creating-a-gpu-function/ |
| Quasi-real-time / batch-friendly GPU | https://help.aliyun.com/zh/functioncompute/fc-3-0/user-guide/quasi-real-time-inference-scenarios |
| vLLM model service (Function AI) | https://help.aliyun.com/zh/functioncompute/fc-3-0/create-a-model-service-using-the-vllm-inference-engine |
| LLM metrics | https://help.aliyun.com/zh/functioncompute/fc/user-guide/llm-indicator-monitoring |
| CreateFunction API | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-createfunction |
| PutScalingConfig | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-putscalingconfig |
| PutAsyncInvokeConfig | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-putasyncinvokeconfig |
| LogConfig (enableLlmMetrics) | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-struct-logconfig |
| GpuConfig | https://help.aliyun.com/zh/functioncompute/fc/developer-reference/api-fc-2023-03-30-struct-gpuconfig |
