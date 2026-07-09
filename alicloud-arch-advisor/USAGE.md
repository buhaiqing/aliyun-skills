# alicloud-arch-advisor 使用手册 (USAGE)

**版本**: 1.4.0
**更新日期**: 2026-06-11

本文档详细说明 alicloud-arch-advisor 的所有功能、使用方法和最佳实践。

---

## 目录

- [快速开始](#快速开始)
- [三种工作模式](#三种工作模式)
- [命令行参考](#命令行参考)
- [交互式向导](#交互式向导)
- [多语言支持](#多语言支持)
- [进度条功能](#进度条功能)
- [错误处理](#错误处理)
- [单元测试](#单元测试)
- [常见问题](#常见问题)

---

## 快速开始

### 1. 环境准备

```bash
# 安装依赖工具
brew install jq                    # macOS
apt install jq                     # Ubuntu/Debian

# 安装 aliyun CLI
curl -O https://aliyuncli.alicdn.com/aliyun-cli-linux-3.0.6-amd64.tgz
tar xzf aliyun-cli-linux-3.0.6-amd64.tgz
sudo cp aliyun /usr/local/bin/

# 配置凭证
aliyun configure
```

### 2. 三种启动方式

```bash
# 方式 1: 交互式向导 (推荐新手)
./scripts/interactive-wizard.sh

# 方式 2: 直接命令行 (适合脚本化)
./scripts/assess.sh --reverse-eng true --region cn-hangzhou
./scripts/recommend.sh --scenario ecommerce --dau 100000

# 方式 3: 自动化模式 (CI/CD)
./scripts/assess.sh --mock --output json > report.json
```

### 3. 设置语言

```bash
# 中文 (默认)
export ARCH_ADVISOR_LANG=zh_CN

# 英文
export ARCH_ADVISOR_LANG=en_US
```

---

## 三种工作模式

### Mode A: 架构逆向与分析 (Reverse Engineering)

**用途**: 分析现有云资源架构,生成架构图和文档

**触发场景**:
- "帮我看看我的系统架构"
- "分析一下我的 ECS + RDS 架构"
- "生成当前架构文档"

**输入参数**:

| 参数 | 说明 | 必需 | 示例 |
|------|------|:----:|------|
| `--region` | 阿里云地域 | ✓ | `cn-hangzhou` |
| `--resource-group` | 资源组 ID | ✗ | `rg-xxxxx` |
| `--tags` | 标签过滤 | ✗ | `env=prod,app=web` |
| `--vpc-id` | VPC ID 过滤 | ✗ | `vpc-xxxxx` |
| `--output` | 输出格式 | ✗ | `markdown` / `json` |

**输出**:
- 拓扑图 (Mermaid 格式)
- 架构模式识别 (single-node, 3-tier, microservice, serverless, multi-region)
- 架构文档 (Markdown)
- 资源清单 (JSON)

**使用示例**:

```bash
# 分析杭州地域的所有生产环境资源
./scripts/assess.sh \
  --reverse-eng true \
  --region cn-hangzhou \
  --tags "env=prod" \
  --output markdown

# 仅分析特定 VPC
./scripts/assess.sh \
  --reverse-eng true \
  --vpc-id vpc-2ze0jx9vjk6n2j4f7xxxx \
  --mock  # 无凭证时使用 Mock 数据
```

### Mode B: WAF 成熟度评估 (Assessment)

**用途**: 基于阿里云 Well-Architected Framework 的五支柱评估

**五支柱**:
1. **Security (安全)**: 安全组、访问控制、加密、审计
2. **Reliability (可靠性)**: 高可用、备份、多 AZ 容错
3. **Performance (性能)**: 实例规格、存储 IOPS、网络带宽
4. **Cost (成本)**: 资源利用率、闲置资源、付费模式
5. **Efficiency (效率)**: 自动化、运维流程、资源编排

**评估维度选择**:

```bash
# 评估所有维度
./scripts/assess.sh --reverse-eng false --pillars all

# 仅评估安全和可靠性
./scripts/assess.sh --reverse-eng false --pillars security,reliability

# 评估单个维度
./scripts/assess.sh --reverse-eng false --pillars cost
```

**输出**:
- 五支柱评分卡 (0-100 分)
- 风险清单 (Critical/High/Medium/Low)
- 改进建议 (按优先级排序)
- 资源优化建议

### Mode C: 架构方案推荐 (Recommendation)

**用途**: 根据业务场景推荐最优架构方案

**支持的业务场景**:
- `ecommerce` - 电商平台
- `saas` - SaaS 应用
- `data-platform` - 数据平台
- `microservice` - 微服务架构
- `serverless` - Serverless 应用
- `game` - 游戏后端

**输入参数**:

| 参数 | 说明 | 必需 | 示例 |
|------|------|:----:|------|
| `--scenario` | 业务场景 | ✓ | `ecommerce` |
| `--dau` | 日活跃用户数 | ✓ | `100000` |
| `--ha` | 高可用等级 | ✗ | `multi-az` (默认) |
| `--compliance` | 合规要求 | ✗ | `pci` / `hipaa` / `gdpr` |
| `--budget` | 月预算 (USD) | ✗ | `5000` |
| `--region` | 部署地域 | ✗ | `cn-hangzhou` |

**使用示例**:

```bash
# 推荐电商平台架构 (10万 DAU, 多 AZ, $5000/月预算)
./scripts/recommend.sh \
  --scenario ecommerce \
  --dau 100000 \
  --ha multi-az \
  --compliance pci \
  --budget 5000 \
  --region cn-hangzhou

# 数据平台 (50万 DAU, 单 AZ)
./scripts/recommend.sh \
  --scenario data-platform \
  --dau 500000 \
  --ha single-az \
  --region cn-shanghai
```

**输出**:
- 架构蓝图 (JSON + Mermaid)
- 组件清单 (ECS/RDS/Redis/SLB 等)
- 规格可用性验证 (自动降级)
- 成本估算 (规格感知)
- 实施步骤

---

## 命令行参考

### assess.sh 参数

```bash
./scripts/assess.sh [OPTIONS]

资源过滤:
  --region REGION        阿里云地域 (默认: cn-hangzhou)
  --resource-group RG    资源组 ID
  --tags "k=v,k=v"       标签过滤
  --vpc-id VPC_ID        VPC ID 过滤

跨账号:
  --cross-account        启用跨账号模式
  --assume-role ARN      AssumeRole ARN

评估选项:
  --pillars LIST         WAF 维度: security,reliability,performance,cost,efficiency
  --output FORMAT        markdown | json
  --reverse-eng BOOL     true | false (默认: true)
  --mock                 使用 Mock 数据模式

其他:
  -h, --help             显示帮助
```

### recommend.sh 参数

```bash
./scripts/recommend.sh [OPTIONS]

必需参数:
  --scenario NAME        业务场景: ecommerce,saas,data-platform,microservice,serverless,game
  --dau NUM              日活跃用户数

可选参数:
  --ha LEVEL             single-az | multi-az | multi-region (默认: multi-az)
  --compliance TYPE      none | pci | hipaa | gdpr (默认: none)
  --budget NUM           月预算 (USD)
  --region REGION        部署地域 (默认: cn-hangzhou)
  --output FORMAT        markdown | json
  --output-dir PATH      输出目录 (默认: ./output)
```

### interactive-wizard.sh 参数

```bash
./scripts/interactive-wizard.sh
# 无参数,完全交互式
# 按提示选择模式、输入参数、确认执行
```

---

## 交互式向导

### 使用流程

```
┌─────────────────────────────────────────┐
│  阿里云架构顾问 - 交互式向导 (Wizard)    │
└─────────────────────────────────────────┘

请选择您需要的服务:
  1. 分析现有系统架构 (Mode A)
  2. 做一次 WAF 成熟度评估 (Mode B)
  3. 设计新系统架构方案 (Mode C)
  0. 退出
```

### 优势

- **零记忆成本**: 不需要记住所有参数
- **实时验证**: 输入时检查格式和有效性
- **配置确认**: 执行前显示完整配置,确认后运行
- **超时保护**: 30分钟自动超时,避免挂起

### 适用场景

- 首次使用,不熟悉参数
- 探索性分析,需要多次尝试
- 教学/演示场景

---

## 多语言支持

### 切换语言

```bash
# 方式 1: 环境变量 (推荐)
export ARCH_ADVISOR_LANG=en_US   # English
export ARCH_ADVISOR_LANG=zh_CN   # Chinese (默认)

# 方式 2: LANG 环境变量
export LANG=en_US.UTF-8
export LANG=zh_CN.UTF-8
```

### 支持的字符串

- 通用日志前缀 (INFO/WARN/ERROR/SUCCESS)
- 进度条消息 (Elapsed/ETA/Complete)
- 交互式向导菜单
- 参数提示 (Region/DAU/HA/Compliance/Budget)
- 场景选择
- 执行消息
- 验证错误消息

### 扩展新语言

1. 在 `scripts/i18n.sh` 添加新的翻译字典:

```bash
declare -A I18N_JA_JP=(
    ["common_info"]="[情報]"
    ["wizard_menu_title"]="サービスを選択してください:"
    # ... 更多翻译
)
```

2. 更新 `detect_language()` 函数支持新语言代码

---

## 进度条功能

### 基础进度条

```bash
source scripts/common.sh

progress_start 5 "📦 Deploying Service"
for i in {1..5}; do
    sleep 1
    progress_update $i "Step $i"
done
progress_complete "Deployment done"
```

### 嵌套进度条 (子任务)

```bash
progress_start 3 "Main Task"
progress_update 1 "..."

# 开始子任务
progress_nested_start 4 "Building image"
progress_nested_update 1 "Compiling..."
progress_nested_update 2 "Packaging..."
progress_nested_update 3 "Tagging..."
progress_nested_complete "Image built"

progress_update 2 "..."
progress_complete "Main task done"
```

### 持久化和恢复

```bash
# 启用状态保存
progress_persistence_enable "/tmp/my-task-state.json"
progress_start 10 "Long task"
# ... 中断 (Ctrl+C) ...

# 恢复执行
progress_resume "/tmp/my-task-state.json"
progress_update 4  # 从中断处继续
```

### 图形化进度条 (iTerm2/TrueColor)

```bash
# 自动检测终端能力并使用最佳渲染
for i in 0 20 40 60 80 100; do
    progress_graphic "$i" 100 "Loading ($i%)"
    sleep 0.2
done
```

### Spinner 动画

```bash
spinner_start "Processing..."
# ... 长时间操作 ...
spinner_stop
log_success "Done"
```

### 进度条 API 完整列表

| 函数 | 用途 |
|------|------|
| `progress_start <total> <desc>` | 启动主进度条 |
| `progress_update <current> [desc]` | 更新主进度 |
| `progress_complete [msg]` | 完成主进度 |
| `progress_nested_start <total> <desc>` | 启动子进度 |
| `progress_nested_update <current> [desc]` | 更新子进度 |
| `progress_nested_complete [msg]` | 完成子进度 |
| `progress_persistence_enable <file>` | 启用状态持久化 |
| `progress_resume <file>` | 恢复进度 |
| `progress_persistence_disable` | 禁用持久化 |
| `progress_graphic <cur> <total> [label]` | 图形化进度条 |
| `spinner_start <msg>` | 启动旋转动画 |
| `spinner_stop` | 停止旋转动画 |

---

## 错误处理

### 错误类型

| 错误类型 | 触发场景 | 恢复建议 |
|---------|---------|----------|
| `CREDENTIAL_ERROR` | AK/SK 无效或缺失 | 重新配置凭证 |
| `QUOTA_EXCEEDED` | 资源配额超限 | 提交配额提升申请 |
| `NETWORK_TIMEOUT` | 网络连接超时 | 检查网络/重试 |
| `PERMISSION_DENIED` | RAM 角色权限不足 | 附加 AliyunAdvisorFullAccess |
| `API_RATE_LIMIT` | API 调用频率超限 | 降低并发/分批处理 |
| `INVALID_PARAMETER` | 参数格式错误 | 检查参数格式 |
| `RESOURCE_NOT_FOUND` | 资源 ID 无效 | 验证资源存在性 |
| `DEPENDENCY_MISSING` | 工具未安装 | 安装 aliyun CLI / jq |
| `CONFIGURATION_ERROR` | .env 配置错误 | 检查环境变量 |
| `INTERNAL_ERROR` | 内部错误 | 查看日志/重试 |
| `VALIDATION_FAILED` | 输入验证失败 | 检查输入参数 |
| `OPERATION_TIMEOUT` | 操作超时 | 增加超时/缩小范围 |

### 使用示例

```bash
source scripts/error-handler.sh

# 手动处理错误
result=$(aliyun ecs DescribeInstances 2>&1)
if [[ $? -ne 0 ]]; then
    err_type=$(classify_error "$result")
    handle_error "$err_type" "$result" 1
fi

# 安全执行命令
safe_exec "Creating ECS instance" aliyun ecs CreateInstance \
    --RegionId cn-hangzhou \
    --ImageId m-xxxxx

# 重试机制
retry_operation 3 2 aliyun ecs DescribeInstances
# 最多重试 3 次,初始延迟 2 秒,指数退避
```

---

## 单元测试

### 运行测试

```bash
# 运行所有单元测试
./tests/test-core-functions.sh

# 运行进度条测试
./scripts/test-progress-advanced.sh

# 验证修复
./scripts/verify-fixes-simple.sh
```

### 测试覆盖

| 测试组 | 测试数 | 覆盖范围 |
|--------|:-----:|----------|
| Cost Estimation | 5 | ECS/RDS/Redis 价格计算 |
| Progress Bar | 5 | 百分比/ETA/进度条宽度 |
| Error Classification | 6 | 6 种错误类型识别 |
| Error Description | 5 | 12 种错误的描述和恢复 |
| Terminal Detection | 2 | 终端能力检测 |
| Input Validation | 5 | Region/DAU/Tags 格式 |
| Architecture Patterns | 3 | 6 种架构模式识别 |
| **总计** | **31** | **100% 通过率** |

### 添加自定义测试

```bash
source scripts/test-framework.sh

test_init
test_start "My custom test"
result=$(my_function "input")
assert_equals "expected" "$result"
test_end
test_summary
```

---

## 常见问题

### Q1: 如何在没有阿里云凭证时使用?

```bash
# 使用 Mock 数据模式
./scripts/assess.sh --mock
./scripts/recommend.sh --scenario ecommerce --dau 1000
```

### Q2: 如何加快大规模资源的扫描?

```bash
# 1. 使用资源组限定范围
./scripts/assess.sh --resource-group rg-prod

# 2. 使用标签过滤
./scripts/assess.sh --tags "env=prod,tier=web"

# 3. 分批处理 (按 VPC)
./scripts/assess.sh --vpc-id vpc-1
./scripts/assess.sh --vpc-id vpc-2
```

### Q3: 推荐的架构是否一定可用?

不是。`recommend.sh` 会验证 ECS/RDS/Redis 规格的可用性,并在不可用时自动降级。最终方案在输出前会标注降级路径。

### Q4: 如何集成到 CI/CD?

```bash
#!/bin/bash
set -e

# CI 模式: 非交互 + JSON 输出
./scripts/assess.sh --mock --output json > /tmp/arch-report.json
./scripts/recommend.sh \
    --scenario ecommerce --dau 50000 \
    --output json \
    --output-dir /tmp/recommend

# 检查结果
if jq -e '.pillars.security.score > 80' /tmp/arch-report.json; then
    echo "Security score OK"
fi
```

### Q5: 如何自定义场景模板?

在 `references/scenario-templates/` 创建新的 YAML 文件,然后在 `index.yaml` 中注册。

```yaml
# my-custom-scenario.yaml
scenario: my-app
description: My custom application
components:
  - type: ecs
    count: 2
    instance_type: g6.xlarge
```

### Q6: 进度条在非交互式终端 (如 CI) 中能用吗?

可以。`progress_start` 会检测是否在 TTY 中,非 TTY 模式下使用纯文本输出,不会影响日志。

---

## 最佳实践

1. **首次使用**: 从交互式向导开始 (`./scripts/interactive-wizard.sh`)
2. **CI/CD 集成**: 使用 `--mock --output json` 模式
3. **大规模扫描**: 使用 `--resource-group` 或 `--tags` 限定范围
4. **成本敏感**: 推荐 Mode C 时使用 `--budget` 限制
5. **审计场景**: 使用 Mode B 评估现有架构
6. **生产部署前**: 运行 WAF 评估确保符合最佳实践
7. **多语言**: 在团队脚本中固定 `ARCH_ADVISOR_LANG` 避免混淆

---

## 相关链接

- [CHANGELOG.md](CHANGELOG.md) - 版本变更日志
- [README.md](README.md) - 项目概览
- [OPTIMIZATION_REVIEW.md](OPTIMIZATION_REVIEW.md) - 优化复盘
- [CODE_REVIEW_FIXES.md](CODE_REVIEW_FIXES.md) - 代码审查修复

---

**最后更新**: 2026-06-11
**维护者**: alicloud-arch-advisor 团队
**许可**: Apache 2.0
