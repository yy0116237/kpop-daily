# KPOP DAILY · 系列（1.0 晨报 → 2.0 工作台）

> 一个 KPOP 粉丝的全套数字化工具箱：**1.0 每日资讯晨报生成器** + **2.0 粉丝个人记录工作台**（本地版 & 资料库版）。

---

## 系列总览

| 版本 | 形态 | 目录 | 一句话 |
| --- | --- | --- | --- |
| 1.0 | 每日晨报生成器（WorkBuddy skill / 脚本） | 仓库根（SKILL.md / scripts/） | 自动抓新闻 + Melon 音源榜，按你的偏好排 Top 30，产出单文件 HTML 晨报 |
| 2.0 本地版 | 零依赖本地工作台 | `workbench/` | 日报 × 日程 × 收藏 × Con 记忆 × 账本，Python 标准库 + JSON 本地运行（端口 8765） |
| 2.0 资料库版 | 单文件轻应用（参赛版） | `kpop-note/` | **KPOP NOTE · 日报 × 记录**：HTML ↔ CSV 双向同步、数据在线存储，可发布为 workbuddy.link 链接 |

### 快速开始
- **1.0 晨报**：见下方《KPOP DAILY · for you（1.0 · 每日晨报）》完整说明；或把本仓库作为 skill 复制到 `~/.workbuddy/skills/kpop-daily/` 后，对 WorkBuddy 说「帮我生成今天的 KPOP 日报」。
- **2.0 本地工作台**：`cd workbench && python server.py` → 打开 http://localhost:8765（数据存 `workbench/data.json`，日报联动读取上级 `dailies/`）。
- **2.0 资料库版**：把 `kpop-note/kpop-note-workspace.html` 上传到 WorkBuddy 资料库 → 打开文件与配套 CSV 表格双向同步 → 「分享 → 发布为网站」得到 workbuddy.link 链接；离线打开自动降级本地存储，功能完整。

---

# KPOP DAILY · for you（1.0 · 每日晨报）

> 一份「为你定制」的 KPOP 每日资讯晨报生成器。纯免费、零 API Key，自动抓新闻 + 音源榜，按你的偏好打分排序，产出单文件 HTML。

---

## 一、简单介绍

**KPOP DAILY · for you** 是一个可复用的脚本集合，用来生成一份**个性化 KPOP 每日晨报**：

- 自动抓取当天 KPOP 新闻（回归、舞台、热点、官宣）和韩国最大音源榜 **Melon** 的实时排名；
- 把新闻标题 / 摘要翻译成中文（人名用「中文（English）」格式，团名 / 歌名保持原文）；
- 根据你填写的偏好（本命团、代际、男女团、公司、常 tour 团）打分排序，挑出**新闻 Top 30**；
- 最终生成一份**单文件 HTML 网页**——深色渐变版头、新闻三列网格、音源榜单紧凑排列，双击即可在浏览器打开，也方便分享。

整个项目**不依赖任何付费 API**，所有数据源都是公开、免费、无需 Key 的。

---

## 二、目的

- 给 KPOP 粉丝一份「每天花 3 分钟就能看完」的定制化资讯，而不是被信息流淹没；
- 让日报**跟着你的口味走**：你本命的团、你偏好的代际 / 公司 / 性别构成，决定哪些新闻排前面；
- 提供一个**可分享、可重跑、可二次开发**的模板，任何人都能换成自己的本命团和审美。

---

## 三、主要内容

### 固定版块（5 个）
| 版块 | 内容 |
| --- | --- |
| 回归·新曲发行 | 新歌 / MV / 专辑发行 |
| 舞台·打歌 | 打歌舞台、竞演、获奖 |
| 热点·话题 | 话题趋势、热议事件 |
| 官宣·事件 | 公司官宣、行程、成员动态 |
| 数据·榜单 | Melon 实时音源榜 Top 30（独立，不参与新闻排序） |

### 日报结构
- **Hero 版头**：标题 + 日期 + 你的偏好徽章（本命团 / 代际 / 公司）
- **今日头条 LEAD**：当日最高分的一条新闻
- **快讯条**：热门聚合链接
- **五大版块**：新闻三列网格，榜单单列紧凑
- **页脚**：数据来源与说明

### 核心能力
- ✅ 纯免费零 Key 信息源（RSS / YouTube RSS / Melon / gtx 翻译）
- ✅ 中文（English）人名本地化，团名 / 歌名原文保留
- ✅ 个性化打分排序（重要程度 × 你的偏好）
- ✅ 单文件 HTML 输出，自带响应式（手机 / 平板 / 桌面）
- ✅ JSON Schema 校验，保证数据结构稳定

