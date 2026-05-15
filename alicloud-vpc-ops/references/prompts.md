# VPC Operations — Prompts Handbook

> **Purpose:** 30+ categorized prompt examples for VPC operations.

## VPC 生命周期类

1. "创建 VPC，网段 192.168.0.0/16"
2. "查看当前有多少个 VPC"
3. "删除 VPC vpc-xxx，先确认依赖"
4. "列出所有可用区"

## 交换机管理

5. "在 VPC 里创建交换机"
6. "查看 VPC 里有多少个交换机"
7. "删除交换机 vsw-xxx"

## NAT 网关

8. "创建增强型 NAT 网关"
9. "查看 NAT 网关详情"
10. "删除 NAT 网关"

## SNAT/DNAT

11. "给 NAT 配置 SNAT，让 10.0.1.0/24 能上网"
12. "配置 DNAT，把公网 8080 映射到内网 80"
13. "查看 SNAT 条目"
14. "删除 DNAT 映射"

## EIP 操作

15. "申请弹性公网 IP"
16. "绑定 EIP 到 ECS"
17. "解绑 EIP"
18. "释放 EIP"
19. "修改 EIP 带宽"

## VPN 与 IPsec

20. "创建 VPN 网关"
21. "查看 VPN 网关状态"

## 网络 ACL

22. "创建网络 ACL"
23. "关联 ACL 到 vSwitch"

## 网络诊断

24. "查看 VPC 的路由表"
25. "检查这个 VPC 下有多少资源"
26. "帮我看看 SNAT 是否配置正确"

## 多指标关联巡检

27. "执行 NAT 多指标巡检"
28. "检查 EIP 是否有异常模式"
29. "查看当前 NAT 连接池使用情况"

## 告警诊断

30. "收到 NAT 带宽告警，帮我诊断"
31. "EIP 流量突降了，帮我排查原因"
32. "网络不通了，帮我从 VPC 层面诊断"

## 完整网络打通

33. "帮我从零创建一套网络：VPC + 交换机 + NAT + SNAT"
34. "清理整个 VPC 环境"
