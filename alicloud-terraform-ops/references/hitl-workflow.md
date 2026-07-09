# HITL（Human-in-the-Loop）工作流程

人工参与 Terraform 操作的工作流程设计规范。

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **安全优先** | 生产环境强制多级确认，防止误操作 |
| **分级管控** | 不同环境采用不同的确认策略 |
| **体验流畅** | 开发环境减少阻塞，保留灵活性 |
| **可追溯** | 所有人工决策记录审计日志 |

## 2. 五级环境确认策略

| 环境 | 用途 | CP1 意图 | CP2 审核 | CP3 Plan | CP5 销毁 | 审批人 |
|------|------|---------|---------|---------|---------|--------|
| **int** | 集成测试 | **required** | skip | auto | single | 无 |
| **dev** | 开发联调 | required | optional | required | single | 无 |
| **uat** | 预演验收 | required | required | required | double | 单人 |
| **performance** | 压测环境 | required | required | strict | double | 单人 |
| **production** | 生产环境 | required | required | strict + 窗口 | double + 冷却 | 双人 |

### 2.1 策略说明

- **CP1 意图确认**: NL2HCL 解析后确认资源清单
- **CP2 配置审核**: HCL 生成后审核代码质量
- **CP3 Plan 确认**: terraform plan 后确认变更范围
- **CP5 销毁确认**: destroy 前强制确认

## 3. 关键检查点（CheckPoint）

### CP1: 意图确认

**触发**: NL2HCL 语义解析完成后

**人工操作**:
- 查看识别的资源类型和数量
- 确认或修改配置参数
- 选择保存为模板

**示例交互**:
```
═══════════════════════════════════════════════════
  意图识别结果 (CP1: 意图确认)
═══════════════════════════════════════════════════
检测到以下资源需求：

  [1] VPC
      └─ CIDR: 10.0.0.0/16
      
  [2] VSwitch × 2
      └─ 可用区: cn-hangzhou-b, cn-hangzhou-g
      
  [3] ECS × 2
      └─ 规格: ecs.c6.large

请选择：
  [Y]  确认生成配置
  [M]  修改参数
  [S]  保存为模板
  [N]  取消
```

### CP2: 配置审核

**触发**: HCL 代码生成完成后

**人工操作**:
- 预览生成的 main.tf
- 修改变量默认值
- 调整标签和命名规范

**环境差异化**:
- int: 跳过
- dev: 可选
- uat/production: 必须

### CP3: Plan 确认

**触发**: `terraform plan` 执行后

**人工操作**:
- 查看变更摘要（创建/修改/删除数量）
- 审查详细 diff
- 确认费用影响

**严格模式**（production）:
```
═══════════════════════════════════════════════════
  生产环境变更 (CP3: 严格模式)
═══════════════════════════════════════════════════

⚠️  警告: 当前环境为 PRODUCTION

检查清单:
  [PASS] 变更窗口: 02:00-04:00 (当前在窗口内)
  [PASS] 变更单关联: DOPS-xxxxx
  [WARN] 最近备份: 12 小时前

变更影响:
  - 服务中断: 预计 2 分钟
  - 回滚时间: 5 分钟
  
请输入确认: "我已确认变更影响" > 
```

### CP4: 导入确认（Reverse Engineering）

**触发**: 资源逆向扫描完成后

**人工操作**:
- 查看发现的资源分级
- 选择导入范围
- 处理警告项

**资源分级**:
| 分级 | 含义 | 操作 |
|------|------|------|
| [PASS] | 可自动导入 | 一键导入 |
| [WARN] | 需要确认 | 逐一审核 |
| [SKIP] | 不支持 | 手动处理 |

### CP5: 销毁确认

**触发**: `terraform destroy` 执行前

**确认强度**:
- single: 单次确认
- double: 双重确认 + 资源清单展示
- double + 冷却: 30 秒倒计时，可取消

## 4. 审批人机制

### 4.1 配置格式

