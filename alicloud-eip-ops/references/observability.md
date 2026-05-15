# EIP Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for EIP resources.

## Metrics → Logs 联动

| CMS 指标异常 | SLS/FlowLog 查询目标 | 目的 |
|-------------|--------------------|------|
| `InternetIn` 突增 | VPC FlowLog 中 `dst_ip = EIP` 的流入条目 | 确认流量来源 IP 和协议分布 |
| `InternetOut` 突增 | VPC FlowLog 中 `src_ip = EIP` 的流出条目 | 确认出流量来源和目的地 |
| `DropPacketBlackHole` > 0 | DDoS 防护日志 + FlowLog 入流量 | 确认攻击源 IP、协议、流量大小 |
| `DropPacketTX` 上升 | 安全组日志 + NACL 日志 | 确认被丢弃包的原因（ACL deny / 安全组拒绝） |
| `ActiveConnection` 异常 | 应用侧连接日志 | 确认哪些客户端占用了最多连接 |

### FlowLog 查询示例

```bash
# 查询 EIP 流量分布
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "vpc-flowlog" \
  --query "src_ip = '{{user.eip_address}}' or dst_ip = '{{user.eip_address}}' | SELECT src_ip, dst_ip, protocol, sum(bytes) as total_bytes group by src_ip, dst_ip, protocol order by total_bytes desc limit 20"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| EIP 绑定目标响应延迟 | ARMS 入口 Trace（从 EIP 进入的请求链） | 区分是网络问题还是后端应用问题 |
| 流量异常但后端正常 | 网络层 Trace | 确认是否是中间网络设备（如 NAT/SLB）导致 |

## 降级策略

若 SLS/FlowLog 不可用：
1. 直接检查 EIP 绑定目标的安全组规则
2. 使用 `ping`/`curl` 测试 EIP 连通性
3. 检查 EIP 绑定目标（ECS/NAT/SLB）的状态和日志
4. 使用阿里云 DDoS 控制台查看黑洞状态
