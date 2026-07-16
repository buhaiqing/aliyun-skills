English | [中文](README_CN.md)

# aliyun-skills

Alibaba Cloud Agent Skills

## Overview

This project is a collection of Alibaba Cloud operations Agent Skills, providing automated operations, monitoring, and management capabilities for cloud products.

> **Requirements & Development Documentation**: See [REQUIREMENTS.md](REQUIREMENTS.md), which contains functional requirements, architecture design, technical specifications, and development guides for all Skills.

## Core Value

**Skills Farm is a Meta Skill system** — transforming operations knowledge into structured, AI Agent-parseable, executable, and verifiable declarative specifications.

### Key Features

| Feature | Description |
|---------|-------------|
| **Placeholder System** | `{{env.*}}` (environment variables), `{{user.*}}` (user input), `{{output.*}}` (output capture), enabling human-machine dual-channel interaction |
| **Delegation** | `SHOULD/SHOULD NOT Use` defines boundaries, cross-product operations are automatically delegated |
| **Generator** | Automatically generates Skill framework templates from OpenAPI specs, supporting human review and refinement |
| **CLI-first Execution** | Prefers `aliyun` CLI (static Go binary); JIT builds Go SDK scripts when CLI is insufficient |
| **Security Mechanism** | Credential isolation (`{{env.*}}` never exposed), operation safety gates (delete/recovery require confirmation) |
| **Cross-platform Design** | Based on standard Markdown + OpenSpec, compatible with multiple Agent frameworks |

## Project Structure

