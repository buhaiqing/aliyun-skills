# alicloud-topo-discovery Upgrade Design (v1.0 MVP + v1.1)

> **Status**: Design — pending user review
> **Date**: 2026-06-04
> **Owner**: TBD
> **Repo**: `aliyun-skills/alicloud-topo-discovery/`

---

## 1. Context & Goals

### 1.1 Background
`alicloud-topo-discovery` 当前是只读网络拓扑扫描器(33 个 product skill 之外的横向能力)。基于前 5 轮对话,本 skill 需升级为:

> **"Cloud Resource Discovery + Declarative Archive" 双职能源 skill** —— 保留全部 read-only 安全门,新增按需 HCL 导出与周期 baseline 管理。

### 1.2 Why
- **现状**:日常运维 80% 用 skill + CLI 即可(无需 TF);但 4 类场景(多资源编排、DR、合规审计、跨团队交接)需要"设计意图存档"——而该存档在云上不存在
- **痛点**:TF 维护成本高(每个 skill 加 TF 模式会膨胀 3x);`terraform plan` 的 drift 检测需要 SSOT 假设
- **机会**:`alicloud-topo-discovery` 已有 read-only 扫描器、跨产品聚合、JSON 输出——天然适合"按需生成 + 周期 baseline + 双快照 diff"的 Reverse-engineered IaC 模式

### 1.3 Goals
1. 提供按需 HCL 导出能力,让"设计意图存档"成本接近 0
2. 提供周期 baseline 存档 + 双快照 diff,实现"事后审计式"drift 检测
3. 严格保持 read-only 红线,绝不调用 `terraform apply` 或任何写操作
4. 不破坏现有 scan-topo 行为,向下兼容

### 1.4 Non-Goals
- 不做"真 IaC"(`terraform apply` 由用户/Pulumi/CDK 接手)
- 不做实时事件驱动 drift 检测(周期 baseline 足够)
- 不做模块市场、TF Registry、内部 artifact 分发
- 不替代各 product skill 的 `Describe*` API(本 skill 是聚合层,不是新的产品客户端)

---

## 2. Decisions Locked (用户确认)

| # | 决策 | 选择 | 影响 |
|---|------|------|------|
| Q1 | MVP 资源类型覆盖 | **Top-18** | 完整覆盖,但工作量 +50% |
| Q2 | Cross-account | **需要,加 STS AssumeRole** | 多账号企业场景 |
| Q3 | Baseline 存储后端 | **三种都支持(local/Git/OSS),--backend 切换** | 最灵活,+1 周 |
| Q4 | 实施优先级 | **MVP 优先** | v1.0 = scan-topo + export-hcl + baseline;v1.1 = diff + blueprint |

### 2.5 Decisions Locked in Final Review(第二轮用户确认)

| # | 决策 | 选择 | 影响 |
|---|------|------|------|
| OQ-1 | git backend 存放结构 | **子路径** `baselines/YYYY-MM-DD/` | 跟业务代码同 repo 共存;CI commit path 固定 |
| OQ-2 | oss backend 加密 | **不支持**(仅依赖 bucket 自身策略) | 文档明确警告 bucket policy 必须配置 |
| OQ-3 | GCL 集成时机 | **v1.0 必须**(与项目 §12 一致) | W10 milestone 强制包含 GCL 评审 |
| OQ-4 | 文档长度 & 工期 | **满意,直接进入 writing-plans** | 529 行 spec 保持现状;12-14 周工期确认 |

### 2.1 重新评估的工期(诚实披露)

原 Top-18 估算 6-8 周;加入 cross-account 和 3 backend 后:

| 版本 | 范围 | 工期 |
|------|------|------|
| **v1.0 (MVP)** | scan-topo(保留) + export-hcl + baseline + cross-account STS + 3 backends + Top-18 资源 | **8-10 周** |
| **v1.1** | baseline-diff + export-blueprint + 3 个 blueprint 模板 | **3-4 周** |
| **总计** | | **~12-14 周** |

比原始 6-8 周估算**超出约 60-70%**。建议团队评估是否:
- 砍 v1.0 资源到 Top-10(回到 6-8 周)
- 或接受 12-14 周(完成度更高)

---

## 3. v1.0 Scope (MVP)

### 3.1 scan-topo(现有,无功能变更)

| 项 | 状态 |
|------|------|
| 行为 | 不变 |
| 增强 | 支持 `--assume-role` 参数(为后续 export-hcl 复用) |
| 文件 | `SKILL.md` §Execution Flows / `references/execution-commands.md` 增量更新 |

