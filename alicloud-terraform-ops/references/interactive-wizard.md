# Terraform IaC 交互式向导

> 版本: 1.0.0 | 适用于: NL2HCL / Reverse Engineering / 标准 Terraform 操作

## 1. 向导架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Terraform 交互式向导                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 意图识别  │→│ 参数收集  │→│ Dry-Run  │→│ 确认执行  │    │
│  │  (NLU)   │  │ (交互式) │  │ (验证)   │  │ (HITL)   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│       ↓             ↓             ↓             ↓          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              执行轨迹记录 (GCL Trace)                 │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 2. 向导流程

### 2.1 NL2HCL 向导流程

```
用户输入: "帮我创建一个 VPC"
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 1: 意图识别                                         │
│ ✓ 检测到: NL2HCL - VPC 创建                              │
│ ✓ 提取实体: resource_type=vpc, action=create            │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 2: 交互式参数收集 (渐进式披露)                        │
│                                                         │
│ [2.1] 环境选择 ❯                                         │
│   ❯ dev      ○ staging    ○ prod                       │
│                                                         │
│ [2.2] VPC 配置 ❯                                         │
│   VPC 名称: [my-vpc                    ]                │
│   CIDR 块:  [10.0.0.0/16               ] ← 默认推荐      │
│                                                         │
│ [2.3] 可用区配置 ❯                                       │
│   可用区数量: [2 ▼] (1-3)                               │
│   可用区:     ☑ cn-hangzhou-a ☑ cn-hangzhou-b          │
│                                                         │
│ [2.4] 高级选项 ▶                                         │
│   ○ 启用 NAT 网关     ○ 配置安全组                       │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 3: 配置预览                                         │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 生成的资源清单:                                       │ │
│ │ • alicloud_vpc.main                                  │ │
│ │ • alicloud_vswitch.az_a (10.0.1.0/24)               │ │
│ │ • alicloud_vswitch.az_b (10.0.2.0/24)               │ │
│ │                                                    │ │
│ │ 估算月费用: ¥ 0 (VPC 免费)                           │ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ [编辑参数]  [开始 Dry-Run]  [保存模板]                   │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 4: Dry-Run 执行 (自动)                               │
│ ╔══════════════════════════════════════════════════════╗│
│ ║              🔍 DRY-RUN MODE (干运行模式)              ║│
│ ║      此执行仅用于预览和验证，不会创建或修改任何资源      ║│
│ ╚══════════════════════════════════════════════════════╝│
│ ┌────────────────────────────────────────────────────┐ │
│ │ [DRY-RUN] [11:23:45] [INIT] 初始化临时工作目录...     │ │
│ │ [DRY-RUN] [11:23:46] [EXEC] terraform init -backend=false│ │
│ │ [DRY-RUN] [11:23:48] [VALIDATE] terraform validate    │ │
│ │ [DRY-RUN] ✓ 配置验证通过                              │ │
│ │ [DRY-RUN] [11:23:50] [PLAN] terraform plan            │ │
│ │                                                    │ │
│ │ [DRY-RUN] Plan: 3 to add, 0 to change, 0 to destroy│ │
│ │                                                    │ │
│ │ [DRY-RUN] + alicloud_vpc.main                      │ │
│ │ [DRY-RUN] + alicloud_vswitch.az_a                  │ │
│ │ [DRY-RUN] + alicloud_vswitch.az_b                  │ │
│ │                                                    │ │
│ │ [DRY-RUN] ⚠️  注意: 以上仅为预览，实际执行请确认      │ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ [查看详细日志]  [查看生成的 HCL]  [立即执行]             │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 5: 确认执行 (HITL CP3)                              │
│                                                         │
│ ⚠️  即将在 [dev] 环境创建 3 个资源                        │
│                                                         │
│ 执行方式:                                                │
│   ○ 立即执行                                             │
│   ○ 生成 Git PR (推荐用于 staging/prod)                  │
│   ○ 保存为草稿稍后执行                                    │
│                                                         │
│ 请输入确认码执行: [DEV-2024    ]                        │
│              (自动生成，防止误操作)                       │
│                                                         │
│ [确认执行]  [返回修改]  [放弃]                           │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 6: 执行结果                                         │
│ ✓ 执行成功                                               │
│                                                         │
│ 创建的资源:                                              │
│ • vpc-bp1xxxxxxxx (VPC)                                │
│ • vsw-bp1xxxxxxxx (vSwitch-AZ-a)                       │
│ • vsw-bp1xxxxxxxx (vSwitch-AZ-b)                       │
│                                                         │
│ 输出值:                                                  │
│ vpc_id = "vpc-bp1xxxxxxxx"                             │
│                                                         │
│ [导出状态]  [查看监控]  [创建下一资源]                   │
└────────────────────────────────────────────────────────┘
```

