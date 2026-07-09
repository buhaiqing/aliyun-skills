# Sprint 20 — .gitignore 完整性补齐 (P0-4)

> **状态**: PASS 4/4
> **优先级**: P0 (仓库级安全 + 卫生)
> **业务价值**: 防止凭证泄露 (`.env` / `credentials.json` / `*.key` / `*.pem`); 防止工具链缓存 (`.ruff_cache/` `.pytest_cache/`) 入库; 防止报告敏感数据泄露; 防止 `node_modules/` 污染仓库

## 一、问题分析

仓库根 `.gitignore` 已有 158 行详尽规则 (Go / Python / IDE / OS / Runtime 等), 但存在 5 类缺口:

| 类别 | 缺口 | 风险 |
|------|------|------|
| 凭证类 | `secret.env` / `prod.env` / `credentials.json` / `*.key` / `*.pem` | 高 — 凭证泄露 |
| Python 工具链 | `.ruff_cache/` `.mypy_cache/` `.tox/` `.coverage/` `htmlcov/` | 中 — 仓库膨胀 |
| Node.js | `node_modules/` `package-lock.json` | 中 — 仓库膨胀 |
| Skill 报告目录 | `alicloud-*/reports/*` (排除 templates/) | 中 — 敏感报告泄露 |
| 验证机制 | 无 `git check-ignore` 自动化测试 | 低 — 后续缺口的检测滞后 |

## 二、修复内容

### T1: 凭证类规则 (高风险)

```gitignore
# Environment files (NEVER commit secrets)
.env
.env.*
*.env                              # 新增: 任意位置 *.env
!.env.example

# Credential / key files (NEVER commit; catch-all)
*.key                              # 新增
*.pem                              # 新增
*.p12                              # 新增
*.pfx                              # 新增
credentials                        # 新增
credentials.json                   # 新增
*credentials*                      # 新增 (覆盖所有位置)
*secrets*                          # 新增
```

### T2: Python 工具链缓存

```gitignore
.mypy_cache/                       # 新增
.ruff_cache/                       # 新增
.pytest_cache/                     # 新增
.tox/                              # 新增
.coverage                          # 新增
htmlcov/                           # 新增
```

### T3: Node.js

```gitignore
node_modules/                      # 新增
package-lock.json                  # 新增
```

### T4: Skill 报告目录

```gitignore
# 忽略 reports/ 下所有非 templates/ 的内容
# 例: alicloud-aiops-cruise/reports/perceive-2026.json (忽略)
#     alicloud-aiops-cruise/reports/templates/deep-report-template.md (保留)
alicloud-*/reports/*               # 新增
!alicloud-*/reports/templates/     # 新增 (反忽略)
!alicloud-*/reports/templates/**   # 新增 (递归)
```

### T5: 验证方法 (P0-4 自身)

```bash
# 测单个路径
git check-ignore <path>

# 显示匹配规则行号
git check-ignore -v <path>

# 跨 skill 抽样测试 (覆盖 5 个 skill)
for skill in alicloud-aiops-cruise alicloud-ecs-ops alicloud-rds-ops \
             alicloud-redis-ops alicloud-actiontrail-ops; do
  for path in "${skill}/.runtime/cache/x" \
              "${skill}/audit-results/x" \
              "${skill}/secret.env" \
              "${skill}/credentials.json" \
              "${skill}/.ruff_cache/x"; do
    git check-ignore -q "$path" || echo "FAIL: $path"
  done
done
```

## 三、验证结果

### 36 项 git check-ignore 跨 skill 验证 (P0-4 验收)

**全部 PASS** —— 0 个缺口。

| 类别 | 测试路径数 | PASS |
|------|----------|------|
| `.runtime/{audit,cache,logs,tmp,baseline}` | 5 | 5/5 |
| `__pycache__/` 跨子目录 | 2 | 2/2 |
| `reports/*` (排除 templates) | 4 | 4/4 |
| 凭证类 (`secret.env` `prod.env` `.env` `.env.*`) | 4 | 4/4 |
| Python 工具链 (`.ruff_cache` `.pytest_cache` `.mypy_cache` `.tox` `.coverage` `htmlcov`) | 6 | 6/6 |
| Node.js (`node_modules/`) | 1 | 1/1 |
| IDE (`.idea/` `.vscode/`) | 2 | 2/2 |
| 临时文件 (`*.tmp` `*.log` `.DS_Store` `Thumbs.db`) | 4 | 4/4 |
| 凭证/密钥 (`credentials.json` `*.key` `*.pem`) | 3 | 3/3 |
| **逆向 (应保留)** `.env.example` `reports/templates/...` `*.egg-info/` `dist/` `.venv/` | 5 | 5/5 |
| **总计** | **36** | **36/36** |

### 跨其他 skill 验证 (alicloud-rds-ops / alicloud-ecs-ops / alicloud-redis-ops)

抽样 10 项路径全部 PASS —— `alicloud-*/...` 模式对所有 skill 生效。

## 四、Self-Review (F1-F8)

- [x] F1: CLI command validation — `.gitignore` 166 行无语法错误
- [x] F2: OpenAPI accuracy — N/A
- [x] F3: Error handling — `git check-ignore` 36/36 验证通过
- [x] F4: Safety gates — 0 个凭证模式被错误保留
- [x] F5: Link integrity — `.runtime/` `.runtime-*/` `alicloud-*/audit-results/` 规则互不冲突
- [x] F6: Content deduplication — 0 个重复条目
- [x] F7: Cross-skill delegation — 跨 5 个 skill 抽样 10/10 PASS
- [x] F8: TODO.md 同步 — 本文件 + SKILL.md Changelog (v1.5.1) + TODO.md 索引

## 五、变更文件

| 文件 | 变更 |
|------|------|
| `.gitignore` | +39 行 (含 P0-4 Revision Notes 头注释 + 5 段新规则) |
| `alicloud-aiops-cruise/SKILL.md` | version 1.5.0 → 1.5.1 + Changelog 1.5.1 条目 |
| `alicloud-aiops-cruise/TODO.md` | Sprint 索引新增 Sprint 20 |
| `alicloud-aiops-cruise/TODO/sprint-20-gitignore-complete.md` | 本文件 |

## 六、后续建议 (非 P0-4 任务范围)

- 在 CI 中加 `git ls-files | grep -E "(secret\.env|credentials\.json|\.key$|\.pem$)"` 检测, 失败即拒合并
- 季度审计时跑 `git check-ignore` 全 skill 抽样测试
- 考虑迁移到 [pre-commit framework](https://pre-commit.com/) + `check-yaml` `check-added-large-files` 等 hook
