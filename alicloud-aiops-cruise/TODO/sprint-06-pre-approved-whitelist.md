# Sprint 6: 预授权白名单（P2）

> **状态**: PASS 8/8
> **业务价值**：在不破坏"安全铁律"前提下，让低风险可逆操作自动执行（如 RDS 清理 binlog），将 MTTR 从"发现->等用户->确认->执行"压缩到秒级。Sprint 12 (双引擎) 的"固化工作流引擎"完全依赖本白名单
> **交付物**：`references/pre-approved-whitelist.md`（白名单矩阵 + 审批流程 + 季度复审 + 审计日志）
> **前置条件**：Sprint 1（核心脚本化 PASS 已闭环）
> **关联验收项**：S1-D3

---

## 一、为什么需要白名单

> 当前所有写操作均 `[SUGGESTED]` 标记，需要用户逐条确认。即使是 RDS 清理 binlog 这种几乎无副作用的运维操作，也必须等用户点头。在"应急排查"场景下，这种同步等待会导致 MTTR 显著拉长。
>
> 白名单的本质：**预先把"哪些操作可以无副作用执行"达成共识**，让运行时不用再问。

---

## 二、白名单分级

| 级别 | 标签 | 含义 | 触发条件 | 通知 |
|------|------|------|---------|------|
| **L0 极低** | `[AUTO-QUIET]` | 只读但通过 CloudAssistant 在 ECS 内执行的诊断命令 | 任何诊断场景 | 不通知 |
| **L1 低** | `[AUTO-NOTIFY]` | 数据清理类（binlog 清理、临时文件清理），可逆或影响极小 | 满足前置条件 + 立即通知 | 钉钉/企微 |
| **L2 中** | `[AUTO-CONFIRM]` | 资源扩缩容类（升配），需提前通知用户 | 用户预授权 + 5min 等待期 | 通知 + 二次确认 |
| **L3 高** | `[MANUAL]` | 安全组规则变更、删除类操作、跨账号操作 | 始终需用户确认 | — |

---

## 三、初始白名单矩阵（v1.0）

> 安全团队审批后生效；首批 3 项覆盖 L0 + L1；L2 及以上首批不纳入，需更多实战验证

| # | 操作 | CLI/SDK | 风险级别 | 自动执行条件 | 通知方式 | 验证命令 | 批准日期 |
|---|------|---------|---------|--------------|---------|---------|---------|
| **W-01** | ECS 内执行只读诊断命令（ps/top/df/ss/iptables -L 等） | `aliyun ecs RunCommand --CommandContent "..."` | L0 | 命令前缀必须是只读白名单（见 §四） | 不通知 | `command -v <cmd>` | 2026-Q2 |
| **W-02** | RDS 清理已消费 binlog | `CALL mysql.rds_cycle_binlog()` | L1 | 磁盘使用率 > 85% AND binlog 占用 > 50% | 钉钉 @oncall | `aliyun rds DescribeBinlogFiles` | 2026-Q2 |
| **W-03** | Redis 修改 maxmemory-policy 为 allkeys-lru | `aliyun r-kvstore ModifyInstanceConfig --Config '{"maxmemory-policy":"allkeys-lru"}'` | L1 | 内存使用率 > 80% AND 逐出次数 > 0 | 钉钉 @oncall | `aliyun r-kvstore DescribeInstances` | 2026-Q2 |
| W-04 | RDS 存储空间扩容 | `aliyun rds ModifyDBInstanceSpec --DBInstanceStorage N` | L2 | **首批不纳入**，需更多 L1 实战数据 | — | — | TBD |
| W-05 | 安全组规则删除 | `aliyun ecs RevokeSecurityGroup` | L3 | **禁止纳入** | — | — | — |

---

## 四、L0 极低风险命令白名单（嵌套）

CloudAssistant 在 ECS 内执行的命令必须以前缀匹配以下模式才允许 `[AUTO-QUIET]`：

```bash
# 允许的只读命令前缀（按行匹配，开头允许有 sudo / path）
ps | top | htop | free | df | du | ss | netstat | ip | ifconfig |
iostat | vmstat | mpstat | sar | uptime | uname | hostname |
cat | head | tail | less | more | grep | awk | sed | cut | sort |
ls | find | stat | file | wc | lsof | tcpdump | strace | ltrace |
systemctl status | journalctl | dmesg | crontab -l | date | who | w |
iptables -L | nft list | ulimit
```

**禁止**：
- `rm` `mv` `chmod` `chown` `kill` `killall` `pkill`
- `curl` `wget` `nc`（除非带 `-V` 仅做版本查询）
- `bash -c` `sh -c` `eval`（命令注入面太大）
- 任何含 `>` `>>` `<` 重定向或 `|` 写管道的命令

---

## 五、审批与复审机制

### 5.1 准入审批

