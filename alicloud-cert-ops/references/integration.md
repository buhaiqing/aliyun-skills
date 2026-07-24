---
name: alicloud-cert-ops-integration
description: >-
  CAS integration guide: Go SDK fallback, cross-product delegation.
  Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.0"
  last_updated: "2026-06-25"
---

# Integration Guide — CAS

## Cross-Product Delegation

| Scenario | Delegation Target | What to Delegate |
|----------|-----------------|-------------------|
| ALB HTTPS listener binding | `alicloud-alb-ops` | Bind certificate to ALB listener |
| SLB HTTPS listener binding | `alicloud-slb-ops` | Bind certificate to SLB listener |
| CDN HTTPS configuration | `aliyun cdn` CLI | Configure CDN domain HTTPS |
| OSS HTTPS configuration | `alicloud-oss-ops` | Configure OSS bucket HTTPS |
| RAM permissions for CAS | `alicloud-ram-ops` | Create CAS service RAM policy |
| KMS key management | `alicloud-kms-ops` | (unrelated — separate product) |

## Go SDK Fallback

When CLI does not support an operation, use JIT Go SDK.

### SDK Package

```text
github.com/alibabacloud-go/cas-20200407/v3/client
```

### Bootstrap

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init cas-sdk-fallback
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea-utils/v2/service
go get github.com/alibabacloud-go/cas-20200407/v3/client
```

### Example: UploadUserCertificate (Go SDK)

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    cas "github.com/alibabacloud-go/cas-20200407/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("cas.aliyuncs.com"),
    }

    client, err := cas.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &cas.UploadUserCertificateRequest{
        Name: tea.String("my-cert"),
        Cert: tea.String(os.Getenv("CERT_PEM")),  // via env, not hardcoded
        Key:  tea.String(os.Getenv("KEY_PEM")),   // via env, not hardcoded
    }

    resp, err := client.UploadUserCertificate(request)
    if err != nil {
        panic(err)
    }
    fmt.Printf("CertId: %s\n", tea.ToString(resp.Body.CertId))
}
```

### Credential Handling

| Pattern | Safe? | Notes |
|---------|-------|-------|
| `os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")` | Yes | Read from env |
| `fmt.Printf("%s", secret)` | No | Never log secrets |
| `AccessKeySecret: tea.String("hardcoded")` | No | Must use env var |
| Private key via `--Key env_var` | Yes | CLI reads from env |