### 3.2 export-hcl(新)

#### 3.2.1 CLI 接口
```bash
aliyun-topo-discovery export-hcl \
  --scope {vpc-xxx | all} \
  --output-dir ./hcl-export/ \
  [--assume-role arn:acs:ram::1234:role/TopologyReader] \
  [--provider-version 1.220.0] \
  [--include-types vpc,vswitch,slb,ecs,rds] \
  [--exclude-types ack,nat] \
  [--dry-run]
```

#### 3.2.2 资源类型覆盖(Top-18)

| # | 资源类型 | 主要 API | HCL Resource | 备注 |
|---|----------|----------|--------------|------|
| 1 | VPC | `vpc DescribeVpcs` | `alicloud_vpc` | |
| 2 | VSwitch | `vpc DescribeVSwitches` | `alicloud_vswitch` | |
| 3 | SLB | `slb DescribeLoadBalancers` | `alicloud_slb` | 含 `alicloud_slb_listener` |
| 4 | EIP | `vpc DescribeEipAddresses` | `alicloud_eip` | |
| 5 | NAT Gateway | `vpc DescribeNatGateways` | `alicloud_nat_gateway` | |
| 6 | ECS | `ecs DescribeInstances` | `alicloud_instance` | 含 `alicloud_disk` |
| 7 | SecurityGroup | `ecs DescribeSecurityGroups` | `alicloud_security_group` | + rules |
| 8 | RDS | `rds DescribeDBInstances` | `alicloud_db_instance` | |
| 9 | ACK | `cs DescribeClustersV1` | `alicloud_cs_kubernetes` | |
| 10 | RAM Role | `ram ListRoles` | `alicloud_ram_role` | |
| 11 | PolarDB | `polardb DescribeDBClusters` | `alicloud_polardb_cluster` | |
| 12 | Redis | `kvstore DescribeInstances` | `alicloud_redis_instance` | |
| 13 | OSS | `oss GetBucketInfo` | `alicloud_oss_bucket` | |
| 14 | KMS | `kms ListKeys` | `alicloud_kms_key` | |
| 15 | ActionTrail | `actiontrail DescribeTrails` | `alicloud_actiontrail` | |
| 16 | NAS | `nas DescribeFileSystems` | `alicloud_nas_file_system` | |
| 17 | FC | `fc ListServices` + `fc ListFunctions` | `alicloud_fc_service` + `alicloud_fc_function` | |
| 18 | VPN / SAG | `vpc DescribeVpnConnections` + `smartag DescribeSmartAccessGateways` | `alicloud_vpn_connection` + `alicloud_sag` | 合并 |

#### 3.2.3 输出文件结构
```
{output-dir}/
├── provider.tf           # Provider 锁版本
├── variables.tf          # 变量定义(region, name prefix, tags)
├── main.tf               # 所有 resource 块
├── outputs.tf            # 关键 ID 输出
├── terraform.tfstate     # 导入用状态(供 `terraform import` 消费)
├── import.sh             # 一键 import 脚本(可选执行)
├── unsupported.tf        # 不支持的资源类型(可删除)
└── manifest.json         # 元数据
```

#### 3.2.4 manifest.json Schema
```json
{
  "schema_version": "1.0",
  "generator": "alicloud-topo-discovery",
  "generator_version": "1.0.0",
  "generated_at": "2026-06-04T15:00:00Z",
  "account_id": "1234567890",
  "account_alias": "prod-finance",
  "role_arn": "arn:acs:ram::1234:role/TopologyReader",
  "region": "cn-hangzhou",
  "scope": "vpc-xxx",
  "provider_version": "1.220.0",
  "resource_count": 47,
  "by_type": {"vpc": 1, "vswitch": 3, "ecs": 12, "rds": 2, ...},
  "sensitive_masked": ["rds.password", "ram.access_key"],
  "unsupported_types": ["fc.function_code"],
  "import_ids_stable": true,
  "execution_time_ms": 12345
}
```

#### 3.2.5 敏感字段处理(必须)

| 字段 | 处理方式 |
|------|----------|
| `RDS.AccountPassword` | `password = var.rds_password` + `sensitive = true` |
| `RAM.AccessKey` | 不输出,只在 import.sh 注释中提示 |
| `KMS.OriginMaterial` | 输出 `sensitive = true` |
| `ECS.Password` (如有) | 变量化 + sensitive |
| `ActionTrail.OssBucketName` | 输出(非密钥) |
| `FC.FunctionCode` (二进制) | `filebase64` 引用 + sensitive |

