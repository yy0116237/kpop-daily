import argparse, json, re, html, os, urllib.request, urllib.parse, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(HERE, "kpop_daily.schema.json")
N = 30
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://www.melon.com/chart/",
    "Cookie": "ml-CountryId=KR; ml_language=ko;",
}


def _get(u, timeout=25):
    req = urllib.request.Request(u, headers=HDR)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _extract_col(m, col):
    # 旧结构: <div class="ellipsis rank01"><a title="歌名">
    a = re.findall(r'<div class="ellipsis %s"><a[^>]+title="([^"]+)"' % col, m)
    if a:
        return [html.unescape(x) for x in a]
    # 反爬结构: <div class="ellipsis rank01"><span><a>歌名</a></span>  (取 <a> 文本)
    b = re.findall(r'<div class="ellipsis %s">.*?<a[^>]*>([^<]+)</a>' % col, m, re.S)
    return [html.unescape(x).strip() for x in b]


def fetch_melon_once():
    m = _get("https://www.melon.com/chart/")
    titles = _extract_col(m, "rank01")
    artists = _extract_col(m, "rank02")
    out = []
    for i, t in enumerate(titles[:N]):
        a = artists[i] if i < len(artists) else ""
        out.append((i + 1, t, a))
    return out


def fetch_melon(retries=4):
    last = []
    for i in range(retries):
        try:
            rows = fetch_melon_once()
            if rows:
                return rows
        except Exception as e:
            print("  melon fetch err:", repr(e)[:80])
        if i < retries - 1:
            time.sleep(3)
    return last


def has_ko(s):
    return bool(re.search(r"[가-힣]", s or ""))


def build_items(rows, date):
    items = []
    for rank, title, artist in rows:
        t = ("%s — %s" % (title, artist)) if artist else title
        items.append({
            "id": "melon-%s-%d" % (date, rank),
            "title": t,
            "summary": "Melon 音源榜第%d位" % rank,
            "source": {"name": "Melon", "type": "chart"},
            "links": {"original": "https://www.melon.com/chart/"},
            "publishedAt": "%sT00:00:00+09:00" % date,
            "discoveredAt": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"),
            "category": "chart",
            "groups": [artist] if artist else [],
            "company": "",
            "selected": True,
            "lang": "ko" if has_ko(t) else "en",
            "consensusRank": rank,
            "perSourceRank": {"melon": rank},
            "spread": 0,
            "coverage": 1,
            "versions": [],
            "multiVersion": False,
            "dateMismatch": False,
        })
    return items


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="用 Melon 单源榜替换个性化日报榜单")
    p.add_argument("--date", help="日报日期，默认取最新个性化日报")
    p.add_argument("--input", help="个性化日报 JSON 路径")
    p.add_argument("--retries", type=int, default=3)
    return p.parse_args(argv)


def resolve_input(args):
    daily_dir = os.path.join(REPO_ROOT, "dailies")
    if args.input:
        path = os.path.abspath(args.input)
        date = args.date or os.path.basename(path).split(".")[0]
        return path, date
    dates = sorted(m.group(1) for n in os.listdir(daily_dir)
                   if (m := re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.personalized\.json", n)))
    if not dates and not args.date:
        raise SystemExit("dailies/ 中没有个性化日报 JSON")
    date = args.date or dates[-1]
    return os.path.join(daily_dir, date + ".personalized.json"), date


def main(argv=None):
    args = parse_args(argv)
    json_path, date = resolve_input(args)
    print("[melon] 单发直连抓取 top %d ..." % N)
    rows = fetch_melon(retries=max(args.retries, 1))
    print("  melon rows:", len(rows))
    if not rows:
        print("[melon] 仍为空(被限流), 跳过替换")
        return 2

    r = json.load(open(json_path, encoding="utf-8"))
    for s in r["sections"]:
        if s["label"] == "数据·榜单":
            s["items"] = build_items(rows, date)
            print("  替换「数据·榜单」为 Melon 单源, %d 条" % len(s["items"]))
            break

    r["totalCount"] = sum(len(s.get("items", [])) for s in r.get("sections", []))
    sources = set(r.get("attribution", {}).get("sources", []))
    sources.add("Melon")
    r.setdefault("attribution", {})["sources"] = sorted(sources)
    json.dump(r, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    import jsonschema
    schema = json.load(open(SCHEMA_PATH, encoding="utf-8"))
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(r))
    print("schema:", "PASS ✅" if not errs else errs[:3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
