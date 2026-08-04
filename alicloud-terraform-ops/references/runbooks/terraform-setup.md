# Runbook: Terraform 工具安装与配置

> **Scope**: Terraform CLI 安装、阿里云 Provider 配置、Backend 初始化、凭证管理

---

## 1. Terraform CLI 安装

### 1.1 Linux / macOS (官方脚本)

```bash
# 下载并安装最新版本
curl -fsSL https://apt.releases.hashicorp.com/install.sh | sh

# 验证安装
terraform -version
# Terraform v1.9.0

# 指定版本安装 (推荐生产环境)
TERRAFORM_VERSION="1.9.0"
curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o /tmp/terraform.zip
unzip /tmp/terraform.zip -d /usr/local/bin/
chmod +x /usr/local/bin/terraform
rm /tmp/terraform.zip
```

### 1.2 macOS (Homebrew)

```bash
brew install terraform
terraform -version
```

### 1.3 Windows (Chocolatey)

```powershell
choco install terraform -y
terraform -version
```

### 1.4 版本要求

| 最低版本 | 推荐版本 |
|---------|---------|
| ≥ 1.5.0 | ≥ 1.8.0 |

---

## 2. 阿里云 Provider 配置

### 2.1 Provider 版本约束

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.200.0"
    }
  }
}
```

### 2.2 凭证配置 (环境变量)

```bash
# 方式 1: 环境变量 (推荐)
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"
export ALIBABA_CLOUD_REGION="cn-hangzhou"

# 方式 2: aliyun configure (自动读取)
aliyun configure set --mode AK --access-key-id $ALIBABA_CLOUD_ACCESS_KEY_ID \
  --access-key-secret $ALIBABA_CLOUD_ACCESS_KEY_SECRET \
  --region $ALIBABA_CLOUD_REGION
```

⚠️ **安全警告**: 禁止将 AK/SK 写入 tfvars 文件或 git 仓库。

### 2.3 多账号配置

```hcl
# 方式 1: 多 Provider Alias
provider "alicloud" {
  alias = "prod"
  region = "cn-hangzhou"
}

provider "alicloud" {
  alias = "dev"
  region = "cn-qingdao"
}

# 方式 2: 环境变量切换
export ALIBABA_CLOUD_ACCESS_KEY_ID="prod_key"
terraform apply
```

---

## 3. OSS Backend 配置

### 3.1 架构

```
OSS Bucket (状态存储)
├── environments/
│   ├── production/
│   │   └── terraform.tfstate
│   └── development/
│       └── terraform.tfstate
│
OTS Table (状态锁)
└── terraform_state_lock
```

### 3.2 创建 OSS Bucket

```bash
# 通过阿里云 CLI 创建
aliyun oss mb oss://terraform-state-${ALIBABA_CLOUD_ACCOUNT_ID}-${ALIBABA_CLOUD_REGION} \
  --region ${ALIBABA_CLOUD_REGION}

# 或通过控制台创建
# 存储类型: 标准存储
# 加密: AES256 (可选)
```

### 3.3 创建 OTS 表

```bash
# 通过阿里云 CLI 创建 OTS 实例
aliyun ots CreateInstance \
  --instanceName "terraform-lock-${ALIBABA_CLOUD_REGION}" \
  --description "Terraform State Lock"

# 创建表
aliyun ots CreateTable \
  --instanceName "terraform-lock-${ALIBABA_CLOUD_REGION}" \
  --tableName "terraform_state_lock" \
  --primaryKey '[{"Name": "LockID", "Type": "STRING"}]'
