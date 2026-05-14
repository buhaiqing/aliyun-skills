# CI Environment Compatibility Guide

## Overview

This guide addresses common issues when running Alibaba Cloud Redis/Tair operations in CI environments (GitHub Actions, GitLab CI, Travis CI, CircleCI, etc.).

## Common CI Environment Issues

### Issue 1: CLI Plugin Installation Permission Denied

**Symptom:**
```
ERROR: mkdir ~/.aliyun/plugins/aliyun-cli-r-kvstore: operation not permitted
```

**Root Cause:**
- CI environments often have restricted file system permissions
- Home directory may be read-only or have limited write access
- Plugin installation requires write access to `~/.aliyun/plugins`

**Solution:**

**Option A: Use SDK Fallback (Recommended)**
```yaml
# GitHub Actions example
- name: Run Redis Operations
  run: |
    # Load credentials from secrets
    export ALIBABA_CLOUD_ACCESS_KEY_ID="${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}"
    export ALIBABA_CLOUD_ACCESS_KEY_SECRET="${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}"
    export ALIBABA_CLOUD_REGION_ID="${{ secrets.ALIBABA_CLOUD_REGION_ID }}"
    
    # Use SDK fallback instead of CLI
    cd alicloud-redis-ops/scripts
    go run sdk-fallback.go
```

**Option B: Pre-install Plugin in CI Image**
```yaml
# Custom Dockerfile for CI
FROM aliyun-cli-base:latest

# Pre-install Redis plugin during image build
RUN aliyun plugin install --names aliyun-cli-r-kvstore

# Use in CI workflow
- name: Run Redis Operations
  run: |
    aliyun r-kvstore describe-instances --RegionId "$ALIBABA_CLOUD_REGION_ID"
```

**Option C: Use Temporary Directory**
```bash
# Override plugin directory location
export ALIBABA_CLOUD_PLUGIN_DIR=/tmp/aliyun-plugins
mkdir -p "$ALIBABA_CLOUD_PLUGIN_DIR"

# Install plugin to temporary directory
aliyun plugin install --names aliyun-cli-r-kvstore --plugin-dir "$ALIBABA_CLOUD_PLUGIN_DIR"
```

### Issue 2: Environment Variables Not Loaded

**Symptom:**
```
ERROR: ALIBABA_CLOUD_ACCESS_KEY_ID is NOT set
```

**Root Cause:**
- CI secrets not properly exported to environment
- .env file not present in CI environment
- Shell configuration not loaded

**Solution:**

**Option A: Use CI Secrets (Recommended)**
```yaml
# GitHub Actions
env:
  ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
  ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
  ALIBABA_CLOUD_REGION_ID: cn-hangzhou

steps:
  - name: Run operations
    run: |
      bash scripts/preflight-check.sh
      # Environment variables already set via env section
```

**Option B: Create .env File in CI**
```yaml
steps:
  - name: Setup credentials
    run: |
      cat > .env <<EOF
      ALIBABA_CLOUD_ACCESS_KEY_ID=${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
      ALIBABA_CLOUD_ACCESS_KEY_SECRET=${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
      ALIBABA_CLOUD_REGION_ID=cn-hangzhou
      EOF
  
  - name: Run operations
    run: |
      bash scripts/preflight-check.sh
      # Pre-flight check will auto-load .env file
```

### Issue 3: Go SDK Version Compatibility

**Symptom:**
```
cannot use config (variable of type *v2/client.Config) as *client.Config
```

**Root Cause:**
- Go version mismatch
- SDK import path version mismatch
- Missing dependencies

**Solution:**

**Option A: Use Go 1.21+**
```yaml
# GitHub Actions
steps:
  - uses: actions/setup-go@v3
    with:
      go-version: '1.24'
  
  - name: Run SDK fallback
    run: |
      cd alicloud-redis-ops/scripts
      go mod download
      go run sdk-fallback.go
```

**Option B: Use Correct Import Paths**
```go
// Use v2 import path for darabonba-openapi
import openapi "github.com/alibabacloud-go/darabonba-openapi/client"

// Use v2 import path for r-kvstore
import rkvstore "github.com/alibabacloud-go/r-kvstore-20150101/v2/client"
```

### Issue 4: Network Connectivity Restrictions

**Symptom:**
```
ERROR: Cannot reach Alibaba Cloud endpoint
```

**Root Cause:**
- CI environment firewall restrictions
- Proxy configuration required
- Network isolation

**Solution:**

**Option A: Configure Proxy**
```yaml
env:
  HTTP_PROXY: ${{ secrets.HTTP_PROXY }}
  HTTPS_PROXY: ${{ secrets.HTTPS_PROXY }}
  NO_PROXY: localhost,127.0.0.1

steps:
  - name: Run operations
    run: |
      # Proxy settings will be used by SDK/CLI
      bash scripts/preflight-check.sh
```

