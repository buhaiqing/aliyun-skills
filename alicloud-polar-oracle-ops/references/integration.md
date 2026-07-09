# Integration — PolarDB Oracle-compatible (IO)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Environment Setup

**Primary path:** `aliyun polardb-io` CLI

**Fallback path:** JIT Go SDK via `polardb-io-20211126/v3/client`

## Go SDK Package

```
github.com/alibabacloud-go/polardb-io-20211126/v3/client
```

## JIT Go SDK Workflow

```bash
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/polardb-io-20211126/v3/client
go run ./main.go
```

## Credential Configuration

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=***
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=***
export ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

> **SECURITY:** Never echo secret values. Verify existence only.
