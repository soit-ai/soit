# SOIT 1.0 发布交接说明

更新日期：2026 年 3 月 11 日

## 当前状态

SOIT 1.0 已经具备进入 `Release Candidate` 阶段的条件。

工程侧工作已经完成，当前剩余的发布门槛只有两项：

1. Release owner 最终签字确认。
2. 按 [docs/SOIT_1.0_Owner_UI_Spotcheck.md](/f:/soit/soit-pro/docs/SOIT_1.0_Owner_UI_Spotcheck.md) 完成一轮简短的 UI 点检。

## 1.0 已包含范围

- 统一后的工作区导航与历史路径重定向。
- ModelHub Provider 管理与 Catalog 同步能力。
- Knowledge 的创建、文档 ingest、查询与运行时入口主链路。
- Agent 的创建、版本管理、发布与执行主链路。
- Chat 中的 Agent 选择与 response/run 关联。
- Workflow Builder 保存为版本并进入执行的最小闭环。
- Runs 的筛选、详情查看与链路跳转。
- Settings Overview，以及 Team、API、Secrets、Security 的管理入口。
- Runtime Tasks 的列表与详情可见性。

## 已完成验证

### 前端

- `web -> npm run build` 已于 2026 年 3 月 10 日通过。

### 后端

- 目标 pytest 用例已于 2026 年 3 月 10 日至 3 月 11 日通过。
- smoke 流程已于 2026 年 3 月 11 日通过，覆盖：
  - Workflow 创建 / 发布 / 执行
  - Knowledge 上传 / ingest / 查询
  - Thread + Responses Runtime 执行
  - Secret 创建 / 测试

详细证据可见 [docs/SOIT_1.0_Release_Signoff_Summary.md](/f:/soit/soit-pro/docs/SOIT_1.0_Release_Signoff_Summary.md)。

## 已知约束

- `Tasks` 当前仍然是运行时任务视图，不是更广义的任务管理模块。
- Workflow Builder 当前只对齐到已支持的 `workflow.v1` runtime 子集。
- 正式对外发布前，仍建议由 owner 做一轮简短的 UI 点检。

详情见 [docs/SOIT_1.0_Known_Limitations.md](/f:/soit/soit-pro/docs/SOIT_1.0_Known_Limitations.md)。

## 建议发布顺序

1. Owner 按 [docs/SOIT_1.0_Owner_UI_Spotcheck.md](/f:/soit/soit-pro/docs/SOIT_1.0_Owner_UI_Spotcheck.md) 执行 UI 点检。
2. Owner 按 [docs/SOIT_1.0_Release_Checklist.md](/f:/soit/soit-pro/docs/SOIT_1.0_Release_Checklist.md) 完成最终 sign-off。
3. 团队在对外或对内沟通时，使用 [docs/SOIT_1.0_Known_Limitations.md](/f:/soit/soit-pro/docs/SOIT_1.0_Known_Limitations.md) 明确说明 deferred scope。

## 建议内部公告文案

截至 2026 年 3 月 11 日，SOIT 1.0 已完成工程验证与本地 smoke 验证。前端构建、目标后端合同测试，以及本地端到端主链路 smoke 均已通过。当前剩余工作已收敛为 release owner 的 UI 签收与常规发布协调，所有 deferred scope 已明确记录，并排除在 1.0 正式范围之外。
