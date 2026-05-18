# NAT Operations — Prompts Handbook

> **Purpose:** 20+ categorized prompt examples for NAT operations.

## NAT 生命周期

1. "创建 NAT 网关"
2. "所有 NAT 网关"
3. "创建增强型 NAT"
4. "删除 NAT 网关"

## SNAT 操作

5. "配置 SNAT"
6. "删除 SNAT"
7. "查看 SNAT"
8. "用 SNAT 让内网能上网"

## DNAT 操作

9. "配置 DNAT 端口映射"
10. "DNAT 不通了"
11. "查看 DNAT 条目"
12. "删除 DNAT"

## 诊断/告警

13. "NAT 带宽满了，帮我诊断"
14. "SNAT 不工作了，排查原因"
15. "DNAT 端口映射不通"

## 多指标关联巡检

16. "执行 NAT 多指标异常巡检"
17. "检查 NAT 连接池使用情况"
18. "SNAT 容量快满了，帮我分析"

## 告警风暴处理

19. "NAT 网关同时多个告警，帮我聚合分析"
20. "找出 NAT 告警的根因"

## 级联诊断

21. "NAT 带宽饱和，帮我检查 EIP"
22. "DNAT 不通，排查后端 ECS"
23. "内网无法访问互联网，帮我排查 NAT 链路"

## FinOps 成本优化

24. "检查是否有闲置的 NAT 网关"
25. "分析 NAT 网关的成本，看看有没有优化空间"
26. "NAT 网关的计费模式应该选 PayBySpec 还是 PayByActualUsage？"
27. "帮我做 NAT 网关的规格右调（Right-Sizing）"
28. "检查 NAT 关联的 EIP 是否有浪费"
29. "生成 NAT 网关月度成本优化报告"
30. "NAT 网关成本突然涨了 30%，帮我排查原因"
31. "多个 EIP 绑在 NAT 上，是否应该用共享带宽包？"

## SecurityOps 安全审计

32. "审计所有 DNAT 条目，检查是否有高危端口暴露"
33. "检查 SNAT 的源 CIDR 是否过于宽泛"
34. "NAT 网关安全基线检查"
35. "有 DNAT 把 22 端口映射到公网了，帮我紧急处理"
36. "查看 NAT 网关的操作审计日志"
37. "帮我配置 NAT 网关的最小权限 RAM 策略"
38. "检查 NAT 网关的 DNAT 是否有对应的安全组规则"
39. "执行 NAT 网关安全巡检"