---

## 四、技术栈与数据源

| 用途 | 来源 | 是否免费 |
| --- | --- | --- |
| 新闻 RSS | Soompi / Allkpop / Koreaboo | ✅ |
| 团体新闻 | Google News RSS（按团名查询） | ✅ |
| 回归信号 | YouTube 频道 RSS（免 Key） | ✅ |
| 音源榜 | Melon 实时榜（带 Cookie 破反爬） | ✅ |
| 翻译 | Google `gtx` + MyMemory 兜底 | ✅ |
| 网页 | 原生 HTML/CSS，无框架 | ✅ |

**已知限制**
- 沙箱共享 IP 偶尔会触发 Melon 限流；`patch_melon.py` 已带「单发直连 + 重试 + Cookie」，失败重跑即可。
- Spotify 免费端点需要 OAuth，暂不可用，因此音源榜用 **Melon 单源**。
- 新闻为英文 RSS，翻译依赖 gtx / MyMemory，偶有不稳定的情况。

---

## 五、其他人如何使用

### 方式 A：作为 skill 使用
1. 把 `kpop-daily-skill/` 整个目录复制到：
   - 用户级
   - 或项目级
2. 在agent对话中说"帮我生成今天的 KPOP 日报"，skill 会自动加载并按流程执行。

### 方式 B：直接用脚本（任意 Python 环境）
无需 WorkBuddy，只要有 Python 3.9+：

```bash
cd kpop-daily-skill/scripts
python kpop_daily_proto.py     # 1. 抓取新闻 + 图表
python retra_final.py          # 2. 对入选内容重翻
python personalize_report.py   # 3. 按偏好打分排序 Top 30
python patch_melon.py          # 4. 抓取 Melon 音源榜
python build_html.py           # 5. 生成 HTML
```

生成的 `dailies/<日期>.personalized.html` 就是成品，双击打开即可。

---

## 六、个性化配置（最重要的一步）

打开 `scripts/personalize_report.py`，修改**文件顶部**的几个变量：

```python
FAV = {"TWICE", "LE SSERAFIM", "NMIXX", "ILLIT", "KIIKIII", "IVE"}  # 你的本命团
GENDER_PREF = "F"        # 女团为主: "F" / 男团为主: "M" / 都看: "B"
GEN_PREF = {4, 5}        # 偏好的代际, 例如 4代+5代
COMPANY_PREF = {"HYBE", "JYP"}   # 偏好的公司
TOUR_HEAVY = {"Stray Kids", "BTS", "TWICE", ...}  # 常办 tour 的团(加分)
```

并在 `GROUP_META` 里补充你追踪团体的元数据 `(性别, 代际, 公司)`，例如：
```python
"NewJeans": ("F", 4, "HYBE"),
```

想换追踪的团体，编辑 `scripts/kpop_daily_proto.py` 顶部的 `GROUPS` 列表。

---

## 七、目录结构

```
kpop-daily-skill/
├── SKILL.md              # WorkBuddy skill 描述（加载用）
├── README.md             # 本文档
├── demo.html             # 一份示例成品（2026-08-15），先看效果
└── scripts/
    ├── kpop_daily_proto.py   # 抓取 + 归一 + 分版块
    ├── chart_align.py        # 多源榜单共识对齐
    ├── name_localization.py  # 人名本地化 / 团名保护
    ├── retra_final.py        # 仅对入选内容重翻
    ├── personalize_report.py # 偏好打分排序 Top 30
    ├── patch_melon.py        # Melon 音源榜抓取替换
    ├── build_html.py         # 生成单文件 HTML
    └── kpop_daily.schema.json# 输出 JSON Schema 校验
```

> 运行脚本时，**在 `scripts/` 目录下执行**即可，所有 `dailies/` 与 `*.schema.json` 相对路径都会自动落到该目录内。

---

## 八、可扩展方向

- **换翻译后端**：把 `gtx` 换成自托管 LibreTranslate / 正式翻译 API / LLM 摘要。
- **加团体**：改 `kpop_daily_proto.py` 的 `GROUPS`。
- **多源榜单**：恢复 Circle / Bugs 做交叉验证（见 `chart_align.py`）。
- **定时推送**：用自动化（cron / WorkBuddy 自动化）每天定时生成并发到飞书 / 邮件 / 群里。
- **换审美**：直接改 `build_html.py` 里的 CSS（版头渐变、三列网格、榜单间距等）。

---

## 九、许可证

本项目按 MIT 许可证开源，可自由使用、修改、再分发。数据源请遵守各站点的使用条款。
