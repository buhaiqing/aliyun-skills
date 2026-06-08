# Sprint 4: 拓扑渲染联动（P1）

> **状态**: PASS 3/3
> 业务价值: 巡检报告自带拓扑图 + 健康状态叠加
> 交付物: `runbooks/01-daily-health-check.md` (Phase 3 更新版)
> 前置条件: 无 (D3-01 已完成)
> 关联验收项: S1-D4

### 任务

- [x] **4.0** topo-render.py 支持 `--health-json` (已完成)
- [x] **4.1** Phase 3 末尾调用 `topo-scan.sh --health-json <巡检报告>`
    实现: `daily-health-check.py` 新增 `_write_topology_health_json()` 生成简化健康 JSON,
    `_call_topo_render()` 调用 topo-scan.sh (非阻塞), `_merge_topology_into_report()` 合并拓扑到巡检报告
    容错: topo-scan.sh 不存在或超时 -> 日志警告,不影响主流程
- [x] **4.2** 输出 ASCII + Mermaid 拓扑图，健康状态叠加
    实现: topo-render.py 已有 ASCII 树 + Mermaid 图双格式输出;
    health JSON 包含 critical/warning/anomaly 资源的 level + z_score -> get_health() 叠加 emoji CRITICALWARNINGPASS

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q4.1 | 拓扑图存在 | `grep -c 'mermaid\|ASCII' report.md` | >= 1 种格式 |
| Q4.2 | 健康状态正确 | 已知异常资源拓扑图中显示 CRITICAL | 对应关系正确 |
| Q4.3 | 命令容错 | `topo-scan.sh --health-json bad.json 2>&1` | 非 0 退出但巡检继续 |
| Q4.4 | 健康 JSON 格式 | `python3 -c "import json; json.load(open('topology-health.json'))"` | 合法 JSON, 含 level/z_score |
| Q4.5 | 合并报告存在 | `grep -c '拓扑' report.md` | >= 1 行 |