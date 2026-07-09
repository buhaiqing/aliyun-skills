# alicloud-cms-ops Scripts

## cms-skillopt-wrapper.sh (recommended)

Wraps `aliyun cms` with SkillOpt self-repair and dynamic optimization.

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization --Period 60 \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

Runtime artifacts: `${SKILLS_DIR}/.runtime/logs/alicloud-cms-ops/cms-skillopt-*.log` and
`${SKILLS_DIR}/.runtime/metrics/alicloud-cms-ops/cms-skillopt-runtime.json` (gitignored).

## skillopt-self-repair.sh (legacy alias)

Thin wrapper that calls `cms-skillopt-wrapper.sh` with `--skillopt-enable`.
Accepts optional leading `cms` token for backward compatibility.

```bash
./scripts/skillopt-self-repair.sh DescribeMetricList \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization
```

## Requirements

- Alibaba Cloud CLI (`aliyun`) with `cms` plugin
- `jq` for JSON validation
- See [skillopt-integration.md](../references/skillopt-integration.md)