**实现位置**:`scripts/lib/sensitive-masker.py` + `scripts/field-mappings/*.md` 的 `sensitive_fields` 列表

#### 3.2.6 Provider 版本策略
- 默认:Lock 到执行时 Aliyun Provider 最新稳定版(从 Registry API 获取)
- 覆盖:`--provider-version 1.220.0` 显式指定
- 升级检测:CI 中跑 `export-hcl --dry-run` 时,如 provider > 30 天未更新,WARNING 提示
- 升级流程:团队评审 changelog → 更新版本号 → 重跑 export-hcl → diff 检查 HCL 兼容性

#### 3.2.7 ID 稳定性保证
- resource block 名:`{type}_{slug(name)}` (e.g. `alicloud_vswitch_vswitch_prod_web_a`)
- import ID:遵循 Aliyu Provider 官方格式(`vpc:REGION:VPC_ID` 等)
- 同一资源二次导出 HCL diff 必须**仅**时间戳不同
- 测试用例:AC-2(见 §9)

#### 3.2.8 依赖图推断

```python
# scripts/lib/dependency-inference.py
def infer_dependencies(resources):
    # 显式依赖:VPC ID 字段、SG ID 字段、Subnet ID 字段
    # 隐式依赖:tag、name pattern、ARN 前缀
    # 输出:HCL `depends_on` 列表(罕见,主要靠 Terraform 自动推断)
    pass
```

### 3.3 baseline(新)

#### 3.3.1 CLI 接口
```bash
# 单次运行
aliyun-topo-discovery baseline \
  --output-dir ./infra-baseline/ \
  [--date 2026-06-04] \
  [--assume-role arn:...] \
  [--backend {local|git|oss}]

# CI/CD 调度(默认今天)
aliyun-topo-discovery baseline --backend git
```

#### 3.3.2 输出结构
```
{output-dir}/{YYYY-MM-DD}/
├── {完整 export-hcl 输出}
├── manifest.json(同 §3.2.4)
└── summary.txt(人类可读摘要)
{output-dir}/CHANGELOG.md(自动维护)
```

#### 3.3.3 三种 Backend

| Backend | 适用 | 配置项 | 失败行为 |
|---------|------|--------|----------|
| `local`(默认) | 个人/小团队 | `--output-dir` | 直接写本地 |
| `git` | 中小团队,需 PR 审计 | `--git-repo`, `--git-branch`, `--git-path`(默认 `baselines/`),`--git-user`, `--git-email` | 每次 commit 到 `baselines/YYYY-MM-DD/` 子路径;自动 commit + push;push 失败 → fallback 到 local + 报警 |
| `oss` | 大账号/合规 | `--oss-bucket`, `--oss-prefix`(默认 `topo-baseline/`), `--oss-access-key`(可选,默认用主凭证) | multipart upload;失败 → 重试 3 次 → 报警;**⚠️ 不做 ServerSide 加密,仅依赖 bucket policy —— 用户必须自行配置** |

#### 3.3.4 保留策略
- 默认 90 天
- `--retention-days N` 可配
- 过期:标记 `.expired` 后缀(不删除,留给用户决定)
- 提供 `baseline-prune` 子命令做手动清理

#### 3.3.5 CI/CD 模板
- `.github/workflows/topology-baseline.yml`(GitHub Actions)
- `.gitlab-ci.yml` 片段(GitLab)
- `Jenkinsfile` 片段(Jenkins)
- **核心**:`cron: 0 2 * * *`(凌晨 2 点)+ 每次 prod 部署后 webhook 触发

### 3.4 Cross-Account STS AssumeRole

#### 3.4.1 触发场景
- 资源中心账号(汇总所有业务账号拓扑)
- 财务托管账号(读取所有账号账单相关资源)
- 日志审计账号(读取所有账号配置)

#### 3.4.2 工作流
```
1. 用户配置 `~/.aliyun/config.json`:
   {
     "role_arn": "arn:acs:ram::1234:role/TopologyReader",
     "session_name": "topo-discovery",
     "duration_seconds": 3600
   }

2. Skill 检测到 --assume-role 参数:
   a. 调 sts AssumeRole 获取临时凭证
   b. 用临时凭证 export AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN
   c. 跑 export-hcl/baseline
   d. 凭证用完即弃,不入 manifest

3. 目标账号要求:
   - 角色需有 `AliyunReadOnlyAccess` 策略
   - 信任策略包含源账号的 `sub` 或 `roles`
```

