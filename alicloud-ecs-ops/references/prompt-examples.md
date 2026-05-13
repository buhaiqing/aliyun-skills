# Prompt Examples — Alibaba Cloud ECS

This document provides **natural language prompt examples** that users can use to interact with the `alicloud-ecs-ops` skill. Each example demonstrates a common operational scenario. Users can copy and adapt these prompts directly.

> **使用方式:** 将下面任意一条提示词发给 Agent，Skill 会自动识别场景、收集缺失参数、执行操作并返回结果。
> **变量约定:** `{变量}` 表示需要用户提供的信息，Agent 会在执行前主动询问。

---

## 1. 实例生命周期管理 (Instance Lifecycle)

### 1.1 创建实例

```
帮我创建一台 ECS 实例，用 CentOS 7.9 镜像，ecs.g7.large 规格，放在杭州可用区 H，
20GB 系统盘，安全组用 sg-bp67acfmxazb4ph***，VSwitch 用 vsw-bp67acfmxazb4ph***，
绑一个 1Mbps 的公网带宽
```

```
在阿里云上给我起一台测试服务器，2 核 4G，Ubuntu 22.04，用密钥对登录，不要公网 IP
```

```
我需要批量创建 3 台 web 服务器，配置都一样，名字前缀叫 web-server
```

### 1.2 查询实例

```
查看我在杭州地域的所有 ECS 实例
```

```
帮我查一下实例 i-bp67acfmxazb4ph*** 的详细信息，包括 IP、状态、到期时间
```

```
列出所有状态为 Running 的实例，只看 InstanceId、InstanceName 和公网 IP
```

### 1.3 启动 / 停止 / 重启

```
启动 i-bp67acfmxazb4ph*** 这台机器
```

```
把所有标记了 Environment=Test 的实例关掉
```

```
重启 web-server-01，不要强制重启
```

### 1.4 删除实例

```
把 dev-app-01 (i-bp67acfmxazb4ph***) 删掉，先确认一下再操作
```

```
清理项目中所有带 Project=Obsolete 标签的实例
```

### 1.5 修改实例属性

```
把 i-bp67acfmxazb4ph*** 改名为 production-web-01
```

```
重置 i-bp67acfmxazb4ph*** 的 root 密码，先关机再改
```

---

## 2. 云盘管理 (Disk Management)

### 2.1 创建云盘

```
在杭州可用区 H 创建一块 200GB 的 ESSD 云盘，名字叫 data-disk-01
```

```
帮我创建一块加密数据盘，100GB，ESSD 类型
```

### 2.2 挂载 / 卸载

```
把云盘 d-bp67acfmxazb4ph*** 挂载到 i-bp67acfmxazb4ph*** 上
```

```
从 i-bp67acfmxazb4ph*** 卸载数据盘 d-bp67acfmxazb4ph***，注意不要卸载系统盘
```

### 2.3 扩容

```
把云盘 d-bp67acfmxazb4ph*** 从 100GB 扩容到 200GB，在线扩容
```

### 2.4 删除云盘

```
删除 d-bp67acfmxazb4ph*** 这块云盘，先确认是否已经卸载了
```

---

## 3. 快照管理 (Snapshot Management)

### 3.1 创建快照

```
给 d-bp67acfmxazb4ph*** 创个快照，名字叫 before-upgrade-20260514
```

```
对实例 i-bp67acfmxazb4ph*** 的系统盘做一次备份快照
```

### 3.2 查询快照

```
查看我在杭州的所有快照
```

```
查下快照 s-bp67acfmxazb4ph*** 创建好了没
```

### 3.3 删除快照

```
删掉快照 s-bp67acfmxazb4ph***，确认一下再删
```

---

## 4. 安全组管理 (Security Group)

### 4.1 创建安全组

```
在 VPC vpc-bp67acfmxazb4ph*** 里创建一个安全组，名字叫 web-sg
```

### 4.2 添加规则

```
给安全组 sg-bp67acfmxazb4ph*** 放通 22 端口，只允许 203.0.113.10 这个 IP 访问
```

```
在 sg-bp67acfmxazb4ph*** 上允许 HTTP(80) 和 HTTPS(443) 的入站流量
```

```
开放安全组 sg-bp67acfmxazb4ph*** 的 3306 端口给另一台 ECS 的内网 IP
```

### 4.3 删除规则

```
从安全组 sg-bp67acfmxazb4ph*** 上移除那条允许 22 端口对全网开放的规则
```

### 4.4 查询规则

```
看看安全组 sg-bp67acfmxazb4ph*** 的所有入站规则
```

---

## 5. 云助手远程执行 (Cloud Assistant)

### 5.1 执行命令

```
在 i-bp67acfmxazb4ph*** 上执行 'df -h' 看看磁盘使用情况
```

```
帮我在 web-server-01 上运行这个脚本：检查 nginx 进程是否在运行
```

```
对所有带 Project=WebServer 标签的实例执行 'systemctl status nginx'
```

### 5.2 诊断场景

