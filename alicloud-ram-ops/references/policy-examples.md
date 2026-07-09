# Policy Examples for RAM

## Least-Privilege Policy for RAM Management

Grant a RAM user limited permission to manage other RAM users, groups, and
policies without full `AliyunRAMFullAccess`:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ram:Get*",
        "ram:List*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ram:CreateUser",
        "ram:DeleteUser",
        "ram:UpdateUser",
        "ram:CreateAccessKey",
        "ram:UpdateAccessKey",
        "ram:DeleteAccessKey",
        "ram:CreateLoginProfile",
        "ram:UpdateLoginProfile",
        "ram:DeleteLoginProfile"
      ],
      "Resource": "acs:ram::*:user/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ram:CreateGroup",
        "ram:DeleteGroup",
        "ram:AddUserToGroup",
        "ram:RemoveUserFromGroup"
      ],
      "Resource": "acs:ram::*:group/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ram:CreatePolicy",
        "ram:DeletePolicy",
        "ram:CreatePolicyVersion",
        "ram:DeletePolicyVersion",
        "ram:AttachPolicyToUser",
        "ram:DetachPolicyFromUser",
        "ram:AttachPolicyToGroup",
        "ram:DetachPolicyFromGroup"
      ],
      "Resource": [
        "acs:ram::*:policy/*",
        "acs:ram::*:user/*",
        "acs:ram::*:group/*"
      ]
    }
  ]
}
```

## Cross-Account Role Trust Policy

Allow another Alibaba Cloud account to assume this role:

```json
{
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "RAM": [
          "acs:ram::1234567890123456:root"
        ]
      },
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "my-external-id-123"
        }
      }
    }
  ],
  "Version": "1"
}
```

> **Security:** Always use `sts:ExternalId` for cross-account roles to prevent
> the confused deputy problem.

## Service-Linked Role Trust Policy

Allow an Alibaba Cloud service to assume this role:

```json
{
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ecs.aliyuncs.com",
          "rds.aliyuncs.com"
        ]
      }
    }
  ],
  "Version": "1"
}
```

## Read-Only ECS Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:Describe*",
        "ecs:List*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Region-Restricted ECS Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeInstances",
        "ecs:StartInstance",
        "ecs:StopInstance",
        "ecs:RebootInstance"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "acs:RegionId": "cn-hangzhou"
        }
      }
    }
  ]
}
```

## Deny High-Risk Actions Policy

Explicitly deny destructive actions (overrides any Allow):

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecs:*",
      "Resource": "*"
    },
    {
      "Effect": "Deny",
      "Action": [
        "ecs:DeleteInstance",
        "ecs:TerminateInstance",
        "ecs:Release*"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Note:** `Deny` always takes precedence over `Allow`.

## Time-Based Access Policy

Restrict access to business hours (UTC+8):

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecs:*",
      "Resource": "*",
      "Condition": {
        "DateTimeGreaterThan": {
          "acs:CurrentTime": "2026-01-01T09:00:00+08:00"
        },
        "DateTimeLessThan": {
          "acs:CurrentTime": "2026-01-01T18:00:00+08:00"
        }
      }
    }
  ]
}
```

## IP-Restricted Policy

Restrict access to specific source IP ranges:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ram:*",
      "Resource": "*",
      "Condition": {
        "IpAddress": {
          "acs:SourceIp": [
            "192.168.1.0/24",
            "10.0.0.0/8"
          ]
        }
      }
    }
  ]
}
```

## HTTPS-Only Policy

Enforce that all API calls use HTTPS (secure transport):

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecs:*",
      "Resource": "*",
      "Condition": {
        "Bool": {
          "acs:SecureTransport": "true"
        }
      }
    }
  ]
}
```

> **Note:** When `acs:SecureTransport` is `"false"` or absent, the condition
> fails and the `Allow` does not apply. Combine with a base `Deny` for
> defense-in-depth.

## STS AssumeRole Permission Policy

Allow a RAM user to assume a specific role:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "acs:ram::1234567890123456:role/MyCrossAccountRole"
    }
  ]
}
```

## Policy for Agent Runtime (Minimal)

Minimal policy for an AI agent to read RAM configuration:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ram:Get*",
        "ram:List*",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```
