# Aliyun Skills — Agent Guide

This repository is a Skills Farm for Alibaba Cloud operations — structured, AI-agent-parseable runbooks for cloud resource management.

Every section here is high-signal: agents must follow these patterns or they will produce broken or inconsistent skills.

---

## 1. Repo Layout

```
alicloud-[product]-ops/
├── SKILL.md          # What to do (triggers, pre-flight, variables, references)
├── references/       # How to do (detailed CLI/SDK scripts, troubleshooting)
├── assets/           # Example configs
└── scripts/          # Executable pre-flight/shared scripts
```

## 2. Content Separation Rule (MANDATORY)

**SKILL.md 只描述 What to do，How to do 放置在 references/\***

| 文件 | 职责 | 内容 |
|------|------|------|
| `SKILL.md` | What | 触发条件、Pre-flight Checks、变量约定、执行概览、链接到 references/ |
| `references/*.md` | How | 完整命令、脚本、退出码表、日志解读、故障恢复 |

```markdown
<!-- SKILL.md — 对的做法 -->
#### Execution
完整脚本见 [references/redis-cli-execution.md](references/redis-cli-execution.md)

| Step | 操作 | 说明 |
|------|------|------|
| 1 | `aliyun r-kvstore describe-instance-attribute` | 获取连接地址 |
| 2 | `aliyun ecs RunCommand` | 幂等检查 redis-cli |

<!-- 错误做法：在 SKILL.md 中内联 500 行脚本 -->
```

## 3. Operation Design Pattern

每个操作必须包含以下节（按顺序）：

### Pre-flight Checks
```markdown
| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| {前提} | {验证命令} | {正常值} | HALT — {人工动作} |
```

### 变量约定
```markdown
| 变量 | 含义 | 来源 |
|------|------|------|
| `{{user.xxx}}` | 用户输入 | 问一次，复用 |
| `{{env.xxx}}` | 环境变量 | NEVER 问用户，缺了就 HALT |
| `{{output.xxx}}` | 上一步输出 | 解析 API 返回值 |
```

### Execution → Post-execution Validation → Failure Recovery

每个操作的 CLI 脚本必须包含 **结构化诊断日志**（见 §4）。

## 4. Diagnostic Logging Standard (MANDATORY for data-plane ops)

所有通过 Cloud Assistant 或其他远程执行的脚本，日志格式必须一致：

```
[HH:MM:SS] [PHASE] key=value
```

### 日志阶段前缀

| PHASE | 含义 | 示例 |
|-------|------|------|
| `DIAG` | 诊断信息/环境快照 | `[DIAG] PHASE=env-snapshot`, `[DIAG] OS=Ubuntu 22.04` |
| `INSTALL` | 安装过程 | `[INSTALL] pkg_manager=apt`, `[INSTALL] exit code 0` |
| `EXEC` | 正在执行的命令 | `[EXEC] redis-cli -h host -p 6379 DEL key` |
| `RESULT` | 关键结果键值对 | `[RESULT] INSTALL=SUCCESS`, `[RESULT] NETWORK=REACHABLE` |
| `WARN` | 警告 | `[WARN] redis-cli not found, installing...` |
| `ERROR` | 错误分类 | `[ERROR] TYPE=AUTH_FAILED FIX=Check password` |
| `SUMMARY` | 最终摘要 | `[SUMMARY] Result: (integer) 1` |

### 错误分类规范（ERROR TYPE）

```
[ERROR] TYPE={大类} FIX={一句话建议}
```

内置错误类型（以 Redis 为例）：

| ERROR TYPE | 含义 | FIX |
|------------|------|-----|
| `AUTH_FAILED` | 需要密码但未提供 | Check redis password |
| `WRONG_PASSWORD` | 密码错误 | Verify credentials |
| `CLUSTER_MOVED` | 集群模式下 Key 不在本节点 | Use redis-cli -c |
| `CONNECTION_REFUSED` | 端口不可达 | Port closed or instance down |
| `TIMEOUT` | 连接超时 | Network latency or congestion |
| `UNKNOWN_COMMAND` | 命令语法错误 | Check syntax |

