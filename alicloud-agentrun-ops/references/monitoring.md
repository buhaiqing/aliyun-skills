# Monitoring Guide — AgentRun Sandbox

> **Purpose**: Observability, metrics, and alerting patterns for AgentRun Sandbox operations.

## 1. Observability Overview

AgentRun Sandbox provides two levels of observability:
- **Control Plane**: Template and sandbox lifecycle via ActionTrail
- **Data Plane**: Sandbox health, execution metrics, process monitoring

---

## 2. Health Check

### 2.1 Sandbox Health API

```
GET https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/health
```

**Response**:
```json
{
  "status": "ok",
  "service": "sandbox-code-interpreter",
  "version": "v1",
  "timestamp": "2025-11-15T09:45:01Z",
  "uptime": 1142269582541
}
```

**Usage**:
- Pre-execution check before running code
- Post-creation validation after sandbox becomes READY
- Periodic monitoring for long-running sandboxes

### 2.2 Health Check Integration Pattern

```python
def check_sandbox_health(sandbox_id, account, region, auth_headers):
    """Check sandbox health before operations."""
    url = f"https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandbox_id}/health"
    response = requests.get(url, headers=auth_headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "ok":
            return True, data
    return False, response.text

# Pre-execution pattern
if not check_sandbox_health(sandbox_id, ...):
    raise Exception("Sandbox not healthy, cannot execute code")
```

---

## 3. Metrics

### 3.1 Key Metrics

| Metric | Source | Description | Usage |
|---|---|---|---|
| `SandboxCount` | ListSandboxes | Active sandbox count | Capacity planning |
| `TemplateCount` | ListTemplates | Template inventory | Resource audit |
| `ExecutionTime` | ExecuteCode response | Code execution duration | Performance analysis |
| `SandboxAge` | createdAt + current time | Sandbox lifetime | Lifecycle management (6h limit) |
| `ProcessCount` | ListProcesses | Running processes | Resource utilization |

### 3.2 Execution Metrics

**ExecuteCode Response Fields**:
```json
{
  "results": [
    {"type": "stdout", "text": "..."},
    {"type": "stderr", "text": "..."},
    {"type": "endOfExecution", "status": "ok", "executionTimeMs": 150}
  ]
}
```

**Metric Extraction**:
- `executionTimeMs`: Execution duration
- `status`: `ok` / `error` / `timeout`
- `stdout.length`: Output size

### 3.3 Resource Metrics

**ListFiles Response**:
```json
{
  "entries": [
    {"name": "file.txt", "size": 1024, "type": "file"}
  ]
}
```

**Metric Extraction**:
- Total file count
- Total disk usage (sum of `size`)
- Largest file identification

**Process Metrics** (ListProcesses):
```json
{
  "items": [
    {"processId": 12345, "status": "running", "command": "...", "createdAt": "..."}
  ]
}
```

---

## 4. Logging

### 4.1 ActionTrail (Control Plane)

**Logged Operations**:
- CreateTemplate, UpdateTemplate, DeleteTemplate
- CreateSandbox, StopSandbox, DeleteSandbox
- ActivateTemplateMCP, StopTemplateMCP

**Query via ActionTrail API**:
```bash
# Query sandbox creation events
aliyun actiontrail LookupEvents \
  --EventName "CreateSandbox" \
  --ResourceType "acs:agentrun:*:*:sandbox/*" \
  --StartTime "2025-01-01T00:00:00Z" \
  --EndTime "2025-01-02T00:00:00Z"
```

### 4.2 Execution Logs (Data Plane)

**stdout/stderr via ExecuteCode**:
```json
{
  "results": [
    {"type": "stdout", "text": "console output"},
    {"type": "stderr", "text": "error messages"}
  ]
}
```

**Log Analysis Patterns**:
- Error detection: grep `stderr` for "Error", "Exception", "Traceback"
- Performance profiling: analyze `executionTimeMs`
- Output validation: check `stdout` for expected patterns

---

## 5. Alerting

### 5.1 Recommended Alerts