```yaml
# ~/.pi/terraform-ops-config.yaml
environments:
  uat:
    approvers:
      - name: "tech-lead"
        type: single          # 单人审批，任一通过
        users: ["zhangsan", "lisi"]
        
  production:
    approvers:
      - name: "tech-lead"
        type: single
        users: ["zhangsan", "lisi"]
        required: true
        
      - name: "ops-manager"   # 第二级审批
        type: single
        users: ["wangwu"]
        required: true
        
      - name: "dba"           # 条件审批
        type: conditional
        condition: "has_resource('alicloud_db_instance')"
        users: ["dba-team"]

notifications:
  channel: "dingtalk"
  webhook: "https://oapi.dingtalk.com/xxx"
```

### 4.2 审批类型

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| **single** | 任一审批人通过即可 | uat, performance |
| **any-of** | 多人中任一通过 | 平级审批 |
| **all-of** | 所有审批人必须通过 | 会签场景 |
| **conditional** | 满足条件时触发 | DBA/安全专项审批 |

### 4.3 审批流程

```
═══════════════════════════════════════════════════
  审批流程 (Production)
═══════════════════════════════════════════════════

第 1 级审批 (Tech Lead):
  状态: 待审批
  审批人: zhangsan, lisi (任一)
  [通知已发送] 钉钉消息已推送
  
  请输入审批单号 > DOPS-APPROVAL-12345
  [PASS] 审批通过 (zhangsan)

第 2 级审批 (Ops Manager):
  状态: 待审批
  审批人: wangwu
  [通知已发送] 钉钉消息已推送
  
  请输入审批单号 > DOPS-APPROVAL-12346
  [PASS] 审批通过 (wangwu)

[全部审批完成，进入执行阶段]
```

## 5. 交互式 CLI 工作流

### 5.1 完整流程示例

```bash
$ pi "用 terraform 创建一个 VPC，包含 2 台 ECS"

[分析中...]

# === CP1: 意图确认 ===
Agent: 解析到以下资源：
         - VPC: 1 个
         - VSwitch: 2 个  
         - ECS: 2 台
       确认生成？[Y/n/modify] > Y

[生成中...]

# === CP2: 配置审核 (dev 环境可选，已跳过) ===

# === CP3: Plan 确认 ===
Agent: 变更预览：
         + 创建: 5 个资源
         ~ 修改: 0 个
         - 销毁: 0 个
       执行 apply？[Y/dry-run/N] > Y

[执行中...]

[PASS] 资源创建完成
```

### 5.2 中途取消机制

所有检查点支持取消操作，状态回滚：
- CP1/CP2: 取消后无状态变更
- CP3: 取消后保留 plan 文件，可重新确认
- CP5: 取消后无资源销毁

## 6. 生产环境特殊流程

### 6.1 变更窗口检查

```python
def check_maintenance_window(env, current_time):
    if env == "production":
        window = get_config("production.maintenance_window")  # 02:00-04:00
        if not in_window(current_time, window):
            return FAIL, f"当前不在变更窗口 {window} 内"
    return PASS
```

### 6.2 冷却期设计

```bash
[冷却期: 30 秒内可 Ctrl+C 取消]
[30] [29] [28] ... [1]
[开始执行...]
```

### 6.3 自动回滚准备

执行前自动生成回滚方案：
- 创建当前 state 备份
- 生成 `terraform plan -destroy` 回滚脚本
- 记录回滚所需时间估算

## 7. 审计与追溯

### 7.1 决策记录格式

```json
{
  "timestamp": "2024-06-08T02:15:30Z",
  "environment": "production",
  "operation": "apply",
  "checkpoints": {
    "cp1": {"status": "confirmed", "user": "developer"},
    "cp2": {"status": "confirmed", "user": "developer"},
    "cp3": {"status": "confirmed", "user": "developer"},
    "approval": {
      "tech-lead": {"approver": "zhangsan", "time": "2024-06-08T01:55:00Z"},
      "ops-manager": {"approver": "wangwu", "time": "2024-06-08T01:58:00Z"}
    }
  },
  "plan_digest": "sha256:abc123...",
  "apply_result": "success"
}
```

### 7.2 日志存储

- 本地: `~/.pi/terraform-ops/audit/`
- 远程: 可选配置发送到 Loki/SLS

## 8. 配置优先级

配置来源（优先级从高到低）：

