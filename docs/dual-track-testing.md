# Dual-Track Testing — 双轨测试规范

> **Source**: extracted from `AGENTS.md §11.2`. MANDATORY for every cloud operation /
> GCL / Reflexion / Memory feature delivered to production.

> **原则**：每个涉及云操作 / GCL / Reflexion / Memory 的功能点交付前，**必须**完成双轨测试，缺一不可。

---

## 1. 双轨定义

| 轨道 | 目标 | 工具 | 通过条件 |
|------|------|------|----------|
| **Track 1: dry-run / 机制层** | 用最小代价跑通整个功能逻辑（路径、分支、store、注入） | `--dry-run` / unit test / 单元 fixture | 链路全绿，无路径分支跳过 |
| **Track 2: 真实环境 / 集成层** | 在真实凭证 + 真实 `aliyun` CLI 调用下，跑一次端到端集成 | 真实云账号 + `aliyun <product> <action>` + GCL runner | trace 落盘、memory_store / reflexion_store 真实触发 |

**禁止**：

- 只跑 dry-run 就宣称交付（机制 ≠ 集成）
- 只跑真实环境就宣称交付（路径覆盖 ≠ 真实数据）
- 跳过任一轨道（违反双轨原则，回归风险翻倍）

**优先级**：真实环境出现破坏性风险时，**先 Track 1 跑通，再 Track 2 用只读操作集成**（如 `Describe*` / `List*` / `Get*`），避免误删资源。

---

## 2. 典型场景举例

| 功能 | Track 1 | Track 2 |
|------|---------|---------|
| GCL pre-flight 注入 | `gcl_runner.py --dry-run --user-request "..."` 验链路 | 任意产品 skill 跑一次非 dry-run GCL，trace 中 `generator_prompt_with_memory` 含真实替换文本 |
| Reflexion memory 落盘 | `--dry-run` 验 `memory_store result=success` | 非 dry-run 跑失败命令（如 MAX_ITER）验 `reflexion_store result=success` |
| memory_preflight retrieval | `memory_preflight_test.py` 单测 | 跑一次 GCL，trace 含真实 `slots.known_traps` 内容 |

**例外**（仅以下情况可单轨）：

- 纯静态文档改动（不涉及代码）→ 只跑 lint
- 仅 stub / fixture 改动 → Track 1 即可

---

## 3. 凭证不可用时的处理（`[BLOCKED:no-credentials]`）

> **场景**：真实环境集成（Track 2）需要 `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`，但当前会话拿不到有效凭证（例如离线开发、CI 无 secret、临时租户切换等）。

### 3.1 判定凭证不可用的标准（任一满足即触发）

| # | 检查 | 命令 | 失败信号 |
|---|------|------|----------|
| 1 | 环境变量缺失 | `env \| grep -E '^ALIBABA_CLOUD_ACCESS_KEY_(ID\|SECRET)='` | 空输出 |
| 2 | CLI 未配置 profile | `aliyun configure list` | Profile 列表为空 / 标记 `Invalid` |
| 3 | CLI 探测调用失败 | `aliyun ecs DescribeRegions --RegionId cn-hangzhou` | exit code 非 0 / `InvalidAccessKeyId.NotFound` 等鉴权错误 |

### 3.2 处理流程

1. **Track 1 必须全绿**——dry-run / 单测 / 路径分支全部覆盖。
2. **在交付物 / PR 描述 / trace 注释中显式标注**：

   ```text
   [BLOCKED:no-credentials] Track 2 skipped — see env check output.
   Track 1 status: PASS (5/5 dry-run traces, all stores verified)
   ```

3. **列出 Track 2 待办**（让接手人知道怎么补）：

   ```bash
   # 恢复 Track 2 的最小复现步骤：
   export ALIBABA_CLOUD_ACCESS_KEY_ID=<valid_ak>
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<valid_sk>
   aliyun configure set --profile default --region cn-hangzhou
   # 重跑任意一个 GCL dry-run 改为非 dry-run
   python3 alicloud-gcl-runner-ops/scripts/gcl_runner.py \
     --skill alicloud-ecs-ops --op DescribeInstances \
     --command "aliyun ecs DescribeInstances --RegionId cn-hangzhou" \
     --output-dir .runtime/audit/gcl-runner-ops
   ```

4. **禁止掩盖**：不得在凭证缺失时编造"已集成验证"或伪造 trace。

**回退**：一旦凭证恢复，立即补 Track 2，并把 `[BLOCKED:no-credentials]` 标记替换为 `[INTEGRATED:verified <date>]`。

---

## 4. 相关规范

- 完整 GCL 流程：见 [`docs/generator-critic-loop.md`](generator-critic-loop.md)（§12 GCL 的完整规范）
- 凭证安全约束：见 `AGENTS.md §8 Security`（不输出凭证 / 密码走 env / 删除 op 需确认）
- GCL Runner 实现：见 [`alicloud-gcl-runner-ops/SKILL.md`](../alicloud-gcl-runner-ops/SKILL.md)