#### 3.4.3 安全约束
- 临时凭证永不入 manifest / 日志 / 输出文件
- 凭证在脚本内存中用完即弃
- 失败 HALT,绝不带主账号凭证"兜底"——多账号场景必须有 AssumeRole 角色

#### 3.4.4 相关文件
- `scripts/sts-helper.sh`(AssumeRole wrapper)
- `references/cross-account-sts.md`(详细配置 + 故障排查)
- `references/safety-gate.md` 增量:多账号凭证安全规则

---

## 4. v1.1 Scope

### 4.1 baseline-diff(新)

#### CLI 接口
```bash
aliyun-topo-discovery baseline-diff \
  --from 2026-06-04 \
  --to 2026-06-11 \
  [--filter resource_type=vpc] \
  [--filter region=cn-hangzhou] \
  [--output report.md|json] \
  [--offline --from ./baselineA/ --to ./baselineB/]
```

#### 输出结构(Markdown)
```markdown
# Drift Report: 2026-06-04 → 2026-06-11

**Account**: 1234567890 (prod-finance)
**Region**: cn-hangzhou
**Generator**: alicloud-topo-discovery v1.0.0

## Summary
- 资源增加: 3
- 资源删除: 1
- 资源修改: 5
- 风险评级: **High**(删除 + 安全组规则变更)

## 🔴 High Risk Changes
### [DELETE] alicloud_instance.i-xxx (ECS, i-xxx)
- Previous config: instance_type=ecs.g6.large
- Detected at: 2026-06-08 14:23 UTC
- CloudTrail event: [link](...)
- ⚠️ 请确认是否经审批

### [MODIFY] alicloud_security_group.sg_web (SecurityGroup, sg-xxx)
- Rule added: ingress 22/0.0.0.0/0
- Detected at: 2026-06-10 09:15 UTC
- CloudTrail event: [link](...)
- ⚠️ SSH 全开,合规风险

## 🟡 Medium Risk Changes
...
## 🟢 Low Risk Changes
...
```

#### 风险评级规则
| 操作 | 评级 |
|------|------|
| 任何资源删除 | High |
| 安全组规则变更(尤其入方向) | High |
| 计费相关变更(实例规格、磁盘) | High |
| 资源 tag 变更 | Low |
| 资源增加 | Medium |
| 资源描述/name 变更 | Low |

#### CloudTrail 集成
- 改动时间窗内自动查询 CloudTrail
- 失败时输出 `CloudTrail query failed, please manually correlate`
- 不强依赖,优雅降级

### 4.2 export-blueprint(新)

#### CLI 接口
```bash
aliyun-topo-discovery export-blueprint \
  --source vpc-xxx \
  --target-region cn-beijing \
  --vars-file vars.yaml \
  --template standard-3tier
```

#### vars.yaml 格式
```yaml
name_prefix: "prod-dr"
environment: "dr"
region: "cn-beijing"
vpc_cidr: "10.20.0.0/16"
az_mapping:
  cn-hangzhou-a: cn-beijing-a
  cn-hangzhou-b: cn-beijing-b
tags:
  Environment: dr
  ManagedBy: topo-discovery
```

#### 输出
```
{output-dir}/
├── main.tf(变量化,可移植)
├── variables.tf
├── terraform.tfvars.example
└── import.sh
```

#### 起步模板
| 模板 | 包含 | 适用 |
|------|------|------|
| `standard-3tier` | VPC + 3 VSwitch(public/app/db)+ ALB + 2 ECS + RDS | Web 应用 |
| `web-stack` | VPC + 2 VSwitch + ALB + N ECS + Redis | 轻量 Web |
| `data-stack` | VPC + 2 VSwitch + EMR + OSS + DataWorks | 数据平台 |

---

## 5. Cross-Cutting NFR

| 维度 | 要求 |
|------|------|
| **Token 经济性** | SKILL.md 主章节只列子模式入口;详细命令/字段映射放 references/ |
| **敏感数据** | 输出文件 grep `LTAI\|AKIA\|wJalr` 必须 0 命中;AC-1 |
| **Provider 版本** | Lock + 30 天升级警告 |
| **ID 稳定性** | 二次导出 byte-for-byte 一致(除时间戳);AC-2 |
| **可重入** | baseline 目录二次跑幂等(覆盖式) |
| **错误处理** | 部分资源失败 → `unsupported.tf` + manifest 报告;不阻塞整体 |
| **GCL 集成** | 4 个子模式全部走 GCL §12 双 Agent 评审 |
| **可观测** | 所有子模式输出 manifest.json |
| **依赖** | 不依赖其他 skill 写操作;只调 `Describe*` |
| **Python 版本** | 3.10+(与项目一致) |
| **测试覆盖** | pytest 单元测试 ≥ 80%;集成测试用 mock aliyun CLI |

