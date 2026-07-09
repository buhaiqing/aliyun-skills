# Integration Guide — AgentRun Sandbox Operations

> **Purpose**: Credential setup, signing workflow, and environment configuration.

## 1. Environment Setup

### 1.1 Required Environment Variables

| Variable | Description | Example |
|---|---|---|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | AccessKey ID | `LTAI5t...` |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | AccessKey Secret | `abc123...` |
| `ALIBABA_CLOUD_REGION_ID` | Region ID | `cn-hangzhou` |
| `ALIBABA_CLOUD_ACCOUNT_ID` | Main account ID | `1234567890123456` |

**Configuration**:
```bash
# ~/.bashrc or ~/.zshrc
export ALIBABA_CLOUD_ACCESS_KEY_ID="LTAI5t..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="abc123..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export ALIBABA_CLOUD_ACCOUNT_ID="1234567890123456"
```

### 1.2 Credential Security

**Best Practices**:
- ✅ Use environment variables (never hardcode)
- ✅ Prefer STS temporary credentials (expires in 1h)
- ✅ Store secrets in KMS or Secrets Manager
- ✅ Rotate AK/SK every 90 days
- ❌ Never log AK/SK values
- ❌ Never commit credentials to git

---

## 2. Signing Workflow

### 2.1 ACS3-HMAC-SHA256 Overview

**Required Headers**:
| Header | Value | Source |
|---|---|---|
| `Content-Type` | `application/json` | Fixed |
| `X-Acs-Parent-Id` | `{主账号ID}` | Environment |
| `X-Acs-Date` | `20250910T083000Z` | Current UTC time |
| `X-Acs-Content-Sha256` | `{body-hash}` | SHA-256 of body |
| `Authorization` | `ACS3-HMAC-SHA256 ...` | Calculated signature |

### 2.2 Signing Steps

```
1. Build Canonical Request
   ├─ HTTP Method
   ├─ Canonical URI (path)
   ├─ Canonical Query String (sorted)
   ├─ Canonical Headers (sorted + lowercase)
   ├─ Signed Headers (names list)
   └─ Hashed Payload (body SHA-256)

2. Calculate StringToSign
   ├─ Algorithm: "ACS3-HMAC-SHA256"
   ├─ RequestDateTime: ISO8601
   ├─ CredentialScope: date/region/service/aliyun_v4_request
   └─ HashedCanonicalRequest

3. Derive Signing Key
   ├─ kSecret = "ACS3" + SecretKey
   ├─ kDate = HMAC-SHA256(kSecret, date)
   ├─ kRegion = HMAC-SHA256(kDate, region)
   ├─ kService = HMAC-SHA256(kRegion, "agentrun")
   └─ kSigning = HMAC-SHA256(kService, "aliyun_v4_request")

4. Calculate Signature
   └─ HMAC-SHA256(kSigning, StringToSign)

5. Build Authorization Header
   └─ "ACS3-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={headers}, Signature={hex}"
```

### 2.3 Python Signing Helper

```python
import hashlib
import hmac
import datetime
import urllib.parse

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def hmac_sha256(key: bytes, data: str) -> bytes:
    return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

def sign_request(method, host, path, query, body, ak, sk, region):
    # Timestamp
    now = datetime.datetime.utcnow()
    date_time = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    
    # Body hash
    body_bytes = body if isinstance(body, bytes) else body.encode('utf-8')
    body_hash = sha256_hex(body_bytes)
    
    # Canonical headers
    headers = {
        "content-type": "application/json",
        "host": host,
        "x-acs-content-sha256": body_hash,
        "x-acs-date": date_time
    }
    
    # Sort headers
    sorted_headers = sorted(headers.keys())
    canonical_headers = "".join([f"{k}:{headers[k]}\n" for k in sorted_headers])
    signed_headers = ";".join(sorted_headers)
    
    # Canonical query string
    if query:
        sorted_query = sorted(query.items())
        canonical_query = "&".join([f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}" for k, v in sorted_query])
    else:
        canonical_query = ""
    
    # Canonical request
    canonical_request = f"{method}\n{path}\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{body_hash}"
    
    # String to sign
    credential_scope = f"{date}/{region}/agentrun/aliyun_v4_request"
    cr_hash = sha256_hex(canonical_request.encode('utf-8'))
    string_to_sign = f"ACS3-HMAC-SHA256\n{date_time}\n{credential_scope}\n{cr_hash}"
    
    # Signing key
    k_secret = ("ACS3" + sk).encode('utf-8')
    k_date = hmac_sha256(k_secret, date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, "agentrun")
    k_signing = hmac_sha256(k_service, "aliyun_v4_request")
    
    # Signature
    signature = hmac_sha256(k_signing, string_to_sign).hex()
    
    # Authorization header
    authorization = f"ACS3-HMAC-SHA256 Credential={ak}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    
    return {
        "Authorization": authorization,
        "X-Acs-Date": date_time,
        "X-Acs-Content-Sha256": body_hash,
        "X-Acs-Parent-Id": "${ALIBABA_CLOUD_ACCOUNT_ID}",
        "Content-Type": "application/json"
    }

# Example usage
headers = sign_request(
    method="POST",
    host="agentrun.cn-hangzhou.aliyuncs.com",
    path="/2025-09-10/templates",
    query={},
    body='{"templateName":"my-template","cpu":2,"memory":4096}',
    ak="${ALIBABA_CLOUD_ACCESS_KEY_ID}",
    sk="${ALIBABA_CLOUD_ACCESS_KEY_SECRET}",
    region="${ALIBABA_CLOUD_REGION_ID}"
)
```

