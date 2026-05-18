# 认证与签名实现指南

> **目的**: 如何实现 ACS3-HMAC-SHA256 签名算法以调用阿里云 AgentRun Sandbox API。

## 1. 签名流程概览

```
请求准备
│
├─ 1. 构建规范的 HTTP 请求
│   ├─ HTTP Method (POST/GET/DELETE)
│   ├─ CanonicalURI (路径)
│   ├─ CanonicalQueryString (排序后的查询参数)
│   ├─ CanonicalHeaders (排序 + 小写的 header)
│   ├─ SignedHeaders (签名涉及的 header 名列表)
│   └─ HashedPayload (Body 的 SHA-256 Hex)
│
├─ 2. 构建 Canonical Request
│   └─ Method + URI + Query + Headers + SignedHeaders + HashedPayload
│
├─ 3. 计算 Canonical Request 的 SHA-256 Hash
│
├─ 4. 构建 StringToSign
│   ├─ Algorithm: "ACS3-HMAC-SHA256"
│   ├─ RequestDateTime: ISO8601 格式
│   ├─ CredentialScope: Date/Region/Service/aliyun_v4_request
│   └─ HashedCanonicalRequest: Step 3 的结果
│
├─ 5. 派生签名密钥 (Signing Key)
│   └─ HMAC-SHA256(HMAC-SHA256(HMAC-SHA256(HMAC-SHA256("ACS3" + SecretKey, Date), Region), Service), "aliyun_v4_request")
│
├─ 6. 计算签名
│   └─ HMAC-SHA256(SigningKey, StringToSign)
│
└─ 7. 构建 Authorization Header
    └─ "ACS3-HMAC-SHA256 Credential=AK/Scope, SignedHeaders=headers, Signature=hex"
```

## 2. Go 实现关键点

### 2.1 签名核心函数

```go
func (s *Signer) Sign(req *http.Request, body []byte) error {
    // 关键：bodyHash 是对原始请求 body 的 SHA-256 哈希
    bodyHash := sha256.Sum256(body)
    bodyHashHex := hex.EncodeToString(bodyHash[:])

    // headers 必须包含这些
    headers := map[string]string{
        "host":                  req.Host,
        "content-type":          req.Header.Get("Content-Type"),
        "x-acs-content-sha256":  bodyHashHex,
        "x-acs-date":            dateTime,
    }
    
    // 注意：header 名称必须小写，值必须 TrimSpace
}
```

### 2.2 Header 排序规则

- Header **名称**必须按字母升序排序
- Header **名称**必须转为**小写**
- Header **值**必须去除首尾空格
- 每个 Header 行末必须有 `\n`（包括最后一个）

### 2.3 CanonicalRequest 格式

```
HTTPMethod
CanonicalURI
CanonicalQueryString
CanonicalHeaders
SignedHeaders
HashedPayload
```

每个字段之间用 `\n` 分隔（6 行总共）。**注意最后一个字段后也有隐式的换行分隔**。

完整拼接为：
```
fmt.Sprintf("%s\n%s\n%s\n%s\n%s\n%s", 
    method, uri, query, headers, signedHeaders, hash)
```

### 2.4 StringToSign 格式

```
ACS3-HMAC-SHA256
20250910T083000Z
20250910/cn-hangzhou/agentrun/aliyun_v4_request
<hashed-canonical-request>
```

4 行，用 `\n` 分隔。

### 2.5 Signing Key 派生链

```
kSecret = "ACS3" + SecretKey  (注意是字符串拼接，不是 HMAC)
kDate    = HMAC-SHA256(kSecret, Date)
kRegion  = HMAC-SHA256(kDate, Region)
kService = HMAC-SHA256(kRegion, Service)
kSigning = HMAC-SHA256(kService, "aliyun_v4_request")
```

## 3. Python 实现关键点

### 3.1 Python 签名实现

```python
import hashlib
import hmac
import datetime

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def hmac_sha256(key: bytes, data: str) -> bytes:
    return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

def derive_signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    k_secret = ("ACS3" + secret).encode('utf-8')
    k_date = hmac_sha256(k_secret, date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    k_signing = hmac_sha256(k_service, "aliyun_v4_request")
    return k_signing

def sign_request(method, path, query, body, ak, sk, region, service="agentrun"):
    now = datetime.datetime.utcnow()
    date_time = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")

    body_hash = sha256_hex(body if isinstance(body, bytes) else body.encode('utf-8'))
    
    # 构建 CanonicalRequest
    canonical_headers = f"content-type:application/json\nhost:{host}\nx-acs-content-sha256:{body_hash}\nx-acs-date:{date_time}\n"
    signed_headers = "content-type;host;x-acs-content-sha256;x-acs-date"
    
    canonical_request = (
        f"{method}\n{path}\n{query}\n{canonical_headers}\n{signed_headers}\n{body_hash}"
    )
    
    cr_hash = sha256_hex(canonical_request.encode('utf-8'))
    credential_scope = f"{date}/{region}/{service}/aliyun_v4_request"
    string_to_sign = f"ACS3-HMAC-SHA256\n{date_time}\n{credential_scope}\n{cr_hash}"
    
    signing_key = derive_signing_key(sk, date, region, service)
    signature = hmac_sha256(signing_key, string_to_sign).hex()
    
    authorization = (
        f"ACS3-HMAC-SHA256 "
        f"Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    
    return {
        "Authorization": authorization,
        "X-Acs-Date": date_time,
        "X-Acs-Content-Sha256": body_hash,
    }
```

## 4. 常见错误排查

| 错误现象 | 原因 | 解决方案 |
|---|---|---|
| `403 SignatureDoesNotMatch` | Header 排序错误或值含空格 | 确保 headers 按字母排序，值 TrimSpace |
| `403 SignatureDoesNotMatch` | Body Hash 不匹配 | 签名前读取完整 body，签名后重新设置 Body |
| `403 InvalidDate` | 时间偏差 > 15 分钟 | 同步系统时钟，使用 NTP |
| `403 MissingAuthenticationToken` | 缺少 X-Acs-Date header | 签名后必须设置所有相关 headers |
| `400 Bad Request` | Content-Type 不匹配 | 确保请求和签名使用相同的 Content-Type |
| 401 Unauthorized | AK/SK 错误或无权限 | 验证凭证和 RAM 权限 |

## 5. 测试签名正确性

```bash
# 使用 curl 手动构建签名请求进行测试
# 先用 Python 脚本生成 Authorization header:
python3 -c "
import sys
sys.path.append('.')
from signer import sign_request
headers = sign_request('GET', '/sandboxes/test-id/health', '', b'', 'AK', 'SK', 'cn-hangzhou')
print(headers['Authorization'])
"

# 然后用 curl 发起请求
curl -X GET "https://{account}.agentrun-data.cn-hangzhou.aliyuncs.com/sandboxes/test-id/health" \
  -H "X-Acs-Parent-Id: ${ACCOUNT_ID}" \
  -H "Content-Type: application/json" \
  -H "X-Acs-Date: $(date -u +%Y%m%dT%H%M%SZ)" \
  -H "Authorization: <generated-auth-header>"
```

## 6. 安全最佳实践

1. **AK/SK 存储在内存中时考虑加密**：可使用 AES-GCM 加密后存储，签名前再解密
2. **日志中绝不记录 Signature/AK**：调试时使用 "***MASKED***" 替代
3. **定期轮换 AK/SK**：使用 RAM 子账号 AK，至少每 90 天更换一次
4. **优先使用 STS 临时凭据**：有效期短（1h），泄露影响小
5. **签名失败时不重试**：403 是客户端错误，重试不会改变签名结果
