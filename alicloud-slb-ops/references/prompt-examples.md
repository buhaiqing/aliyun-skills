# Prompt Examples — Alibaba Cloud SLB/CLB

> **Purpose:** This document provides ready-to-use prompt templates for common SLB operational scenarios. Copy-paste these prompts (or adapt them) when interacting with an AI agent equipped with the `alicloud-slb-ops` skill.

---

## How to Use This Guide

1. **Identify your scenario** from the categories below.
2. **Copy the prompt template** and fill in the `{{placeholders}}`.
3. **Send to the AI agent** — it will invoke the appropriate operations from `alicloud-slb-ops`.
4. Each prompt cross-references the relevant operation(s) in [SKILL.md](../SKILL.md) for advanced customization.

---

## 1. Instance Lifecycle Management

### 1.1 Create a Public SLB Instance

```
请帮我在 {{region}} 区域创建一个公网 SLB 实例：
- 实例名称：{{load_balancer_name}}
- 网络类型：VPC
- VPC ID：{{vpc_id}}
- VSwitch ID：{{vswitch_id}}
- 计费方式：{{internet_charge_type|paybytraffic}}
- 带宽上限：{{bandwidth|10}} Mbps
- 实例规格：{{load_balancer_spec|slb.s1.small}}

请返回实例 ID、分配的 IP 地址。
```

