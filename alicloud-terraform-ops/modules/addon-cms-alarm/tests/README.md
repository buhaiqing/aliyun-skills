# Terratest Suite — addon-cms-alarm

> 云监控告警模块的集成测试套件

## 测试覆盖

| 测试用例 | 说明 | 覆盖场景 |
|----------|------|----------|
| `TestCmsAlarmBasicCreate` | 基础告警创建 | 创建 CPU/内存/磁盘/SLB 502 告警 |
| `TestCmsAlarmCustomThresholds` | 自定义阈值 | 阈值配置差异化 |
| `TestCmsAlarmWithDingtalk` | 钉钉 Webhook | 钉钉通知集成 |
| `TestCmsAlarmWithFeishu` | 飞书 Webhook | 飞书通知集成 |
| `TestCmsAlarmWithWeCom` | 企业微信 Webhook | 企业微信通知集成 |
| `TestCmsAlarmMultiChannel` | 多渠道 Webhook | 同时配置多个渠道 |
| `TestCmsAlarmResourceSpecific` | 指定资源告警 | 按实例 ID 告警 |
| `TestCmsAlarmDriftDetection` | 漂移检测 | 配置与实际一致性 |
| `TestCmsAlarmIdempotency` | 幂等性 | 重复 apply 无变更 |
| `TestCmsAlarmTags` | 标签验证 | 标签正确性 |
| `TestOutputsFormat` | 输出格式 | Output 结构正确 |
| `TestConfigValidation` | 配置验证 | 变量边界检查 |

## 快速开始

### 1. 环境准备

```bash
# 设置阿里云凭证
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_sk"
export ALIBABA_CLOUD_REGION="cn-hangzhou"

# 可选：测试邮箱
export TF_TEST_EMAIL="your@email.com"

# 可选：钉钉 Webhook
export TF_TEST_DINGTALK_WEBHOOK="https://oapi.dingtalk.com/..."

# 可选：飞书 Webhook
export TF_TEST_FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 可选：企业微信 Webhook
export TF_TEST_WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"

# 可选：指定 ECS 实例 ID（用于资源级告警测试）
export TF_TEST_ECS_INSTANCE_ID="i-xxxxxxxxx"
```

### 2. 运行测试

```bash
cd tests

# 下载依赖
go mod download

# 运行所有测试（跳过需要真实资源的）
go test -v -tags=integration ./...

# 运行特定测试
go test -v -tags=integration -run TestCmsAlarmBasicCreate

# 运行性能基准测试
go test -bench=. -benchmem -tags=integration

# 清理测试资源
go test -v -tags=integration -run TestCmsAlarmBasicCreate -cleanup
```

### 3. 理解测试输出

```
=== RUN   TestCmsAlarmBasicCreate
   alarm_test.go:52: Environment: test, Region: cn-hangzhou
    alarm_test.go:54: Running terraform init...
    alarm_test.go:58: Running terraform plan...
    alarm_test.go:63: Running terraform apply...
    alarm_test.go:71: Validating outputs...
    alarm_test.go:87: ✅ Basic creation test passed
--- PASS: TestCmsAlarmBasicCreate (45.23s)
```

## 测试架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Terratest Test Suite                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Setup    │───▶│   Apply    │───▶│   Validate  │     │
│  │  Variables │    │            │    │   Outputs   │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│                                                │             │
│                                                ▼             │
│                                        ┌─────────────┐      │
│                                        │   Destroy  │      │
│                                        │   Cleanup  │      │
│                                        └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 预期结果

### 通过标准

```
✅ 所有测试 PASS
✅ 无 drift（apply 后 plan 为空）
✅ 告警 ID 稳定（幂等性）
✅ 输出格式正确
```

### 失败诊断

| 失败类型 | 可能原因 | 排查命令 |
|----------|----------|----------|
| `terraform init` 失败 | Provider 未下载 | `terraform init -upgrade` |
| `terraform apply` 失败 | 凭证无效/权限不足 | `aliyun configure get` |
| Alarm ID 为空 | 联系人组配置错误 | 检查 `email_contacts` |
| Drift 检测失败 | 云上资源被手动修改 | `terraform plan` 查看差异 |

## CI/CD 集成

### GitHub Actions

```yaml
# .github/workflows/test-cms-alarm.yml
name: CMS Alarm Terratest

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0

      - name: Configure Alibaba Cloud
        env:
          ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
          ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
          ALIBABA_CLOUD_REGION: cn-hangzhou
        run: |
          go mod download
          go test -v -tags=integration ./...

      - name: Cleanup
        if: always()
        run: |
          cd tests
          terraform destroy -auto-approve || true
```

### Jenkins Pipeline

```groovy
pipeline {
    agent { label 'terraform' }

    environment {
        ALIBABA_CLOUD_ACCESS_KEY_ID = credentials('alibaba-cloud-ak')
        ALIBABA_CLOUD_ACCESS_KEY_SECRET = credentials('alibaba-cloud-sk')
        ALIBABA_CLOUD_REGION = 'cn-hangzhou'
        TF_TEST_EMAIL = 'test@example.com'
    }

    stages {
        stage('Test') {
            steps {
                dir('modules/addon-cms-alarm/tests') {
                    sh '''
                        go mod download
                        go test -v -tags=integration -timeout 30m
                    '''
                }
            }
        }
    }

    post {
        always {
            dir('modules/addon-cms-alarm/tests') {
                sh 'terraform destroy -auto-approve || true'
            }
        }
    }
}
```

## 本地调试

```bash
# 1. 单独运行 plan
cd tests
terraform init ..
terraform plan -var="environment=debug" -var="email_contacts=test@example.com" ..

# 2. 单步 apply
terraform apply -var="environment=debug" ..
terraform state list | grep cms

# 3. 查看告警
aliyun cms DescribeMetricRuleList --PageSize 100

# 4. 清理
terraform destroy -var="environment=debug" ..
```

## 测试矩阵

| 场景 | Dev | Staging | Prod |
|------|-----|---------|------|
| 基础创建 | ✅ | ✅ | ✅ |
| 自定义阈值 | ✅ | ✅ | ⚠️ |
| 钉钉通知 | ✅ | ✅ | ✅ |
| 资源级告警 | ⚠️ | ⚠️ | ⚠️ |
| 并发测试 | ❌ | ❌ | ❌ |

- ✅ 完全支持
- ⚠️ 需要特定资源
- ❌ 不建议在 CI 运行

## 相关文档

| 文档 | 说明 |
|------|------|
| [SPEC-cms-alarm.md](../SPEC-cms-alarm.md) | 模块规格 |
| [ADR-001](../adr/ADR-001-terraform-cms-alarm-management.md) | 架构决策 |
| [Terratest 官方文档](https://terratest.gruntwork.io/) | Terratest 用法 |
