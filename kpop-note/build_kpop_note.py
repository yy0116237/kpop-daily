#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 KPOP NOTE · 日报×记录 资料库版单文件工作台
- 自动取 dailies/ 下最新 YYYY-MM-DD.json 提取精简日报（lead/flashes/sections+榜单）
- 从 workbench/data.json 提取示例记录（seed）
- 注入 kpop_note_template.html 的占位符，输出 kpop-note-workspace.html
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "kpop_note_template.html")
SEED = os.path.join(BASE, "workbench", "data.json")
OUT = os.path.join(BASE, "kpop-note-workspace.html")


def latest_daily_path():
    """dailies/ 下最新日期的 YYYY-MM-DD.json（排除 .personalized 等后缀）。"""
    cands = []
    for name in os.listdir(os.path.join(BASE, "dailies")):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.json", name)
        if m:
            cands.append(m.group(1))
    if not cands:
        raise SystemExit("dailies/ 下没有 YYYY-MM-DD.json")
    latest = max(cands)
    return os.path.join(BASE, "dailies", latest + ".json"), latest


def slim_item(it):
    o = {"id": it.get("id"), "title": it.get("title"), "summary": it.get("summary")}
    for k in ("category", "groups", "artist", "album", "rank", "perSourceRank", "publishedAt", "discoveredAt"):
        if it.get(k) is not None:
            o[k] = it[k]
    if it.get("source"):
        o["source"] = {"name": it["source"].get("name")}
    if it.get("links"):
        o["links"] = {"original": it["links"].get("original")}
    return o


def pick_daily(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    flashes = []
    for f in (d.get("flashes") or []):
        if isinstance(f, str):
            flashes.append({"text": f, "link": ""})
        elif isinstance(f, dict):
            flashes.append({"text": f.get("text") or f.get("title") or "", "link": f.get("link") or f.get("url") or ""})
    out = {
        "date": d.get("date"),
        "lead": d.get("lead"),
        "flashes": flashes,
        "sections": [],
    }
    for s in (d.get("sections") or []):
        out["sections"].append({
            "label": s.get("label"),
            "items": [slim_item(it) for it in (s.get("items") or [])],
        })
    return out


def js(v):
    return json.dumps(v, ensure_ascii=False).replace("</", "<\\/")


def main():
    with open(TPL, encoding="utf-8") as f:
        html = f.read()
    daily_path, daily_date = latest_daily_path()
    daily = pick_daily(daily_path)
    with open(SEED, encoding="utf-8") as f:
        seed = json.load(f)
    if "__EMBED_DAILY__" not in html or "__EMBED_SEED__" not in html:
        raise SystemExit("模板缺少占位符")
    html = html.replace("__EMBED_DAILY__", js(daily)).replace("__EMBED_SEED__", js(seed))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK ->", OUT)
    print("daily date:", daily_date)
    print("size:", os.path.getsize(OUT), "bytes")
    print("daily sections:", [s["label"] for s in daily["sections"]])
    print("daily items:", sum(len(s["items"]) for s in daily["sections"]))
    print("seed: events=%d items=%d cons=%d" % (len(seed.get("events", [])), len(seed.get("items", [])), len(seed.get("cons", []))))


if __name__ == "__main__":
    main()
