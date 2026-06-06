---
name: well-architected-assessment
version: "1.0.0"
parent: alicloud-aiops-cruise
---

# Well-Architected 五支柱评估

> GCL 评分时需要参考本文件。日常巡检不需要加载。

## 安全 (Security)

| 方面 | 指导 |
|---|---|
| **IAM** | 最小权限原则，巡检仅需各产品只读权限 + CloudAssistant 执行权限 |
| **Credential** | `{{env.*}}` ONLY，输出掩码 |
| **数据敏感** | 资源 ID、IP、配置是敏感基础设施数据，限报告分发范围 |

## 稳定 (Stability)

| 方面 | 指导 |
|---|---|
| **面向失败** | 单个 Analyzer 失败不影响其他 Analyzer，部分结果仍有价值 |
| **运维管控** | 定期巡检可追踪配置漂移和容量变化 |
| **应急恢复** | 故障 runbook 的决策树帮助快速定位根因 |

## 成本 (Cost)

Describe/List/Get 类 API 免费，仅 CloudAssistant RunCommand 消耗少量执行费用。

## 效率 (Efficiency)

- **并行采集**：CLI 命令可后台并发执行（`& PID` + `wait`）
- **渐进式深度**：标准模式仅 CloudMonitor + CLI；深度模式按需开启 DAS / CloudAssistant

## 性能 (Performance)

| 操作 | API 调用数 | 预估时间 |
|---|---|---|
| Phase 1 拓扑发现 | ~5-8 次 | < 1min |
| Phase 2 标准采集 | ~15-25 次 | 2-5min |
| Phase 2 深度模式 (+DAS/+CloudAssistant) | +5-10 次 | +3-8min |