1. 命令行参数 `--skip-confirmations`
2. 环境变量 `TF_OPS_ENV=uat`
3. 项目配置 `./.pi/terraform-ops.yaml`
4. 用户配置 `~/.pi/terraform-ops.yaml`
5. 系统默认

## 9. 异常处理

| 场景 | 处理策略 |
|------|---------|
| 审批人不在线 | 超时转交，或升级通知 |
| 审批被拒绝 | 记录原因，返回修改 |
| 网络中断 | 保存状态，恢复后继续 |
| 长时间无操作 | 会话超时，需重新确认 |

## 10. 多模式协作界面

### 10.1 模式对比

| 模式 | 适用场景 | 交互方式 | 审计能力 | 实现复杂度 |
|------|---------|---------|---------|-----------|
| **A: 交互式 CLI** | 开发/测试环境 | 命令行问答 | 本地日志 | 低 |
| **B: PR 式审核** | 生产发布、团队协作 | Git PR 评论 | PR 记录 + 提交历史 | 中 |
| **C: CheckPoint 暂停** | 批量导入、复杂审核 | 会话恢复 | 检查点文件 | 中 |

### 10.2 模式 B：PR 式审核（Git-based Review）

#### 适用场景

- 生产环境变更需留痕审计
- 多人协作的基础设施代码审查
- 需要异步审批（审批人不实时在线）
- 变更需关联业务需求（Jira/钉钉审批单）

#### 工作流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 配置生成 (本地/CI)                                    │
│     Agent: NL2HCL 生成配置 → 自动创建 Git 分支              │
└────────────┬────────────────────────────────────────────┘
             │ git checkout -b terraform/20240608-vpc
             ▼
┌─────────────────────────────────────────────────────────┐
│  2. 自动提交                                              │
│     git add . → git commit -m "[terraform] Add VPC..."   │
│     git push origin terraform/20240608-vpc               │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  3. PR 创建                                               │
│     - 调用 GitHub/GitLab API 创建 PR                      │
│     - 自动生成 PLAN.md (terraform plan 结果)              │
│     - 添加标签: terraform, needs-review                  │
│     - @通知 CODEOWNERS                                   │
└────────────┬────────────────────────────────────────────┘
             │ PR #123 创建成功
             │ 链接: https://git.example.com/pr/123
             ▼
┌─────────────────────────────────────────────────────────┐
│  4. 人工审核 (Reviewer)                                   │
│     - 查看 PLAN.md 变更摘要                               │
│     - 评论: /plan (重新plan) /approve (通过) /reject (拒绝) │
│     - 或直接在 PR 界面 Approve                            │
└────────────┬────────────────────────────────────────────┘
             │ PR 状态变更 webhook
             ▼
┌─────────────────────────────────────────────────────────┐
│  5. 自动执行 (CI Pipeline)                                │
│     检测到 /approve 或 PR Approved:                      │
│     - terraform apply (使用 PR 中的配置)                  │
│     - 更新 PR 状态: Applied                              │
│     - 添加执行结果评论                                    │
│     - 自动合并分支 (可选)                                 │
└─────────────────────────────────────────────────────────┘
```

#### PLAN.md 自动生成格式

```markdown
<!-- Generated by alicloud-terraform-ops -->
# Terraform Plan 摘要

## 变更概览

| 类型 | 数量 | 资源 |
|------|------|------|
| + 创建 | 5 | VPC, VSwitch×2, ECS×2 |
| ~ 修改 | 0 | - |
| - 销毁 | 0 | - |

## 预计费用

~¥ 2.5/小时 (按量付费)

## 风险检查

- [PASS] 非生产环境 (dev)
- [PASS] 无资源销毁
- [WARN] 公网 IP 分配 (可能产生流量费)

## 详细变更

<details>
<summary>点击查看完整 diff</summary>

\`\`\`hcl
  # alicloud_vpc.main will be created
  + resource "alicloud_vpc" "main" {
      + cidr_block = "10.0.0.0/16"
      + id         = (known after apply)
    }
\`\`\`

</details>

## 审批

- [ ] Tech Lead: _____________
- [ ] Ops Manager (prod only): _____________

---
*Generated at 2024-06-08 10:30:00 by alicloud-terraform-ops*
```

