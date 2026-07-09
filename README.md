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

```
aliyun-skills/
├── README.md                          # English version
├── README_CN.md                       # Chinese version
├── REQUIREMENTS.md                    # Requirements & development docs (functional details, architecture design, technical specs)
├── go.mod                              # Go module configuration (optional)
├── .env.example                       # Environment variable template
├── .gitignore                         # Git exclusion rules
├── alicloud-jit-setup.sh              # JIT Go SDK one-click setup script
├── alicloud-skill-generator/          # Skill Generator (Meta Skill)
│   ├── SKILL.md
│   ├── assets/
│   └── references/
│       ├── alicloud-skill-template.md   # Skill template
│       └── governance-and-adversarial-review.md
├── alicloud-ecs-ops/                  # Elastic Compute Service (ECS)
├── alicloud-rds-ops/                  # ApsaraDB RDS
├── alicloud-redis-ops/                # ApsaraDB for Redis/Tair
├── alicloud-ack-ops/                  # Container Service for Kubernetes (ACK)
├── alicloud-slb-ops/                  # Server Load Balancer (SLB/CLB)
├── alicloud-ram-ops/                  # Resource Access Management (RAM)
├── alicloud-cms-ops/                  # Cloud Monitor Service (CMS)
├── alicloud-das-ops/                  # Database Autonomy Service (DAS)
├── alicloud-kms-ops/                  # Key Management Service (KMS)
├── alicloud-sas-ops/                  # Security Center (SAS)
├── alicloud-polar-mysql-ops/          # PolarDB for MySQL
├── alicloud-polar-postgresql-ops/      # PolarDB for PostgreSQL
├── alicloud-polar-oracle-ops/         # PolarDB for Oracle (compatible)
├── alicloud-bailian-ops/              # Bailian (百炼) GenAI Platform - LLM, Agent, RAG, Prompt
└── alicloud-topo-discovery/          # [Discovery Skill] Network topology & resource inventory
```

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
| [README_CN.md](README_CN.md) | Chinese version of this document |

---

See `alicloud-skill-generator/SKILL.md` for complete usage of the generator.