### 2.2 Reverse Engineering 向导流程

```
用户输入: "导入这个 VPC"
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 1: 资源发现                                         │
│                                                         │
│ 发现方式:                                                │
│   ● 通过资源 ID 导入    ○ 通过标签筛选                   │
│     ○ 自动发现当前 Region 所有资源                       │
│                                                         │
│ 输入 VPC ID: [vpc-bp1xxxxxxxx          ]                │
│                                                         │
│ [自动发现关联资源] ← 勾选后将自动发现关联的 vSwitch/Router │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 2: 资源扫描结果                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ VPC: vpc-bp1xxxxxxxx                               │ │
│ │ ├── Name: production-vpc                           │ │
│ │ ├── CIDR: 172.16.0.0/16                            │ │
│ │ ├── Status: Available                              │ │
│ │ └── Associated Resources:                          │ │
│ │     ├── vsw-bp1xxxxxx1 (cn-hangzhou-a)            │ │
│ │     ├── vsw-bp1xxxxxx2 (cn-hangzhou-b)            │ │
│ │     └── vrt-bp1xxxxxx (Route Table)               │ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ 选择要导入的资源:                                        │
│ ☑ VPC (vpc-bp1xxxxxxxx)                               │
│ ☑ vSwitch-A (vsw-bp1xxxxxx1)                          │
│ ☑ vSwitch-B (vsw-bp1xxxxxx2)                          │
│ ☐ Route Table (vrt-bp1xxxxxx)                         │
│                                                         │
│ [全选]  [仅 VPC]  [自定义选择]                           │
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 3: Dry-Run 导入验证                                 │
│ ╔══════════════════════════════════════════════════════╗│
│ ║              🔍 DRY-RUN MODE (干运行模式)              ║│
│ ║      此执行仅用于预览和验证，未修改 Terraform 状态      ║│
│ ╚══════════════════════════════════════════════════════╝│
│ ┌────────────────────────────────────────────────────┐ │
│ │ [DRY-RUN] 生成导入配置...                             │ │
│ │                                                    │ │
│ │ [DRY-RUN] 生成的文件:                                 │ │
│ │ [DRY-RUN] ├── generated/vpc.tf                        │ │
│ │ [DRY-RUN] ├── generated/vswitch.tf                    │ │
│ │ [DRY-RUN] └── generated/import.sh                     │ │
│ │                                                    │ │
│ │ [DRY-RUN] 验证结果:                                   │ │
│ │ [DRY-RUN] ✓ HCL 语法有效                              │ │
│ │ [DRY-RUN] ✓ 资源 ID 格式正确                          │ │
│ │ [DRY-RUN] ⚠ 检测到潜在漂移:                           │ │
│ │ [DRY-RUN]   - VPC 的 description 字段未设置            │ │
│ │                                                    │ │
│ │ [DRY-RUN] 导入预览 (不会实际执行):                     │ │
│ │ [DRY-RUN] → 将导入: alicloud_vpc.imported_vpc (vpc-bp1xxxxxx)     │ │
│ │ [DRY-RUN] → 将导入: alicloud_vswitch.imported_vswitch_1 (vsw-bp1xxxxxx) │ │
│ │                                                    │ │
│ │ [DRY-RUN] ⚠️  注意: 以上仅为预览，确认后才执行导入     │ │
│ └────────────────────────────────────────────────────┘ │
│                                                         │
│ [查看生成的 HCL]  [下载导入脚本]  [修复漂移问题]  [确认导入]│
└────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────┐
│ Step 4: 确认导入 (HITL CP4)                              │
│                                                         │
│ ⚠️  警告: 导入操作将修改 Terraform 状态文件               │
│     请确保已备份当前状态!                                │
│                                                         │
│ 导入前自动执行:                                          │
│ ☑ 备份当前状态: terraform state pull                     │
│ ☑ 验证资源不存在于当前状态                                │
│ ☐ 创建 Git 分支记录变更                                  │
│                                                         │
│ 确认导入 3 个资源?                                       │
│                                                         │
│ [确认并导入]  [仅生成配置，稍后手动导入]  [取消]          │
└────────────────────────────────────────────────────────┘
```

