# -*- coding: utf-8 -*-
"""生成 KPOP 个性化日报的单文件网页版 (数据内联, 双击即开)。"""
import json, html, os

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "dailies", "2026-08-15.personalized.json")
OUT = os.path.join(ROOT, "dailies", "2026-08-15.personalized.html")

DATA = json.load(open(SRC, encoding="utf-8"))

# 板块顺序与中文标签
SECTION_ORDER = ["回归·新曲发行", "舞台·打歌", "热点·话题", "官宣·事件", "数据·榜单"]
SECTION_SUB = {
    "回归·新曲发行": "Comeback · 新曲发行",
    "舞台·打歌": "Stage · 打歌舞台",
    "热点·话题": "Trend · 热点话题",
    "官宣·事件": "Event · 官宣事件",
    "数据·榜单": "Chart · 数据榜单",
}
SECTION_ACCENT = {
    "回归·新曲发行": "#e85aad",
    "舞台·打歌": "#7c5cff",
    "热点·话题": "#ff8a3d",
    "官宣·事件": "#2bb3a3",
    "数据·榜单": "#3b6fe0",
}


def esc(t):
    return html.escape(t or "", quote=True)


def chip(text, kind):
    cls = "chip chip-group" if kind == "group" else "chip chip-idol"
    return '<span class="%s">%s</span>' % (cls, esc(text))


def fmt_date(iso):
    # 2026-08-15T10:50:35... -> 2026-08-15 10:50
    if not iso:
        return ""
    return iso[:16].replace("T", " ")


def item_card(it):
    title = it.get("title", "")
    link = (it.get("links") or {}).get("original", "")
    src = (it.get("source") or {}).get("name", "")
    summary = it.get("summary", "")
    groups = it.get("groups", []) or []
    idols = it.get("idols", []) or []
    dup = it.get("dupCount", 0)

    title_html = esc(title)
    if link:
        title_html = '<a class="ttl" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(link), title_html)
    else:
        title_html = '<span class="ttl">%s</span>' % title_html

    chips = ""
    for g in groups:
        chips += chip(g, "group")
    for p in idols:
        chips += chip(p, "idol")

    dup_badge = '<span class="dup">聚合 %d 条</span>' % dup if dup and dup > 1 else ""

    summary_html = ""
    if summary:
        s = summary.strip()
        if s != title.strip():
            summary_html = '<p class="sum">%s</p>' % esc(s)

    return (
        '<li class="item">'
        '<div class="item-main">'
        '%s'
        '%s'
        '%s'
        '</div>'
        '<div class="meta"><span class="src">%s</span>%s</div>'
        '</li>'
        % (title_html, chips, summary_html, esc(src), dup_badge)
    )


def chart_row(it):
    rank = it.get("consensusRank", "")
    title = esc(it.get("title", ""))
    summary = esc(it.get("summary", ""))
    groups = it.get("groups", []) or []
    chips = "".join(chip(g, "group") for g in groups)
    return (
        '<li class="crow">'
        '<span class="rk">%s</span>'
        '<div class="cmain"><span class="ctitle">%s</span>%s'
        '<span class="csum">%s</span></div>'
        '</li>'
        % (rank, title, chips, summary)
    )


def section_block(sec):
    label = sec.get("label", "")
    items = sec.get("items", []) or []
    accent = SECTION_ACCENT.get(label, "#888")
    sub = SECTION_SUB.get(label, "")
    if not items:
        body = '<p class="empty">本版块本次为空。</p>'
    elif label == "数据·榜单":
        body = '<ol class="clist">%s</ol>' % "".join(chart_row(i) for i in items)
    else:
        body = '<ul class="ilist">%s</ul>' % "".join(item_card(i) for i in items)
    return (
        '<section class="sec" style="--accent:%s">'
        '<header class="sec-head"><span class="dot"></span>'
        '<h2>%s</h2><span class="sec-sub">%s</span>'
        '<span class="sec-count">%d</span></header>'
        '%s'
        '</section>'
        % (accent, esc(label), esc(sub), len(items), body)
    )


