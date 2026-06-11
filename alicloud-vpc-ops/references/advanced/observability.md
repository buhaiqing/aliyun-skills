# VPC/EIP/NAT Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for VPC, EIP, and NAT networking resources.

## Metrics → Logs 联动

| CMS 指标异常 | 日志查询目标 | 目的 |
|-------------|-------------|------|
| NAT `OutRatePercent` > 85% | VPC FlowLog + 应用访问日志 | 确认哪些内部服务产生大量出站流量 |
| EIP `DropPacketTX` 上升 | 安全组/NACL 日志 | 确认被丢弃包的目标地址和原因（ACL deny vs 带宽限制） |
| EIP `DropPacketBlackHole` > 0 | DDoS 防护日志 + 入流量日志 | 确认 DDoS 攻击源 IP 和流量特征 |
| NAT `DropConnection` 上升 | NAT Gateway 日志 + 后端连接日志 | 确认哪些连接被丢弃及原因（连接数限制 vs 超时） |
| VPC `DropConnection` 上升 | FlowLog 中 `action=REJECT` 的条目 | 确认哪些流量被安全组/NACL 拒绝 |

### FlowLog 查询示例

```bash
# 查询 VPC FlowLog 中被拒绝的流量
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "vpc-flowlog" \
  --query "action = REJECT | SELECT src_ip, dst_ip, dst_port, protocol, count(\*) group by src_ip, dst_ip, dst_port, protocol"
```

## Metrics → Traces 联动

网络层通常不直接产生 Trace，但网络异常会间接影响 Trace：

| 网络指标异常 | Trace 影响 | 目的 |
|-------------|-----------|------|
| NAT/EIP 延迟增加 | 应用 Trace 中 `http.client` span 延迟增加 | 区分是网络问题还是应用问题 |
| SLB→NAT→ECS 链路异常 | 全链路 Trace 中的超时环节 | 定位具体是哪个环节阻塞了请求 |

## 降级策略

若 SLS/FlowLog 不可用：
1. 直接检查安全组/NACL 规则
2. 使用 `ping`/`telnet`/`curl` 从不同位置测试连通性
3. 检查 ECS 实例 `iptables` 和本地防火墙规则
4. 检查 VPC 路由表配置