#### 评论指令系统

| 指令 | 执行动作 | 权限要求 |
|------|---------|---------|
| `/plan` | 重新执行 terraform plan | PR 创建者/维护者 |
| `/apply` | 执行 terraform apply | 需先通过审批 |
| `/approve` | 标记审批通过 | 配置中的审批人 |
| `/reject [原因]` | 拒绝并记录原因 | 配置中的审批人 |
| `/skip-cp [cp-id]` | 跳过指定检查点 | 维护者 |
| `/help` | 显示可用指令 | 任何人 |

#### 配置示例

```yaml
# .pi/terraform-ops.yaml
hitl:
  mode: "pr"  # cli / pr / checkpoint
  
  pr:
    provider: "gitlab"  # github / gitlab / gitee
    repository: "https://git.example.com/ops/terraform-aliyun"
    base_branch: "main"
    
    codeowners:
      - pattern: "*"
        owners: ["@ops-team", "@zhangsan"]
      - pattern: "*/production/*"
        owners: ["@ops-manager"]
        
    notifications:
      channel: "dingtalk"
      webhook: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
      
    auto_merge: false  # apply 后是否自动合并
    delete_branch: true  # 合并后是否删除分支
```

### 10.3 模式 C：CheckPoint 暂停（Session-based Pause）

#### 适用场景

- 批量资源导入（Reverse Engineering）
- 复杂架构需要人工选择部分资源
- 长时间任务需中断恢复
- 需要分步确认（先导入网络，再导入计算）

#### 核心概念

**检查点 (Checkpoint)**：保存当前会话状态的文件，支持中断后恢复。

```json
{
  "checkpoint_id": "cp-20240608-001",
  "created_at": "2024-06-08T10:30:00Z",
  "status": "paused",
  "mode": "reverse_engineering",
  "context": {
    "source_vpc": "vpc-bp1xxxxxx",
    "discovered_resources": [...],
    "selected_resources": [...],
    "imported_resources": [...]
  },
  "current_step": "review_warnings"
}
```

#### 工作流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 资源发现                                              │
│     Agent: 扫描阿里云资源 → 分类标记                       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  2. 分类展示                                              │
│     [PASS] 8个  可自动导入 (ECS, Disk)                     │
│     [WARN] 5个  需确认 (SLB规则复杂, RDS白名单敏感)         │
│     [SKIP] 2个  不支持 (Custom Image)                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  3. 用户选择 (CheckPoint 暂停)                            │
│     选项:                                                 │
│     [1] 导入全部 [PASS] (8个)                             │
│     [2] 逐一审核 [WARN] (5个)                             │
│     [3] 自定义选择 → 显示多选列表                          │
│     [4] 干运行 (dry-run)                                  │
│     [5] 保存并退出 (稍后继续)                              │
└────────────┬────────────────────────────────────────────┘
             │ 选择 [3] 自定义选择
             ▼
┌─────────────────────────────────────────────────────────┐
│  4. 多选界面                                              │
│     [x] ECS-i-bp1xxx (Web服务器)                          │
│     [x] ECS-i-bp1yyy (Web服务器)                          │
│     [ ] SLB-lb-bp1xxx (监听规则复杂 - WARN)               │
│     [x] RDS-rm-bp1xxx (生产数据库 - WARN)                 │
│     [ ] Custom Image (不支持 - SKIP)                      │
│                                                           │
│     已选择: 3个  全选  反选  确认选择                       │
└────────────┬────────────────────────────────────────────┘
             │ 确认选择 3个资源
             ▼