```

### 3.4 Backend 配置

```hcl
# backend.tf
terraform {
  backend "oss" {
    bucket               = "terraform-state-prod"        # 替换为你的 bucket 名
    prefix              = "environments/production"   # 状态文件前缀
    key                 = "terraform.tfstate"          # 状态文件 key
    tablestore_endpoint = "https://terraform-lock.cn-hangzhou.ots.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
    encrypt             = true                        # 状态加密
  }
}
```

### 3.5 多环境配置

```hcl
# environments/production/backend.tf
terraform {
  backend "oss" {
    bucket               = "terraform-state-prod"
    prefix              = "environments/production"
    tablestore_endpoint = "https://terraform-lock.cn-hangzhou.ots.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}

# environments/staging/backend.tf
terraform {
  backend "oss" {
    bucket               = "terraform-state-staging"
    prefix              = "environments/staging"
    tablestore_endpoint = "https://terraform-lock.cn-hangzhou.ots.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}
```

---

## 4. 初始化与验证

### 4.1 首次初始化

```bash
# 本地开发环境
cd environments/development
terraform init

# 验证
terraform validate
terraform version
```

### 4.2 远程状态迁移

```bash
# 从本地迁移到 OSS
terraform init -migrate-state

# 确认迁移
terraform state list
```

### 4.3 状态锁定检查

```bash
# 查看当前锁
terraform state pull | jq '.serial'

# 强制解锁 (慎用!)
terraform force-unlock <LOCK_ID>
```

---

## 5. 凭证安全实践

### 5.1 RAM 最小权限

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:Describe*",
        "ecs:Create*",
        "ecs:Delete*",
        "ecs:Modify*",
        "vpc:Describe*",
        "vpc:Create*",
        "rds:Describe*",
        "rds:Create*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5.2 环境变量注入

```bash
# 在 CI/CD 中注入
export ALIBABA_CLOUD_ACCESS_KEY_ID=$(vault read -field=access_key_id secret/terraform/prod)
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=$(vault read -field=access_key_secret secret/terraform/prod)

# 使用 1Password
export ALIBABA_CLOUD_ACCESS_KEY_ID=$(op read "op://Terraform/Prod Access Key/access_key_id")
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=$(op read "op://Terraform/Prod Access Key/access_key_secret")
```

### 5.3 tfvars 安全

```bash
# .gitignore
*.tfvars
*.tfstate
.terraform/

# 本地开发
cp environments/production/terraform.tfvars.example environments/production/terraform.tfvars
# 编辑 terraform.tfvars (已忽略)
```

---

## 6. 多 Region 部署

### 6.1 跨 Region Provider

```hcl
# providers.tf
variable "regions" {
  type    = map(string)
  default = {
    primary   = "cn-hangzhou"
    disaster  = "cn-shanghai"
  }
}

provider "alicloud" {
  alias = "primary"
  region = var.regions.primary
}

provider "alicloud" {
  alias = "disaster"
  region = var.regions.disaster
}
```

### 6.2 数据源跨 Region 引用

```hcl
# 异地 VPC 对等连接
resource "alicloud_vpc_peer_connection" "example" {
  name                = "peer-connection"
  vpc_id             = alicloud_vpc.primary.id
  peer_vpc_id        = alicloud_vpc.disaster.id
  region             = var.regions.disaster
  peer_region        = var.regions.primary
}
```

---

## 7. 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Error: No valid credential sources found` | 环境变量未设置 | 检查 `ALIBABA_CLOUD_ACCESS_KEY_ID` |
| `Error: Bucket not found` | Bucket 不存在 | 先创建 OSS Bucket |
| `Error: Failed to lock state` | 状态被锁定 | 检查是否有其他 Terraform 进程 |
| `Error: Schema mismatch` | Provider 版本不一致 | `terraform init -upgrade` |
| `Error: cycle detected` | 资源依赖循环 | 检查 `depends_on` 配置 |

---

## 8. 卸载 Terraform

```bash
# Linux
rm /usr/local/bin/terraform

# macOS
brew uninstall terraform
```

---

## 9. 快速验证脚本

```bash
#!/bin/bash
set -e

echo "=== Terraform 环境检查 ==="

# 1. Terraform 版本
TF_VERSION=$(terraform -version 2>&1 | grep -oP 'v\K[\d.]+')
echo "Terraform: v${TF_VERSION}"

if [[ $(echo "$TF_VERSION < 1.5" | bc -l) -eq 1 ]]; then
  echo "❌ Terraform 版本过低，需要 >= 1.5.0"
  exit 1
fi

# 2. 阿里云凭证
if [[ -z "$ALIBABA_CLOUD_ACCESS_KEY_ID" ]]; then
  echo "❌ ALIBABA_CLOUD_ACCESS_KEY_ID 未设置"
  exit 1
fi
echo "✅ 凭证: $ALIBABA_CLOUD_ACCESS_KEY_ID"

# 3. 区域
echo "✅ 区域: ${ALIBABA_CLOUD_REGION:-cn-hangzhou}"

# 4. Backend Bucket
if [[ -z "$TF_BACKEND_BUCKET" ]]; then
  echo "⚠️  TF_BACKEND_BUCKET 未设置 (将使用本地状态)"
else
  echo "✅ Backend Bucket: $TF_BACKEND_BUCKET"
fi

echo "=== 检查完成 ==="
```
