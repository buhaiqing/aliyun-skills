---
name: pre-approved-whitelist
version: "1.0.0"
parent: alicloud-aiops-cruise
status: mandatory
---

# 预授权白名单 — AIOps Cruise 自动执行操作白名单

> **目的**：在不破坏"安全铁律"前提下，让低风险可逆操作自动执行（如 RDS 清理 binlog、ECS 内只读诊断），将 MTTR 从"发现->等用户->确认->执行"压缩到秒级。Sprint 12 (双引擎) 的"固化工作流引擎"完全依赖本白名单。
>
> **本文件是 MR-9 (写操作确认规范) 的执行细则。** 所有白名单操作仍需满足 §五的审批 + §六的审计要求。

---

## 一、为什么需要白名单

> 当前所有写操作均 `[SUGGESTED]` 标记，需要用户逐条确认。即使是 RDS 清理 binlog 这种几乎无副作用的运维操作，也必须等用户点头。在"应急排查"场景下，这种同步等待会导致 MTTR 显著拉长。
>
> 白名单的本质：**预先把"哪些操作可以无副作用执行"达成共识**，让运行时不用再问。

**核心约束**：
- 白名单不是"放开手脚"，而是"提前谈好边界"
- 每个白名单项必须有：可观测、可回滚、季度复审
- 任何"对账"操作（涉及钱/安全）永远不进白名单

---

## 二、白名单分级

| 级别 | 标签 | 含义 | 触发条件 | 通知 | 风险 |
|------|------|------|---------|------|------|
| **L0 极低** | `[AUTO-QUIET]` | 只读但通过 CloudAssistant 在 ECS 内执行的诊断命令 | 任何诊断场景 | 不通知 | 极低（只读） |
| **L1 低** | `[AUTO-NOTIFY]` | 数据清理类（binlog 清理、临时文件清理），可逆或影响极小 | 满足前置条件 | 钉钉/企微 @oncall | 低 |
| **L2 中** | `[AUTO-CONFIRM]` | 资源扩缩容类（升配），需提前通知用户 | 用户预授权 + 5min 等待期 | 通知 + 二次确认 | 中 |
| **L3 高** | `[MANUAL]` | 安全组规则变更、删除类操作、跨账号操作 | 始终需用户确认 | — | 高 |

**标签用途**：所有输出报告中的 CLI 命令前缀必须用对应标签，详见 `references/maintenance-rules.md` MR-9。

---

## 三、初始白名单矩阵（v1.0）

> **状态**：安全团队 + 运维负责人双签后生效；首批 3 项覆盖 L0 + L1；L2 及以上首批不纳入，需更多实战验证

| # | 操作 | CLI/SDK | 风险级别 | 自动执行条件 | 通知方式 | 验证命令 | 回滚命令 | 批准日期 |
|---|------|---------|---------|--------------|---------|---------|---------|---------|
| **W-01** | ECS 内执行只读诊断命令（ps/top/df/ss/iptables -L 等） | `aliyun ecs RunCommand --CommandContent "..."` | L0 | 命令前缀必须在 §四 允许清单内 | 不通知 | `command -v <cmd>` | N/A（只读无副作用） | 2026-Q2 |
| **W-02** | RDS 清理已消费 binlog | `CALL mysql.rds_cycle_binlog()` | L1 | 磁盘使用率 > 85% AND binlog 占用 > 50% | 钉钉 @oncall | `aliyun rds DescribeBinlogFiles` | binlog 重新生成，业务无感 | 2026-Q2 |
| **W-03** | Redis 修改 maxmemory-policy 为 allkeys-lru | `aliyun r-kvstore ModifyInstanceConfig --Config '{"maxmemory-policy":"allkeys-lru"}'` | L1 | 内存使用率 > 80% AND 逐出次数 > 0 | 钉钉 @oncall | `aliyun r-kvstore DescribeInstanceConfig` | `ModifyInstanceConfig --Config '{"maxmemory-policy":"volatile-lru"}'` | 2026-Q2 |
| W-04 | RDS 存储空间扩容 | `aliyun rds ModifyDBInstanceSpec --DBInstanceStorage N` | L2 | **首批不纳入**，需更多 L1 实战数据 | — | — | 仅扩容不缩容，无回滚 | TBD |
| W-05 | 安全组规则删除 | `aliyun ecs RevokeSecurityGroup` | L3 | **禁止纳入白名单** | — | — | `aliyun ecs AuthorizeSecurityGroup` 重添 | — |
| W-06 | 资源删除/释放 | `aliyun ecs DeleteInstance` / `DeleteDBInstance` | L3 | **禁止纳入白名单** | — | — | 不可回滚 | — |

---

## 四、L0 极低风险命令白名单（嵌套）

> CloudAssistant 在 ECS 内执行的命令必须以前缀匹配以下模式才允许 `[AUTO-QUIET]`。
> **不匹配 -> 自动降级为 `[SUGGESTED]`，等用户确认**

### 4.1 允许的只读命令前缀

