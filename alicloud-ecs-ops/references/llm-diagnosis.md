# LLM辅助诊断

## 诊断工作流

```
用户报告问题 → 提取关键信息 → 查询ECS状态+监控+日志 → 构建诊断Prompt → LLM分析 → 返回修复步骤
```

## CLI + LLM 集成

```bash
INSTANCE_ID="{{user.instance_id}}"

# 获取实例状态
STATUS=$(aliyun ecs DescribeInstances --RegionId "{{user.region}}" --InstanceIds "[\"$INSTANCE_ID\"]" --output cols=Status rows=Instances.Instance[0].Status)

# 获取最近告警
ALERTS=$(aliyun cms DescribeAlertHistoryList --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%MZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%MZ 2>/dev/null)" --EndTime "$(date -u +%Y-%m-%dT%H:%MZ)" --InstanceId "$INSTANCE_ID" --output json)

# 构建诊断信息
cat << 'EOF'
你是阿里云ECS运维专家。请分析：
实例ID: $INSTANCE_ID, 状态: $STATUS
最近告警: $ALERTS
用户报告: {{user.problem_description}}
EOF
```

## 支持的问题类型

| 问题类型 | 关键数据 | 分析要点 |
|----------|----------|----------|
| 无法连接 | 安全组、VPC、状态 | 网络路径分析 |
| 性能问题 | CPU、内存、IO | 资源瓶颈定位 |
| 磁盘满 | 磁盘使用率 | 清理建议 |
| 应用崩溃 | 内存、OOM | 堆栈分析 |

> **注意：** 需要外部LLM API集成（如DashScope、OpenAI）。