| Alert Condition | Threshold | Severity | Action |
|---|---|---|---|
| Sandbox creation failure | > 5% failure rate | Warning | Check quota, RAM permissions |
| Sandbox approaching 6h limit | age > 5.5 hours | Warning | Notify user, suggest recreation |
| Code execution timeout rate | > 10% | Warning | Review code complexity |
| Sandbox health check failure | consecutive > 3 | Critical | Investigate sandbox status |
| Template deletion without cleanup | dependent sandboxes exist | Critical | Block deletion, notify user |

### 5.2 Alert Implementation Pattern

```python
def check_sandbox_age(sandbox_id, max_age_hours=5.5):
    """Alert if sandbox approaching 6h limit."""
    sandbox = get_sandbox(sandbox_id)
    age_hours = (datetime.now() - sandbox["createdAt"]).total_seconds() / 3600
    
    if age_hours > max_age_hours:
        alert(f"Sandbox {sandbox_id} age {age_hours:.1f}h approaching 6h limit")
        return "WARNING"
    return "OK"

def check_execution_timeout_rate(sandbox_id, sample_size=10):
    """Alert if high timeout rate."""
    # Sample recent executions
    timeout_count = 0
    for result in recent_executions:
        if result["status"] == "timeout":
            timeout_count += 1
    
    rate = timeout_count / sample_size
    if rate > 0.1:
        alert(f"High timeout rate {rate:.0%} for sandbox {sandbox_id}")
        return "WARNING"
    return "OK"
```

---

## 6. Dashboard Metrics

### 6.1 Recommended Dashboard

| Widget | Metric | Visualization |
|---|---|---|
| Active Sandboxes | `SandboxCount` (status=READY) | Gauge |
| Sandbox Age Distribution | Histogram of `createdAt` | Bar chart |
| Execution Success Rate | `ok` / `total` ratio | Percentage |
| Template Inventory | `TemplateCount` by type | Pie chart |
| Top Processes | Process count by sandbox | Table |

### 6.2 Metrics Collection Pattern

```python
def collect_sandbox_metrics():
    """Collect metrics for dashboard."""
    sandboxes = list_sandboxes(status="READY")
    
    metrics = {
        "total_active": len(sandboxes),
        "by_template": {},
        "age_distribution": [],
        "execution_stats": {}
    }
    
    for sb in sandboxes:
        template = sb["templateName"]
        metrics["by_template"][template] = metrics["by_template"].get(template, 0) + 1
        
        age_hours = (datetime.now() - sb["createdAt"]).total_seconds() / 3600
        metrics["age_distribution"].append(age_hours)
        
        # Execution stats (requires history tracking)
        # ...
    
    return metrics
```

---

## 7. Observability Integration

### 7.1 ARMS Integration

AgentRun sandbox metrics can be integrated with ARMS (Application Real-Time Monitoring Service):

1. **Custom Metrics**: Push execution metrics via ARMS API
2. **Alert Rules**: Configure alerts in ARMS console
3. **Dashboard**: Create ARMS dashboard for sandbox monitoring

### 7.2 Log Service Integration

Execution logs can be shipped to Log Service (SLS):

1. **stdout/stderr collection**: Capture from ExecuteCode responses
2. **SLS shipper**: Send logs to SLS for analysis
3. **Log search**: Query logs for error patterns, performance analysis

---

## 8. Best Practices

### 8.1 Monitoring Checklist

- [ ] Health check before every code execution
- [ ] Track sandbox age (approaching 6h limit)
- [ ] Monitor execution timeout rate
- [ ] Log stdout/stderr for debugging
- [ ] Alert on creation failures (> 5% rate)
- [ ] Periodic sandbox cleanup (> 6h TERMINATED)

### 8.2 Performance Monitoring

| Metric | Target | Action if Below |
|---|---|---|
| Sandbox creation time | < 30s | Investigate service health |
| Code execution latency | < 5s (simple) | Optimize code complexity |
| Health check response | < 1s | Network diagnostics |

### 8.3 Cost Monitoring

| Metric | Target | Action |
|---|---|---|
| Sandbox count per template | Minimize | Consolidate templates |
| Idle sandbox count | 0 | Stop idle sandboxes |
| Execution cost per sandbox | Track | Budget planning |