> **Note**: There is no root-level `go.mod` — Go is used via the JIT SDK setup (`alicloud-jit-setup.sh`) and per-skill `scripts/` only. There is also no committed `.env.example`; credentials are configured via `aliyun configure` or by exporting env vars (see [Credential Configuration](#credential-configuration)).

```
aliyun-skills/
├── README.md                          # English version
├── README_CN.md                       # Chinese version
├── REQUIREMENTS.md                    # Requirements & development docs (functional details, architecture design, technical specs)
├── AGENTS.md                          # Agent behavior guide & repo conventions
├── .gitignore                         # Git exclusion rules
├── Makefile                           # Lint / test / validate / runtime cleanup
├── alicloud-jit-setup.sh              # JIT Go SDK one-click setup script
├── scripts/                           # Repo-level tooling (validation, token rollup, harness discovery)
├── docs/                              # GCL spec, harness guide, token-efficiency & memory strategy
│
├── # ── Meta / Cross-cutting Skills ──
├── alicloud-skill-generator/          # Skill Generator (Meta Skill) — scaffold new Skills from OpenAPI spec
├── alicloud-skillopt-ops/             # Legacy SkillOpt compatibility layer (shared lib)
├── alicloud-gcl-runner-ops/           # Generator-Critic-Loop runner + memory/reflexion/strategy engine
├── alicloud-runtime-harness-ops/      # Runtime Harness shared capability (wrapper-first, tracing)
│
├── # ── Discovery / Advisory / Orchestration Skills ──
├── alicloud-topo-discovery/           # Network topology & resource inventory discovery
├── alicloud-aiops-cruise/             # Full-link AIOps inspection (perception agents)
├── alicloud-arch-advisor/             # Architecture review framework
├── alicloud-auto-scaling-orch/        # Elastic scaling orchestration
├── alicloud-sandbox-dev/              # Sandbox development (sidecar mode)
├── alicloud-aiyun-skills/             # (reserved / migration placeholder)
│
├── # ── Product Skills (45 × -ops) ──
├── alicloud-ack-ops/                  # Container Service for Kubernetes (ACK)
├── alicloud-actiontrail-ops/          # ActionTrail
├── alicloud-advisor-ops/              # Advisor (best-practice recommendations)
├── alicloud-agentrun-ops/             # AgentRun
├── alicloud-alb-ops/                  # Application Load Balancer (ALB)
├── alicloud-ask-ops/                  # ASK (Serverless Kubernetes)
├── alicloud-bailian-ops/              # Bailian (百炼) GenAI Platform — LLM, Agent, RAG, Prompt
├── alicloud-billing-ops/              # Billing
├── alicloud-cen-ops/                  # Cloud Enterprise Network (CEN)
├── alicloud-cms-ops/                  # Cloud Monitor Service (CMS)
├── alicloud-das-ops/                  # Database Autonomy Service (DAS)
├── alicloud-dms-ops/                  # Data Management Service (DMS)
├── alicloud-dns-ops/                  # DNS (Alibaba Cloud DNS)
├── alicloud-dts-ops/                  # Data Transmission Service (DTS)
├── alicloud-eci-ops/                  # Elastic Container Instance (ECI)
├── alicloud-ecs-ops/                  # Elastic Compute Service (ECS)
├── alicloud-eip-ops/                  # Elastic IP Address (EIP)
├── alicloud-elasticsearch-ops/        # Elasticsearch
├── alicloud-ess-ops/                  # Auto Scaling (ESS)
├── alicloud-fc-ops/                   # Function Compute (FC)
├── alicloud-kms-ops/                  # Key Management Service (KMS)
├── alicloud-mongodb-ops/              # ApsaraDB for MongoDB
├── alicloud-nas-ops/                  # File Storage NAS
├── alicloud-nat-ops/                  # NAT Gateway
├── alicloud-oss-ops/                  # Object Storage Service (OSS)
├── alicloud-polar-mysql-ops/          # PolarDB for MySQL
├── alicloud-polar-oracle-ops/         # PolarDB for Oracle (compatible)
├── alicloud-polar-pg-ops/             # PolarDB for PostgreSQL (compact)
├── alicloud-polar-postgresql-ops/     # PolarDB for PostgreSQL
├── alicloud-pts-ops/                  # Performance Testing Service (PTS)
├── alicloud-ram-ops/                  # Resource Access Management (RAM)
├── alicloud-rds-ops/                  # ApsaraDB RDS
├── alicloud-redis-ops/                # ApsaraDB for Redis/Tair
├── alicloud-resourcemanager-ops/      # Resource Manager
├── alicloud-sas-ops/                  # Security Center (SAS)
├── alicloud-slb-ops/                  # Server Load Balancer (SLB/CLB)
├── alicloud-sls-ops/                  # Simple Log Service (SLS)
├── alicloud-sms-ops/                  # Short Message Service (SMS)
├── alicloud-terraform-ops/            # Terraform / IaC
├── alicloud-voice-ops/                # Voice / Intelligent Speech Interaction
├── alicloud-vpc-ops/                  # Virtual Private Cloud (VPC)
└── alicloud-waf-ops/                  # Web Application Firewall (WAF)
```

> A standard product Skill (`alicloud-<product>-ops/`) contains: `SKILL.md`, `references/` (`core-concepts.md`, `cli-usage.md`, `api-sdk-usage.md`, `troubleshooting.md`, `rubric.md`, `prompt-templates.md`, `monitoring.md`, etc.), `assets/` (`example-config.yaml`, `eval_queries.json`), and per-skill `scripts/` + `test-*.sh` where applicable.

## Quick Start

### 1. Install aliyun CLI

```bash
# Official one-click install (auto-detects OS + architecture)
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

### 2. Configure Credentials

```bash
# Method 1: Environment variables (recommended)
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Method 2: Interactive configuration
aliyun configure
```

### 3. Generate a New Skill

Reference the generator in an Agent Runtime, then provide a prompt:

> "Generate a Skill for Alibaba Cloud ECS, name alicloud-ecs-ops, core features: instance lifecycle management, disks, snapshots"

**Generated structure**:
```
alicloud-ecs-ops/
├── SKILL.md
├── references/
│   ├── cli-usage.md
│   ├── api-sdk-usage.md
│   ├── core-concepts.md
│   ├── integration.md
│   ├── monitoring.md
│   └── troubleshooting.md
└── assets/
    └── example-config.yaml
```

## aliyun CLI Behavior

### Correct CLI Invocation

```bash
# RPC-style API (most products)
aliyun <product> <OperationName> --RegionId cn-hangzhou --Param1 value1

# Examples
aliyun ecs DescribeInstances --RegionId cn-hangzhou
aliyun rds DescribeDBInstances --RegionId cn-hangzhou

# JMESPath field extraction
aliyun ecs DescribeInstances --output cols=InstanceId,Status rows=Instances.Instance[]

# Polling with waiter
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300
```

## Installing aliyun CLI

**Official one-click install (auto-detects OS + architecture):**
```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

`install.sh` handles automatically:
- **macOS**: Downloads the `universal` package (Intel + Apple Silicon compatible)
- **Linux AMD64**: `aliyun-cli-linux-latest-amd64.tgz`
- **Linux ARM64**: `aliyun-cli-linux-latest-arm64.tgz`
- Installs to `/usr/local/bin/aliyun`

**Alternative methods:**
```bash
# macOS Homebrew
brew install aliyun-cli
```

## Credential Configuration

### Method 1: Generate .env from Template (recommended)

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit configuration with actual credentials
vim .env
```

`.env.example` contains the following variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | AccessKey ID | `YOUR_ACCESS_KEY_ID` |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | AccessKey Secret | `YOUR_ACCESS_KEY_SECRET` |
| `ALIBABA_CLOUD_REGION_ID` | Default region | `cn-hangzhou` |

**Load environment variables:**
```bash
source .env
```

### Method 2: Export Environment Variables Directly

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

### Method 3: Interactive Configuration

```bash
aliyun configure
```

**Configuration file:**
```json
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "YOUR_AK",
      "access_key_secret": "YOUR_SECRET",
      "region_id": "cn-hangzhou"
    }
  ]
}
```

## Skill Authoring Guidelines

- CLI examples: use `bash`, JSON uses `json`, YAML uses `yaml`
- Tables: product lists, monitoring metrics, alert thresholds
- Credential configuration: see the environment variables section above

## Validation

```bash
# Check Markdown formatting
npx markdownlint-cli2 "alicloud-*/SKILL.md"
```

Verify: CLI commands are executable, links are valid, examples are correct.

## References

- [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud SDK for Go](https://github.com/alibabacloud-go)
- [Agent Skills OpenSpec](https://agentskills.io/specification)
- [Alibaba Cloud Documentation](https://help.aliyun.com)

## FAQ

| Q | A |
|---|---|
| Relationship between Skills and MCP Server? | Skills are documentation, MCP is the execution service |
| Can one Skill cover multiple products? | Single responsibility is recommended; cross-reference via References |
| How to update a Skill? | Modify the files, then update the version and changelog |

---

### Related Documents

| Document | Description |
|----------|-------------|
| [REQUIREMENTS.md](REQUIREMENTS.md) | **Requirements & Development Documentation** — functional details, architecture design, technical specs, and development guides for all Skills |
| [alicloud-skill-generator/SKILL.md](alicloud-skill-generator/SKILL.md) | Complete usage guide for the Skill Generator |
| [SKILL-MATRIX.md](SKILL-MATRIX.md) | Skill capability matrix — what each skill can do, by capability dimension |
| [README_CN.md](README_CN.md) | Chinese version of this document |

---

See `alicloud-skill-generator/SKILL.md` for complete usage of the generator.
