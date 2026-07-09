# manifest.json Schema (v1.0)

每个 `export-hcl` 输出目录中的 `manifest.json` 必须符合本 schema。schema 自身在 [`manifest-schema.json`](./manifest-schema.json) 用 JSON Schema Draft-07 定义,本文档提供字段表 + 示例。

## 字段

### 必需字段(14 个)

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string (const `"1.0"`) | 锁定到 1.0,后续版本用新值(如 `"2.0"`) |
| `generator` | string (const `"alicloud-topo-discovery"`) | 生成器标识 |
| `generator_version` | string (semver 正则) | 生成器版本,如 `"1.0.0"` |
| `generated_at` | string (ISO 8601 date-time) | 生成时间,UTC,格式 `YYYY-MM-DDTHH:MM:SSZ` |
| `account_id` | string (minLength 1) | 阿里云账号 ID(纯数字字符串) |
| `region` | string (minLength 1) | 区域,如 `"cn-hangzhou"` |
| `scope` | string (minLength 1) | 扫描范围,`"all"` 或 `"vpc-xxx"` |
| `provider_version` | string (semver 正则) | Aliyun Provider 锁版本,如 `"1.220.0"` |
| `resource_count` | integer (≥ 0) | 导出资源总数 |
| `by_type` | object (string → integer) | 按资源类型统计,如 `{"vpc": 1, "ecs": 12}` |
| `sensitive_masked` | array of string | 被脱敏的字段路径列表,如 `["rds.account_password"]` |
| `unsupported_types` | array of string | 不支持的资源类型,如 `["fc.function_code"]` |
| `import_ids_stable` | boolean | 二次导出 ID 是否稳定(总是 true) |
| `execution_time_ms` | integer (≥ 0) | 导出耗时(毫秒) |

### 可选字段(2 个)

| 字段 | 类型 | 说明 |
|------|------|------|
| `account_alias` | string | 账号别名(便于人类阅读) |
| `role_arn` | string (ARN 正则) | 跨账号时源角色 ARN,如 `arn:acs:ram::1234:role/TopologyReader` |

### 严格性

- `additionalProperties: false` —— 不允许除上述字段外的任何键(防止 typo 和隐式扩展)

## 示例

```json
{
  "schema_version": "1.0",
  "generator": "alicloud-topo-discovery",
  "generator_version": "1.0.0",
  "generated_at": "2026-06-04T15:00:00Z",
  "account_id": "1234567890",
  "account_alias": "prod-finance",
  "role_arn": "arn:acs:ram::1234:role/TopologyReader",
  "region": "cn-hangzhou",
  "scope": "vpc-xxx",
  "provider_version": "1.220.0",
  "resource_count": 47,
  "by_type": {
    "vpc": 1,
    "vswitch": 3,
    "ecs": 12,
    "rds": 2,
    "slb": 2
  },
  "sensitive_masked": [
    "rds.account_password",
    "ram.access_key"
  ],
  "unsupported_types": [
    "fc.function_code"
  ],
  "import_ids_stable": true,
  "execution_time_ms": 12345
}
```

## 验证

### Python 验证

```python
import json
from scripts.lib.manifest_validator import ManifestValidator

manifest = json.load(open("infra-baseline/2026-06-04/manifest.json"))
ManifestValidator().validate(manifest)  # 抛 ManifestValidationError on failure
```

### CLI 验证(在 export-hcl 输出后)

```bash
python -c "
import json
import sys
sys.path.insert(0, 'alicloud-topo-discovery/scripts')
from lib.manifest_validator import ManifestValidator
m = json.load(open('infra-baseline/2026-06-04/manifest.json'))
ManifestValidator().validate(m)
print('OK')
"
```

## 版本演进

- **v1.0** (本版本):14 必需 + 2 可选字段
- 未来:任何破坏性变更(如新增必需字段、改变类型)必须发新 `schema_version`,旧版 validator 拒绝新版 manifest
- 兼容性策略:validator 严格匹配自己版本的 schema_version,跨版本应显式升级 generator