┌─────────────────────────────────────────────────────────┐
│  5. 分步执行                                              │
│     Step 1: 生成 HCL → [PASS]                             │
│     Step 2: terraform init → [PASS]                       │
│     Step 3: terraform plan → [PASS]                       │
│     Step 4: 等待确认...                                   │
│                                                           │
│     [CHECKPOINT] 已保存到 cp-20240608-001.json            │
│     可安全退出，下次运行自动恢复                           │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  6. 恢复/继续                                             │
│     $ pi "继续上次的导入任务"                              │
│     Agent: 发现检查点 cp-20240608-001                     │
│             状态: Step 4 等待确认                          │
│             继续执行? [Y/n] > Y                            │
│             → terraform import → [PASS]                   │
│             → 清理检查点                                   │
└─────────────────────────────────────────────────────────┘
```

#### 状态机模型

```
         ┌──────────┐
         │  START   │
         └────┬─────┘
              │ 发现资源
              ▼
         ┌──────────┐
    ┌────│ CLASSIFY │◄────┐
    │    └────┬─────┘     │ 修改选择
    │         │ 展示分类   │
    │         ▼           │
    │    ┌──────────┐     │
    └────│ SELECT   │─────┘
         └────┬─────┘
              │ 用户确认
              ▼
         ┌──────────┐
         │ GENERATE │
         └────┬─────┘
              │ 生成HCL
              ▼
         ┌──────────┐
         │  REVIEW  │◄──── 检查点保存
         └────┬─────┘
              │ 审核通过
              ▼
         ┌──────────┐
         │  IMPORT  │
         └────┬─────┘
              │ 导入完成
              ▼
         ┌──────────┐
         │   DONE   │
         └──────────┘
```

#### 检查点文件格式

```json
{
  "checkpoint_id": "cp-20240608-001",
  "version": "1.0",
  "created_at": "2024-06-08T10:30:00Z",
  "updated_at": "2024-06-08T10:45:00Z",
  "expires_at": "2024-06-15T10:30:00Z",
  
  "session": {
    "mode": "reverse_engineering",
    "environment": "production",
    "user": "developer"
  },
  
  "state": {
    "current_phase": "review",
    "completed_phases": ["discover", "classify"],
    "resources": {
      "total": 15,
      "classified": {
        "pass": 8,
        "warn": 5,
        "skip": 2
      },
      "selected": ["i-bp1xxx", "i-bp1yyy", "rm-bp1xxx"]
    }
  },
  
  "context": {
    "source": {
      "type": "vpc",
      "id": "vpc-bp1xxxxxx"
    },
    "generated_files": {
      "main_tf": "/tmp/tf-gen-xxx/main.tf",
      "import_sh": "/tmp/tf-gen-xxx/import.sh"
    }
  },
  
  "recovery": {
    "last_action": "select_resources",
    "next_action": "generate_hcl",
    "prompt": "已选择 3 个资源，是否继续生成 HCL?"
  }
}
```

#### 恢复命令

```bash
# 自动检测并恢复
$ pi "继续上次的导入任务"
[发现检查点] cp-20240608-001
[状态] 已选择 3 个资源，等待生成 HCL
[创建时间] 2024-06-08 10:30 (15分钟前)

是否继续? [Y/n/view/skip] > Y
[恢复中...] → 继续执行

# 列出所有检查点
$ pi "列出所有暂停的任务"
检查点列表:
  [1] cp-20240608-001 - 导入VPC资源 (15分钟前) [可恢复]
  [2] cp-20240607-003 - 创建测试环境 (1天前) [已过期]

# 强制清理
$ pi "清理检查点 cp-20240608-001"
[已删除] cp-20240608-001
```

### 10.4 模式切换

支持在不同模式间切换或组合使用：

```yaml
# 混合模式示例
hitl:
  default_mode: "cli"
  
  overrides:
    - env: "production"
      mode: "pr"
      
    - env: "uat"
      mode: "checkpoint"
      trigger: "reverse_engineering"  # 仅导入场景使用 checkpoint
      
    - resource_count: ">10"
      mode: "checkpoint"  # 资源数量多时使用 checkpoint
```

## 11. 与其他 Skill 的协作

| 场景 | HITL 行为 | 协作 Skill |
|------|----------|-----------|
| Terraform 创建 RDS | CP3 后提示 SQL 初始化 | alicloud-rds-ops |
| Terraform 创建 ECS | CP3 后提示应用部署 | alicloud-ecs-ops |
| 导入发现异常资源 | CP4 提示诊断 | alicloud-topo-discovery |

---

*该方案设计用于 alicloud-terraform-ops，具有云无关性，可扩展至其他云 Terraform Skill。*
