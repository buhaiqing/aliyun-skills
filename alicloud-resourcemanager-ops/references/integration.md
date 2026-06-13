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

Minimum permissions for ResourceManager operations:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "resourcemanager:Describe*",
        "resourcemanager:List*",
        "resourcemanager:Get*"
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
    "resourcemanager:Create*",
    "resourcemanager:Modify*",
    "resourcemanager:Delete*"
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
go get github.com/alibabacloud-go/resourcemanager-20200331/client
```

## Cross-Skill Integration

See individual SKILL.md files for delegation rules.
