# CLI Usage — PTS (`aliyun pts`)

> Version: 1.0.0 | Last Updated: 2026-06-16

## Plugin Installation (Required)

```bash
aliyun plugin install --names aliyun-cli-pts
aliyun pts version
```

> Plugin commands use **kebab-case**. PascalCase API names (e.g. `ListPtsScene`) are **not** valid without the plugin.

## Command Map — PTS Native Scenes

| Goal | Example |
|------|---------|
| List scenes | `aliyun pts list-pts-scene --page-number 1 --page-size 10 --region cn-hangzhou` |
| Search by keyword | `aliyun pts list-pts-scene --page-number 1 --page-size 10 --key-word "{{name_or_id}}"` |
| Get scene detail | `aliyun pts get-pts-scene --scene-id "{{scene_id}}"` |
| Create scene | `aliyun pts create-pts-scene --scene '{"sceneName":"demo",...}'` |
| Save scene | `aliyun pts save-pts-scene --scene '{...}'` |
| Modify scene | `aliyun pts modify-pts-scene --scene-id "{{id}}" ...` |
| Start debug | `aliyun pts start-debug-pts-scene --scene-id "{{id}}"` |
| Stop debug | `aliyun pts stop-debug-pts-scene --scene-id "{{id}}"` |
| **Start load test** | `aliyun pts start-pts-scene --scene-id "{{id}}"` **High risk** |
| Stop load test | `aliyun pts stop-pts-scene --scene-id "{{id}}"` |
| Running status | `aliyun pts get-pts-scene-running-status --scene-id "{{id}}"` |
| Running metrics | `aliyun pts get-pts-scene-running-data --scene-id "{{id}}"` |
| Adjust speed | `aliyun pts adjust-pts-scene-speed --scene-id "{{id}}" --all-rps-limit 200` |
| Delete one | `aliyun pts delete-pts-scene --scene-id "{{id}}"` **Destructive** |
| Delete batch | `aliyun pts delete-pts-scenes --scene-ids '["id1","id2"]'` **Destructive** |
| Debug sample logs | `aliyun pts get-pts-debug-sample-logs --scene-id "{{id}}"` |

## Command Map — Reports & Baselines

| Goal | Example |
|------|---------|
| List reports | `aliyun pts list-pts-reports --page-number 1 --page-size 10` |
| Report by scene | `aliyun pts get-pts-reports-by-scene-id --scene-id "{{id}}"` |
| Report detail | `aliyun pts get-pts-report-details --report-id "{{report_id}}"` |
| Get baseline | `aliyun pts get-pts-scene-base-line --scene-id "{{id}}"` |
| Set baseline from report | `aliyun pts create-pts-scene-base-line-from-report --scene-id "{{id}}" --report-id "{{rid}}"` |
| Update baseline | `aliyun pts update-pts-scene-base-line --scene-id "{{id}}" ...` |
| Delete baseline | `aliyun pts delete-pts-scene-base-line --scene-id "{{id}}"` |

## Command Map — JMeter

| Goal | Example |
|------|---------|
| List JMeter scenes | `aliyun pts list-open-jmeter-scenes --page-number 1 --page-size 10` |
| Get JMeter scene | `aliyun pts get-open-jmeter-scene --open-jmeter-scene-id "{{id}}"` |
| Save JMeter scene | `aliyun pts save-open-jmeter-scene --open-jmeter-scene '{...}'` |
| Remove JMeter scene | `aliyun pts remove-open-jmeter-scene --open-jmeter-scene-id "{{id}}"` |
| Start JMeter debug | `aliyun pts start-debugging-jmeter-scene --open-jmeter-scene-id "{{id}}"` |
| Start JMeter test | `aliyun pts start-testing-jmeter-scene --open-jmeter-scene-id "{{id}}"` |
| Stop JMeter test | `aliyun pts stop-testing-jmeter-scene --open-jmeter-scene-id "{{id}}"` |
| JMeter report | `aliyun pts get-jmeter-report-details --report-id "{{id}}"` |
| JMeter metrics | `aliyun pts get-jmeter-sample-metrics --report-id "{{id}}"` |
| List JMeter envs | `aliyun pts list-envs --page-number 1 --page-size 10` |
| Save env | `aliyun pts save-env --env '{...}'` |

## Command Map — VPC Helpers

| Goal | Example |
|------|---------|
| List VPCs | `aliyun pts get-user-vpcs` |
| List VSwitches | `aliyun pts get-user-vpc-vswitch --vpc-id "{{vpc_id}}"` |
| List security groups | `aliyun pts get-user-vpc-security-group --vpc-id "{{vpc_id}}"` |

## Command Map — Infrastructure

| Goal | Example |
|------|---------|
| List regions | `aliyun pts get-all-regions` |
| List API versions | `aliyun pts list-api-versions` |
| Dry run | `aliyun pts get-pts-scene --scene-id "{{id}}" --cli-dry-run` |

## Parameter Notes

| Pattern | Correct | Wrong |
|---------|---------|-------|
| Scene JSON | `--scene '{"sceneName":"x",...}'` | Unescaped newlines in shell |
| Complex scene | `--scene "$(cat scene.json)"` | Inline 10KB without file |
| Region | `--region cn-hangzhou` or env | Omit region on multi-region accounts |
| Pagination | `--page-number 1 --page-size 10` | `PageSize` < 10 |
| Keyword search | `--key-word` ≤30 chars | Long fuzzy strings |

## JMESPath Output

```bash
aliyun pts list-pts-scene --page-number 1 --page-size 10 \
  --cli-query 'SceneViewList[].{Id:SceneId,Name:SceneName,Status:Status}'
```

## Coverage Gap (SDK-only)

| Operation | Reason |
|-----------|--------|
| Complex Scene builder UI export | Console export → JSON file → CLI |
| Multi-scene orchestration loops | SDK for scripted pipelines |
| Custom report analytics | SDK + data export |

All primary CRUD + run/stop/report APIs are covered by the plugin CLI.