---

## 3. HTTP Client Setup

### 3.1 curl Example

```bash
# Create Template
AK="${ALIBABA_CLOUD_ACCESS_KEY_ID}"
SK="${ALIBABA_CLOUD_ACCESS_KEY_SECRET}"
REGION="${ALIBABA_CLOUD_REGION_ID}"
ACCOUNT="${ALIBABA_CLOUD_ACCOUNT_ID}"

# Generate signature (use Python helper or custom script)
SIGNATURE=$(python3 sign_helper.py "POST" "/2025-09-10/templates" '{"templateName":"test","cpu":2,"memory":4096}')

BODY='{"templateName":"test","cpu":2,"memory":4096}'
BODY_HASH=$(echo -n "$BODY" | sha256sum | cut -d' ' -f1)
DATE=$(date -u +%Y%m%dT%H%M%SZ)

curl -X POST "https://agentrun.${REGION}.aliyuncs.com/2025-09-10/templates" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Parent-Id: ${ACCOUNT}" \
  -H "X-Acs-Date: ${DATE}" \
  -H "X-Acs-Content-Sha256: ${BODY_HASH}" \
  -H "Authorization: ${SIGNATURE}" \
  -d "$BODY"
```

### 3.2 Python HTTP Client

```python
import requests
import json

class AgentRunClient:
    def __init__(self, ak, sk, region, account):
        self.ak = ak
        self.sk = sk
        self.region = region
        self.account = account
        self.control_plane_base = f"https://agentrun.{region}.aliyuncs.com/2025-09-10"
        self.data_plane_base = f"https://{account}.agentrun-data.{region}.aliyuncs.com"
    
    def _sign(self, method, host, path, query, body):
        return sign_request(method, host, path, query, body, self.ak, self.sk, self.region)
    
    def create_template(self, template_name, cpu=2, memory=4096, **kwargs):
        path = "/2025-09-10/templates"
        body = {
            "templateName": template_name,
            "cpu": cpu,
            "memory": memory,
            **kwargs
        }
        headers = self._sign("POST", f"agentrun.{self.region}.aliyuncs.com", path, {}, json.dumps(body))
        headers["X-Acs-Parent-Id"] = self.account
        
        response = requests.post(
            f"{self.control_plane_base}/templates",
            headers=headers,
            json=body
        )
        return response.json()
    
    def create_sandbox(self, template_name):
        path = "/2025-09-10/sandboxes"
        body = {"templateName": template_name}
        headers = self._sign("POST", f"agentrun.{self.region}.aliyuncs.com", path, {}, json.dumps(body))
        headers["X-Acs-Parent-Id"] = self.account
        
        response = requests.post(
            f"{self.control_plane_base}/sandboxes",
            headers=headers,
            json=body
        )
        return response.json()
    
    def execute_code(self, sandbox_id, code, language="python", timeout=30):
        path = f"/sandboxes/{sandbox_id}/contexts/execute"
        body = {
            "language": language,
            "code": code,
            "timeout": timeout
        }
        headers = self._sign("POST", f"{self.account}.agentrun-data.{self.region}.aliyuncs.com", path, {}, json.dumps(body))
        headers["X-Acs-Parent-Id"] = self.account
        
        response = requests.post(
            f"{self.data_plane_base}/sandboxes/{sandbox_id}/contexts/execute",
            headers=headers,
            json=body
        )
        return response.json()

# Usage
client = AgentRunClient(
    ak="${ALIBABA_CLOUD_ACCESS_KEY_ID}",
    sk="${ALIBABA_CLOUD_ACCESS_KEY_SECRET}",
    region="${ALIBABA_CLOUD_REGION_ID}",
    account="${ALIBABA_CLOUD_ACCOUNT_ID}"
)

# Create template
template = client.create_template("my-template", cpu=2, memory=4096)

# Create sandbox
sandbox = client.create_sandbox("my-template")
sandbox_id = sandbox["sandboxId"]

# Execute code
result = client.execute_code(sandbox_id, "print('Hello, World!')")
```