```bash
# 进程与系统（只读）
ps | top | htop | free | df | du | ss | netstat | ip | ifconfig |
iostat | vmstat | mpstat | sar | uptime | uname | hostname | lscpu | lsmem |
lsblk | lsmod | lsof | w | who | last | lastlog

# 文件查看（只读）
cat | head | tail | less | more | file | stat | wc | find | ls | tree |
grep | awk | sed | cut | sort | uniq | tr | xargs -n1 | diff

# 网络诊断（只读）
ping | traceroute | tracepath | nslookup | dig | host | mtr | ss | netstat |
tcpdump | ip route show | ip addr show

# 服务与日志（只读）
systemctl status | systemctl list-units | systemctl is-active |
journalctl | dmesg | crontab -l | date | cal | env

# 安全与防火墙（只读）
iptables -L | iptables -S | iptables -nvL | nft list | nft list ruleset |
ufw status | firewall-cmd --list-all | getenforce

# 资源限制
ulimit -a
```

### 4.2 禁止的命令（绝对黑名单）

```bash
# 任何修改/删除
rm | mv | chmod | chown | chgrp | ln | cp -f | truncate | dd of= | mkfs | mount | umount
kill | killall | pkill | skill | kill -9

# 任何下载/网络写入
curl | wget | nc | ncat | socat | ssh | scp | rsync

# 任何 shell 解释器（防注入）
bash -c | sh -c | eval | exec | source | . /

# 任何重定向
> file | >> file | < file | tee file
```

### 4.3 校验逻辑

```
校验流程（每次 CloudAssistant 调用前）:
  1. 提取命令的 "binary name"（第一个 token，去掉 sudo/path）
  2. 检查是否在 §4.1 允许清单
  3. 检查是否匹配 §4.2 黑名单（即使白名单里有，黑名单优先）
  4. 检查是否含 `> >> < | tee` 重定向符
  5. 全部通过 -> 标记 [AUTO-QUIET]
     任一失败 -> 降级 [SUGGESTED]，等用户确认
```

---

## 五、审批与复审机制

### 5.1 准入审批

新增白名单项必须满足：

| 维度 | 要求 | 提交物 |
|------|------|--------|
| **技术验证** | 在测试环境执行 ≥ 3 次无副作用 | 测试报告 |
| **影响评估** | 列出可能的副作用及概率 | 风险评估表 |
| **回滚路径** | 必须有对应的回滚命令/操作 | 回滚 runbook |
| **观测能力** | 执行后必须输出 trace 记录 | trace schema |
| **安全评审** | 安全团队 + 运维负责人双签 | 评审 checklist（见 §八） |

### 5.2 季度复审

> **强制**：每季度末月（3/6/9/12 月）执行一次白名单复审

| 维度 | 检查项 | 指标来源 | 不通过处理 |
|------|--------|---------|----------|
| **执行次数** | 季度内执行 N 次 | 审计日志 | N=0 -> 降级为 L1 需确认 |
| **成功率** | 成功 / 总数 | 审计日志 | < 99% -> 临时降级 `[MANUAL]` |
| **误操作率** | 用户投诉 / 总数 | 投诉单 | > 0.5% -> 立刻移出白名单 |
| **回滚触发率** | 回滚次数 / 总数 | 审计日志 | > 1% -> 重新评估前置条件 |
| **执行耗时** | P95 耗时 | 审计日志 | > 5min -> 检查是否需拆步骤 |

### 5.3 紧急下线

出现以下任一情况，**当天** 移出白名单并降级为 `[MANUAL]`：

- 一次事故由白名单操作直接导致
- 安全团队紧急通知
- 30 天内 2 次执行失败
- 涉及资源的 SLA 协议变更

### 5.4 季度复审报告模板

```markdown
## 白名单季度复审报告 - {YYYY}-Q{N}

### 执行统计
| 白名单项 | 执行次数 | 成功率 | 误操作 | 回滚 | 结论 |
|----------|---------|--------|--------|------|------|
| W-01     | 142     | 100%   | 0      | 0    | 保留 |
| W-02     | 8       | 100%   | 0      | 0    | 保留 |
| W-03     | 3       | 100%   | 0      | 0    | 保留 |

### 变更建议
- W-04 (RDS 存储扩容)：本期 L1 稳定后申请升级 L2 [AUTO-CONFIRM]
- W-XX (新增候选)：{描述}

### 审批
- 安全团队: _____________  日期: ___
- 运维负责人: _____________  日期: ___
```

---

## 六、审计日志

### 6.1 日志 Schema

每次白名单操作必须落盘 1 条记录（JSONL 格式，1 行 1 条）：

