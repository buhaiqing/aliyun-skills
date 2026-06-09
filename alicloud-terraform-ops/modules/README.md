# Terraform Modules — Module-First NL2HCL

NL2HCL 生成器在根目录 `main.tf` 中**仅输出 `module` 块**；本目录为可复用、可审查的实现源。

Agent 扩展模块 → [AGENTS.md](../AGENTS.md) §4 + [references/module-coverage.md](../references/module-coverage.md)

## 模块清单

| 模块 | 职责 |
|------|------|
| `vpc-network` | VPC + 多 AZ vSwitch |
| `compute-ecs` | 安全组 + ECS（含可选 data disk） |
| `web-stack` | 组合网络 + 计算 + 可选 RDS/Redis/SLB/NAT/EIP |
| `addon-rds` | RDS MySQL |
| `addon-redis` | Redis |
| `addon-slb` | SLB |
| `addon-nat` | NAT Gateway |
| `addon-eip` | EIP |
| `addon-disk` | 独立云盘 |
| `addon-route-table` | 路由表 |

## 生成物结构

```
generated/
├── main.tf          # 仅 module 调用
├── provider.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars
└── modules/         # 从本目录复制
    ├── web-stack/
    ├── vpc-network/
    └── ...
```

逆向工程（`reverse_engineering.py`）仍生成裸 `resource` 块用于 `terraform import`，与 NL2HCL 路径分离。
