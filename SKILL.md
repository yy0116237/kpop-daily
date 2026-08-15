---
name: kpop-daily
description: 生成「KPOP DAILY · for you」个性化每日 KPOP 资讯晨报。纯免费零 API Key 自动抓取 KPOP 新闻(RSS/YouTube)与 Melon 音源榜，按用户本命团/代际/男女团/公司偏好打分排序出新闻 Top 30，并产出单文件 HTML 网页。当用户要求"做一份 KPOP 每日日报/晨报""按我的偏好定制 KPOP 新闻""KPOP 每日资讯"时使用。
---

# KPOP DAILY · for you

生成一份「为你定制」的 KPOP 每日资讯晨报：自动抓取当日 KPOP 新闻与音源榜，翻译为中文，按你的偏好打分排序，最后产出一份单文件 HTML 网页（深色版头、新闻三列网格、音源榜单紧凑排列）。

## 何时使用
- 用户要"生成今天的 KPOP 日报 / 晨报"
- 用户要"按我的本命团 / 偏好定制 KPOP 新闻"
- 用户想每天或定期收到量身定制的 KPOP 资讯

## 信息源（全部免费、零 API Key）
- **新闻**：Soompi / Allkpop / Koreaboo RSS、Google News RSS（按团体名查询）、YouTube 频道 RSS（新视频 = 回归信号）
- **音源榜**：Melon 实时榜（带 Cookie 破解反爬，单发直连）
- **翻译**：Google `gtx`（沙箱可用）兜底 MyMemory（免费额度，常被 429 限流）

## 工作流程
1. `kpop_daily_proto.py` — 抓取新闻 + 图表，归一为 item，分 5 版块，输出 `dailies/<date>.json`
2. `name_localization.py` — 人名「中文（English）」本地化；团名 / 歌名 / 专辑名不翻译
3. `retra_final.py` — 只对入选日报的内容重翻（避免噪声项被翻译改写）
4. `personalize_report.py` — 按用户偏好打分排序，筛选新闻 Top 30，榜单独立保留 → `*.personalized.json/.md`
5. `patch_melon.py` — 抓取 Melon 实时音源榜，替换「数据·榜单」版块
6. `build_html.py` — 由 `*.personalized.json` 生成单文件 HTML 网页

## 个性化配置
编辑 `scripts/personalize_report.py` 顶部：
- `FAV` 本命团集合、`GENDER_PREF` 男女偏好、`GEN_PREF` 代际、`COMPANY_PREF` 公司、`TOUR_HEAVY` 常 tour 团
- `GROUP_META` 团体元数据（性别 / 代际 / 公司）按需补充

## 运行
在 `scripts/` 目录按上述顺序运行（所有相对路径从脚本目录解析）：
```bash
cd scripts
python kpop_daily_proto.py
python retra_final.py
python personalize_report.py
python patch_melon.py
python build_html.py
```
输出：`dailies/<date>.personalized.html`（双击即开）。

## 已知限制
- 沙箱共享 IP 对 Melon 间歇限流；`patch_melon.py` 已带单发 + 重试 + Cookie，失败可重跑
- Spotify 免费端点不可用（需 OAuth），故「数据·榜单」采用 Melon 单源
- 新闻源为英文 RSS，翻译依赖 gtx / MyMemory，偶有不稳定

## 可扩展
- 调 `kpop_daily_proto.py` 的 `GROUPS` 增加追踪团体
- 替换翻译后端为 LibreTranslate / 正式 API / LLM
- 接入自动化（每日定时生成日报）
