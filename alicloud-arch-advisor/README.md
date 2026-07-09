# alicloud-arch-advisor

> 阿里云架构顾问 - 三模式架构分析、WAF 评估、方案推荐

[![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Bash](https://img.shields.io/badge/bash-3.2%2B-orange.svg)](https://www.gnu.org/software/bash/)
[![Tests](https://img.shields.io/badge/tests-31%20passed-brightgreen.svg)](tests/)

---

## 🌟 核心特性

- **🎯 三种工作模式**: 架构分析 (A)、WAF 评估 (B)、方案推荐 (C)
- **🌍 多语言支持**: 中英文界面切换 (`ARCH_ADVISOR_LANG`)
- **📊 高级进度条**: 嵌套、持久化、图形化 (iTerm2/TrueColor)
- **🛡️ 安全加固**: 修复命令注入漏洞,添加超时控制
- **💰 成本感知**: 规格感知的成本估算
- **🧪 单元测试**: 31 个测试用例,100% 通过率
- **🎨 交互式向导**: 零记忆成本的引导式操作

---

## 🚀 快速开始

### 一行启动

```bash
./scripts/interactive-wizard.sh
```

### 手动命令

```bash
# 模式 A: 分析现有架构
./scripts/assess.sh --reverse-eng true --region cn-hangzhou

# 模式 B: WAF 评估
./scripts/assess.sh --reverse-eng false --pillars security,reliability

# 模式 C: 架构推荐
./scripts/recommend.sh --scenario ecommerce --dau 100000 --budget 5000
```

### 切换语言

```bash
export ARCH_ADVISOR_LANG=en_US   # English
export ARCH_ADVISOR_LANG=zh_CN   # Chinese (default)
```

---

## 📦 工作模式

### Mode A: 架构逆向与分析
- 自动识别架构模式 (single-node, 3-tier, microservice, serverless, multi-region)
- 生成 Mermaid 拓扑图
- 输出架构文档 (Markdown)
- 资源清单 (JSON)

### Mode B: WAF 成熟度评估
基于阿里云 Well-Architected Framework 的**五支柱**评估:
1. **Security** (安全)
2. **Reliability** (可靠性)
3. **Performance** (性能)
4. **Cost** (成本)
5. **Efficiency** (效率)

输出: 评分卡 + 风险清单 + 改进建议

### Mode C: 架构方案推荐
**支持的场景**:
- 🛒 E-commerce (电商)
- 💼 SaaS Application
- 📊 Data Platform (数据平台)
- 🏗️ Microservice (微服务)
- ⚡ Serverless
- 🎮 Game Backend (游戏后端)

**输入**: 业务场景 + DAU + HA 等级 + 合规要求 + 预算
**输出**: 架构蓝图 + 组件清单 + 成本估算 + 实施步骤

---

## 📚 文档导航

| 文档 | 用途 |
|------|------|
| [USAGE.md](USAGE.md) | 📖 详细使用手册 (命令行、API、示例) |
| [CHANGELOG.md](CHANGELOG.md) | 📋 版本变更日志 |
| [OPTIMIZATION_REVIEW.md](OPTIMIZATION_REVIEW.md) | 🔍 优化复盘 (三轮反思分析) |
| [CODE_REVIEW_FIXES.md](CODE_REVIEW_FIXES.md) | 🛠️ 代码审查问题修复 |

---

## 🧪 测试

```bash
# 单元测试 (31 个用例)
./tests/test-core-functions.sh

# 进度条功能测试
./scripts/test-progress-advanced.sh

# 修复验证
./scripts/verify-fixes-simple.sh
```

**测试覆盖**:
- ✅ Cost Estimation (5)
- ✅ Progress Bar (5)
- ✅ Error Classification (6)
- ✅ Error Description (5)
- ✅ Terminal Detection (2)
- ✅ Input Validation (5)
- ✅ Architecture Patterns (3)

---

## 🏗️ 架构

```
alicloud-arch-advisor/
├── SKILL.md                    # 入口文档
├── README.md                   # 项目概览 (本文件)
├── USAGE.md                    # 使用手册
├── CHANGELOG.md                # 变更日志
├── OPTIMIZATION_REVIEW.md      # 优化复盘
├── CODE_REVIEW_FIXES.md        # 审查修复
│
├── scripts/                    # 核心脚本
│   ├── common.sh              # 共享工具 (日志、进度、错误)
│   ├── assess.sh              # 模式 A + B
│   ├── recommend.sh           # 模式 C
│   ├── interactive-wizard.sh  # 交互式向导
│   ├── i18n.sh                # 多语言
│   ├── error-handler.sh       # 错误处理
│   ├── test-framework.sh      # 测试框架
│   ├── test-progress.sh       # 进度条测试
│   ├── test-progress-advanced.sh  # 高级进度条测试
│   └── verify-fixes-simple.sh # 修复验证
│
├── references/                 # 参考文档
│   ├── core-concepts.md
│   ├── well-architected-assessment.md
│   ├── integration.md
│   ├── troubleshooting.md
│   ├── prompt-templates.md
│   ├── rubric.md
│   ├── rules/                  # WAF 规则
│   └── scenario-templates/     # 场景模板
│       ├── ecommerce.md
│       ├── saas.md
│       ├── data-platform.md
│       ├── microservice.md
│       ├── serverless.md
│       ├── game.md
│       └── index.yaml
│
├── assets/                     # 资源
│   ├── example-config.yaml
│   └── eval_queries.json
│
├── tests/                      # 单元测试
│   └── test-core-functions.sh
│
└── output/                     # 运行时输出 (gitignored)
    ├── report-data.json
    └── recommendation-blueprint.json
```

---

## 🔧 技术栈

- **Shell**: Bash 3.2+ (兼容 macOS 默认版本)
- **依赖**: `aliyun` CLI, `jq`, `bc`
- **可选**: `tput` (终端能力检测)
- **GCL 集成**: optional, max_iter=5

---

## 📊 性能指标

| 指标 | 数值 |
|------|-----:|
| Token Budget (SKILL.md) | ~5000 tokens |
| 单元测试通过率 | 100% (31/31) |
| 支持地域 | 30+ |
| 业务场景模板 | 6 |
| 错误处理类型 | 12 |
| 进度条特性 | 11 API |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

### 开发流程
1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 运行测试 (`./tests/test-core-functions.sh`)
4. 提交更改 (`git commit -m 'Add amazing feature'`)
5. 推送分支 (`git push origin feature/amazing-feature`)
6. 创建 Pull Request

### 代码规范
- 遵循 [AGENTS.md](../AGENTS.md) 规范
- 所有新功能必须有单元测试
- 更新 CHANGELOG.md
- Token 预算控制

---

## 📜 许可证

Apache 2.0

---

## 🔗 相关项目

- [alicloud-skill-generator](../alicloud-skill-generator/) - Skill 生成器
- [alicloud-gcl-runner-ops](../alicloud-gcl-runner-ops/) - GCL 跨 Skill 运行器
- [alicloud-topo-discovery](../alicloud-topo-discovery/) - 拓扑发现
- [alicloud-advisor-ops](../alicloud-advisor-ops/) - 阿里云 Advisor
- [alicloud-cms-ops](../alicloud-cms-ops/) - 云监控

---

**最后更新**: 2026-06-11 | **版本**: 1.4.0 | **维护**: alicloud-arch-advisor 团队