## 3. 交互组件规范

### 3.1 输入组件

| 组件 | 用途 | 示例 |
|------|------|------|
| `selector` | 单选/多选 | 环境选择、可用区选择 |
| `text_input` | 文本输入 | 资源名称、ID |
| `cidr_input` | CIDR 块输入 | 带验证的 10.0.0.0/16 |
| `number_spinner` | 数值选择 | 实例数量、可用区数 |
| `toggle` | 开关选项 | 启用/禁用功能 |
| `code_viewer` | 代码预览 | HCL 预览、Plan 输出 |
| `log_viewer` | 日志展示 | Dry-run 执行日志 |

### 3.2 智能默认值

```yaml
智能推荐规则:
  vpc:
    cidr_default: "10.0.0.0/16"
    cidr_rules:
      - env: dev
        cidr: "10.0.0.0/16"
      - env: staging
        cidr: "10.1.0.0/16"
      - env: prod
        cidr: "10.2.0.0/16"
  
  availability_zones:
    default_count: 2
    max_count: 3
    recommendation: "跨 2 个可用区实现高可用"
  
  instance_types:
    default: "ecs.g7.large"
    rules:
      - condition: "environment == 'prod'"
        recommendation: "ecs.g7.xlarge 或更高"
```

### 3.3 实时验证

```
用户输入: VPC 名称 "my vpc"
              ↓
    [实时验证] 包含空格
              ↓
    ⚠️ 建议使用下划线或连字符: "my-vpc" 或 "my_vpc"
              ↓
    [一键修复] → 自动替换为 "my-vpc"
```

## 4. Dry-Run 集成

### 4.1 Dry-Run 触发点

| 场景 | 自动触发 | 手动触发 |
|------|----------|----------|
| NL2HCL 配置生成后 | ✓ | ✓ |
| Reverse Engineering 扫描后 | ✓ | ✓ |
| 参数修改后 | 延迟 2s | ✓ |
| 用户请求预览 | — | ✓ |

### 4.2 Dry-Run 结果展示