> **Related Operation:** [Create Load Balancer](../SKILL.md#operation-create-load-balancer)

**Example:**
```
请帮我在 cn-hangzhou 区域创建一个公网 SLB 实例：
- 实例名称：prod-web-slb
- 网络类型：VPC
- VPC ID：vpc-bp1xxxxxxxx
- VSwitch ID：vsw-bp1xxxxxxxx
- 计费方式：paybytraffic
- 带宽上限：100 Mbps
- 实例规格：slb.s2.medium

请返回实例 ID、分配的 IP 地址。
```

### 1.2 Create an Intranet SLB Instance

```
请帮我在 {{region}} 区域创建一个内网 SLB 实例：
- 实例名称：{{load_balancer_name}}
- VPC ID：{{vpc_id}}
- VSwitch ID：{{vswitch_id}}
- 实例规格：{{load_balancer_spec|slb.s1.small}}
```

> **Related Operation:** [Create Load Balancer](../SKILL.md#operation-create-load-balancer)

### 1.3 List All SLB Instances

```
请列出我在 {{region}} 区域的所有 SLB 实例，
包括：实例 ID、实例名称、状态、IP 地址、地址类型、规格、创建时间。
```

> **Related Operation:** [Describe Load Balancers](../SKILL.md#operation-describe-load-balancers)

### 1.4 Get SLB Instance Details

```
请查询 SLB 实例 {{load_balancer_id}} 的详细信息，包括：
- 实例状态
- IP 地址和地址类型
- 实例规格和带宽
- VPC / VSwitch 信息
- 监听器列表及端口
- 删除保护状态
- 修改保护状态
```

> **Related Operation:** [Describe Load Balancer Attribute](../SKILL.md#operation-describe-load-balancer-attribute)

### 1.5 Resize SLB Instance Spec

```
请将 SLB 实例 {{load_balancer_id}} 的规格从当前规格升级为 {{target_spec|slb.s3.medium}}。
注意：
- 变配会造成秒级连接中断
- 变配完成后请验证实例状态和新规格
```

> **Related Operation:** [Modify Load Balancer Instance Spec](../SKILL.md#operation-modify-load-balancer-instance-spec)

### 1.6 Enable Deletion Protection

```
请启用 SLB 实例 {{load_balancer_id}} 的删除保护功能，
防止误删除。
```

> **Related Operation:** [Set Load Balancer Status](../SKILL.md#operation-set-load-balancer-status)

### 1.7 Delete an SLB Instance

```
请帮我删除 SLB 实例 {{load_balancer_id}}。
注意：
- 此操作不可逆，删除后所有监听器和配置将被清除
- 请确认实例 ID 正确
- 如果开启了删除保护，请先关闭
- 删除后请验证实例已不存在
```

> **Related Operation:** [Delete Load Balancer](../SKILL.md#operation-delete-load-balancer)

---

## 2. Listener Management

### 2.1 Create TCP Listener (80 -> 8080)

```
请为 SLB 实例 {{load_balancer_id}} 创建一个 TCP 监听器：
- 监听端口：80
- 后端端口：8080
- 调度算法：wrr
- 健康检查：开启
- 健康检查端口：8080

创建完成后请验证监听器状态为 running。
```

> **Related Operation:** [Create TCP Listener](../SKILL.md#operation-create-tcp-listener)

### 2.2 Create HTTP Listener for Web Service

```
请为 SLB 实例 {{load_balancer_id}} 创建一个 HTTP 监听器：
- 监听端口：80
- 后端端口：8080
- 调度算法：wrr
- 健康检查：开启，检查路径 /health
- 开启 X-Forwarded-For

请返回监听器状态。
```

> **Related Operation:** [Create HTTP Listener](../SKILL.md#operation-create-http-listener)

### 2.3 Create HTTPS Listener with Certificate

```
请为 SLB 实例 {{load_balancer_id}} 创建一个 HTTPS 监听器：
- 监听端口：443
- 后端端口：8080
- 调度算法：wrr
- 服务器证书 ID：{{certificate_id}}
- 健康检查：开启，检查路径 /health
- 开启 X-Forwarded-For

请返回监听器状态。
```

> **Related Operation:** [Create HTTPS Listener](../SKILL.md#operation-create-https-listener)

### 2.4 Create UDP Listener

```
请为 SLB 实例 {{load_balancer_id}} 创建一个 UDP 监听器：
- 监听端口：514
- 后端端口：514
- 调度算法：wrr
- 健康检查：开启，检查端口 514
```

> **Related Operation:** [Create UDP Listener](../SKILL.md#operation-create-udp-listener)

### 2.5 Stop and Start a Listener (Maintenance)

```
请先停止 SLB 实例 {{load_balancer_id}} 的 80 端口监听器，
执行运维操作，
然后重新启动该监听器。
每个步骤完成后请验证状态。
```

> **Related Operations:** [Stop Listener](../SKILL.md#operation-stop-listener), [Start Listener](../SKILL.md#operation-start-listener)

### 2.6 Delete a Listener

```
请帮我删除 SLB 实例 {{load_balancer_id}} 上的 {{listener_port}} 端口监听器。
注意：删除后该端口将不再提供服务，请确认。
```

> **Related Operation:** [Delete Listener](../SKILL.md#operation-delete-listener)

---

## 3. VServer Group & Backend Server Management

### 3.1 Create VServer Group and Add Backends

```
请为 SLB 实例 {{load_balancer_id}} 创建一个 VServer Group：
- 组名称：{{group_name|web-backend}}
- 后端服务器：
  - 服务器 1：{{server_id_1}}，端口 8080，权重 100
  - 服务器 2：{{server_id_2}}，端口 8080，权重 100

创建完成后请返回 VServer Group ID。
```

> **Related Operations:** [Create VServer Group](../SKILL.md#operation-create-vserver-group), [Add Backend Servers to VServer Group](../SKILL.md#operation-add-backend-servers-to-vserver-group)

### 3.2 Add a New Backend Server to Existing Group

```
请将服务器 {{server_id}}（端口 {{port}}，权重 {{weight}}）添加到 VServer Group {{vserver_group_id}} 中。
```

> **Related Operation:** [Add Backend Servers to VServer Group](../SKILL.md#operation-add-backend-servers-to-vserver-group)

### 3.3 Remove a Backend Server

```
请将服务器 {{server_id}} 从 VServer Group {{vserver_group_id}} 中移除。
该服务器当前正在处理流量，请先确认是否继续。
```

> **Related Operation:** [Remove Backend Servers from VServer Group](../SKILL.md#operation-remove-backend-servers-from-vserver-group)

### 3.4 Add Backend Servers to Default Group

```
请将服务器 {{server_id}}（权重 100）添加到 SLB 实例 {{load_balancer_id}} 的默认后端服务器组中。
```

> **Related Operation:** [Add Backend Servers to Default Group](../SKILL.md#operation-add-backend-servers-to-default-group)

### 3.5 Adjust Backend Weights for Traffic Distribution

```
请查看 SLB 实例 {{load_balancer_id}} 的 VServer Group {{vserver_group_id}} 的当前权重配置，
然后将以下服务器的权重调整为：
- {{server_id_1}}：权重 50
- {{server_id_2}}：权重 100

目的是让 server_2 承担双倍流量。
```

> **Related Operations:** [Describe VServer Group Attribute](../SKILL.md#operation-describe-vserver-group-attribute), [Add Backend Servers to VServer Group](../SKILL.md#operation-add-backend-servers-to-vserver-group)

### 3.6 Apply Gradual Rollout (Canary)

```
请创建一个新的 VServer Group {{new_group_name}}，
将新版本服务器 {{new_server_id}}（权重 10）加入该组，
然后创建一个 HTTP 转发规则将 /api/v2/* 的流量转发到这个新组。
```

> **Related Operations:** [Create VServer Group](../SKILL.md#operation-create-vserver-group), [Create Forwarding Rules](../SKILL.md#operation-create-forwarding-rules)

---

## 4. Certificate Management

### 4.1 Upload a Server Certificate

```
请帮我在 {{region}} 区域上传一个服务器证书：
- 证书名称：{{certificate_name}}
- 证书内容（PEM 格式）：
  {{certificate_content}}
- 私钥内容（PEM 格式）：
  {{private_key_content}}

请返回证书 ID 和过期时间。
```

> **Related Operation:** [Upload Server Certificate](../SKILL.md#operation-upload-server-certificate)

**Example:**
```
请帮我在 cn-hangzhou 区域上传一个服务器证书：
- 证书名称：www-example-com
- 证书内容（PEM 格式）：
  -----BEGIN CERTIFICATE-----
  MIIF...
  -----END CERTIFICATE-----
- 私钥内容（PEM 格式）：
  -----BEGIN RSA PRIVATE KEY-----
  MIIE...
  -----END RSA PRIVATE KEY-----

请返回证书 ID 和过期时间。
```

### 4.2 List All Certificates

```
请列出 {{region}} 区域的所有服务器证书，
包括：证书 ID、证书名称、通用名称（CN）、过期时间。
```

> **Related Operation:** [Describe Server Certificates](../SKILL.md#operation-describe-server-certificates)

### 4.3 Check Certificate Expiry

```
请检查 {{region}} 区域所有证书的过期状态，
列出 30 天内即将过期的证书。
```

> **Related Operation:** [Describe Server Certificates](../SKILL.md#operation-describe-server-certificates)

### 4.4 Renew a Certificate (Upload + Bind)

```
我的证书 {{certificate_id}} 即将过期，请帮我：
1. 上传新证书（名称：{{new_cert_name}}）
2. 找到引用了旧证书 {{certificate_id}} 的所有 HTTPS 监听器
3. 将这些监听器的证书更新为新证书
4. 删除旧证书
```

> **Related Operations:** [Upload Server Certificate](../SKILL.md#operation-upload-server-certificate), [Describe Listeners](../SKILL.md#operation-describe-listeners), [Delete Server Certificate](../SKILL.md#operation-delete-server-certificate)

### 4.5 Delete a Certificate

```
请删除证书 {{certificate_id}}。
注意：请先确认没有 HTTPS 监听器在使用此证书，否则删除会失败。
```

> **Related Operation:** [Delete Server Certificate](../SKILL.md#operation-delete-server-certificate)

---

## 5. Access Control List (ACL) Management

### 5.1 Create an ACL and Add IP Entries

```
请帮我在 {{region}} 区域创建一个访问控制列表：
- ACL 名称：{{acl_name|allow-office-ips}}
- 条目：
  - 允许 203.0.113.0/24
  - 允许 198.51.100.1
  - 拒绝 0.0.0.0/0

创建完成后请返回 ACL ID。
```

> **Related Operations:** [Create Access Control List](../SKILL.md#operation-create-access-control-list), [Add ACL Entries](../SKILL.md#operation-add-acl-entries)

### 5.2 Associate ACL with Listener

```
请将 ACL {{acl_id}} 关联到 SLB 实例 {{load_balancer_id}} 的 {{listener_port}} 端口监听器，
设置为白名单模式（仅允许 ACL 中的 IP 访问）。
```

> **Related Operation:** [Create HTTP Listener](../SKILL.md#operation-create-http-listener) (set AclStatus/AclId via SDK)

### 5.3 Add IP to Existing ACL

```
请将 IP {{new_ip}} 添加到 ACL {{acl_id}} 中（黑/白名单类型为 {{acl_type|allow}}）。
```

> **Related Operation:** [Add ACL Entries](../SKILL.md#operation-add-acl-entries)

### 5.4 Remove IP from ACL

```
请从 ACL {{acl_id}} 中移除条目 {{entry_id_or_ip}}。
```

> **Related Operation:** [Delete Access Control List](../SKILL.md#operation-delete-access-control-list) (use RemoveAccessControlListEntry)

---

## 6. Forwarding Rule Management

### 6.1 Create URL-Based Forwarding Rules

```
请为 SLB 实例 {{load_balancer_id}} 的 {{listener_port}} 端口 HTTP 监听器创建以下转发规则：
1. 规则名：api-rule，域名：api.example.com，URL：/*，转发到 VServer Group {{vserver_group_id_1}}
2. 规则名：static-rule，域名：*.example.com，URL：/static/*，转发到 VServer Group {{vserver_group_id_2}}
3. 规则名：default-rule，域名：*.example.com，URL：/*，转发到 VServer Group {{vserver_group_id_3}}
```

> **Related Operation:** [Create Forwarding Rules](../SKILL.md#operation-create-forwarding-rules)

### 6.2 List and Verify Forwarding Rules

```
请列出 SLB 实例 {{load_balancer_id}} 的 {{listener_port}} 端口监听器上的所有转发规则，
包括：规则 ID、规则名称、域名匹配、URL 匹配、目标 VServer Group。
请帮我检查规则顺序是否正确。
```

> **Related Operation:** [Describe Rules](../SKILL.md#operation-describe-rules)

### 6.3 Delete a Forwarding Rule

```
请删除规则 {{rule_id}}。
注意：删除后该规则的流量将不再转发到指定的 VServer Group。
```

> **Related Operation:** [Delete Rules](../SKILL.md#operation-delete-rules)

---

## 7. Diagnostics & Troubleshooting

### 7.1 "用户访问不了网站，请帮我排查"

```
用户报告无法访问 SLB 实例 {{load_balancer_id}} 的服务，
请帮我执行端到端诊断：
1. 检查 SLB 实例状态
2. 检查监听器状态
3. 检查后端服务器健康状态
4. 检查 ACL 配置是否拦截了用户 IP
5. 给出根因分析和修复建议
```

> **Related Operation:** [Diagnose Service Unreachable](../SKILL.md#operation-diagnose-service-unreachable)

### 7.2 "502 Bad Gateway，请排查"

```
SLB 实例 {{load_balancer_id}} 返回 502 Bad Gateway，
请帮我排查：
1. 检查后端服务器健康状态
2. 检查健康检查配置
3. 检查后端响应时间
4. 给出根因和修复建议
```

> **Related Operation:** [Diagnose 502/504 Errors](../SKILL.md#operation-diagnose-502504-errors)

### 7.3 "HTTPS 访问报证书错误"

```
用户访问 https://{{domain}} 时报证书错误，
请帮我诊断：
1. 检查 SLB 实例 {{load_balancer_id}} 的 443 端口 HTTPS 监听器使用的证书
2. 检查证书是否过期
3. 检查证书域名是否匹配 {{domain}}
4. 给出根因和修复建议
```

> **Related Operation:** [Diagnose HTTPS/SSL Issues](../SKILL.md#operation-diagnose-httpsssl-issues)

### 7.4 "流量分布不均匀"

```
SLB 实例 {{load_balancer_id}} 的后端服务器流量分布不均，
部分服务器负载很高，部分几乎无流量。
请帮我排查：
1. 检查后端权重配置
2. 检查会话保持是否开启
3. 检查后端健康状态
4. 给出优化建议
```

> **Related Operation:** [Diagnose Traffic Imbalance](../SKILL.md#operation-diagnose-traffic-imbalance)

### 7.5 "新加的转发规则不生效"

```
我为 SLB 实例 {{load_balancer_id}} 的 80 端口监听器添加了转发规则，
但访问时没有按预期转发，请帮我检查：
1. 列出当前所有转发规则
2. 检查规则顺序
3. 检查 URL 和域名匹配模式是否正确
4. 给出修复建议
```

> **Related Operation:** [Describe Rules](../SKILL.md#operation-describe-rules)

### 7.6 Full Health Check

```
请对 SLB 实例 {{load_balancer_id}} 执行一次全量健康检查：
1. 实例状态和配置
2. 所有监听器状态
3. 每个监听器的后端健康状态
4. 所有 VServer Group
5. 关联的证书
6. 生成一份健康检查报告
```

> **Related Operation:** [Run Full Health Audit](../SKILL.md#operation-run-full-health-audit)

---

## 8. Multi-Step Workflows

### 8.1 "帮我从零搭建一个 Web 服务"

```
请帮我从零搭建一个 Web 服务：
1. 在 {{region}} 区域创建一个公网 SLB 实例，名称 {{slb_name}}，规格 slb.s2.medium
2. 创建一个 VServer Group，名称 {{group_name}}，包含服务器 {{server_id_1}} 和 {{server_id_2}}，端口 8080
3. 创建 HTTP 监听器，端口 80 -> 后端 8080，关联到上诉 VServer Group
4. 启用健康检查，检查路径 /health
5. 开启 X-Forwarded-For
6. 返回 SLB 实例 ID 和公网 IP

请按步骤执行，每个步骤完成后向我汇报结果。
```

> **Related Operations:** [Create Load Balancer](../SKILL.md#operation-create-load-balancer), [Create VServer Group](../SKILL.md#operation-create-vserver-group), [Add Backend Servers to VServer Group](../SKILL.md#operation-add-backend-servers-to-vserver-group), [Create HTTP Listener](../SKILL.md#operation-create-http-listener)

### 8.2 "将 HTTP 升级为 HTTPS"

```
请将 SLB 实例 {{load_balancer_id}} 的 80 端口 HTTP 监听器升级为 HTTPS：
1. 先上传一个新的服务器证书（名称：{{cert_name}}）
2. 创建 443 端口的 HTTPS 监听器，复用原有的 VServer Group 和健康检查配置
3. 创建一个 HTTP -> HTTPS 的重定向规则（如果 SLB 支持）
4. 保留原有的 80 端口 HTTP 监听器（用于自动跳转）

请返回 HTTPS 监听器的状态。
```

> **Related Operations:** [Upload Server Certificate](../SKILL.md#operation-upload-server-certificate), [Create HTTPS Listener](../SKILL.md#operation-create-https-listener)

### 8.3 "后端服务器滚动更新"

```
我需要执行后端服务器滚动更新，SLB 实例 {{load_balancer_id}}，监听器端口 {{listener_port}}：
1. 先检查当前后端健康状态，记录所有正常服务器
2. 将服务器 {{server_id_1}} 的权重设为 0（停止接收新流量）
3. 等待 30 秒让现有连接完成
4. 告知我 "服务器 1 已离线，请在服务器上执行更新操作"
5. 等我确认更新完成后，将权重恢复为 100
6. 检查健康状态，确认恢复为 normal
7. 对服务器 {{server_id_2}} 重复步骤 2-6
8. 所有服务器更新完成后，执行一次全量健康检查
```

> **Related Operations:** [Describe Health Status](../SKILL.md#operation-describe-health-status), [Set Backend Server Weights (Default Group)](../SKILL.md#operation-set-backend-server-weights-default-group), [Run Full Health Audit](../SKILL.md#operation-run-full-health-audit)

### 8.4 "跨区域容灾搭建"

```
请帮我搭建跨区域容灾方案：
1. 在 {{region_1}} 区域创建主 SLB 实例 {{slb_name_1}}
2. 在 {{region_2}} 区域创建备 SLB 实例 {{slb_name_2}}
3. 两个实例配置相同的监听器（端口 80 和 443）
4. 创建 VServer Group 并添加对应的后端服务器
5. 上传 SSL 证书并配置 HTTPS
6. 生成两份配置对比报告，确认两区域配置一致
```

> **Related Operations:** Cross-region orchestration using Create Load Balancer, Create Listener, Upload Server Certificate, etc.

### 8.5 "迁移旧 SLB 实例到新实例"

```
请帮我将 SLB 实例 {{old_lb_id}} 的配置迁移到新实例 {{new_lb_id}}：
1. 获取旧实例的所有监听器配置
2. 获取旧实例的所有 VServer Group 和后端服务器配置
3. 获取旧实例的转发规则
4. 在新实例上创建相同的配置
5. 生成配置迁移报告，列出所有已迁移的配置项
```

> **Related Operations:** [Describe Listeners](../SKILL.md#operation-describe-listeners), [Describe VServer Groups](../SKILL.md#operation-describe-vserver-groups), [Describe Rules](../SKILL.md#operation-describe-rules), [Create TCP/HTTP/HTTPS/UDP Listener](../SKILL.md#operation-create-tcp-listener), [Create VServer Group](../SKILL.md#operation-create-vserver-group), [Create Forwarding Rules](../SKILL.md#operation-create-forwarding-rules)

---

## 9. Batch & Reporting

### 9.1 "批量检查所有 SLB 实例的健康状态"

```
请列出 {{region}} 区域的所有 SLB 实例，
对每个实例执行一次健康检查，
生成一个汇总报告，包括：
- 实例 ID 和名称
- 实例状态
- 监听器数量
- 健康后端/全部后端比例
- 证书即将过期提醒（30天内）
```

> **Related Operations:** [Describe Load Balancers](../SKILL.md#operation-describe-load-balancers), [Run Full Health Audit](../SKILL.md#operation-run-full-health-audit)

### 9.2 "审计所有 SLB 实例的安全配置"

```
请对 {{region}} 区域的所有 SLB 实例进行安全审计：
1. 列出所有开启了公网访问的实例
2. 检查哪些公网实例未配置 ACL
3. 检查哪些 HTTPS 监听器使用了即将过期的证书
4. 检查哪些实例开启了删除保护
5. 生成安全审计报告及整改建议
```

> **Related Operations:** [Describe Load Balancers](../SKILL.md#operation-describe-load-balancers), [Describe Load Balancer Attribute](../SKILL.md#operation-describe-load-balancer-attribute), [Describe Server Certificates](../SKILL.md#operation-describe-server-certificates)

---

## 10. Quick References (Common Queries)

These are simple one-liner queries users commonly ask:

| 你可能想做的 | 直接这样说 |
|-------------|-----------|
| 查看实例列表 | "列出 {{region}} 的所有 SLB 实例" |
| 查看监听器 | "列出 {{load_balancer_id}} 的所有监听器" |
| 查看后端健康 | "检查 {{load_balancer_id}} 的 80 端口后端健康状态" |
| 查看证书 | "列出 {{region}} 的所有服务器证书" |
| 查看 ACL | "列出 {{region}} 的所有访问控制列表" |
| 查看转发规则 | "列出 {{load_balancer_id}} 的 80 端口上的转发规则" |
| 检查实例规格 | "{{load_balancer_id}} 是什么规格？带宽多少？" |
| 检查是否开启了保护 | "{{load_balancer_id}} 是否开启了删除保护？" |
| 诊断不通 | "{{load_balancer_id}} 访问不了，帮我查一下" |
| 诊断 502 | "{{load_balancer_id}} 报 502 了，怎么回事" |
| 证书快过期了 | "检查一下 {{region}} 有没有快过期的证书" |

---

## Prompt Design Tips

### Best Practices

1. **提供实例 ID 和区域：** 始终提供 `load_balancer_id` 和 `region`，这是所有操作的前提。
2. **明确约束条件：** 如果操作需要避免停机、保留配置，请在提示中说明。
3. **请求验证：** 操作完成后请让 Agent 验证结果（如"请验证状态"、"请返回结果"）。
4. **提供上下文：** 排障提示中请包含错误信息、症状描述等上下文。
5. **使用占位符：** 用 `{{placeholder}}` 标记需要替换的值。
6. **渐进式复杂：** 从简单的单步操作开始，逐步组合成多步骤工作流。

### Safety Reminders

- **删除操作**（删除 SLB、删除监听器、删除证书）应始终包含明确确认。
- **变更操作**（修改规格、修改权重）应说明潜在影响。
- **生产环境操作**前建议先执行 Describe 操作确认当前状态。

### Linking to SKILL.md

Each prompt template in this document cross-references the relevant operation in [SKILL.md](../SKILL.md). If you need to customize the underlying command, open SKILL.md and look up the corresponding **Execution — CLI** section for full parameter details.

---

*Last updated: 2026-05-14*