---

## 6. Out of Scope (明确边界)

| 不做 | 理由 |
|------|------|
| ❌ `terraform apply` 自动执行 | 违反 read-only 红线 |
| ❌ Terraform State 文件修改 | skill 只读生成 |
| ❌ 从零编写 HCL 模块脚手架 | 那是 IDE / `terraform scaffold` |
| ❌ 模块市场 / 版本分发 | 那是 TF Registry / 内部 artifact repo |
| ❌ 实时事件驱动 drift 检测 | 周期 baseline 足够 |
| ❌ 给每个 product skill 加 TF 章节 | 破坏 Single Responsibility |
| ❌ 删除资源 / 回滚 | skill 永远不修改云资源 |
| ❌ 跨账号 RAM 策略自动配置 | 安全风险,需人工 |
| ❌ 复杂多区域 multi-cloud | 单一阿里云、不做 AWS/Azure 兼容 |

---

## 7. File Structure(预期)

```
alicloud-topo-discovery/
├── SKILL.md                                  # 更新:4 个子模式入口
├── references/
│   ├── safety-gate.md                       # 现有,扩展 STS 规则
│   ├── execution-commands.md                # 现有,加 cross-account
│   ├── hcl-export.md                        # NEW: HCL 引擎设计、字段映射
│   ├── baseline-management.md               # NEW: 3 backend、保留策略
│   ├── cross-account-sts.md                 # NEW: AssumeRole 详细配置
│   ├── diff-report.md                       # NEW(v1.1): diff 报告规则
│   ├── blueprint-templates.md               # NEW(v1.1): 3 个模板说明
│   └── field-mappings/                      # NEW: 18 个资源类型
│       ├── vpc.md
│       ├── vswitch.md
│       ├── slb.md
│       ├── ecs.md
│       ├── ... (18 个)
├── assets/
│   ├── eval_queries.json                    # 现有或新
│   └── ci-cd-templates/                     # NEW: GitHub Actions / GitLab CI
├── scripts/
│   ├── topo-scan.sh                         # 现有,加 --assume-role
│   ├── topo-render.py                       # 现有
│   ├── export-hcl.py                        # NEW: HCL 生成器入口
│   ├── baseline-manager.py                  # NEW: 3 backend
│   ├── baseline-diff.py                     # NEW(v1.1)
│   ├── export-blueprint.py                  # NEW(v1.1)
│   ├── sts-helper.sh                        # NEW: AssumeRole wrapper
│   └── lib/
│       ├── field-mapper.py                  # NEW: JSON → HCL 核心
│       ├── sensitive-masker.py              # NEW: 字段脱敏
│       ├── provider-locker.py               # NEW: 版本管理
│       ├── dependency-inference.py          # NEW: 关系推断
│       ├── baseline-local.py                # NEW: local backend
│       ├── baseline-git.py                  # NEW: git backend
│       └── baseline-oss.py                  # NEW: oss backend
└── templates/
    ├── vpc-topology.md                      # 现有
    ├── hcl-header.md                        # NEW: HCL 文件头模板
    ├── baseline-manifest.json               # NEW: manifest schema
    ├── diff-report.md                       # NEW(v1.1)
    └── blueprints/                          # NEW(v1.1)
        ├── standard-3tier/
        ├── web-stack/
        └── data-stack/
```

---

## 8. Risks & Open Questions

| # | Risk | 概率 | 影响 | Mitigation |
|---|------|------|------|------------|
| R1 | Top-18 资源字段映射工作量低估 | 中 | 高 | 已加 buffer 8-10 周;每周 review |
| R2 | ID 稳定性难以保证(资源 name 变化会导致 block 名变化) | 中 | 中 | block 名加 hash 后缀,二次导出 block 名稳定 |
| R3 | Cross-account AssumeRole 失败模式多(角色不存在/无权限/时间漂移) | 中 | 中 | 详细故障排查文档 + 友好错误信息 |
| R4 | Git backend 推送失败(冲突/无权限) | 中 | 中 | 显式提示,fallback 到 local |
| R5 | Provider 升级导致 HCL 兼容性破坏 | 低 | 中 | 升级前 changelog review + 旧版本 export 保留 |
| R6 | 大账号 export 性能(>1000 资源) | 中 | 中 | 并行 API + 流式生成 + progress 报告 |
| R7 | `terraform.tfstate` 含敏感字段泄漏 | 低 | 高 | state 文件加 `.gitignore` 提示 + 文档警告 |