```
┌────────────────────────────────────────────────────────┐
│ Dry-Run 结果                                             │
├────────────────────────────────────────────────────────┤
│ ╔══════════════════════════════════════════════════════╗│
│ ║              🔍 DRY-RUN MODE (干运行模式)              ║│
│ ║      此执行仅用于预览和验证，不会创建或修改任何资源      ║│
│ ╚══════════════════════════════════════════════════════╝│
│                                                         │
│ [DRY-RUN] 执行摘要                  [查看完整日志]      │
│ ┌─────────────────────────────────────────────────┐    │
│ │ [DRY-RUN] Duration: 12.3s                       │    │
│ │ [DRY-RUN] Exit Code: 0                          │    │
│ │ [DRY-RUN] Status: ✅ 成功 (仅验证，未实际执行)   │    │
│ └─────────────────────────────────────────────────┘    │
│                                                         │
│ [DRY-RUN] 资源变更预览                                  │
│ ┌─────────────────────────────────────────────────┐    │
│ │  🟢 将创建  5    🟡 将修改  0    🔴 将删除  0   │    │
│ └─────────────────────────────────────────────────┘    │
│                                                         │
│ [DRY-RUN] 详情:                                         │
│ [DRY-RUN] + alicloud_vpc.main                          │
│ [DRY-RUN]   ├─ cidr_block: "10.0.0.0/16"              │
│ [DRY-RUN]   └─ vpc_name: "dev-vpc"                    │
│ [DRY-RUN] + alicloud_vswitch.main[0]                   │
│ [DRY-RUN]   ├─ availability_zone: "cn-hangzhou-a"     │
│ [DRY-RUN]   └─ cidr_block: "10.0.1.0/24"              │
│                                                         │
│ [DRY-RUN] 风险检查:                                     │
│ [DRY-RUN] ✓ 无敏感信息暴露                              │
│ [DRY-RUN] ✓ 资源命名符合规范                            │
│ [DRY-RUN] ⚠ CIDR 可能与现有网络冲突 (建议检查)          │
│                                                         │
│ [DRY-RUN] GCL 评分:                                     │
│ ┌──────────────┬────────┬──────────┐                  │
│ │ Dimension    │ Score  │ Status   │                  │
│ ├──────────────┼────────┼──────────┤                  │
│ │ Correctness  │ 1.0    │ ✓        │                  │
│ │ Safety       │ 1.0    │ ✓        │                  │
│ │ Idempotency  │ 1.0    │ ✓        │                  │
│ │ Traceability │ 1.0    │ ✓        │                  │
│ └──────────────┴────────┴──────────┘                  │
│                                                         │
│ ⚠️  注意: 以上仅为预览，实际执行请在下方确认             │
│                                                         │
│ [继续执行]  [返回修改]  [导出报告]                       │
└────────────────────────────────────────────────────────┘
```

## 5. 命令行交互模式

### 5.1 向导启动命令

```bash
# 启动 NL2HCL 向导
aliyun-terraform wizard nl2hcl

# 启动 Reverse Engineering 向导
aliyun-terraform wizard import

# 快速模式 (跳过交互，使用默认值)
aliyun-terraform wizard nl2hcl --quick \
  --environment dev \
  --template vpc-basic

# 从文件加载参数
aliyun-terraform wizard nl2hcl --config ./my-vpc.yaml
```

### 5.2 会话恢复

```bash
# 保存会话 (在任意步骤)
[Ctrl+S] 或输入: save
Session saved to: ~/.aliyun-terraform/sessions/session-20240608-112345.json

# 恢复会话
aliyun-terraform wizard resume session-20240608-112345
```

## 6. 执行轨迹记录

### 6.1 轨迹文件格式

```json
{
  "wizard_version": "1.0.0",
  "session_id": "tf-wiz-20240608-112345",
  "user_id": "user@example.com",
  "workflow_type": "nl2hcl",
  "started_at": "2026-06-08T11:23:45Z",
  "completed_at": "2026-06-08T11:30:12Z",
  "steps": [
    {
      "step": 1,
      "name": "intent_recognition",
      "input": "帮我创建一个 VPC",
      "output": {
        "intent": "nl2hcl_vpc",
        "confidence": 0.95
      },
      "timestamp": "2026-06-08T11:23:46Z"
    },
    {
      "step": 2,
      "name": "parameter_collection",
      "input": {
        "environment": "dev",
        "vpc_name": "my-vpc",
        "cidr_block": "10.0.0.0/16",
        "az_count": 2
      },
      "validation": {
        "passed": true,
        "warnings": []
      },
      "timestamp": "2026-06-08T11:24:30Z"
    },
    {
      "step": 3,
      "name": "dry_run",
      "gcl_trace": {
        "scores": {
          "correctness": 1,
          "safety": 1,
          "idempotency": 1,
          "traceability": 1,
          "spec_compliance": 1
        },
        "execution_time_ms": 12500
      },
      "timestamp": "2026-06-08T11:25:00Z"
    },
    {
      "step": 4,
      "name": "execution",
      "confirmed": true,
      "confirmation_code": "DEV-2024",
      "result": {
        "status": "success",
        "resources_created": [
          {"type": "alicloud_vpc", "id": "vpc-bp1xxxxxxxx"},
          {"type": "alicloud_vswitch", "id": "vsw-bp1xxxxxx1"},
          {"type": "alicloud_vswitch", "id": "vsw-bp1xxxxxx2"}
        ]
      },
      "timestamp": "2026-06-08T11:30:10Z"
    }
  ],
  "artifacts": {
    "generated_hcl": "...",
    "gcl_trace_file": "./audit-results/gcl-trace-...json"
  }
}
```