---

## 4. RAM Permission Setup

### 4.1 Required Permissions

| Action | RAM Policy Action | Required For |
|---|---|---|
| CreateTemplate | `fc:CreateTemplate` | Template creation |
| GetTemplate | `fc:GetTemplate` | Template query |
| ListTemplates | `fc:ListTemplates` | Template listing |
| UpdateTemplate | `fc:UpdateTemplate` | Template modification |
| DeleteTemplate | `fc:DeleteTemplate` | Template deletion |
| CreateSandbox | `fc:CreateSandbox` | Sandbox creation |
| GetSandbox | `fc:GetSandbox` | Sandbox query |
| ListSandboxes | `fc:ListSandboxes` | Sandbox listing |
| StopSandbox | `fc:StopSandbox` | Sandbox termination |
| DeleteSandbox | `fc:DeleteSandbox` | Sandbox deletion |
| ExecuteCode | `fc:ExecuteSandboxCode` | Code execution (data plane) |

### 4.2 RAM Policy JSON

#### Read-Only Policy (Monitoring)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:GetSandbox",
        "fc:ListSandboxes"
      ],
      "Resource": [
        "acs:agentrun:*:*:template/*",
        "acs:agentrun:*:*:sandbox/*"
      ]
    }
  ]
}
```

#### Operator Policy (DevOps — Recommended)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fc:CreateTemplate",
        "fc:GetTemplate",
        "fc:ListTemplates",
        "fc:UpdateTemplate",
        "fc:CreateSandbox",
        "fc:GetSandbox",
        "fc:ListSandboxes",
        "fc:StopSandbox",
        "fc:ExecuteSandboxCode"
      ],
      "Resource": [
        "acs:agentrun:*:*:template/*",
        "acs:agentrun:*:*:sandbox/*"
      ],
      "Condition": {
        "IpAddress": {
          "acs:SourceIp": ["${trusted_ip_range}"]
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": [
        "fc:DeleteTemplate",
        "fc:DeleteSandbox"
      ],
      "Resource": "*"
    }
  ]
}
```

> **⚠️ Security Note:** Never use `Resource: "*"` with `Effect: Allow` for write operations. Always scope to `acs:agentrun:*:*:template/*` or specific resource ARNs. See [security-enhancement.md](security-enhancement.md) for full policy templates.

### 4.3 Create RAM User

1. Log in to RAM Console
2. Create new user or use existing
3. Attach policy above
4. Create AccessKey (AK/SK)
5. Store AK/SK in environment variables

---

## 5. Network Configuration

### 5.1 Endpoints

| Plane | Endpoint Pattern | Example |
|---|---|---|
| Control Plane | `agentrun.{region}.aliyuncs.com` | `agentrun.cn-hangzhou.aliyuncs.com` |
| Data Plane | `{account}.agentrun-data.{region}.aliyuncs.com` | `123456.agentrun-data.cn-hangzhou.aliyuncs.com` |

### 5.2 Firewall Requirements

| Endpoint | Port | Protocol |
|---|---|---|
| Control Plane | 443 | HTTPS |
| Data Plane | 443 | HTTPS |
| WebSocket TTY | 443 | WSS |

---

## 6. Verification Checklist

**Before First Operation**:

- [ ] Environment variables configured
- [ ] RAM permissions attached
- [ ] Signing helper tested (signature validation)
- [ ] Network connectivity verified (curl endpoint)
- [ ] Clock synchronized (NTP)
- [ ] Account ID confirmed

**Test Commands**:

```bash
# Test credentials (MASKED output — never echo full values)
AK="${ALIBABA_CLOUD_ACCESS_KEY_ID}"
if [ -n "$AK" ]; then
  MASKED_AK="${AK:0:4}***${AK: -2}"
  echo "✅ ALIBABA_CLOUD_ACCESS_KEY_ID: ${MASKED_AK}"
else
  echo "❌ ALIBABA_CLOUD_ACCESS_KEY_ID: not set"
fi
echo "✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET: <masked>"
echo "✅ Region: ${ALIBABA_CLOUD_REGION_ID}"
echo "✅ Account: ${ALIBABA_CLOUD_ACCOUNT_ID}"

# Test network
curl -I https://agentrun.${ALIBABA_CLOUD_REGION_ID}.aliyuncs.com

# Test signing
python3 sign_helper.py --test
```