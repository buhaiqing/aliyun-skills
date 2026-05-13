# Core Concepts — RAM

## Identity Types

### RAM User

A long-term identity representing a person or application within your Alibaba
Cloud account. RAM users have persistent credentials (password for console,
AccessKey pair for API).

- **Use case:** Individual employees, service accounts for applications
- **Limit:** 1000 RAM users per account (soft limit, can be raised)
- **Access keys:** Max 2 per user

### RAM User Group

A collection of RAM users. Permissions attached to a group are inherited by all
members.

- **Use case:** Organize users by team or function (e.g., `developers`,
  `admins`, `finance`)
- **Limit:** A user can belong to multiple groups; a group can have many users

### RAM Role

An identity that can be assumed by a trusted principal to obtain temporary
credentials. RAM roles do not have long-term credentials.

- **Use case:** Cross-account access, service-linked roles, federated SSO,
  temporary elevated privileges
- **Trust policy:** JSON document defining who can assume the role
- **Session duration:** 900–43200 seconds (15 min – 12 hours)
- **Common principals:**
  - Alibaba Cloud account: `acs:ram::{{account_id}}:root`
  - RAM user: `acs:ram::{{account_id}}:user/{{user_name}}`
  - Service: `ecs.aliyuncs.com`
  - Identity provider: `acs:ram::{{account_id}}:saml-provider/{{provider_name}}`

## Policy Types

### System Policy

Managed by Alibaba Cloud. Cannot be modified or deleted. Examples:
- `AliyunRAMFullAccess` — Full RAM management
- `AliyunECSFullAccess` — Full ECS management
- `AliyunReadOnlyAccess` — Read-only across all services

### Custom Policy

Created and managed by the account owner. Can be modified, versioned, and
deleted.

- **Versions:** Max 5 versions per policy. One version is marked as default.
- **Size limit:** 6144 characters per policy document

## Policy Document Structure

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow|Deny",
      "Action": "<service>:<operation>",
      "Resource": "acs:<service>:<region>:<account-id>:<resource-type>/<resource-id>",
      "Condition": {
        "<condition-operator>": {
          "<condition-key>": ["<value>"]
        }
      }
    }
  ]
}
```

### Effect

- `Allow`: Grants permission
- `Deny`: Explicitly denies permission (overrides any `Allow`)

### Action

- Format: `<service>:<operation>`
- Wildcards: `ecs:*`, `ecs:Describe*`
- Multiple actions: array of strings

### Resource

- Format: `acs:<service>:<region>:<account-id>:<resource-type>/<resource-id>`
- `*` for all resources
- Examples:
  - `acs:ecs:*:*:instance/i-bp67acfmxazb4ph***`
  - `acs:oss:*:*:my-bucket/*`

### Condition

Optional. Restricts when the policy applies.

Common condition keys:
- `acs:CurrentTime` — Current date/time
- `acs:SourceIp` — Source IP address
- `acs:RegionId` — Region ID
- `acs:SecureTransport` — HTTPS only (`true`/`false`)
- `sts:ExternalId` — External ID for cross-account roles

Common operators:
- `StringEquals`, `StringNotEquals`
- `StringLike`, `StringNotLike` (supports `*` wildcard)
- `NumericEquals`, `NumericGreaterThan`
- `DateTimeGreaterThan`, `DateTimeLessThan`
- `IpAddress`, `NotIpAddress`
- `Bool`

## Access Keys

Long-term credentials for programmatic access.

- **AccessKey ID:** Public identifier (starts with `LTAI` or `AK`)
- **AccessKey Secret:** Private key, shown ONLY at creation time
- **Status:** `Active` or `Inactive`
- **Limit:** 2 per RAM user
- **Rotation:** Recommended every 90 days

## Login Profiles

Console access configuration for RAM users.

- **Password:** Console login password
- **PasswordResetRequired:** Force password change on next login
- **MFABindRequired:** Require MFA before console access

## MFA (Multi-Factor Authentication)

Additional authentication layer using TOTP (Time-based One-Time Password).

- **Virtual MFA device:** Software-based (Google Authenticator, Authy, etc.)
- **Binding:** Requires two consecutive TOTP codes
- **Serial number:** Unique identifier for the MFA device

## STS (Security Token Service)

Issues temporary credentials for assumed roles.

- **AssumeRole:** Obtain temporary credentials by assuming a RAM role
- **GetCallerIdentity:** Identify the current caller (account, ARN, user ID)
- **Temporary credentials:** AccessKeyId, AccessKeySecret, SecurityToken,
  Expiration

## ARN Format

Alibaba Cloud Resource Name (ARN) uniquely identifies a resource:

```
acs:<service>:<region>:<account-id>:<resource-type>/<resource-id>
```

Examples:
- User: `acs:ram::1234567890123456:user/alice`
- Role: `acs:ram::1234567890123456:role/MyRole`
- Policy: `acs:ram::1234567890123456:policy/my-policy`
- Group: `acs:ram::1234567890123456:group/developers`

## Password Policy

Account-wide rules for RAM user passwords:

- `MinimumPasswordLength`: 8–32 characters
- `RequireLowercaseCharacters`: `true`/`false`
- `RequireUppercaseCharacters`: `true`/`false`
- `RequireNumbers`: `true`/`false`
- `RequireSymbols`: `true`/`false`
- `MaxLoginAttempts`: 3–32 (account lockout threshold)
- `PasswordReusePrevention`: 1–24 (prevent reusing last N passwords)
- `MaxPasswordAge`: 0–180 days (0 = no expiration)
- `HardExpiry`: `true`/`false` (force password change after max age)