其他产品可以扩展自己的 TYPE 列表，但 FIX 必须提供可操作的人工指引。

### 退出码规范

| ExitCode | 含义 | Agent 动作 | 人工介入 |
|:--------:|------|-----------|:--------:|
| 0 | 成功 | 读取 SUMMARY 回传 | ❌ |
| 10-19 | 环境检查失败 | 自动触发修复（如安装） | ❌ |
| 20-29 | 安装失败 | 输出 `[DIAG] disk/mem/network` | ✅ |
| 30-39 | 网络问题 | 输出 DNS/连接诊断 | ✅ |
| 40-49 | 命令执行失败 | 输出 `[ERROR] TYPE=... FIX=...` | ✅ |

## 5. Idempotent Provisioning Pattern

对于需要在目标机器上预置工具的操作，必须遵循幂等模式：

```bash
# 1. 探测
if ! command -v redis-cli &>/dev/null; then
  # 2. 仅在缺失时安装
  apt-get install -y redis-tools
fi
# 3. 执行（不关心安装与否）
redis-cli -h host DEL key
```

不要在无判断的情况下每次执行安装。探测结果用 DIAG/RESULT 日志输出。

## 6. Cross-Skill Composition

当一个 Skill 需要另一个 Skill 的基础能力时（如 redis-ops 需要 ecs-ops 的 RunCommand）：

**推荐：在 SKILL.md 中内联必要命令，在注释中注明依赖。**

```markdown
# Execution — CLI  (uses aliyun ecs RunCommand; see alicloud-ecs-ops for advanced usage)
aliyun ecs RunCommand --RegionId ... --CommandContent "..."
```

**不推荐：形式化 import/require 另一个 skill**（Agent 可能未同时加载两个 skill）。内联是更可靠的模式。

## 7. Data Plane vs Control Plane

| Plane | 能力范围 | 使用通道 | 代表操作 |
|-------|---------|---------|---------|
| **Control Plane** | 实例生命周期、配置管理 | `aliyun {product}` API | Create/Delete/Describe/Modify 实例 |
| **Data Plane** | 数据读写、命令执行 | `redis-cli` / SDK 直连 | DEL, GET, SET, TTL, EVAL |

当现有 API 无法覆盖 Data Plane 操作时，使用 **Cloud Assistant + CLI 客户端** 间接实现：

```
redis-ops 编排层 → ecs-ops RunCommand → 目标 ECS 执行 redis-cli
```

## 8. Security Constraints

- **凭证永不输出**：`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 在日志中必须替换为 `****`
- **密码通过环境变量传递**：使用 `REDISCLI_AUTH` 而非 `-a <password>`，避免暴露在 `ps aux` 或命令历史中
- **删除操作必须确认（MUST obtain explicit confirmation）**：在 Pre-flight Checks 表中包含 `Redis 命令确认` 一行

## 9. Quick Reference — Developer Commands

```bash
# Markdown linting
npx markdownlint-cli2 "alicloud-*/SKILL.md"

# Docker sandbox
docker compose --profile dev up -d
docker compose --profile interactive run interactive

# Generate new skill (use meta-skill)
"Generate alicloud-xyz-ops for product XYZ with operations: create, describe, modify, delete"
```

## 10. Five Quality Gates

每个 Skill 必须通过：

1. **Clear Boundaries**: SHOULD/SHOULD NOT triggers with delegation rules
2. **Structured I/O**: Placeholder conventions with documented types
3. **Explicit Steps**: Pre-flight → Execute → Validate → Recover
4. **Failure Strategies**: Error taxonomy (≥5 codes), HALT vs retry logic
5. **Single Responsibility**: One product, one primary resource

---

## Key References

- `README.md` — 项目概述、CLI 安装、凭证配置
- `REQUIREMENTS.md` — 各 Skill 功能需求详情、架构设计
- `alicloud-skill-generator/SKILL.md` — Meta Skill 生成器
- `CLAUDE.md` — 旧版指令（部分内容已合并至此文件）