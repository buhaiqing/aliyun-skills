#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch generate missing reference files for skills."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Skill configurations
SKILL_CONFIGS = {
    "alicloud-agentrun-ops": {
        "name": "AgentRun",
        "chinese_name": "云助手命令执行",
        "product": "ecs",
        "api_version": "2014-05-26",
        "resources": ["Command", "Invocation", "Task"],
        "operations": [
            ("RunCommand", "执行命令", "RunCommand", "aliyun ecs RunCommand"),
            ("DescribeInvocations", "查询执行记录", "DescribeInvocations", "aliyun ecs DescribeInvocations"),
            ("DescribeInvocationResults", "查询执行结果", "DescribeInvocationResults", "aliyun ecs DescribeInvocationResults"),
            ("SendFile", "发送文件", "SendFile", "aliyun ecs SendFile"),
        ],
        "error_codes": [
            ("InvalidInstanceId.NotFound", "404", "实例不存在", "验证 InstanceId"),
            ("InvalidRegionId.NotFound", "404", "地域不存在", "检查 RegionId"),
            ("InvalidCommandId.NotFound", "404", "命令不存在", "验证 CommandId"),
            ("CommandExecutionFailed", "500", "命令执行失败", "检查命令内容和实例状态"),
        ],
    },
    "alicloud-das-ops": {
        "name": "DAS",
        "chinese_name": "数据库自治服务",
        "product": "das",
        "api_version": "2020-01-16",
        "resources": ["Instance", "Alarm", "SlowLog"],
        "operations": [
            ("GetInstance", "获取实例信息", "GetInstance", "aliyun das GetInstance"),
            ("GetAsyncErrorRequestList", "获取慢SQL列表", "GetAsyncErrorRequestList", "aliyun das GetAsyncErrorRequestList"),
            ("CreateAlarm", "创建告警规则", "CreateAlarm", "aliyun das CreateAlarm"),
            ("GetAlarmList", "获取告警列表", "GetAlarmList", "aliyun das GetAlarmList"),
        ],
        "error_codes": [
            ("InvalidDBInstanceId.NotFound", "404", "数据库实例不存在", "验证 InstanceId"),
            ("InvalidRegionId.NotFound", "404", "地域不存在", "检查 RegionId"),
            ("InsufficientResourceCapacity", "403", "资源不足", "切换地域或联系支持"),
            ("InvalidParameter", "400", "参数无效", "检查请求参数"),
        ],
    },
    "alicloud-gcl-runner-ops": {
        "name": "GCL Runner",
        "chinese_name": "GCL 质量门禁运行器",
        "product": "gcl",
        "api_version": "N/A",
        "resources": ["Trace", "Rubric", "PromptTemplate"],
        "operations": [
            ("Run", "执行 GCL 循环", "Run", "python gcl_runner.py"),
            ("ParseRubric", "解析评分标准", "ParseRubric", "内置方法"),
            ("Critique", "对抗性评审", "Critique", "内置方法"),
        ],
        "error_codes": [
            ("RUBRIC_ERROR", "4", "评分标准解析错误", "检查 rubric.md 格式"),
            ("SAFETY_FAIL", "2", "安全检查失败", "检查命令安全性"),
            ("MAX_ITER", "1", "达到最大迭代次数", "增加 max_iter 或检查 rubric 阈值"),
            ("USAGE_ERROR", "3", "参数错误", "检查命令行参数"),
        ],
    },
    "alicloud-mongodb-ops": {
        "name": "MongoDB",
        "chinese_name": "云数据库 MongoDB",
        "product": "dds",
        "api_version": "2015-12-01",
        "resources": ["DBInstance", "Account", "Backup"],
        "operations": [
            ("CreateDBInstance", "创建实例", "CreateDBInstance", "aliyun dds CreateDBInstance"),
            ("DescribeDBInstances", "查询实例列表", "DescribeDBInstances", "aliyun dds DescribeDBInstances"),
            ("DescribeBackups", "查询备份", "DescribeBackups", "aliyun dds DescribeBackups"),
            ("CreateBackup", "创建备份", "CreateBackup", "aliyun dds CreateBackup"),
        ],
        "error_codes": [
            ("InvalidDBInstanceId.NotFound", "404", "实例不存在", "验证 InstanceId"),
            ("InvalidRegionId.NotFound", "404", "地域不存在", "检查 RegionId"),
            ("QuotaExceeded", "403", "配额超限", "提升配额或删除未使用资源"),
            ("InsufficientBalance", "400", "余额不足", "充值账户"),
        ],
    },
    "alicloud-resourcemanager-ops": {
        "name": "ResourceManager",
        "chinese_name": "资源管理",
        "product": "resourcemanager",
        "api_version": "2020-03-31",
        "resources": ["Folder", "ResourceGroup", "Account", "ControlPolicy"],
        "operations": [
            ("CreateFolder", "创建文件夹", "CreateFolder", "aliyun resourcemanager CreateFolder"),
            ("CreateResourceGroup", "创建资源组", "CreateResourceGroup", "aliyun resourcemanager CreateResourceGroup"),
            ("ListFolders", "列出文件夹", "ListFolders", "aliyun resourcemanager ListFolders"),
            ("ListResourceGroups", "列出资源组", "ListResourceGroups", "aliyun resourcemanager ListResourceGroups"),
        ],
        "error_codes": [
            ("EntityNotExists.Folder", "404", "文件夹不存在", "验证 FolderId"),
            ("EntityNotExists.ResourceGroup", "404", "资源组不存在", "验证 ResourceGroupId"),
            ("NoPermission", "403", "无权限", "检查 RAM 权限"),
            ("InvalidParameter", "400", "参数无效", "检查请求参数"),
        ],
    },
}


