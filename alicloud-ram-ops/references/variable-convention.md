# RAM Variable Convention (Agent-Readable)

> All placeholder conventions used across `alicloud-ram-ops` operations.
> Operations reference these placeholders via `{{env.*}}`, `{{user.*}}`,
> and `{{output.*}}`. The agent MUST respect the **MUST NOT ask user**
> constraint on `{{env.*}}` variables and the **secret shown ONCE** rule
> on `{{output.access_key_secret}}`.

## 1. Placeholder Table

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | RAM global default: `cn-hangzhou` |
| `{{user.user_name}}` | User-supplied RAM user name | Ask once; reuse; validate format |
| `{{user.group_name}}` | User-supplied RAM group name | Ask once; reuse; validate format |
| `{{user.role_name}}` | User-supplied RAM role name | Ask once; reuse; validate format |
| `{{user.policy_name}}` | User-supplied policy name | Ask once; reuse; validate format |
| `{{user.policy_document}}` | User-supplied or generated policy JSON | Validate JSON structure before use |
| `{{user.access_key_id}}` | Specific access key to act on | Ask when operation targets a key |
| `{{output.user_id}}` | From CreateUser / GetUser response | Parse per OpenAPI |
| `{{output.role_arn}}` | From CreateRole / GetRole response | Parse per OpenAPI: `acs:ram::{{account_id}}:role/{{role_name}}` |
| `{{output.policy_type}}` | `Custom` or `System` | Parse per OpenAPI |
| `{{output.access_key_id}}` | From CreateAccessKey response | Parse per OpenAPI; SECRET shown ONLY once |
| `{{output.access_key_secret}}` | From CreateAccessKey response | Parse per OpenAPI; show ONCE, then NEVER log again |
| `{{output.account_id}}` | From `GetCallerIdentity` | Use to construct role trust policies |
| `{{output.mfa_serial_number}}` | From CreateVirtualMFADevice | Required for `BindMFADevice` |

## 2. Collection Constraints

- **`{{env.*}}` MUST NOT** be collected from the user. If unset, HALT
  and instruct the user to configure their runtime environment.
- **`{{user.*}}`** MUST be collected interactively when missing — ask
  once, then reuse the value across all subsequent steps in the same
  session.
- **`{{output.*}}`** MUST be parsed from the upstream API response using
  the JSON paths in
  [`api-response-reference.md`](api-response-reference.md). Never hard-code
  these values in prompts or scripts.

## 3. Credential Hygiene

- **凭据安全（强制）：** 参考
  [Credential Masking 规则](../../alicloud-skill-generator/references/credential-masking.md)
- **RAM 特殊：** `{{output.access_key_secret}}` 从 `CreateAccessKey` 返回后必须仅展示**一次**，之后不可记录或存储。完整凭据卫生规则见
  [`api-response-reference.md` §5](api-response-reference.md)
  和 [`operations/user-operations.md`](operations/user-operations.md)。
- **Password via CLI:** Pass `{{user.password}}` and `{{user.new_password}}`
  through single-quoted `--Password` to avoid shell interpolation. Avoid
  embedding passwords in `--output cols=` or any logged command. For
  high-trust environments, prefer `PasswordResetRequired=true` and let
  the user set the password via the console.
- **GCL double-strict:** The GCL Critic MUST scrub 11 RAM-specific secret
  patterns (see [`gcl-quality-gate.md` §2](gcl-quality-gate.md)) before
  any trace is persisted. The absolute threshold for Credential Hygiene
  is **= 1** (zero leaks).
