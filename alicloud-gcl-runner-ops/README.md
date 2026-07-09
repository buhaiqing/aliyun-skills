# alicloud-gcl-runner-ops — Generator-Critic-Loop 共享框架

> **属于 [aliyun-skills](https://github.com/buhaiqing/aliyun-skills) — 阿里云运维技能农场，专为 AI Agent 设计的结构化可执行运维 runbook****

## 为什么需要这个共享 skill？

### 设计决策：在一个共享 skill 中集中 GCL 编排

**GCL (Generator-Critic-Loop，生成者-评审者循环)** 是一个**对抗性质量闸门**，每一个写操作/破坏性云操作在返回结果给最终用户之前**必须**经过它。如果我们把完整的 GCL 编排逻辑复制粘贴到**每一个**产品 skill 中会：

- ❌ **重复反模式**：34+ 个产品技能 × ~500 行 GCL 逻辑 = **17,000 行重复代码**
- ❌ 任何 bug 修复或功能增强需要修改 34+ 份拷贝 → 合并疲劳、代码漂移、行为不一致
- ❌ 很难在所有技能上统一演进 GCL 协议

✅ **集中共享 skill** 设计（本仓库）：

- 只在这一个地方实现完整的 GCL 循环（预检查 → 生成 → 评审 → 决策） → **总计 ~2,000 行**
- 产品技能只需要提供 `references/rubric.md` + `references/prompt-templates.md` → 每个产品技能只需要 ~200-500 行
- 任何 bug 修复/功能增强**只在这里修改一次** → 所有产品技能自动获得改进
- 所有技能行为统一 → 最终用户/Agent 体验一致

- ❌ **Duplication anti-pattern** if every skill implements its own GCL runner:
  - 34+ product skills × ~500 lines of GCL logic = **17,000 lines of duplicated code**
  - Any bug fix or enhancement needs to be applied to 34+ copies → merge fatigue, drift, inconsistent behavior
  - Hard to evolve the GCL protocol uniformly across all skills

- ✅ **Centralized shared skill** design (this repo):
  - One implementation of the full GCL loop (pre-flight → generate → critique → decide) → **~2,000 lines total**
  - Product skills only need to provide `references/rubric.md` + `references/prompt-templates.md` → ~200-500 lines per skill
  - Bug fixes/enhancements apply *once here* → all product skills get the improvement automatically on next pull
  - Uniform protocol across all skills → end-user/agent experience is consistent

## Capabilities

### 已实现阶段

| 阶段 | 状态 | 功能描述 |
|-------|--------|-------------|
| Phase 1 | ✅ | 规范 + 核心角色定义 |
| Phase 2 | ✅ | 机械正则评审（无需 LLM，完全确定性） |
| Phase 3-A | ✅ **基于 LLM 的评审**（支持 mechanical/llm/hybrid 三种模式） |
| Phase 3-B | ✅ | CMS  phantom 告警创建（GCL 结果 → 自定义 CMS 指标） |
| Phase 3-C | ✅ | 操作审计交叉验证（根据云审计日志重新验证 GCL 结果） |
| Phase 4 | ✅ | CMS 通过率告警（安全失败率、正确性下降） |
| Phase 5 | ✅ | 完整发布到所有 17 个 `required` + 8 个 `recommended` 技能 |
| Phase 6 | ✅ | 幻觉检测 (H) 执行前闸门 → 提前捕获 LLM 幻觉 |
| Phase 7 | ✅ | 智能告警循环（模式驱动自动降解） |
| Phase 8 | ✅ | Wrapper 合规性（强制 AGENTS.md §15.8 要求使用 SkillOpt wrapper） |

### 基于 LLM 的评审 (Phase 3-A)

自 2026-06-18 起，`gcl_runner.py` 支持三种评审模式，通过你根目录 `.env` 中的 `GCL_CRITIC_MODE` 配置：

| 模式 | 行为 |
|------|----------|
| **mechanical** (默认) | 纯 Python 正则评审，零网络调用，完全确定性 |
| **llm** | 纯 LLM 打分，所有维度来自 LLM 响应 |
| **hybrid** (启用 LLM 时推荐) | **机械评审处理硬安全闸门**（safety=0 → 立即中止），**LLM 处理细腻软打分** → 结合两者优点 |

### 配置（在根目录 `.env` 中）

```bash
# LLM 评审配置（mechanical 模式下忽略）
GCL_CRITIC_MODE=hybrid                    # mechanical | llm | hybrid
GCL_CRITIC_LLM_FAIL_OPEN=true             # 如果 LLM 失败：回退到 mechanical (true) | 直接退出错误 (false)
GCL_CRITIC_LLM_ENDPOINT=https://.../v1/chat/completions  # OpenAI 兼容端点
GCL_CRITIC_LLM_API_KEY=sk-...          # 端点 API key
GCL_CRITIC_LLM_MODEL=gpt-4o-mini       # 模型名（留空使用端点默认）
GCL_CRITIC_LLM_TIMEOUT=30             # HTTP 请求超时（秒）
```

### How It Works

1. **Every product skill** declares that any write/destructive operation should be delegated to `alicloud-gcl-runner-ops` via GCL
2. **The delegating agent** calls:
   ```bash
   cd alicloud-gcl-runner-ops
   ./scripts/gcl-runner-skillopt-wrapper.sh \
     --skill alicloud-ecs-ops \
     --op DeleteInstance \
     --command "aliyun ecs DeleteInstance --InstanceId i-bp1..."
   ```
3. **`alicloud-gcl-runner-ops`** runs the full GCL loop:
   - Pre-flight: validate credentials, product matching, secret sanitization, LLM endpoint if configured
   - Generate: execute the command via subprocess, capture stdout/stderr/exit-code
   - Critique: mechanical + LLM (hybrid mode) evaluates the output against the product's rubric
   - Decide: PASS / RETRY / MAX_ITER / SAFETY_FAIL / HALLUCINATION_ABORT
   - Persist JSON trace to `./.runtime/audit/gcl-runner-ops/` (gitignored)
4. **The delegating agent** consumes the result trace and decides to continue or abort

## Quality Gates

Every change to this shared framework:
- **100+ unit tests** (pure Python stdlib, no external deps)
- **`ruff` checked and fixed** for code quality
- **all tests pass** before merge to `main`

## References

- Full GCL specification: [`docs/gcl-spec.md`](../docs/gcl-spec.md)
- AGENTS.md rules: [`../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate`](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate)
- SkillOpt integration: [`references/skillopt-integration.md`](./references/skillopt-integration.md)