```json
{
  "whitelist_id": "W-02",
  "level": "L1",
  "executed_at": "2026-06-06T15:30:42+08:00",
  "executed_by": "aiops-cruise",
  "customer": "rg-acfmvyfsd4znnoi",
  "resource_id": "rm-bp1xxxxxxxxxxxx",
  "command": "aliyun rds InvokeDBAction --DBInstanceId rm-bp1xxxxxxxxxxxx --Command 'CALL mysql.rds_cycle_binlog();'",
  "command_label": "[AUTO-NOTIFY]",
  "pre_condition_check": {
    "disk_usage": 97.3,
    "binlog_ratio": 0.68,
    "threshold_critical": 90.0,
    "threshold_binlog_min": 0.5,
    "passed": true
  },
  "result": "success",
  "result_message": "Binlog cleanup completed, freed 23.4GB",
  "trace_id": "9b8c7d6e-5f4a-3b2c-1d0e-9f8a7b6c5d4e",
  "duration_seconds": 1.2,
  "rolled_back": false,
  "rollback_command": null,
  "notified": ["dingtalk:oncall-group"]
}
```

### 6.2 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `whitelist_id` | OK | 白名单项 ID（W-NN） |
| `level` | OK | L0/L1/L2/L3 |
| `executed_at` | OK | ISO8601，含时区 |
| `executed_by` | OK | `aiops-cruise` / `user` / `agent:xxx` |
| `customer` | OK | 客户标识 |
| `resource_id` | OK | 操作的目标资源 |
| `command` | OK | 完整命令字符串 |
| `command_label` | OK | 命令标签 (`[AUTO-QUIET]` 等) |
| `pre_condition_check` | OK | 前置条件检查结果 |
| `result` | OK | `success` / `failed` / `rolled_back` |
| `result_message` | FAIL | 人类可读的执行结果 |
| `trace_id` | OK | 关联 runbook run_id |
| `duration_seconds` | OK | 耗时 |
| `rolled_back` | OK | 是否触发回滚 |
| `rollback_command` | FAIL | 触发的回滚命令 |
| `notified` | FAIL | 通知渠道列表 |

### 6.3 落盘位置

- 路径：`audit-results/audit/whitelist-{YYYY-MM-DD}.jsonl`
- 保留期：**1 年**（季度复审至少需要 90 天数据）
- 命名：按 UTC 日期分文件，便于按日检索

### 6.4 模板文件

参考 `references/whitelist-audit-template.jsonl`。

---

## 七、与现有文档的关系

| 现有文件 | 集成方式 |
|----------|---------|
| `SKILL.md` Safety Gates | 引用本文件，约定"自动执行必须命中白名单" |
| `references/maintenance-rules.md` MR-9 | 维护 4 个标签的定义（`[AUTO-QUIET]` 等） |
| `references/inference-rules.md` | 修复步骤中的命令前缀使用本文件标签 |
| `references/incident-schema.md` | `fix_commands[]` 字段的命令标签语义与本文件一致 |
| `references/architecture-roadmap.md` §3.2 | 本文件是 §3.2 的具体落地实现 |
| Sprint 12 (双引擎) | 固化工作流引擎运行时查询本白名单 |

---

## 八、安全团队评审 Checklist

新增白名单项时，安全团队按此 checklist 评审：

```markdown
## 白名单准入评审 - {whitelist_id}

### 基础信息
- [ ] 申请人: ____
- [ ] 申请日期: ____
- [ ] 业务场景: ____

### 技术评估
- [ ] 测试环境执行 ≥ 3 次无副作用
- [ ] 前置条件检查逻辑可机器化（不是"靠人判断"）
- [ ] 失败时不会进入"半完成"状态（要么成功要么没动）
- [ ] 执行后资源状态可验证（Describe* 可确认）

### 影响评估
- [ ] 最坏情况分析: ____
- [ ] 受影响资源范围（单实例 / 多实例 / 全局）: ____
- [ ] 是否可逆: [ ] 完全可逆 [ ] 部分可逆 [ ] 不可逆
- [ ] 数据丢失风险: [ ] 无 [ ] 可恢复 [ ] 永久丢失

### 回滚
- [ ] 回滚命令/操作文档化
- [ ] 回滚耗时 < 5min
- [ ] 回滚本身是否需要白名单? [ ] 否 [ ] 是

### 观测
- [ ] trace 记录字段完整（§六 全部必填）
- [ ] 失败有告警渠道
- [ ] 异常 case 有定义

### 风险等级
- [ ] L0 极低 / L1 低 / L2 中 / L3 高

### 审批
- [ ] 安全团队负责人签字: ____ 日期: ____
- [ ] 运维负责人签字: ____ 日期: ____
- [ ] 业务方确认（如果是涉及业务的操作）: ____ 日期: ____
```

---

## 九、版本策略

| 版本 | 变更范围 |
|------|---------|
| v1.0.x | 修复文档错漏；调整 L0 命令白名单；新增 §六 审计字段定义 |
| v1.x.0 | 新增/删除白名单项；调整风险等级；调整前置条件 |
| v2.0.0 | 重构分级体系；变更审计日志 schema；变更审批流程 |

---

## 十、变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-06-06 | 初始版本（Stage 1 -> Sprint 6 闭环 S1-D3） |
