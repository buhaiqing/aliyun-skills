#!/usr/bin/env python3
"""
HITL Mode A 使用示例
展示如何在 Python 代码中使用交互式 CLI
"""

from hitl_mode_a import (
    create_checkpoint,
    CLIController,
    CheckpointStore,
    CheckpointType,
    Environment,
    resume_checkpoint,
    list_checkpoints
)


def example_1_basic_nl2hcl():
    """示例1: 基本的 NL2HCL 工作流"""
    print("=" * 60)
    print("示例1: NL2HCL 工作流 (dev 环境)")
    print("=" * 60)
    
    # 创建检查点
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.NL2HCL,
        environment=Environment.DEV,
        resources=[
            {
                "type": "alicloud_vpc",
                "name": "main-vpc",
                "attributes": {"cidr_block": "10.0.0.0/16"}
            },
            {
                "type": "alicloud_vswitch",
                "name": "web-subnet-1",
                "attributes": {"availability_zone": "cn-hangzhou-a"}
            },
            {
                "type": "alicloud_vswitch",
                "name": "web-subnet-2",
                "attributes": {"availability_zone": "cn-hangzhou-b"}
            },
            {
                "type": "alicloud_instance",
                "name": "web-server",
                "attributes": {"instance_type": "ecs.c6.large", "count": 2}
            }
        ]
    )
    
    # 添加生成的配置文件（模拟）
    checkpoint.generated_files = {
        "main.tf": '''
resource "alicloud_vpc" "main" {
  vpc_name   = "main-vpc"
  cidr_block = "10.0.0.0/16"
}

resource "alicloud_vswitch" "web_1" {
  vswitch_name = "web-subnet-1"
  vpc_id       = alicloud_vpc.main.id
  cidr_block   = "10.0.1.0/24"
  zone_id      = "cn-hangzhou-a"
}
''',
        "variables.tf": '''
variable "region" {
  default = "cn-hangzhou"
}
'''
    }
    
    print(f"检查点已创建: {checkpoint.id}")
    print(f"环境: {checkpoint.environment.value}")
    print(f"资源数量: {len(checkpoint.resources)}")
    print(f"步骤: {[s.type.value for s in checkpoint.steps]}")
    print()
    
    # 运行 CLI 控制器
    print("启动交互式 CLI...")
    print("(按 Ctrl+C 保存并退出，或使用 --resume 恢复)")
    print()
    
    store = CheckpointStore()
    controller = CLIController(checkpoint, store)
    
    try:
        completed = controller.run()
        print(f"\n完成! 状态: {completed.status.value}")
    except Exception as e:
        print(f"\n执行中断: {e}")


def example_2_import_with_selection():
    """示例2: 逆向导入（带资源选择）"""
    print("=" * 60)
    print("示例2: 逆向导入工作流 (uat 环境)")
    print("=" * 60)
    
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.IMPORT,
        environment=Environment.UAT,
        resources=[
            {
                "type": "alicloud_vpc",
                "name": "prod-vpc",
                "id": "vpc-bp1xxxxxxxxxxxx",
                "status": "ready"
            },
            {
                "type": "alicloud_vswitch",
                "name": "subnet-1",
                "id": "vsw-bp1xxxxxxxxxxxx",
                "status": "ready"
            },
            {
                "type": "alicloud_instance",
                "name": "legacy-server",
                "id": "i-bp1xxxxxxxxxxxx",
                "status": "ready",
                "warnings": ["该实例有特殊安全组规则，导入后需手动检查"]
            }
        ]
    )
    
    print(f"检查点已创建: {checkpoint.id}")
    print(f"发现资源: {len(checkpoint.resources)}")
    for r in checkpoint.resources:
        warning = f" ⚠️ {r.warnings[0]}" if r.warnings else ""
        print(f"  - {r.name} ({r.id}){warning}")
    print()
    
    store = CheckpointStore()
    controller = CLIController(checkpoint, store)
    
    try:
        completed = controller.run()
        print(f"\n完成! 状态: {completed.status.value}")
    except Exception as e:
        print(f"\n执行中断: {e}")


def example_3_destroy_production():
    """示例3: 生产环境销毁（最高安全级别）"""
    print("=" * 60)
    print("示例3: 销毁工作流 (production 环境)")
    print("=" * 60)
    print("注意: 此示例展示最高安全级别的确认流程")
    print()
    
    checkpoint = create_checkpoint(
        checkpoint_type=CheckpointType.DESTROY,
        environment=Environment.PRODUCTION,
        resources=[
            {"type": "alicloud_instance", "name": "test-server-1", "id": "i-bp1xxxx1"},
            {"type": "alicloud_instance", "name": "test-server-2", "id": "i-bp1xxxx2"},
        ]
    )
    
    print(f"检查点已创建: {checkpoint.id}")
    print(f"⚠️ 将要销毁的资源:")
    for r in checkpoint.resources:
        print(f"  - {r.name} ({r.id})")
    print()
    print("生产环境销毁需要:")
    print("  1. Jira Ticket 编号")
    print("  2. 变更原因")
    print("  3. 30秒冷却期")
    print("  4. 双重确认")
    print()
    
    store = CheckpointStore()
    controller = CLIController(checkpoint, store)
    
    try:
        completed = controller.run()
        print(f"\n完成! 状态: {completed.status.value}")
    except Exception as e:
        print(f"\n执行中断: {e}")


def example_4_resume_checkpoint():
    """示例4: 恢复检查点"""
    print("=" * 60)
    print("示例4: 恢复检查点")
    print("=" * 60)
    
    # 先列出活跃检查点
    store = CheckpointStore()
    checkpoints = list_checkpoints(store)
    
    if not checkpoints:
        print("当前没有活跃检查点")
        print("请先运行其他示例创建检查点")
        return
    
    print("活跃检查点:")
    for i, cp in enumerate(checkpoints, 1):
        print(f"  {i}. {cp.id}")
        print(f"     类型: {cp.type.value}, 环境: {cp.environment.value}")
        print(f"     状态: {cp.status.value}")
        print(f"     当前步骤: {cp.current_step_index + 1}/{len(cp.steps)}")
    
    # 恢复第一个检查点
    cp = checkpoints[0]
    print(f"\n恢复检查点: {cp.id}")
    
    resumed = resume_checkpoint(cp.id, store)
    controller = CLIController(resumed, store)
    
    try:
        completed = controller.run()
        print(f"\n完成! 状态: {completed.status.value}")
    except Exception as e:
        print(f"\n执行中断: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python3 example_usage.py <example_number>")
        print()
        print("可用示例:")
        print("  1 - NL2HCL 工作流 (dev 环境)")
        print("  2 - 逆向导入 (uat 环境)")
        print("  3 - 销毁工作流 (production 环境)")
        print("  4 - 恢复检查点")
        print()
        print("例如: python3 example_usage.py 1")
        sys.exit(1)
    
    example_num = sys.argv[1]
    
    examples = {
        "1": example_1_basic_nl2hcl,
        "2": example_2_import_with_selection,
        "3": example_3_destroy_production,
        "4": example_4_resume_checkpoint,
    }
    
    example_func = examples.get(example_num)
    if example_func:
        example_func()
    else:
        print(f"未知示例: {example_num}")
        print(f"可用示例: {', '.join(examples.keys())}")