新增白名单项必须满足：
1. **技术验证**：在测试环境执行 ≥ 3 次无副作用
2. **安全评审**：安全团队 + 运维负责人双签
3. **可回滚**：必须有对应的回滚命令
4. **可观测**：执行后必须输出 trace 记录

### 5.2 季度复审

> **强制**：每季度末月（3/6/9/12 月）执行一次白名单复审

复审内容：
| 维度 | 检查项 | 不通过处理 |
|------|--------|----------|
| **执行次数** | 季度内执行 N 次 | N=0 -> 考虑降级为 L1 需确认 |
| **成功率** | 成功 / 总数 ≥ 99% | 低于 -> 临时降级为 `[MANUAL]` |
| **误操作率** | 用户投诉 / 总数 ≤ 0.5% | 超过 -> 立刻移出白名单 |
| **回滚触发率** | 回滚次数 / 总数 ≤ 1% | 超过 -> 重新评估前置条件 |

### 5.3 紧急下线

出现以下任一情况，**当天** 移出白名单并降级为 `[MANUAL]`：
- 一次事故由白名单操作直接导致
- 安全团队紧急通知
- 30 天内 2 次执行失败

---

## 六、审计日志

每次白名单操作必须记录：

```json
{
  "whitelist_id": "W-02",
  "level": "L1",
  "executed_at": "ISO8601",
  "executed_by": "aiops-cruise | user",
  "customer": "string",
  "resource_id": "rm-xxx",
  "command": "aliyun rds ...",
  "pre_condition_met": true,
  "result": "success | failed | rolled_back",
  "trace_id": "uuid",
  "duration_seconds": 0.5
}
```

落盘位置：`audit-results/audit/whitelist-{YYYY-MM-DD}.jsonl`

---

## 七、任务清单

- [ ] **6.1** 起草 `references/pre-approved-whitelist.md` 完整初版（§一 ~ §六 全部章节）
- [ ] **6.2** 在 SKILL.md "Safety Gates" 表格中追加 L0/L1/L2/L3 等级说明 + 引用
- [ ] **6.3** 在 `references/maintenance-rules.md` MR-9 中追加"白名单标记"行：`[AUTO-QUIET]` / `[AUTO-NOTIFY]` / `[AUTO-CONFIRM]`
- [ ] **6.4** 在 `references/inference-rules.md` 修复步骤中标注各操作的白名单级别（≥ 3 处示范）
- [ ] **6.5** 编写 `references/whitelist-audit-template.jsonl`（审计日志样例）
- [ ] **6.6** 起草"安全团队评审 checklist"作为本文件附录
- [ ] **6.7** TODO.md / stage-status.json 同步（MR-1 强制）
- [ ] **6.8** Post-Update Self-Review R1 + R2

---

## 八、质量门

| 编号 | 检查项 | 验证命令 | 阈值 |
|------|--------|----------|------|
| Q6.1 | 白名单文件存在 | `test -s references/pre-approved-whitelist.md` | 通过 |
| Q6.2 | L0/L1/L2/L3 四级齐全 | `grep -E 'L0\|L1\|L2\|L3' references/pre-approved-whitelist.md` | 命中 |
| Q6.3 | 至少 3 个 W-NN 初始项 | `grep -cE 'W-0[1-9]' references/pre-approved-whitelist.md` | ≥ 3 |
| Q6.4 | L0 命令白名单 ≥ 10 条 | `awk '/L0 极低风险命令白名单/,/禁止/' references/pre-approved-whitelist.md \| grep -cE '^\| \`' | ≥ 10 |
| Q6.5 | 季度复审章节存在 | `grep -c '季度复审' references/pre-approved-whitelist.md` | ≥ 1 |
| Q6.6 | 审计日志 Schema 示例 | `grep -c 'whitelist_id' references/pre-approved-whitelist.md` | ≥ 1 |
| Q6.7 | SKILL.md 引用 | `grep -c 'pre-approved-whitelist' SKILL.md` | ≥ 1 |
| Q6.8 | MR-9 标记更新 | `grep -c 'AUTO-QUIET\|AUTO-NOTIFY\|AUTO-CONFIRM' references/maintenance-rules.md` | ≥ 3 |
| Q6.9 | inference-rules.md 标注 | `grep -c '\[AUTO-' references/inference-rules.md` | ≥ 3 |
| Q6.10 | audit 模板存在 | `test -s references/whitelist-audit-template.jsonl` | 通过 |
| Q6.11 | TODO.md 同步 | `grep -c 'Sprint 6.*6/' TODO.md` | ≥ 1 |
| Q6.12 | Markdown Lint | `npx markdownlint-cli2 "references/pre-approved-whitelist.md"` | 0 错误 |

---

## 九、Sprint 完成判据

- 所有 8 个任务项 `[x]`
- 所有 12 个 Q 检查项 PASS
- TODO.md / stage-status.json 同步更新
- Post-Update Self-Review R1 + R2 全部 PASS
