# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alibaba Cloud Operations Agent Skills Farm — a **Meta Skill** system that transforms operational knowledge into structured, AI-agent-parseable, executable, and verifiable declarative specifications.

**Core Architecture:**
- **CLI-first execution**: Primary path uses `aliyun` CLI (static Go binary, no runtime dependencies)
- **JIT Go SDK fallback**: When CLI doesn't support an operation, dynamically build and run Go SDK scripts
- **Multi-stage Docker builds**: runtime/dev/agent profiles for sandboxed execution

## Key Conventions

### Placeholder System
| Pattern | Meaning | Agent Action |
|---------|---------|--------------|
| `{{env.*}}` | Environment variable | **NEVER ask user**; fail if unset |
| `{{user.*}}` | User input | Ask once; reuse across session |
| `{{output.*}}` | Captured output | Parse per OpenAPI spec |

### Credential Security
- **NEVER** log or print `ALIBABA_CLOUD_ACCESS_KEY_SECRET` — always mask as `abcd****`
- Verify env vars exist before execution; HALT if missing
- Use existence checks only: `test -n "$var" && echo "set"`

### Skill Structure
Each `alicloud-[product]-ops/` contains:
- `SKILL.md` — Main runbook (triggers, flows, recovery, safety gates)
- `references/` — CLI usage, API/SDK, core concepts, troubleshooting, monitoring
- `assets/` — Example configs

## Development Commands

### Validate Skills
```bash
# Markdown linting
npx markdownlint-cli2 "alicloud-*/SKILL.md"

# YAML validation for configs
python3 -c "import yaml; yaml.safe_load(open('alicloud-*/assets/*.yaml'))"
```

### Docker Sandbox
```bash
# Build and run
docker compose --profile dev up -d
docker compose --profile interactive run interactive

# Validate CLI
docker compose --profile interactive run interactive -- aliyun version
```

### Generate New Skill
Use `alicloud-skill-generator` meta-skill:
```
"Generate alicloud-xyz-ops for product XYZ with operations: create, describe, modify, delete"
``

Output: `alicloud-xyz-ops/` directory with complete structure.

## Execution Flow Protocol

Every operation follows: **Pre-flight → Execute → Validate → Recover**

1. **Pre-flight**: Check CLI/deps, credentials, resource existence
2. **Execute**: CLI primary, Go SDK fallback (JIT build in `/tmp/aliyun-sdk-workspace`)
3. **Validate**: Response success check, data presence, freshness
4. **Recover**: Error taxonomy handling (retry vs HALT vs delegate)

## Go SDK JIT Pattern

```go
// Standard JIT SDK script structure
package main

import (
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    // Product-specific SDK
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("product.aliyuncs.com"),
    }
    // ... operation logic
}
```

Execute:
```bash
cd /tmp/aliyun-sdk-workspace && go mod init sdk-script && go run ./main.go
```

## Cross-Skill Delegation

When operation spans products, delegate to appropriate skill:
| Namespace | Delegate To |
|-----------|-------------|
| `acs_ecs_dashboard` | `alicloud-ecs-ops` |
| `acs_rds_dashboard` | `alicloud-rds-ops` |
| `acs_slb_dashboard` | `alicloud-slb-ops` |

## Five Core Standards (Quality Gates)

Generated skills must satisfy:
1. **Clear Boundaries**: SHOULD/SHOULD NOT triggers with delegation rules
2. **Structured I/O**: Placeholder conventions with documented types
3. **Explicit Steps**: Pre-flight → Execute → Validate → Recover flow
4. **Failure Strategies**: Error taxonomy (≥10 codes), HALT vs retry logic
5. **Single Responsibility**: One product, one primary resource; delegate cross-product

## CLI Applicability Levels

| Level | Meaning | references/cli-usage.md |
|-------|---------|-------------------------|
| `cli-first` | CLI fully supports product | Omit gaps unless partial |
| `dual-path` | CLI supports, SDK fallback | **Required** with coverage gap table |
| `sdk-only` | CLI doesn't expose product | **Omit** |
| `cli-only` | Read-only discovery | **Omit** |

## Environment Variables

Required for all skills:
- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID` (default: `cn-hangzhou`)

## Go Runtime Requirements

- Minimum: Go 1.21+
- JIT recommended: Go 1.24+
- GOPROXY: `https://goproxy.cn,direct` (China CDN mirror)