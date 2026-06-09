# alicloud-terraform-ops — Agent Guide

> **Read this file** when modifying `modules/`, `scripts/`, `assets/`, or adding NL2HCL / Import support.
> Repo-wide rules remain in [`../../AGENTS.md`](../../AGENTS.md). Execution flows live in [`SKILL.md`](SKILL.md).

---

## 1. Scope

| Path | Role | Git |
|------|------|-----|
| `modules/` | **Module-first 模板库**（源码） | ✅ Commit |
| `environments/` | apply/destroy **模板** | ✅ Commit |
| `assets/module-coverage.json` | 覆盖 manifest（单一真相源） | ✅ Commit |
| `.runtime/terraform-ops/` | NL2HCL / import / 工作区 | ❌ gitignore |
| `scripts/` | NL2HCL、Import、HITL、校验 | ✅ Commit |

**Banned:** runtime 产物进 Git；在 skill 内新建 `generated/`、`output/`。

---

## 2. Architecture — 三条路径

```
                    ┌─────────────────┐
  自然语言 create ──►│ NL2HCL          │──► module 块 + copy modules/
                    │ (module-first)  │     .runtime/.../nl2hcl/<env>/
                    └────────┬────────┘
                             │ Module Coverage Gate (必须)
                    ┌────────▼────────┐
  已有资源 import ──►│ Reverse Eng.    │──► 裸 resource 块 + import.sh
                    │ (import path)   │     .runtime/.../import/<batch>/
                    └────────┬────────┘
                             │ resource_registry PreFlight
                    ┌────────▼────────┐
  变更/销毁 apply ──►│ Apply / Destroy │──► environments 模板 seed
                    │ + HITL + GCL    │     .runtime/.../environments/<env>/
                    └─────────────────┘
```

| 路径 | HCL 形态 | 依赖 `modules/` |
|------|----------|-----------------|
| **NL2HCL** | 根目录仅 `module` 块 | ✅ 复制模板 |
| **Import** | 裸 `resource` 块 | ❌ 不复制 |
| **Apply/Destroy** | 用户/模板维护的 workspace | 引用 `../../../modules/` |

---

## 3. Runtime Layout

```
${SKILLS_DIR}/.runtime/terraform-ops/
├── nl2hcl/<env>/          # create 输出
├── import/<batch>/        # import 输出
├── environments/<env>/    # apply/destroy
└── pr-store/              # HITL Mode B

${SKILLS_DIR}/.runtime/audit/terraform-ops/   # traces
```

清理：`make runtime-clean` / `make runtime-clean-apply`（仓库根 Makefile）。

---

## 4. Module Coverage — 防遗漏（MANDATORY）

### 4.1 单一真相源

[`assets/module-coverage.json`](assets/module-coverage.json) 声明每个 `tf_type` 的：

- `nl2hcl_module` — 对应 `modules/<name>/`（`null` = NL2HCL 不可用）
- `registry_name` — 对应 `resource_registry.py`
- `import_supported` — Import 路径是否可用
- `keywords` — 自然语言关键词（防 parse_intent 静默遗漏）

### 4.2 新增/扩展模块 — 四件套（全部必做）

| # | 文件 | 动作 |
|---|------|------|
| 1 | `modules/<module-name>/` | 添加 `main.tf` + `variables.tf` + `outputs.tf` + `versions.tf` |
| 2 | `assets/module-coverage.json` | 登记 `tf_type` → `nl2hcl_module` + `keywords` |
| 3 | `scripts/module_catalog.py` | `plan_modules()` + `render_main_tf()` 编排 |
| 4 | `scripts/nl2hcl_generator.py` | `RESOURCE_PATTERNS` 增加 regex |
| + | `scripts/resource_registry.py` | Import 路径需登记 + PreFlight |
| + | `scripts/test_module_*.py` | 单测覆盖生成与 gate |

**禁止：** 只改 Import、不改 manifest / NL2HCL；只加 regex、不加 module 目录。

### 4.3 运行时门禁

NL2HCL 在生成前调用 `module_coverage.check_nl2hcl_coverage()`：

- 请求含关键词但 intent 未识别 → **HALT**（exit 6）
- intent 含无 module 的资源 → **HALT**，提示走 Import 或补 module

### 4.4 提交前校验（MANDATORY）

```bash
cd alicloud-terraform-ops/scripts
python3 module_coverage.py --verify
python3 -m unittest discover -p 'test_*.py' -q
```

`--verify` 检查：manifest ↔ `modules/` ↔ registry ↔ `RESOURCE_PATTERNS` 一致性。

---

## 5. Content Separation

| 文件 | 职责 |
|------|------|
| **本 AGENTS.md** | Agent 开发约束、架构、门禁 |
| **SKILL.md** | 触发、执行概览、变量 |
| **references/** | CLI 细节、HITL、故障恢复 |
| **references/module-coverage.md** | manifest 字段、HALT 文案、扩展示例 |

---

## 6. Pre-Merge Checklist

- [ ] `module_coverage.py --verify` 通过
- [ ] 全量单测通过
- [ ] 新能力已更新 `TODO.md`（F8）
- [ ] 无 runtime 路径进 `git add`
- [ ] NL2HCL 新资源：四件套齐全，无静默遗漏
- [ ] Import-only 资源：`nl2hcl_module: null` + gate 会 HALT create，文档已说明 Import 路径

---

## 7. Anti-Patterns

| ❌ | ✅ |
|----|-----|
| 用户提 MongoDB，只生成 VPC | Gate HALT + 指引 `import -t mongodb` |
| 复制 `modules/` 进 Git 作为 generated | 仅 `.runtime/` 下有副本 |
| 在 SKILL.md 写 500 行开发细节 | 链到 `references/module-coverage.md` |
| 跳过 manifest 直接加 regex | 先改 `module-coverage.json` |

---

## 8. Key References

| Doc | Purpose |
|-----|---------|
| [SKILL.md](SKILL.md) | What to execute |
| [references/module-coverage.md](references/module-coverage.md) | Coverage manifest spec |
| [modules/README.md](modules/README.md) | Module inventory |
| [TODO.md](TODO.md) | Feature tracking |
| [../../AGENTS.md](../../AGENTS.md) §13 | Runtime artifacts policy |