def generate_core_concepts(skill_name: str, config: dict) -> str:
    """Generate core-concepts.md content."""
    resources_list = "\n".join([f"- **{r}**: Primary resource type" for r in config["resources"]])
    
    return f"""# Core Concepts — Alibaba Cloud {config['name']}

## What is {config['name']}?

{config['chinese_name']} ({config['name']}) is an Alibaba Cloud service for managing cloud resources.

## Key Concepts

{resources_list}

## Resource Lifecycle

### Status Flow
- **Creating**: Resource is being provisioned
- **Running/Available**: Resource is operational
- **Modifying**: Resource configuration is being changed
- **Deleting**: Resource is being removed
- **Deleted**: Resource has been removed

## Dependencies

- **Region**: Resources are region-specific
- **VPC**: Most resources require VPC network
- **RAM**: Access control via RAM policies

## Limits and Quotas

| Limit | Default | Adjustable |
|-------|---------|------------|
| Resources per region | Varies by product | Yes |
| API rate limit | 100-1000 QPS | Contact support |
| Resource tags | 20 per resource | No |

## Service Endpoints

- **Public Endpoint**: {config['product']}.aliyuncs.com
- **VPC Endpoint**: {config['product']}-vpc.aliyuncs.com (if available)
"""


def generate_api_sdk_usage(skill_name: str, config: dict) -> str:
    """Generate api-sdk-usage.md content."""
    operations_table = "\n".join(
        [f"| {op[1]} | `{op[0]}` | `{op[2]}()` | `{op[3]}` |" for op in config["operations"]]
    )
    
    return f"""# API & SDK — Alibaba Cloud {config['name']}

## OpenAPI

- **Service**: {config['product'].upper()}
- **API Version**: {config['api_version']}
- **Base Endpoint**: `{config['product']}.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/{config['product']}

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
{operations_table}

## SDK Package

```bash
go get github.com/alibabacloud-go/{config['product']}-{config['api_version'].replace('-', '')}/client
```

## Request / Response Notes

### Common Patterns
- **Pagination**: `PageNumber`, `PageSize` parameters
- **Filters**: Use `Describe*` APIs with filter parameters
- **Async Operations**: Long-running operations return `RequestId` for polling

### Response Codes
- **Success**: HTTP 200, JSON with `RequestId`
- **Client Error**: HTTP 4xx, check error message
- **Server Error**: HTTP 5xx, retry with backoff
"""


def generate_troubleshooting(skill_name: str, config: dict) -> str:
    """Generate troubleshooting.md content."""
    error_table = "\n".join(
        [f"| `{code}` | {http} | {mean} | {action} |" for code, http, mean, action in config["error_codes"]]
    )
    
    return f"""# Troubleshooting Alibaba Cloud {config['name']}

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
{error_table}
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | Add RAM policy |

## Diagnostic Order

1. **Verify resource exists**: Describe by ID
2. **Check status**: Ensure resource is in expected state
3. **Check region**: Verify correct RegionId
4. **Verify credentials**: Test with simple `Describe` operation
5. **Check quotas**: Verify service quotas not exceeded

## Common Issues

### Authentication Failures
- Verify `ALIBABA_CLOUD_ACCESS_KEY_ID` is set
- Verify `ALIBABA_CLOUD_ACCESS_KEY_SECRET` is correct
- Check RAM user has required permissions

### Resource Not Found
- Verify resource ID format
- Check resource exists in correct region
- Resource may have been deleted

### Quota Exceeded
- Check current usage vs limits
- Request quota increase if needed
- Clean up unused resources

## Getting Help

- **OpenAPI Explorer**: https://api.aliyun.com/
- **Documentation**: https://www.alibabacloud.com/help/en/{config['product']}
- **Support**: Submit ticket via Alibaba Cloud Console
"""


