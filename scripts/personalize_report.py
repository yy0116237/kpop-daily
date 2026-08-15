# -*- coding: utf-8 -*-
"""按用户偏好对日报新闻做个性化排序 + 筛选到 Top 30。
不改动抓取/翻译/对齐逻辑，只读现有 JSON 重新打分、重排、裁剪。
榜单版块(Circle 单源)原样保留, 不挤入 30 条竞争。
"""
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "dailies", "2026-08-15.json")
OUT = os.path.join(HERE, "dailies", "2026-08-15.personalized.json")
MD  = os.path.join(HERE, "dailies", "2026-08-15.personalized.md")
SCHEMA = os.path.join(HERE, "kpop_daily.schema.json")

# ---------- 用户偏好(来自本次问卷) ----------
FAV = {"TWICE", "LE SSERAFIM", "NMIXX", "ILLIT", "KIIKIII", "IVE"}
GENDER_PREF = "F"          # 女团为主
GEN_PREF = {4, 5}           # 4代 + 5代
COMPANY_PREF = {"HYBE", "JYP"}
TOUR_HEAVY = {"Stray Kids", "BTS", "TWICE", "SEVENTEEN", "BLACKPINK",
              "aespa", "IVE", "NMIXX", "LE SSERAFIM"}

# ---------- 团体元数据: gender / gen / company ----------
GROUP_META = {
    "Stray Kids":   ("M", 4, "JYP"),
    "BTS":          ("M", 3, "HYBE"),
    "aespa":        ("F", 4, "SM"),
    "BLACKPINK":    ("F", 3, "YG"),
    "NewJeans":     ("F", 4, "HYBE"),
    "LE SSERAFIM":  ("F", 4, "HYBE"),
    "TWICE":        ("F", 3, "JYP"),
    "SEVENTEEN":    ("M", 3, "HYBE"),
    "(G)I-DLE":     ("F", 4, "Cube"),
    "Red Velvet":   ("F", 3, "SM"),
    "IVE":          ("F", 4, "Starship"),
    "NMIXX":        ("F", 4, "JYP"),
    "ILLIT":        ("F", 5, "HYBE"),
    "KIIKIII":      ("F", 5, "Starship"),
    "HUNTR/X":      ("F", 5, None),
}
# 成员 -> 团 (用于 groups 为空但带 idols 的条目补归属)
IDOL_TO_GROUP = {
    "V": "BTS", "RM": "BTS", "j-hope": "BTS", "Jin": "BTS", "Jimin": "BTS",
    "Jungkook": "BTS", "Suga": "BTS",
    "Karina": "aespa", "Winter": "aespa", "Giselle": "aespa", "Ningning": "aespa",
    "Jennie": "BLACKPINK", "Rosé": "BLACKPINK", "Lisa": "BLACKPINK", "Jisoo": "BLACKPINK",
    "Bang Chan": "Stray Kids", "Hyunjin": "Stray Kids", "Han": "Stray Kids",
    "Felix": "Stray Kids", "Seungmin": "Stray Kids", "I.N": "Stray Kids",
    "Yunjin": "LE SSERAFIM", "Kazuha": "LE SSERAFIM", "Eunchae": "LE SSERAFIM",
    "Sakura": "LE SSERAFIM", "Chaewon": "LE SSERAFIM",
    "Hanni": "NewJeans", "Minji": "NewJeans", "Danielle": "NewJeans",
    "Haerin": "NewJeans", "Hyein": "NewJeans",
}
_CJK_PAREN = re.compile(r"[（(]([^）)]+)[）)]")

def en_of(wrapped):
    m = _CJK_PAREN.search(wrapped or "")
    return m.group(1) if m else wrapped

def resolve_groups(it):
    gs = set(it.get("groups", []) or [])
    for w in it.get("idols", []) or []:
        g = IDOL_TO_GROUP.get(en_of(w))
        if g:
            gs.add(g)
    return gs

CAT_BASE = {"comeback": 10, "event": 8, "stage": 6, "trend": 5}
_TOUR_RE = re.compile(r"tour|world tour|concert|팬미팅|fan ?meeting|comeback show|아레나", re.I)
# 纯观看须知/通知类: 虽关乎本命团, 但重要性低, 不应当头条
_NOTICE_RE = re.compile(r"\[通知\]|如何观看|where to watch|how to watch|watch .*live|vod|直播观看|表演视频", re.I)

def score_item(it):
    cat = it.get("category", "trend")
    base = CAT_BASE.get(cat, 5)
    gs = resolve_groups(it)
    if not gs:
        return base  # 泛 KPOP 资讯, 无个性化加成
    best = 0
    for g in gs:
        s = 0
        if g in FAV:
            s += 25
        meta = GROUP_META.get(g)
        if meta:
            gender, gen, company = meta
            if GENDER_PREF and gender:
                s += 8 if gender == GENDER_PREF else -5
            if gen:
                s += 6 if gen in GEN_PREF else (-3 if gen == 3 else 0)
            if company in COMPANY_PREF:
                s += 6
        if g in TOUR_HEAVY:
            s += 4
        best = max(best, s)
    text = " ".join([it.get("title", ""), it.get("summary", ""), it.get("originalTitle", "")]).lower()
    if _TOUR_RE.search(text):
        best += 3
    if _NOTICE_RE.search(it.get("title", "")):
        best -= 6
    return base + best