```
在 i-bp67acfmxazb4ph*** 上运行 'top -bn1 | head -20' 看看 CPU 最高的进程
```

```
在 web-server-01 上收集诊断信息：查看 dmesg、/var/log/messages 最后 200 行
```

```
帮我检查 i-bp67acfmxazb4ph*** 的内存使用：free -h && cat /proc/meminfo | head -10
```

### 5.3 发送文件

```
把本地的 deploy.sh 脚本发送到 i-bp67acfmxazb4ph*** 的 /tmp 目录下，权限 755
```

```
把这个 nginx.conf 发到 web-server-01 和 web-server-02 的 /etc/nginx/ 下
```

### 5.4 查询结果

```
查一下上次在 i-bp67acfmxazb4ph*** 上执行的命令结果
```

---

## 6. 故障诊断与排错 (Troubleshooting)

### 6.1 连通性诊断

```
我连不上 web-server-01 了，帮我排查一下是什么原因
```

```
SSH 连 i-bp67acfmxazb4ph*** 超时了，帮我检查安全组规则、实例状态和网络配置
```

```
从办公室 IP 203.0.113.10 访问不了生产环境的 ECS，帮我逐层排查
```

### 6.2 性能问题

```
i-bp67acfmxazb4ph*** 的 CPU 一直跑满，帮我看看怎么回事
```

```
数据库服务器的 ECS 磁盘 IO 很高，帮我查一下监控指标
```

### 6.3 状态异常

```
我的实例一直卡在 Starting 状态，启动不起来，帮我排查
```

```
i-bp67acfmxazb4ph*** 被安全锁定了（InstanceLockedForSecurity），怎么处理
```

---

## 7. 批量操作 (Batch Operations)

### 7.1 批量创建

```
批量创建 5 台一样的实例用作 K8s worker 节点，名字前缀 k8s-worker
```

```
在杭州可用区 H 和 I 各创建 2 台 ECS，做跨可用区部署
```

### 7.2 批量管理

```
把所有 Project=Dev 的 ECS 晚上 10 点统一关机
```

```
给所有 web-server 实例的 /var/log 目录用云助手收集日志
```

---

## 8. 镜像管理 (Image Management)

```
查看阿里云官方的 CentOS 7.9 镜像 ID 是什么
```

```
把实例 i-bp67acfmxazb4ph*** 的当前系统盘做成一个自定义镜像，叫 gold-image-v2.0
```

```
给我推荐一下杭州地域的 Ubuntu 22.04 最新镜像
```

---

## 9. 标签管理 (Tag Management)

```
给 i-bp67acfmxazb4ph*** 打上标签 Environment=Production, Owner=DevOps, Project=ecommerce
```

```
帮我找出所有带 Environment=Production 标签的实例
```

```
把 web-server-01 的 Owner 标签从 DevOps 改成 SRE
```

---

## 10. 监控与告警 (Monitoring)

```
看看 i-bp67acfmxazb4ph*** 最近 1 小时的 CPU 使用率
```

```
帮我查 web-server-01 最近 30 分钟的网络流入流出情况
```

```
在 i-bp67acfmxazb4ph*** 上设置一个 CPU 超过 80% 持续 5 分钟的告警
```

---

## 11. 综合运维场景 (Composite Scenarios)

### 11.1 从零部署 Web 服务

```
我要部署一个新的 Web 应用，需要你做：
1. 创建一台 2C4G 的 ECS，装 CentOS 7.9
2. 创建安全组并开放 80 和 443 端口
3. 给实例绑定一个弹性公网 IP
4. 用云助手在实例上安装 Nginx
```

### 11.2 灾备演练

```
灾难恢复演练：
1. 先给 i-bp67acfmxazb4ph*** 的系统盘打一个快照
2. 用这个快照创建一台新的恢复实例
3. 等新实例启动后验证一下服务是否正常
```

### 11.3 批量安全合规检查

```
安全巡检：帮我检查所有实例的安全组规则，找出哪些端口是对 0.0.0.0/0 开放的
```

### 11.4 规模扩容

```
业务要扩容：基于现有的 web-server-01 创建自定义镜像，然后用这个镜像批量起 3 台新实例
```

---

## 使用技巧 (Usage Tips)

### 简短描述即可

不需要精确说出参数名，Agent 会根据 Skill 文档自动映射：

| 你的描述 | 会被识别为 |
|---------|-----------|
| "杭州" | `RegionId: cn-hangzhou` |
| "2 核 4G" | 匹配合适的 `InstanceType` |
| "开放 22 端口" | 添加 SSH 安全组规则 |
| "ESSD 磁盘" | `DiskCategory: cloud_essd` |

### 可以一次说多件事

```
帮我在杭州查一下所有 ECS，然后把 dev 环境的没标签的实例都列出来
```

### 不用记参数名

Agent 会自动询问缺失的信息。你只需要描述"要做什么"和"大概什么配置"。

### 安全操作有确认

涉及删除、重置密码等操作时，Agent 会主动要求二次确认，防止误操作。