### 8.1 Open Questions(已决,见 §2.5)

| # | Question | 决策 | 状态 |
|---|----------|------|------|
| OQ-1 | git backend 存放结构 | 子路径 `baselines/YYYY-MM-DD/` | ✅ Locked(§2.5) |
| OQ-2 | oss backend ServerSide 加密 | 不支持,依赖 bucket policy | ✅ Locked(§2.5) |
| OQ-3 | GCL 集成时机 | v1.0 必须 | ✅ Locked(§2.5) |
| OQ-4 | 文档长度 & 工期 | 满意,直接 writing-plans | ✅ Locked(§2.5) |

---

## 9. Acceptance Criteria

| # | 验收项 | 测试方法 |
|---|--------|----------|
| AC-1 | `export-hcl --scope vpc-xxx` 产出 8 个文件,无明文敏感信息 | `ls` + `grep -E 'LTAI\|AKIA\|wJalr\|SECRET'` 必须 0 命中 |
| AC-2 | 同一 VPC 二次 export 产出 HCL diff 仅 manifest.json 时间戳不同 | `diff -r` 校验 |
| AC-3 | `baseline --backend git` 在 CI 中自动 commit 到 git repo | GitHub Actions 实测 |
| AC-4 | `baseline --backend oss` 成功上传到指定 bucket | OSS 控制台 + 集成测试 |
| AC-5 | `--assume-role` 成功跨账号 export,manifest 含 source account | 多账号 fixture |
| AC-6 | 18 类资源全部支持 export,字段映射准确 | 字段映射单测 + 集成测试 |
| AC-7 | 所有子模式不调用任何写操作 | 静态扫描命令白名单 |
| AC-8 | baseline-diff 准确识别增/删/改(v1.1) | 模拟新增/删除/修改 ECS 跑 diff |
| AC-9 | export-blueprint 输出可移植 HCL(v1.1) | apply 演练(只读账号) |
| AC-10 | 端到端性能:Top-18 资源 scan + export 在 5 分钟内完成 | 性能 benchmark |
| AC-11 | 4 个子模式各跑 1 轮 GCL 评审,rubric 全部 ≥ 0.5 | GCL §12 流程 |
| AC-12 | pytest 单元测试覆盖率 ≥ 80% | coverage report |
| AC-13 | 文档:`references/hcl-export.md`、`baseline-management.md`、`cross-account-sts.md` 全部完成 | 文档 review |

---

## 10. Implementation Milestones(v1.0)

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| W1 | STS + cross-account 基础设施 | `sts-helper.sh`、`references/cross-account-sts.md`、scan-topo 集成 |
| W2-3 | HCL 引擎核心 | `field-mapper.py`、`sensitive-masker.py`、`provider-locker.py` |
| W4-6 | 18 资源类型字段映射 | `field-mappings/*.md` × 18 + 单测 |
| W7 | export-hcl CLI + 输出验证 | `export-hcl.py` + AC-1/AC-2 通过 |
| W8 | baseline 3 backends | `baseline-manager.py` + `baseline-{local,git,oss}.py` |
| W9 | CI/CD 模板 + manifest schema | `.github/workflows/` + manifest 验证 |
| W10 | GCL 集成 + 全量测试 + 文档 | GCL 评审通过、AC-1 ~ AC-13 通过 |

---

## 11. References

- `AGENTS.md` §1-11:项目总规、Quality Gate、Well-Architected
- `AGENTS.md` §12:Generator-Critic-Loop 框架
- `alicloud-skill-generator/SKILL.md`:Meta-skill 规范
- `alicloud-skill-generator/references/governance-and-adversarial-review.md`:合并前审查
- 前置对话:本 spec 来自 5 轮关于 TF 在 skill 生态中角色的讨论

---

**Spec 自检清单(自审)**:
- [x] 无 TBD/TODO 占位
- [x] 内部一致:v1.0/v1.1 边界清晰,out-of-scope 与 goals 一致
- [x] 范围适中:可由单一实施计划承载
- [x] 歧义消除:每条规格有明确测试方法
- [x] 风险诚实:不回避工期超出(6-8 → 12-14 周)

**待用户审查后**:
- 写入 git(单独 commit)
- 启动 `writing-plans` skill 生成实施计划
