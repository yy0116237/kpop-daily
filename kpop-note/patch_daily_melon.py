#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 Melon 实时榜并注入最新日报 JSON 的「数据·榜单」版块（Melon 单源）。"""
import json, re, html, os, sys, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.8,en;q=0.6",
    "Referer": "https://www.melon.com/chart/",
    "Cookie": "ml-CountryId=KR; ml_language=ko;",
}
N = 30


def _get(u, timeout=25):
    req = urllib.request.Request(u, headers=HDR)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def fetch_melon_once():
    m = _get("https://www.melon.com/chart/")
    titles = []
    a = re.findall(r'<div class="ellipsis rank01"><a[^>]+title="([^"]+)"', m)
    if a:
        titles = [html.unescape(x) for x in a]
    else:
        b = re.findall(r'<div class="ellipsis rank01">.*?<a[^>]*>([^<]+)</a>', m, re.S)
        titles = [html.unescape(x).strip() for x in b]
    artists = []
    a2 = re.findall(r'<div class="ellipsis rank02"><a[^>]+title="([^"]+)"', m)
    if a2:
        artists = [html.unescape(x) for x in a2]
    else:
        b2 = re.findall(r'<div class="ellipsis rank02">.*?<a[^>]*>([^<]+)</a>', m, re.S)
        artists = [html.unescape(x).strip() for x in b2]
    out = []
    for i, t in enumerate(titles[:N]):
        ar = artists[i] if i < len(artists) else ""
        out.append((i + 1, t, ar))
    return out


def fetch_melon(retries=5):
    for i in range(retries):
        try:
            rows = fetch_melon_once()
            if rows:
                return rows
        except Exception as e:
            print("  melon err:", repr(e)[:90])
        if i < retries - 1:
            time.sleep(3)
    return []


def latest_daily_path():
    cands = []
    for name in os.listdir(os.path.join(BASE, "dailies")):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.json", name)
        if m:
            cands.append(m.group(1))
    if not cands:
        raise SystemExit("dailies/ 下没有日报 JSON")
    latest = max(cands)
    return os.path.join(BASE, "dailies", latest + ".json"), latest


def main():
    rows = fetch_melon()
    print("melon rows:", len(rows))
    if not rows:
        print("FAIL: 未抓到 Melon 榜单（可能被限流，稍后重试）")
        return 1
    path, date = latest_daily_path()
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    items = []
    for rank, t, ar in rows:
        items.append({
            "id": "melon:%s:%d" % (date, rank),
            "title": t,
            "artist": ar,
            "album": "",
            "rank": rank,
            "perSourceRank": {"melon": rank},
            "source": {"name": "Melon", "type": "chart"},
            "category": "chart",
            "selected": True,
        })
    secs = d.get("sections") or []
    chart_sec = None
    for s in secs:
        if re.search(r"榜单|chart", s.get("label", "")):
            chart_sec = s
            break
    if chart_sec is None:
        chart_sec = {"label": "数据·榜单", "items": []}
        secs.append(chart_sec)
        d["sections"] = secs
    chart_sec["items"] = items
    d.setdefault("lead", d.get("lead") or "今日 KPOP 速览")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print("injected %d melon rows -> %s (date=%s)" % (len(items), path, date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
