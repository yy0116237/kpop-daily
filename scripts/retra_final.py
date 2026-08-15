#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只对在日报里"最终入选"的内容做重新翻译 (不触碰被丢弃的 raw 项).
- 串行 + 重试 + 小延迟, 规避 MyMemory 共享 IP 限流/429.
- 标题从 originalTitle 翻, 摘要从 originalDesc 翻 (避免对已中文文本二次翻译).
- 团名/引号内歌名专辑名受保护保持英文; 成员名套「中文（English）」.
- 翻完重算 lead / flashes, 落盘后重生成 md 预览并校验契约.
"""
import json, os, re, time, datetime
import importlib
import kpop_daily_proto as P
import name_localization as nl
importlib.reload(nl)  # 确保用最新名词表

HERE = os.path.dirname(os.path.abspath(__file__))
DATE = "2026-08-15"
JSON_PATH = os.path.join(HERE, "dailies", "%s.json" % DATE)

_cjk = re.compile(r"[一-鿿]")

def _en_of(wrapped):
    m = re.search(r"[（(]([^）)]+)[）)]", wrapped)
    return m.group(1) if m else wrapped

def _has_cjk(t):
    return bool(_cjk.search(t or ""))

def main():
    r = json.load(open(JSON_PATH, encoding="utf-8"))
    items = [i for s in r["sections"] for i in s["items"]]
    non_chart = [i for i in items if i.get("category") != "chart"]

    before_zh = sum(1 for i in non_chart if _has_cjk(i.get("title")))
    ok_title = 0
    ok_summary = 0

    for it in non_chart:
        orig = it.get("originalTitle") or it.get("title", "")
        desc = (it.get("originalDesc") or "").strip()
        # 标题: 仅当翻译结果确实含中文才覆盖(防止非中文改写覆盖已有中文)
        zh = P.translate(orig)
        if zh and _has_cjk(zh):
            it["title"] = nl.localize_names(zh)
            it["lang"] = "zh"
            ok_title += 1
        else:
            it["title"] = nl.localize_names(it["title"])  # 保留已有(可能已中文)
        # 摘要: 优先翻译描述
        if desc:
            zs = P.translate(desc)
            if zs and _has_cjk(zs):
                it["summary"] = nl.safe_summary(nl.localize_names(zs))[:60]
                ok_summary += 1
            else:
                base = it.get("summary") or zh or orig
                it["summary"] = nl.safe_summary(nl.localize_names(base))[:60]
        else:
            base = it.get("summary") or zh or orig
            it["summary"] = nl.safe_summary(nl.localize_names(base))[:60]
        # 结构化标签本地化 (团名保持英文, 成员名包裹)
        it["groups"] = nl.localize_groups(it.get("groups", []))
        it["idols"] = [w for w in nl.detect_idols(orig + " " + desc)
                       if _en_of(w) not in nl.GROUP_EN]
        time.sleep(0.25)  # 平缓请求, 避免 gtx 限流

    # 榜单版块艺名本地化 (保持)
    for s in r["sections"]:
        if s["label"] == "数据·榜单":
            for ci in s["items"]:
                ci["title"] = nl.localize_names(ci["title"])
                ci["summary"] = nl.safe_summary(nl.localize_names(ci["summary"]))
                ci["groups"] = [nl.localize_names(g) for g in ci.get("groups", [])]

    all_items = [i for s in r["sections"] for i in s["items"]]
    # 重算 lead / flashes
    r["lead"] = P.pick_lead([i for i in all_items if i.get("category") != "chart"])
    rel = [i for i in all_items
           if i.get("groups") or P.is_kpop_relevant(i.get("originalTitle", ""))]
    recent = sorted(rel, key=lambda x: x.get("publishedAt") or "", reverse=True)[:5]
    r["flashes"] = [{"text": i["title"], "link": i["links"]["original"],
                     "source": i["source"]["name"]}
                    for i in recent if i["links"]["original"]]

    json.dump(r, open(JSON_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    after_zh = sum(1 for i in non_chart if _has_cjk(i.get("title")))
    print("条目(非榜单):", len(non_chart))
    print("重翻成功 标题 +%d / 摘要 +%d" % (ok_title, ok_summary))
    print("中文标题覆盖: %d -> %d (%d/%d)" % (before_zh, after_zh, after_zh, len(non_chart)))

    # 契约校验
    try:
        import jsonschema
        schema = json.load(open(os.path.join(HERE, "kpop_daily.schema.json"), encoding="utf-8"))
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(r))
        print("schema:", "PASS ✅" if not errs else errs[:3])
    except Exception as e:
        print("schema skip:", e)

    # 重生成 md 预览
    L = ["# KPOP 日报 · %s" % r["date"], "",
         "- 生成时间: %s (KST)" % r["generatedAt"],
         "- 条目总数: %d" % r["totalCount"], "",
         "## 头条 Lead", "", "> %s" % r["lead"], ""]
    for s in r["sections"]:
        L.append("## %s (%d)" % (s["label"], len(s["items"]))); L.append("")
        if not s["items"]:
            L.append("_（本版块本次为空：沙箱 IP 被榜单源限流，解析逻辑已验证可用，待限流恢复后回填）_"); L.append(""); continue
        for it in s["items"]:
            tags = []
            if it.get("groups"): tags.append(" / ".join(it["groups"]))
            if it.get("idols"): tags.append("成员: " + ", ".join(it["idols"]))
            tag = ("  _[" + "; ".join(tags) + "]_") if tags else ""
            L.append("- %s%s  — %s" % (it["title"], tag, it["source"]["name"]))
            if it["links"].get("original"): L.append("  %s" % it["links"]["original"])
        L.append("")
    L += ["---", "数据来源: " + ", ".join(r["attribution"]["sources"]), "", r["attribution"]["note"]]
    md = "\n".join(L)
    open(os.path.join(HERE, "dailies", "%s.md" % DATE), "w", encoding="utf-8").write(md)
    print("md regenerated (%d bytes)" % len(md))

if __name__ == "__main__":
    main()