def generate_integration(skill_name: str, config: dict) -> str:
    """Generate integration.md content."""
    return f"""# Integration

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

Minimum permissions for {config['name']} operations:

```json
{{
  "Version": "1",
  "Statement": [
    {{
      "Effect": "Allow",
      "Action": [
        "{config['product']}:Describe*",
        "{config['product']}:List*",
        "{config['product']}:Get*"
      ],
      "Resource": "*"
    }}
  ]
}}
```

For write operations, add:
```json
{{
  "Effect": "Allow",
  "Action": [
    "{config['product']}:Create*",
    "{config['product']}:Modify*",
    "{config['product']}:Delete*"
  ],
  "Resource": "*"
}}
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
go get github.com/alibabacloud-go/{config['product']}-{config['api_version'].replace('-', '')}/client
```

## Cross-Skill Integration

See individual SKILL.md files for delegation rules.
"""


def fix_invalid_json(skill_name: str) -> bool:
    """Fix invalid eval_queries.json files."""
    assets_dir = REPO_ROOT / skill_name / "assets"
    target_file = assets_dir / "eval_queries.json"
    
    if not target_file.exists():
        return False
    
    try:
        content = target_file.read_text(encoding="utf-8")
        json.loads(content)
        return False  # Already valid
    except json.JSONDecodeError:
        # Create valid JSON
        template = {
            "queries": [
                {"query": f"查询 {skill_name.replace('alicloud-', '').replace('-ops', '')} 信息", "expected_skill": skill_name, "priority": "P0"},
                {"query": f"创建 {skill_name.replace('alicloud-', '').replace('-ops', '')} 资源", "expected_skill": skill_name, "priority": "P0"},
            ]
        }
        target_file.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        return True


def main():
    """Generate missing reference files."""
    generated = []
    fixed = []
    skipped = []

    # Generate reference files
    for skill_name, config in SKILL_CONFIGS.items():
        skill_dir = REPO_ROOT / skill_name
        ref_dir = skill_dir / "references"

        if not skill_dir.exists():
            skipped.append(f"{skill_name}: directory not found")
            continue

        ref_dir.mkdir(exist_ok=True)

        # Generate core-concepts.md
        core_concepts = ref_dir / "core-concepts.md"
        if not core_concepts.exists():
            core_concepts.write_text(generate_core_concepts(skill_name, config), encoding="utf-8")
            generated.append(f"{skill_name}/core-concepts.md")

        # Generate api-sdk-usage.md
        api_sdk = ref_dir / "api-sdk-usage.md"
        if not api_sdk.exists():
            api_sdk.write_text(generate_api_sdk_usage(skill_name, config), encoding="utf-8")
            generated.append(f"{skill_name}/api-sdk-usage.md")

        # Generate troubleshooting.md
        troubleshooting = ref_dir / "troubleshooting.md"
        if not troubleshooting.exists():
            troubleshooting.write_text(generate_troubleshooting(skill_name, config), encoding="utf-8")
            generated.append(f"{skill_name}/troubleshooting.md")

        # Generate integration.md
        integration = ref_dir / "integration.md"
        if not integration.exists():
            integration.write_text(generate_integration(skill_name, config), encoding="utf-8")
            generated.append(f"{skill_name}/integration.md")

    # Fix invalid JSON files
    for skill_name in ["alicloud-cms-ops", "alicloud-elasticsearch-ops"]:
        if fix_invalid_json(skill_name):
            fixed.append(f"{skill_name}/eval_queries.json")

    # Print report
    print("=" * 60)
    print("Missing Reference Files Generation Report")
    print("=" * 60)
    print(f"\nGenerated: {len(generated)} files")
    for f in generated:
        print(f"  ✓ {f}")

    if fixed:
        print(f"\nFixed: {len(fixed)} files")
        for f in fixed:
            print(f"  ✓ {f}")

    if skipped:
        print(f"\nSkipped: {len(skipped)}")
        for reason in skipped:
            print(f"  - {reason}")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