def meta_badges(pz):
    fav = pz.get("favoriteGroups", []) or []
    gen = pz.get("generations", []) or []
    comp = pz.get("companies", []) or []
    gd = {"female-priority": "女团优先", "male-priority": "男团优先",
          "both": "男女都看", "fav-only": "只看本命团"}.get(pz.get("gender", ""), pz.get("gender", ""))
    parts = []
    if fav:
        parts.append(("本命团", "、".join(fav)))
    if gd:
        parts.append(("偏好", gd))
    if gen:
        parts.append(("代际", "/".join(str(g) + "代" for g in gen)))
    if comp:
        parts.append(("公司", "、".join(comp)))
    return "".join('<span class="pz"><b>%s</b> %s</span>' % (esc(k), esc(v)) for k, v in parts)


def flashes_strip(flashes):
    if not flashes:
        return ""
    items = []
    for f in flashes[:5]:
        link = f.get("link", "")
        t = esc(f.get("text", ""))
        if link:
            items.append('<a class="flash" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(link), t))
        else:
            items.append('<span class="flash">%s</span>' % t)
    return '<div class="flashes">%s</div>' % "".join(items)


# ---- 组装 ----
pz = DATA.get("personalization", {})
lead = esc(DATA.get("lead", ""))
gen = fmt_date(DATA.get("generatedAt", ""))
date = esc(DATA.get("date", ""))
attr_src = "、".join(DATA.get("attribution", {}).get("sources", []))
attr_note = esc(DATA.get("attribution", {}).get("note", ""))

# 排序版块
ordered = []
for lab in SECTION_ORDER:
    for s in DATA["sections"]:
        if s.get("label") == lab:
            ordered.append(s)
            break
# 补上任何未列顺序的版块
for s in DATA["sections"]:
    if s.get("label") not in SECTION_ORDER:
        ordered.append(s)

sections_html = "".join(section_block(s) for s in ordered)
pz_html = meta_badges(pz)
flash_html = flashes_strip(DATA.get("flashes", []))

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KPOP DAILY · for you · @@DATE@@</title>
<style>
  :root{
    --bg:#f4f5fa; --card:#ffffff; --ink:#1f2333; --muted:#707688;
    --line:#e8eaf2; --accent:#e85aad; --soft:#faf6fb;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    line-height:1.6; -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:920px; margin:0 auto; padding:0 18px 60px}
  /* Hero */
  .hero{
    background:linear-gradient(120deg,#ff8fc7 0%%,#c79bff 55%%,#8fb6ff 100%);
    color:#2a1136; padding:34px 18px 30px; border-radius:0 0 26px 26px;
    box-shadow:0 10px 30px rgba(180,120,220,.18);
  }
  .hero-in{max-width:920px; margin:0 auto; padding:0 18px}
  .kicker{font-size:13px; letter-spacing:3px; color:#5a1f63; font-weight:700}
  .hero h1{margin:6px 0 4px; font-size:30px; line-height:1.25; color:#241033}
  .hero .date{font-size:15px; color:#3a1840; font-weight:600}
  .pzbar{margin-top:16px; display:flex; flex-wrap:wrap; gap:8px}
  .pz{background:rgba(255,255,255,.66); backdrop-filter:blur(4px);
      border:1px solid rgba(255,255,255,.85); color:#2a1136;
      padding:5px 11px; border-radius:999px; font-size:12.5px}
  .pz b{font-weight:700; margin-right:4px; opacity:.9}
  /* Lead */
  .lead{
    background:var(--card); border:1px solid var(--line); border-left:5px solid var(--accent);
    border-radius:14px; padding:18px 20px; margin:22px 0 6px;
    box-shadow:0 6px 18px rgba(60,40,90,.06);
  }
  .lead .lab{font-size:12px; font-weight:700; color:var(--accent); letter-spacing:1px}
  .lead .lt{font-size:19px; font-weight:700; margin-top:4px}
  .flashes{display:flex; flex-wrap:wrap; gap:8px; margin:14px 0 4px}
  .flash{font-size:12.5px; color:var(--muted); text-decoration:none;
    background:#f1f2f8; border:1px solid var(--line); padding:6px 10px; border-radius:10px}
  .flash:hover{color:var(--ink); border-color:#d7c8ee}
  /* Sections */
  .sec{background:var(--card); border:1px solid var(--line); border-radius:16px;
    padding:18px 20px 20px; margin-top:18px; box-shadow:0 6px 18px rgba(60,40,90,.05)}
  .sec-head{display:flex; align-items:center; gap:10px; margin-bottom:12px}
  .dot{width:10px; height:10px; border-radius:50%%; background:var(--accent)}
  .sec-head h2{font-size:18px; margin:0}
  .sec-sub{font-size:12px; color:var(--muted); letter-spacing:1px}
  .sec-count{margin-left:auto; font-size:12px; font-weight:700; color:#fff;
    background:var(--accent); padding:2px 10px; border-radius:999px}
  .ilist{list-style:none; margin:0; padding:0; display:grid;
    grid-template-columns:repeat(3,1fr); gap:14px}
  .item{border:1px solid var(--line); border-radius:12px; padding:13px 14px;
    background:var(--soft); display:flex; flex-direction:column; gap:7px}
  .crow{border-bottom:1px dashed var(--line); padding:7px 0}
  .item:last-child, .crow:last-child{border-bottom:none}
  .item-main{display:flex; flex-direction:column; gap:7px}
  .ttl{font-size:15.5px; font-weight:600; color:var(--ink); text-decoration:none}
  .ttl:hover{color:var(--accent)}
  .chips{display:flex; flex-wrap:wrap; gap:6px}
  .chip{font-size:11.5px; padding:2px 9px; border-radius:999px; font-weight:600}
  .chip-group{background:#fdeaf4; color:#c23b8e; border:1px solid #f7d2e6}
  .chip-idol{background:#eef0ff; color:#5a47d6; border:1px solid #dfe1ff}
  .sum{margin:2px 0 0; font-size:13px; color:var(--muted)}
  .meta{margin-top:6px; display:flex; align-items:center; gap:10px; font-size:12px; color:var(--muted)}
  .src{background:#f1f2f8; padding:2px 8px; border-radius:7px}
  .dup{background:#fff5e6; color:#b9772a; border:1px solid #ffe2b8; padding:2px 8px; border-radius:7px}
  /* Chart list */
  .clist{list-style:none; margin:0; padding:0; counter-reset:none}
  .crow{display:flex; gap:13px; align-items:flex-start}
  .rk{flex:0 0 38px; height:38px; border-radius:10px; background:linear-gradient(135deg,#dbe6ff,#c9d4ff);
    color:#28407e; font-weight:800; font-size:16px; display:flex; align-items:center; justify-content:center}
  .cmain{display:flex; flex-direction:column; gap:3px; padding-top:1px}
  .ctitle{font-size:14.5px; font-weight:600}
  .csum{font-size:12px; color:var(--muted)}
  .empty{color:var(--muted); font-size:13px; padding:6px 0}
  footer{margin-top:26px; font-size:12px; color:var(--muted); text-align:center; line-height:1.7}
  footer .srcs{color:#9aa0b4}
  @media(max-width:760px){
    .ilist{grid-template-columns:repeat(2,1fr)}
    .hero h1{font-size:26px}
  }
  @media(max-width:480px){
    .ilist{grid-template-columns:1fr}
    .hero h1{font-size:22px}
    .lead .lt{font-size:16px}
  }
</style>
</head>
<body>
  <div class="hero">
    <div class="hero-in">
      <h1>KPOP DAILY · for you</h1>
      <div class="date">@@DATE@@ ｜ 生成于 @@GEN@@ (KST)</div>
      <div class="pzbar">@@PZ@@</div>
    </div>
  </div>
  <div class="wrap">
    <div class="lead">
      <div class="lab">今日头条 LEAD</div>
      <div class="lt">@@LEAD@@</div>
    </div>
    @@FLASHES@@
    @@SECTIONS@@
    <footer>
      <div>数据来源：<span class="srcs">@@ATTR@@</span></div>
      <div>@@NOTE@@</div>
      <div>新闻按个性化打分取 Top 30（重要程度 × 你的偏好）；数据·榜单为独立 Melon 单源，不参与排序。</div>
    </footer>
  </div>
</body>
</html>
"""
for _k,_v in [("DATE",date),("GEN",gen),("PZ",pz_html),("LEAD",lead),
              ("FLASHES",flash_html),("SECTIONS",sections_html),
              ("ATTR",esc(attr_src)),("NOTE",attr_note)]:
    HTML=HTML.replace("@@%s@@"%_k,_v)

open(OUT, "w", encoding="utf-8").write(HTML)
print("written:", OUT, len(HTML), "bytes")