**Option B: Use Self-hosted Runner**
```yaml
# Use self-hosted runner with proper network access
runs-on: self-hosted

steps:
  - name: Run operations
    run: |
      bash scripts/preflight-check.sh
```

## CI Workflow Templates

### GitHub Actions Complete Template

```yaml
name: Redis Operations

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  ALIBABA_CLOUD_REGION_ID: cn-hangzhou

jobs:
  redis-ops:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - uses: actions/setup-go@v3
      with:
        go-version: '1.24'
    
    - name: Install Alibaba Cloud CLI
      run: |
        /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
    
    - name: Setup credentials
      env:
        ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
        ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
      run: |
        # Create .env file for pre-flight check
        cat > .env <<EOF
        ALIBABA_CLOUD_ACCESS_KEY_ID=$ALIBABA_CLOUD_ACCESS_KEY_ID
        ALIBABA_CLOUD_ACCESS_KEY_SECRET=$ALIBABA_CLOUD_ACCESS_KEY_SECRET
        ALIBABA_CLOUD_REGION_ID=$ALIBABA_CLOUD_REGION_ID
        EOF
    
    - name: Run pre-flight check
      run: |
        cd alicloud-redis-ops
        bash scripts/preflight-check.sh
        PREFLIGHT_STATUS=$?
        
        if [ $PREFLIGHT_STATUS -eq 0 ]; then
          echo "CLI path available"
        elif [ $PREFLIGHT_STATUS -eq 2 ]; then
          echo "SDK fallback required"
        else
          echo "Critical issues detected"
          exit 1
        fi
    
    - name: Execute Redis operations (CLI)
      if: success()
      env:
        ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
        ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
      run: |
        cd alicloud-redis-ops/scripts
        
        # Try CLI first
        if aliyun help r-kvstore 2>&1 | grep -q "Usage"; then
          echo "Using CLI path..."
          aliyun r-kvstore describe-instances --RegionId "$ALIBABA_CLOUD_REGION_ID"
        else
          echo "CLI plugin not available, using SDK fallback..."
          go mod download
          go run sdk-fallback.go
        fi
    
    - name: Execute Redis operations (SDK fallback)
      if: failure()
      env:
        ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
        ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
      run: |
        cd alicloud-redis-ops/scripts
        go mod download
        go run sdk-fallback.go
```

### GitLab CI Complete Template

```yaml
stages:
  - validate
  - execute

variables:
  ALIBABA_CLOUD_REGION_ID: cn-hangzhou

redis-validate:
  stage: validate
  image: golang:1.24
  script:
    - apt-get update && apt-get install -y curl
    - /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
    - cd alicloud-redis-ops
    - bash scripts/preflight-check.sh
  artifacts:
    paths:
      - .env

redis-execute:
  stage: execute
  image: golang:1.24
  dependencies:
    - redis-validate
  script:
    - apt-get update && apt-get install -y curl
    - /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
    - export ALIBABA_CLOUD_ACCESS_KEY_ID="$ALIBABA_CLOUD_ACCESS_KEY_ID"
    - export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$ALIBABA_CLOUD_ACCESS_KEY_SECRET"
    - cd alicloud-redis-ops/scripts
    - go mod download
    - go run sdk-fallback.go
  only:
    - main
```

## Best Practices for CI

### 1. Always Use Pre-flight Check
```bash
bash scripts/preflight-check.sh
```

### 2. Prefer SDK Fallback in CI
- More reliable in restricted environments
- No plugin installation required
- Better error handling

### 3. Use CI Secrets for Credentials
- Never hardcode credentials
- Use environment variables
- Mask credentials in logs

### 4. Handle Both Paths Gracefully
```bash
# Try CLI first, fallback to SDK
if aliyun help r-kvstore 2>&1 | grep -q "Usage"; then
    aliyun r-kvstore describe-instances --RegionId "$ALIBABA_CLOUD_REGION_ID"
else
    go run scripts/sdk-fallback.go
fi
```

### 5. Validate Results
```bash
# Check if operation succeeded
if [ $? -eq 0 ]; then
    echo "Operation successful"
else
    echo "Operation failed, check logs"
    exit 1
fi
```

## Troubleshooting Checklist

1. ✓ Run pre-flight check first
2. ✓ Check CI secrets are properly set
3. ✓ Verify Go version is 1.21+
4. ✓ Test network connectivity
5. ✓ Use SDK fallback if CLI fails
6. ✓ Validate operation results
7. ✓ Check logs for detailed errors
8. ✓ Review RAM permissions

## Support

If issues persist:
1. Run pre-flight check and review output
2. Check CI environment logs
3. Verify credentials and permissions
4. Contact support with RequestId from error messages