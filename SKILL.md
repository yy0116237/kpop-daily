---
name: kpop-daily
description: 抓取公开 KPOP 新闻、视频与榜单，按粉丝偏好筛选并生成中文 HTML 日报。用户要求 KPOP 日报、追踪本命团动态、刷新日报数据或排查日报生成失败时使用；单纯记录日程、收藏或演唱会消费时不使用此 Skill。
---

# KPOP DAILY

生成可追溯的个性化 KPOP 日报。先确认用户的日期与偏好；未指定日期时使用当前 KST 日期，未指定偏好时使用 `scripts/profile.example.json`。

## 生成日报

从 Skill 根目录运行：

```bash
python scripts/run_daily.py
```

常用参数：

```bash
python scripts/run_daily.py --date 2026-09-09 --profile scripts/profile.example.json --top 30
python scripts/run_daily.py --no-translate
python scripts/run_daily.py --skip-melon
```

统一入口依次执行抓取与归一、个性化筛选、Melon 刷新和 HTML 构建。输出固定写入根目录 `dailies/`。不要手动执行旧的硬编码日期流程。

## 完成标准

- 同时保留 `<date>.json`、`<date>.personalized.json`、`<date>.personalized.md` 和 `<date>.personalized.html`。
- 报告实际成功取得的来源；某个来源失败时不得宣称它已参与当期日报。
- 新闻必须保留原文链接、来源、发布时间和发现时间。
- 榜单失败不阻断新闻日报；保留抓取阶段的可用榜单并明确降级。
- 不把 2.0 工作台描述成抓取器：`workbench/` 和 `kpop-note/` 只消费已有日报并管理个人记录。

## 网络与等待

每次 HTTP 请求有超时，失败采用有限次数退避重试；流水线阶段也有总超时。不要无限等待或无上限重试。遇到持续网络失败时，保留已生成文件，报告失败来源和可恢复命令。

需要解释数据源、抓取方式、等待/重试、降级或定时运行时，读取 [references/operations.md](references/operations.md)。

## 个性化

复制 `scripts/profile.example.json` 并修改本命团、性别偏好、代际、公司和常巡演团体。不要直接修改评分脚本来保存每位用户的偏好。

## 2.0 工作台

本地版运行 `python workbench/server.py`，读取根目录 `dailies/` 中最新日报，并把日程、收藏、Con 记录和账本保存在 `workbench/data.json`。它不会自动刷新外部数据；需要新日报时先运行统一入口。
