# alicloud-terraform-ops Scripts

Terraform IaC 工具脚本集。推荐通过统一入口 `terraform_ops.py` 调用。

## 统一 CLI (`terraform_ops.py`)

```bash
# NL2HCL 生成
python3 terraform_ops.py create --request "创建 VPC 和两个交换机" --dry-run

# 交互式向导 (等同 aliyun-terraform wizard)
python3 terraform_ops.py wizard nl2hcl --quick --template vpc-basic
python3 terraform_ops.py wizard import --type vpc --id vpc-xxx
python3 terraform_ops.py wizard history --limit 10
python3 terraform_ops.py wizard resume session-20260608-120000

# 逆向工程
python3 terraform_ops.py import --resource-type vpc --resource-id vpc-xxx --dry-run -D

# HITL 检查点 (Mode C)
python3 terraform_ops.py list
python3 terraform_ops.py resume <checkpoint-id>

# PR 审核 (Mode B)
python3 terraform_ops.py pr-create --workflow-type nl2hcl --env dev --files-dir ./generated
python3 terraform_ops.py pr-status pr-1
```

别名: `python3 wizard_cli.py nl2hcl` (standalone wizard)

---

# Terraform IaC HITL Mode A - 交互式 CLI

人机介入模式 A 的实现：命令行交互式工作流。

## 功能特性

- **五级环境策略**: int / dev / uat / performance / production
- **五大检查点 (CP1-CP5)**:
  - CP1: 意图确认 (Intent Confirmation)
  - CP2: 配置审核 (Config Review)
  - CP3: Plan 确认 (Plan Confirmation)
  - CP4: 导入确认 (Import Confirmation)
  - CP5: 销毁确认 (Destroy Confirmation)
- **会话持久化**: 支持中断恢复
- **超时管理**: 每个检查点可配置超时
- **信号处理**: Ctrl+C 自动保存检查点

## 快速开始

### 1. 创建新会话

```bash
# NL2HCL 场景 - 生成 Terraform 配置
python3 hitl_mode_a.py --type nl2hcl --env dev

# Import 场景 - 导入现有资源
python3 hitl_mode_a.py --type import --env uat

# Destroy 场景 - 销毁资源（最高安全级别）
python3 hitl_mode_a.py --type destroy --env production
```

### 2. 恢复会话

```bash
# 列出活跃检查点
python3 hitl_mode_a.py --list

# 恢复指定检查点
python3 hitl_mode_a.py --resume cp-nl2hcl-dev-20240608-143052
```

### 3. 程序化使用

```python
from hitl_mode_a import (
    create_checkpoint, 
    CLIController, 
    CheckpointStore,
    CheckpointType,
    Environment
)

# 创建检查点
checkpoint = create_checkpoint(
    checkpoint_type=CheckpointType.NL2HCL,
    environment=Environment.DEV,
    resources=[
        {"type": "vpc", "name": "main-vpc"},
        {"type": "ecs", "name": "web-server", "attributes": {"count": 2}}
    ]
)

# 运行控制器
controller = CLIController(checkpoint)
try:
    completed_checkpoint = controller.run()
    print(f"完成: {completed_checkpoint.id}")
except UserAbortedError:
    print("用户中止")
```

## 环境策略差异

| 环境 | CP1 意图 | CP2 审核 | CP3 Plan | CP5 销毁 |
|------|---------|---------|---------|---------|
| int | 必须 (5m) | 可选 | 必须 (自动批准小变更) | 单确认 |
| dev | 必须 (10m) | 可选 | 必须 | 单确认 |
| uat | 必须 (10m) | 必须 | 必须 | 双确认 |
| performance | 必须 (10m) | 必须 | 必须 | 双确认 |
| production | 必须+Jira (15m) | 必须+冷却期 | 必须+冷却期 | 双确认+冷却期 |

## 检查点存储

检查点默认存储在:
```
~/.pi/terraform-ops/checkpoints/
├── cp-nl2hcl-dev-20240608-143052.json
├── cp-import-uat-20240608-150123.json
└── ...
```

## 依赖

- Python 3.8+
- 仅使用标准库 (无外部依赖)

## 文件说明

| 文件 | 说明 |
|------|------|
| `terraform_ops.py` | 统一 CLI 入口 |
| `wizard_cli.py` | Interactive Wizard CLI |
| `nl2hcl_generator.py` | NL2HCL 生成器 |
| `reverse_engineering.py` | 逆向工程导入 |
| `resource_registry.py` | 资源注册与 PreFlight |
| `hitl_mode_a.py` | HITL Mode A 交互式 CLI |
| `hitl_mode_b.py` | HITL Mode B PR 审核 |
| `hitl_mode_c.py` | HITL Mode C 检查点暂停 |
| `hitl_common.py` | 共享层（审计/通知/配置） |
| `test_*.py` | 单元/集成测试 |
| `README.md` | 本文档 |

## 与文档对应关系

| 实现组件 | 规范文档 |
|---------|---------|
| `CLIController` | §3.1 Core Components |
| `CLIRenderer.prompt()` | §3.2 Interaction Patterns |
| `EnvironmentPolicy` | §3.4 Five-Level Environment Policy |
| `CheckpointStore` | §6 Checkpoint Persistence |
| Signal Handler | §7 Error Handling |
