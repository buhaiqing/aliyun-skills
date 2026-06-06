# Sprint 4: 拓扑渲染联动（P1）

> 业务价值: 巡检报告自带拓扑图 + 健康状态叠加
> 交付物: `runbooks/01-daily-health-check.md` (Phase 3 更新版)
> 前置条件: 无 (D3-01 已完成)
> 关联验收项: S1-D4

### 任务

- [x] **4.0** topo-render.py 支持 `--health-json` (已完成)
- [ ] **4.1** Phase 3 末尾调用 `topo-scan.sh --health-json <巡检报告>`
- [ ] **4.2** 输出 ASCII + Mermaid 拓扑图，健康状态叠加

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q4.1 | 拓扑图存在 | `grep -c 'mermaid\|ASCII' report.md` | >= 1 种格式 |
| Q4.2 | 健康状态正确 | 已知异常资源拓扑图中显示 🔴 | 对应关系正确 |
| Q4.3 | 命令容错 | `topo-scan.sh --health-json bad.json 2>&1` | 非 0 退出但巡检继续 |