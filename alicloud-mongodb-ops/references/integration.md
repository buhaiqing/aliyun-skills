# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Prerequisites

- Alibaba Cloud account with valid credentials
- RAM user with appropriate permissions
- Network access to Alibaba Cloud endpoints

### Credential Configuration

```bash
# Environment variables (recommended)
export ALIBABA_CLOUD_ACCESS_KEY_ID=your-access-key
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-secret-key
export ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

### RAM Policy Requirements

Minimum permissions for MongoDB operations:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dds:Describe*",
        "dds:List*",
        "dds:Get*"
      ],
      "Resource": "*"
    }
  ]
}
```

For write operations, add:
```json
{
  "Effect": "Allow",
  "Action": [
    "dds:Create*",
    "dds:Modify*",
    "dds:Delete*"
  ],
  "Resource": "*"
}
```

### JIT SDK Setup

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/dds-20151201/client
```

## Cross-Skill Integration

See individual SKILL.md files for delegation rules.