def main():
    r = json.load(open(SRC, encoding="utf-8"))
    news_sections = [s for s in r["sections"] if s["label"] != "数据·榜单"]
    chart_section = next((s for s in r["sections"] if s["label"] == "数据·榜单"), None)

    scored = []
    for s in news_sections:
        for it in s["items"]:
            scored.append((score_item(it), it, s["label"]))
    scored.sort(key=lambda x: x[0], reverse=True)

    top = scored[:30]
    # 按版块重组(版块内按分数降序)
    from collections import defaultdict
    by_sec = defaultdict(list)
    for sc, it, lab in top:
        by_sec[lab].append((sc, it))
    for lab in by_sec:
        by_sec[lab].sort(key=lambda x: x[0], reverse=True)

    # 重建 sections: 保持原顺序(回归/舞台/热点/官宣/榜单)
    new_sections = []
    for s in r["sections"]:
        lab = s["label"]
        if lab == "数据·榜单":
            new_sections.append(s)  # 原样
        else:
            items = [it for _, it in by_sec.get(lab, [])]
            new_sections.append({"label": lab, "category": s.get("category", lab), "items": items})

    total_news = sum(len(s["items"]) for s in new_sections if s["label"] != "数据·榜单")
    total_all = total_news + (len(chart_section["items"]) if chart_section else 0)

    # lead / flashes 取分数最高
    lead_item = top[0][1]
    flashes = []
    for sc, it, lab in top[:5]:
        if it.get("links", {}).get("original"):
            flashes.append({"text": it["title"], "link": it["links"]["original"],
                            "source": it["source"]["name"]})

    out = dict(r)
    out["sections"] = new_sections
    out["totalCount"] = total_all
    out["lead"] = lead_item["title"]
    out["flashes"] = flashes
    # 标注个性化
    out["personalization"] = {
        "favoriteGroups": sorted(FAV),
        "gender": "female-priority",
        "generations": sorted(GEN_PREF),
        "companies": sorted(COMPANY_PREF),
        "newsSelected": total_news,
        "note": "新闻 4 版块按个性化打分取 Top 30; 数据·榜单为独立 Circle 单源, 不参与排序。",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # ---- 生成人可读 markdown 预览 ----
    pz = out.get("personalization", {})
    chart_n = sum(len(s["items"]) for s in new_sections if s["label"] == "数据·榜单")
    fav_line = "、".join(pz.get("favoriteGroups", []))
    gen_line = "/".join(str(g) for g in pz.get("generations", []))
    comp_line = "、".join(pz.get("companies", []))
    news_n = pz.get("newsSelected", 0)
    L = []
    L.append("# KPOP 日报 · 个性化版 · %s" % out["date"])
    L.append("")
    L.append("> 按你的偏好量身定制：本命团 %s ｜ 女团为主 ｜ %s代 ｜ 公司 %s" % (fav_line, gen_line, comp_line))
    L.append("")
    L.append("- 生成时间: %s (KST)" % out["generatedAt"])
    L.append("- 新闻精选: %d 条（Top 30，按个性化打分排序） ｜ 榜单: 独立 Circle 单源 %d 条" % (news_n, chart_n))
    L.append("")
    L.append("## 头条 Lead")
    L.append("")
    L.append("> %s" % out["lead"])
    L.append("")
    for s in new_sections:
        L.append("## %s (%d)" % (s["label"], len(s["items"])))
        L.append("")
        if not s["items"]:
            L.append("_（本版块本次为空）_")
            L.append("")
            continue
        for it in s["items"]:
            tags = []
            if it.get("groups"):
                tags.append(" / ".join(it["groups"]))
            if it.get("idols"):
                tags.append("成员: " + ", ".join(it["idols"]))
            tag = ("  _[" + "; ".join(tags) + "]_") if tags else ""
            L.append("- %s%s  — %s" % (it["title"], tag, it["source"]["name"]))
            if it.get("summary"):
                L.append("  %s" % it["summary"])
            if it["links"].get("original"):
                L.append("  %s" % it["links"]["original"])
        L.append("")
    L.append("---")
    L.append("数据来源: " + ", ".join(out["attribution"]["sources"]))
    L.append("")
    L.append(out["attribution"]["note"])
    open(MD, "w", encoding="utf-8").write("\n".join(L))
    print("md written, bytes:", len("\n".join(L)))

    # 校验
    try:
        import jsonschema
        schema = json.load(open(SCHEMA, encoding="utf-8"))
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(out))
        print("schema:", "PASS ✅" if not errs else errs[:3])
    except Exception as e:
        print("schema check skipped:", e)

    print("新闻入选:", total_news, " | 各版块:",
          {s["label"]: len(s["items"]) for s in new_sections})
    print("lead:", out["lead"])
    print("\n--- Top 12 (分数 | 团体 | 标题) ---")
    for sc, it, lab in top[:12]:
        print("  %3d | %-12s | %s" % (sc, ",".join(it.get("groups", [])) or "-", it["title"][:55]))

if __name__ == "__main__":
    main()