### 6.2 诊断命令

```bash
# 查看最近会话
tf-wizard history --limit 10

# 查看特定会话详情
tf-wizard show session-20240608-112345

# 诊断问题
tf-wizard diagnose session-20240608-112345
# 输出:
# Step 3 (dry_run) warning: CIDR overlap detected
# Recommendation: Use 10.1.0.0/16 instead

# 导出报告
tf-wizard export session-20240608-112345 --format pdf --output ./report.pdf
```

## 7. 错误处理与恢复

### 7.1 常见错误恢复流程

```
错误: terraform validate 失败
    ↓
┌────────────────────────────────────────────────────────┐
│ 配置验证失败                                             │
│                                                         │
│ 错误: resource 'alicloud_vpc.main'                      │
│       unknown parameter 'name' (did you mean 'vpc_name'?)│
│                                                         │
│ [自动修复] ← 一键修复参数名                              │
│ [编辑配置] ← 打开编辑器手动修复                           │
│ [查看帮助] ← 显示 alicloud_vpc 文档                      │
│ [跳过验证] ← 继续生成 (不推荐)                           │
└────────────────────────────────────────────────────────┘
```

### 7.2 中断恢复

```
会话在 Step 4 被中断
    ↓
┌────────────────────────────────────────────────────────┐
│ 检测到未完成会话                                         │
│ Session: session-20240608-112345                        │
│ 中断点: Step 4 (确认执行)                                │
│                                                         │
│ [恢复会话]  从断点继续                                   │
│ [重新开始]  丢弃当前进度                                 │
│ [导出草稿]  保存配置供手动使用                            │
└────────────────────────────────────────────────────────┘
```

## 8. 集成 GCL

### 8.1 向导与 GCL 交互图

```
用户 → 向导界面 → 参数收集
              ↓
         ┌─────────┐
         │  Generator  │ ← 生成配置/命令
         └────┬────┘
              ↓
         ┌─────────┐
         │     H     │ ← 幻觉检测 (参数校验)
         └────┬────┘
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
 Dry-Run 执行      正式执行
 (验证模式)        (确认后)
    ↓                   ↓
    └─────────┬─────────┘
              ↓
         ┌─────────┐
         │   Critic   │ ← 评分
         └────┬────┘
              ↓
         ┌─────────┐
         │ Orchestrator│ ← 决策
         └────┬────┘
              ↓
         向导界面更新
```

### 8.2 向导中的 GCL 状态展示

```
┌────────────────────────────────────────────────────────┐
│ GCL 质量门检查                                          │
├────────────────────────────────────────────────────────┤
│                                                         │
│ Generator ✓     Hallucination ✓     Critic ✓          │
│                                                         │
│ 维度评分:                                               │
│ Correctness   [████████░░] 1.0                        │
│ Safety        [██████████] 1.0 ✓ Critical             │
│ Idempotency   [████████░░] 1.0                        │
│ Traceability  [████████░░] 1.0                        │
│ Spec          [████████░░] 1.0                        │
│                                                         │
│ 决策: PASS - 可以安全执行                                │
│                                                         │
│ [查看 GCL 详细报告]                                      │
└────────────────────────────────────────────────────────┘
```

---

**References:**
- [GCL Rubric](./rubric.md) - 评分维度详细定义
- [Prompt Templates](./prompt-templates.md) - Generator/Critic 提示词
- [HITL Workflow](./hitl-workflow.md) - 人工介入检查点
