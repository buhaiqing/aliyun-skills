# Integration — Function Compute (FC 3.0)

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)
**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Go Runtime Bootstrap

```bash
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    [ "$ARCH" = "aarch64" ] && ARCH="arm64"
    
    mkdir -p /tmp/go-runtime
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    
    export PATH="/tmp/go-runtime/go/bin:$PATH"
    export GOPATH="/tmp/go-workspace"
    export GOCACHE="/tmp/go-cache"
    export GOMODCACHE="/tmp/go-modcache"
    export GOPROXY="https://goproxy.cn,direct"
fi
go version
```

### JIT Go SDK Workflow

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-fc
   cd /tmp/aliyun-sdk-fc
   go mod init fc-script
   ```

2. **Get dependencies:**
   ```bash
   export GOPROXY="https://goproxy.cn,direct"
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/fc-20230330/v4/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file per SKILL.md)

4. **Execute:** `go run ./main.go`

### SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| FC 3.0 | `github.com/alibabacloud-go/fc-20230330/v4/client` |
| FC 2.0 (legacy) | (not used) |

## Cross-Skill Delegation Matrix

### FC → Other Skills

| FC Issue | Delegate To | When |
|----------|-------------|------|
| RAM permission denied | `alicloud-ram-ops` | When function lacks Execute Role or CLI lacks RAM policy |
| VPC network unreachable | VPC skill (when present) | When function can't reach VPC resource |
| SLB backend unhealthy | `alicloud-slb-ops` | When FC behind SLB reports backend errors |
| RDS connection failure | `alicloud-das-ops` | When function can't connect to database |
| OSS code download fails | `alicloud-oss-ops` (when present) | When OSS bucket/object is inaccessible |
| SLS log analysis needed | SLS skill (when present) | When deep log investigation is required |
| CMS alert rule management | `alicloud-cms-ops` | When creating/modifying FC alert rules |

### Other Skills → FC

| Skill | FC Dependency | Notes |
|-------|--------------|-------|
| `alicloud-slb-ops` | FC as SLB backend | Verify function is Active and reachable |
| `alicloud-eventbridge-ops` | FC as EventBridge target | Verify function ARN is correct |
| `alicloud-oss-ops` | FC as OSS trigger target | Verify trigger config is valid |
| `alicloud-sls-ops` | FC as log processing target | Verify function can read/write SLS |
| `alicloud-cms-ops` | FC metrics monitoring | Use FC metrics from `acs_fc` namespace |

## Function ARN Format

```
acs:fc:<region>:<account-id>:functions/<function-name>
acs:fc:<region>:<account-id>:functions/<function-name>/aliases/<alias-name>
```

Example: `acs:fc:cn-hangzhou:123456789:functions/my-function/aliases/prod`

## Environment Variable Loading

Credentials can be sourced from:
```
Shell env (highest) > `.env` file > `~/.aliyun/config.json` > defaults (lowest)
```

### `.env` File Format

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

> **Security**: `.env` MUST be in `.gitignore` — never commit credentials