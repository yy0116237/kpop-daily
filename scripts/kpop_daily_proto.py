#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KPOP Daily — 最小可运行原型 (proves: 抓取 -> 归一Item -> 分5版块 -> 输出 /dailies JSON)
纯免费栈, 只读请求, 无前端. 复用 chart_align.py 做榜单共识对齐.
运行: python kpop_daily_proto.py
"""
import json, os, re, html, sys, datetime, hashlib, difflib, concurrent.futures as cf
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_align as ca
import name_localization as nl

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
KST = datetime.timezone(datetime.timedelta(hours=9))

# 真实中文摘要层: 无 Key 免费翻译.
# 后端优先 gtx (沙箱共享IP下当前可用), MyMemory 作兜底 (免费额度 5000 词/天, 常被429).
# 生产可替换为自托管 LibreTranslate / 正式翻译 API / LLM 摘要.
TRANSLATE_BACKEND = "gtx"

# ---- 原型追踪团体(易扩展) ----
GROUPS = [
    {"name": "BTS",          "yt": "BTS"},
    {"name": "NewJeans",     "yt": "NewJeans"},
    {"name": "LE SSERAFIM",  "yt": "LESSERAFIM"},
    {"name": "BLACKPINK",    "yt": "BLACKPINK"},
    {"name": "Stray Kids",   "yt": "StrayKids"},
    {"name": "aespa",        "yt": "aespa"},
]

# 5 固定版块 -> category
SECTION_LABELS = ["回归·新曲发行", "舞台·打歌", "热点·话题", "官宣·事件", "数据·榜单"]
CAT2SEC = {"comeback": 0, "stage": 1, "trend": 2, "event": 3, "chart": 4}

# ---- KPOP 相关性 & 语义去重 ----
GROUP_ALIASES = {
    "BTS": ["방탄소년단"],
    "NewJeans": ["뉴진스", "njz"],
    "LE SSERAFIM": ["르세라핌"],
    "BLACKPINK": ["블랙핑크"],
    "Stray Kids": ["스트레이 키즈", "skz"],
    "aespa": ["에스파"],
}
KPOP_KW = ["k-pop", "kpop", "idol", "comeback", "mv", "music video",
           "빌보드", "가수", "아이돌"]

def detect_groups(text):
    """在文本中识别追踪团体 (含韩文/别名匹配), 返回团体名列表."""
    t = (text or "").lower()
    found = []
    for g in GROUPS:
        name = g["name"].lower()
        if name in t:
            found.append(g["name"]); continue
        for al in GROUP_ALIASES.get(g["name"], []):
            if al.lower() in t:
                found.append(g["name"]); break
    return found

def is_kpop_relevant(text):
    """是否为 KPOP 相关内容 (团体命中 或 含 KPOP 关键词)."""
    t = (text or "").lower()
    if any(k in t for k in KPOP_KW):
        return True
    return bool(detect_groups(text))

_STOP = set("to a an the of for in on is are was were will their with at by and or "
            "new set drop release announce announced return comeback mv official video "
            "music from about via into out up off over after before".split())
def core_title(t):
    """去停用词, 仅留实义 token, 用于相似度比较."""
    toks = re.findall(r"[a-z0-9가-힣]+", (t or "").lower())
    return " ".join(w for w in toks if w not in _STOP)

def _epoch(it):
    p = it.get("publishedAt")
    if not p:
        return 0
    try:
        return datetime.datetime.fromisoformat(p).timestamp()
    except Exception:
        return 0

def semantic_dedupe(items, thr=0.7):
    """同 category 内: 共享团体 且 标题核心相似 -> 合并为一条(保留 dupCount)."""
    by_cat = {}
    for it in items:
        by_cat.setdefault(it.get("category"), []).append(it)
    out = []
    for cat, arr in by_cat.items():
        clusters = []
        for it in arr:
            ct = core_title(it.get("originalTitle") or it.get("title", ""))
            placed = False
            for c in clusters:
                rep = c[0]
                cr = core_title(rep.get("originalTitle") or rep.get("title", ""))
                ratio = difflib.SequenceMatcher(None, cr, ct).ratio()
                rep_g = set(rep.get("groups", []))
                it_g = set(it.get("groups", []))
                shared = bool(rep_g & it_g)
                # 共享团体 -> 0.7 即可; 都无团体 -> 需极高相似(0.95)
                if shared and ratio >= thr:
                    c.append(it); placed = True; break
                if not rep_g and not it_g and ratio >= 0.95:
                    c.append(it); placed = True; break
            if not placed:
                clusters.append([it])
        for c in clusters:
            if len(c) == 1:
                out.append(c[0]); continue
            rep = sorted(c, key=lambda x: (0 if x["source"]["name"] == "Soompi" else 1,
                                           x.get("publishedAt") or ""))[0]
            rep = dict(rep)
            rep["groups"] = sorted(set(sum((x.get("groups", []) for x in c), [])))
            rep["dupCount"] = len(c)
            out.append(rep)
    return out

def pick_lead(items):
    """头条: 只在 KPOP 相关、非榜单条目中选; 优先新闻源(news), 其次按 comeback>stage>event>trend 且最新."""
    rel = [i for i in items if i.get("category") != "chart"
           and (i.get("groups") or is_kpop_relevant(i.get("originalTitle", "")))]
    if not rel:
        rel = [i for i in items if i.get("category") != "chart"]
    if not rel:
        return "今日 KPOP 资讯已聚合。"
    order = {"comeback": 0, "stage": 1, "event": 2, "trend": 3}
    # 头条优先新闻源 (Soompi/Google News), 比 SNS/视频更适合做导语
    news = [i for i in rel if i.get("source", {}).get("type") == "news"]
    pool = news if news else rel
    pool = sorted(pool, key=lambda x: (order.get(x.get("category"), 9), -_epoch(x)))
    return pool[0]["title"]


# ---------------- 基础工具 ----------------
def fetch(url, headers=None, data=None, timeout=25, retries=3):
    h = dict(UA); h.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            continue
    raise last or RuntimeError("fetch failed: %s" % url)


_trans_cache = {}

# 翻译保护: 用占位符把 团名 与 引号内歌名/专辑名 暂存, 翻译后再还原,
# 使其保持英文/韩文原样 (用户要求: 团名/歌名/专辑名不翻译为中文).
_PROT_RE = re.compile(r"([\"'「『][^\"'「『]{1,80}[\"'」』])")

def _protect_proper(text):
    restore = []
    def stash(tok):
        restore.append(tok)
        return "@@P%d@@" % (len(restore) - 1)
    # 1) 团名 (en/ko 形态, 整词) -> 占位 (人名不在此列, 照常翻译/包裹)
    for form, en in nl.GROUP_FORMS.items():
        text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(form) + r"(?![A-Za-z0-9])",
                      lambda m, e=en: stash(e), text, flags=re.I)
    # 2) 引号内歌名/专辑名 -> 占位
    text = _PROT_RE.sub(lambda m: stash(m.group(1)), text)
    return text, restore

def _restore_proper(text, restore):
    def repl(m):
        idx = int(m.group(1))
        return restore[idx] if idx < len(restore) else m.group(0)
    return re.sub(r"@@P(\d+)@@", repl, text)

def _detect_sl(text):
    """源语种: 含韩文 -> ko, 否则 en."""
    return "ko" if re.search(r"[\uac00-\ud7a3]", text or "") else "en"

def _gtx_translate(text, sl="en", to="zh-CN", timeout=15):
    """Google gtx 无Key 翻译 (沙箱共享IP下当前可用; MyMemory 被429限流时兜底)."""
    u = ("https://translate.google.com/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t&q=%s"
         % (sl, to, urllib.parse.quote(text[:500], safe="")))
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg[0])

def _mymemory_translate(text, sl="en", to="zh-CN", timeout=12):
    """MyMemory 无Key 翻译 (免费额度 5000 词/天, 沙箱下常被429限流)."""
    q = urllib.parse.quote(text[:500], safe="")
    url = "https://api.mymemory.translated.net/get?q=%s&langpair=%s|%s" % (q, sl, to)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("responseData") or {}).get("translatedText", "")

def translate(text, to="zh-CN", sl=None):
    """真实中文翻译. 团名/引号内歌名专辑名受保护不被改写; 带进程内缓存.
    后端顺序: gtx(当前可用) -> mymemory(兜底); 两者皆失败则回退原文."""
    if not text or not text.strip():
        return text
    sl = sl or _detect_sl(text)
    key = (sl, to, text.strip()[:500])
    if key in _trans_cache:
        return _trans_cache[key]
    protected, restore = _protect_proper(text)
    out = text
    for backend in ("gtx", "mymemory"):
        try:
            t = (_gtx_translate(protected, sl, to) if backend == "gtx"
                 else _mymemory_translate(protected, sl, to))
            if t and t.strip():
                t = _restore_proper(t, restore)
                out = t
                break
        except Exception:
            continue
    _trans_cache[key] = out
    return out

def translate_items(report, max_workers=5):
    """批量并发回填中文 title/summary (跳过榜单版块, 其展示名已是合成名)."""
    jobs = []
    for s in report["sections"]:
        if s["label"] == "数据·榜单":
            continue
        jobs.extend(s["items"])
    if not jobs:
        return report

    def work(it):
        orig = it.get("originalTitle") or it.get("title", "")
        zh = translate(orig)
        if zh and zh != orig:
            it["title"] = zh
            it["lang"] = "zh"
        # summary: 优先翻译描述(更接近"摘要"), 无描述则用标题截断
        desc = (it.get("originalDesc") or "").strip()
        if desc:
            zs = translate(desc)
            it["summary"] = (zs if (zs and zs != desc) else (zh or orig))[:60]
        else:
            it["summary"] = (zh or orig)[:60]
        # 艺名中文化: 标题/摘要 替换成「中文（English）」; 结构化标签同步本地化
        it["title"] = nl.localize_names(it["title"])
        it["summary"] = nl.safe_summary(nl.localize_names(it["summary"]))
        it["groups"] = nl.localize_groups(it.get("groups", []))
        it["idols"] = nl.detect_idols(orig + " " + (it.get("originalDesc") or ""))

    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, jobs))
    return report


def parse_rss(url, limit=200):
    xml = fetch(url)
    root = ET.fromstring(xml)
    out = []
    for it in root.findall(".//item"):
        def g(t):
            e = it.find(t)
            return (e.text or "") if e is not None else ""
        out.append({
            "title": g("title").strip(),
            "link": g("link").strip(),
            "pub": g("pubDate").strip(),
            "desc": re.sub(r"<[^>]+>", "", g("description")).strip(),
        })
        if len(out) >= limit:
            break
    return out


def rss_to_kst(pub):
    try:
        dt = parsedate_to_datetime(pub)
        if dt is None:
            return None
        return dt.astimezone(KST)
    except Exception:
        return None


def iso(dt):
    return dt.isoformat() if dt else None


def norm_title(t):
    return re.sub(r"\W+", "", (t or "").lower())


def detect_category(text):
    t = (text or "").lower()
    if re.search(r"comeback|回归|컴백|mv|music video|new (song|single|album|mini)|debut|teaser|트레iler", t):
        return "comeback"
    if re.search(r"\bwin\b|1st place|first place|음악방송|1위|핫스테이지|stage|performance|music show|\brank\b", t):
        return "stage"
    if re.search(r"tour|concert|콘서트|투어|contract|renew|재계약|계약|announce|confirm|발표|확정|dispatch|lawsuit|소송|endorse|ambassador|예능|variety", t):
        return "event"
    return "trend"


def make_item(original_title, link, pub_kst, source_name, source_type, category,
              groups, company="", lang="en", desc=""):
    # 注: 中文摘要(翻译)延迟到 translate_items 批量并发回填, 避免逐条串行拖慢流水线.
    now = datetime.datetime.now(KST)
    iid = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    return {
        "id": "sha1:%s" % iid,
        "title": original_title,
        "originalTitle": original_title,
        "originalDesc": desc,
        "summary": (original_title or "")[:60],
        "source": {"name": source_name, "type": source_type},
        "links": {"original": link},
        "publishedAt": iso(pub_kst) or iso(now),
        "discoveredAt": iso(now),
        "category": category,
        "groups": groups,
        "idols": [],
        "company": company,
        "selected": True,
        "lang": lang,
    }


# ---------------- 各源 worker ----------------
def worker_soompi(acc):
    try:
        for r in parse_rss("https://www.soompi.com/feed", limit=25):
            text = r["title"] + " " + r["desc"]
            cat = detect_category(text)
            groups = detect_groups(text)
            acc.append(make_item(r["title"], r["link"], rss_to_kst(r["pub"]),
                                 "Soompi", "news", cat, groups, lang="en", desc=r["desc"]))
        print("  [soompi] ok")
    except Exception as e:
        print("  [soompi] FAIL", e)


def worker_googlenews(acc):
    for g in GROUPS:
        try:
            url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(g["name"])
                   + "&hl=en-US&gl=US&ceid=US:en")
            for r in parse_rss(url, limit=12):
                head = r["title"]
                m = re.match(r"^(.*?)\s+-\s+[^-]+$", head)
                title = m.group(1) if m else head
                cat = detect_category(title + " " + r["desc"])
                acc.append(make_item(title, r["link"], rss_to_kst(r["pub"]),
                                     "Google News", "news", cat, [g["name"]], lang="en", desc=r["desc"]))
        except Exception as e:
            print("  [googlenews:%s] FAIL" % g["name"], e)
    print("  [googlenews] ok")


YT_CACHE = {}
def worker_youtube(acc):
    for g in GROUPS:
        try:
            cid = YT_CACHE.get(g["yt"])
            if not cid:
                page = fetch("https://www.youtube.com/@%s" % g["yt"],
                             headers={"Accept-Language": "en-US"})
                m = re.search(r'"rssUrl"\s*:\s*"https://www\.youtube\.com/feeds/videos\.xml\?channel_id=([^"&]+)"', page)
                if not m:
                    m = re.search(r"channel_id=([A-Za-z0-9_\-]+)", page)
                cid = m.group(1) if m else None
                if not cid:
                    print("  [youtube:%s] no channel_id" % g["yt"]); continue
                YT_CACHE[g["yt"]] = cid
            xml = fetch("https://www.youtube.com/feeds/videos.xml?channel_id=%s" % cid)
            root = ET.fromstring(xml)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for e in root.findall("a:entry", ns)[:5]:
                title = (e.find("a:title", ns).text or "").strip()
                link = ""
                for l in e.findall("a:link", ns):
                    link = l.get("href") or link
                pub = e.find("a:published", ns).text
                dt = None
                try:
                    dt = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(KST)
                except Exception:
                    pass
                cat = "comeback" if re.search(r"\b(mv|comeback|teaser|title track|music video)\b", title, re.I) else "trend"
                acc.append(make_item(title, link, dt, "YouTube", "video", cat,
                                     [g["name"]], lang="en", desc=""))
        except Exception as ex:
            print("  [youtube:%s] FAIL" % g["yt"], ex)
    print("  [youtube] ok")


def worker_bugs(date):
    try:
        b = fetch("https://music.bugs.co.kr/chart/track/day/total")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", b, re.S)
        entries, n = [], 0
        for row in rows:
            rm = re.search(r'<div class="ranking"><strong>(\d+)</strong>', row)
            tm = re.search(r'<p class="title"><a[^>]+title="([^"]*)"', row)
            am = re.search(r'<p class="artist"><a[^>]+title="([^"]*)"', row)
            if rm and tm and am:
                entries.append(ca.ChartEntry("bugs", int(rm.group(1)),
                                             html.unescape(tm.group(1)),
                                             html.unescape(am.group(1)), chart_date=date))
                n += 1
        print("  [bugs] parsed %d rows" % n)
        return entries
    except Exception as e:
        print("  [bugs] FAIL", e)
        return []


def worker_melon(date):
    try:
        m = fetch("https://www.melon.com/chart/")
        titles = re.findall(r'<div class="ellipsis rank01"><a[^>]+title="([^"]+)"', m)
        artists = re.findall(r'<div class="ellipsis rank02"><a[^>]+title="([^"]+)"', m)
        entries = []
        for i, t in enumerate(titles):
            a = artists[i] if i < len(artists) else ""
            entries.append(ca.ChartEntry("melon", i + 1, html.unescape(t),
                                         html.unescape(a), chart_date=date))
        print("  [melon] parsed %d rows" % len(entries))
        return entries
    except Exception as e:
        print("  [melon] FAIL (降级, 不阻断流水线)", e)
        return []


def worker_circle(date):
    for back in range(0, 4):
        d = (datetime.date.fromisoformat(date) - datetime.timedelta(days=back)).isoformat()
        ymd = d.replace("-", "")
        try:
            data = urllib.parse.urlencode({"termGbn": "day", "yyyymmdd": ymd}).encode()
            req = urllib.request.Request(
                "https://circlechart.kr/data/api/chart/global", data=data,
                headers={"User-Agent": UA["User-Agent"],
                         "Content-Type": "application/x-www-form-urlencoded",
                         "Referer": "https://circlechart.kr/page_chart/global.circle",
                         "X-Requested-With": "XMLHttpRequest"})
            with urllib.request.urlopen(req, timeout=25) as r:
                j = json.loads(r.read())
            lst = (j.get("List") or {})
            if not lst:
                continue
            entries = []
            for k in sorted(lst.keys(), key=lambda x: int(x)):
                row = lst[k]
                entries.append(ca.ChartEntry("circle", int(row.get("Rank", 0)),
                                             row.get("Title", ""), row.get("Artist", ""),
                                             chart_date=d))
            print("  [circle] ok (yyyymmdd=%s, %d rows)" % (ymd, len(entries)))
            return entries
        except Exception as e:
            print("  [circle:%s] FAIL %s" % (ymd, e))
    return []


# ---------------- 去重 / 日报构建 ----------------
def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = (norm_title(it.get("originalTitle") or it.get("title", "")),
               tuple(it.get("groups", [])))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def build_daily(items, date):
    sections = [{"label": lbl, "items": []} for lbl in SECTION_LABELS]
    for it in items:
        if it["category"] == "chart":
            sections[CAT2SEC["chart"]]["items"].append(it)
        else:
            sections[CAT2SEC.get(it["category"], 2)]["items"].append(it)
    # 各版块按时间倒序; 非榜单版块软上限, 控制可读量级
    cap = {"回归·新曲发行": 40, "舞台·打歌": 20, "热点·话题": 30, "官宣·事件": 40}
    for s in sections:
        if s["label"] == "数据·榜单":
            continue
        s["items"].sort(key=lambda x: x.get("publishedAt") or "", reverse=True)
        n = cap.get(s["label"])
        if n and len(s["items"]) > n:
            s["items"] = s["items"][:n]
    # lead: 只在 KPOP 相关、非榜单条目里挑
    lead_text = pick_lead(items)
    # flashes: 最新 5 条带链接 (限 KPOP 相关)
    rel = [i for i in items if i.get("groups") or is_kpop_relevant(i.get("originalTitle", ""))]
    recent = sorted(rel, key=lambda x: x.get("publishedAt") or "", reverse=True)[:5]
    flashes = [{"text": i["title"], "link": i["links"]["original"], "source": i["source"]["name"]}
               for i in recent if i["links"]["original"]]
    total = sum(len(s["items"]) for s in sections)
    return {
        "date": date,
        "generatedAt": iso(datetime.datetime.now(KST)),
        "windowStart": "%sT00:00:00+09:00" % date,
        "windowEnd": "%sT00:00:00+09:00" % (datetime.date.fromisoformat(date) + datetime.timedelta(days=1)).isoformat(),
        "lead": lead_text,
        "sections": sections,
        "flashes": flashes,
        "attribution": {
            "sources": ["Soompi", "Google News", "YouTube", "Bugs", "Melon", "Circle", "Wikidata"],
            "note": "内容版权归各原媒体所有, 本日报仅作聚合索引与翻译摘要, 不构成官方发布。",
        },
        "totalCount": total,
    }


def _p(*a):
    print(*a, flush=True)


def main():
    date = datetime.date.today().isoformat()
    _p("=== KPOP Daily prototype  build date=%s ===" % date)
    news_items = []
    print("[1] news/video workers:")
    worker_soompi(news_items)
    worker_googlenews(news_items)
    worker_youtube(news_items)

    print("[2] chart workers:")
    chart_entries = []
    chart_entries += worker_circle(date)
    chart_entries += worker_bugs(date)
    chart_entries += worker_melon(date)

    print("[3] align charts (Borda consensus):")
    lengths = {"circle": 100, "bugs": 100, "melon": 100}
    if chart_entries:
        # 以实际取到的最新榜单日期为对齐基准(允许各源差 tolerance 天内)
        chart_target = max(e.chart_date for e in chart_entries)
        songs, meta = ca.align_charts(chart_entries, lengths, chart_target, tolerance_days=2)
    else:
        songs, meta = [], {"missing_sources": list(lengths)}
    chart_items = ca.to_chart_items(songs, chart_target if chart_entries else date)
    # 榜单条目艺名中文化 (艺人名可能是英文/韩文, 统一「中文（English）」)
    for ci in chart_items:
        ci["title"] = nl.localize_names(ci["title"])
        ci["summary"] = nl.safe_summary(nl.localize_names(ci["summary"]))
        ci["groups"] = [nl.localize_names(g) for g in ci.get("groups", [])]
    print("  consensus songs=%d  missing_sources=%s  chart_date=%s"
          % (len(songs), meta.get("missing_sources"), chart_target if chart_entries else date))

    print("[4] KPOP 相关性过滤 + 语义去重:")
    non_chart = [i for i in news_items if i.get("category") != "chart"]
    before = len(non_chart)
    non_chart = [i for i in non_chart
                 if i.get("groups") or is_kpop_relevant(i.get("originalTitle", ""))]
    non_chart = semantic_dedupe(non_chart)
    print("  kpop 新闻: 过滤前 %d -> 相关性过滤 %d -> 语义去重 %d"
          % (before, len([i for i in news_items if i.get("category") != "chart"
                          and (i.get("groups") or is_kpop_relevant(i.get("originalTitle", "")))]), len(non_chart)))
    all_items = dedupe(non_chart + chart_items)
    print("  total items after dedupe=%d (含榜单 %d)" % (len(all_items), len(chart_items)))

    print("[5] build daily report:")
    report = build_daily(all_items, date)

    print("[6] 中文摘要 (MyMemory 并发翻译, 跳过榜单版块):")
    translate_items(report, max_workers=5)
    # 翻译后重算 lead / flashes, 使其为中文
    all_report_items = [i for s in report["sections"] for i in s["items"]]
    report["lead"] = pick_lead(all_report_items)
    rel = [i for i in all_report_items
           if i.get("groups") or is_kpop_relevant(i.get("originalTitle", ""))]
    recent = sorted(rel, key=lambda x: x.get("publishedAt") or "", reverse=True)[:5]
    report["flashes"] = [{"text": i["title"], "link": i["links"]["original"],
                          "source": i["source"]["name"]}
                         for i in recent if i["links"]["original"]]

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dailies")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s.json" % date)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("  written -> %s" % out_path)
    print("  totalCount=%d  sections=%s" % (report["totalCount"],
          {s["label"]: len(s["items"]) for s in report["sections"]}))

    # 校验契约
    try:
        import jsonschema
        schema = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "kpop_daily.schema.json"), encoding="utf-8"))
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(report))
        print("  [schema] validate:", "PASS ✅" if not errs else "ERRORS: %s" % errs)
    except Exception as e:
        print("  [schema] skip (%s)" % e)


if __name__ == "__main__":
    main()
