# NAT Observability Integration

> **Purpose:** Metrics→Logs→Traces linkage for NAT Gateway resources.

## Metrics → Logs 联动

| CMS 指标异常 | FlowLog/SLS 查询目标 | 目的 |
|-------------|---------------------|------|
| `OutRatePercent` > 85% | VPC FlowLog 中 `src_ip IN (VPC CIDR) AND dst_ip NOT IN (VPC CIDR)` | 确认哪些内部 IP 产生了最多出站流量 |
| `InRatePercent` > 85% | VPC FlowLog 中 `dst_ip IN (VPC CIDR) AND src_ip NOT IN (VPC CIDR)` | 确认入流量来源和分布 |
| `DropConnection` 上升 | NAT Gateway 日志 + 安全组日志 | 确认被丢弃连接的原因（带宽限制 vs 连接限制 vs 安全组规则） |

### FlowLog 查询示例

```bash
# 查询 NAT Gateway 出站流量 Top 源
aliyun log GetLogs \
  --project "{{user.sls_project}}" \
  --logstore "vpc-flowlog" \
  --query "action = ACCEPT AND dst_ip NOT IN ('10.%', '172.16.%', '192.168.%') | SELECT src_ip, sum(bytes) as total_out_bytes group by src_ip order by total_out_bytes desc limit 20"
```

## Metrics → Traces 联动

| CMS 指标异常 | Trace 目标 | 目的 |
|-------------|-----------|------|
| NAT 延迟增加 | ARMS 应用 Trace 中的外部服务调用段 | 区分是 NAT 网络问题还是外部服务响应慢 |
| SNAT 失败率增加 | 应用侧网络错误 Trace | 定位是哪个应用的出口被阻断 |

## Metrics → DAS 联动

NAS (Not directly supported by DAS, use CMS + custom analysis)

| CMS 指标异常 | 分析能力 | 目的 |
|-------------|---------|------|
| NAT 连接耗尽 | CMS 自定义指标分析 (连接趋势/规格对比) | 预测何时达到连接上限 |
| 带宽饱和 | CMS 带宽趋势分析 | 预测何时需要升级带宽规格 |

## 降级策略

若 FlowLog 不可用：
1. 检查 NAT Gateway 绑定的 EIP 状态
2. 逐一检查 SNAT/DNAT 配置
3. 从 VPC 内部使用 `curl`/`wget` 测试外部连通性
4. 检查 VPC 路由表确保默认路由指向 NAT Gateway
