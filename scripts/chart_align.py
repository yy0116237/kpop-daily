# -*- coding: utf-8 -*-
"""
chart_align.py — KPOP 日报「数据·榜单」三源对齐引擎 (参考实现 / 思路原型)
=========================================================================
把三个独立免费榜单 (Circle 官方JSON / Melon 服务端HTML / Bugs! 服务端HTML)
归一化为一张「共识榜单」, 并标注各源分歧。

这是日报「数据·榜单」版块的精华逻辑, 镜像 AI HOT 的"统一 Item 归一化"思想,
但多了一步 AI HOT 没有的: 跨源排名合并 (cross-source rank fusion)。

v2 增强 (F 阶段):
  • 版本级归一   : 同歌不同版本(SWIM vs SWIM (Spotify Edit))按 (标题,艺人) 归并, 收集版本标注
  • 日期对齐     : 各源榜单快照日期(chartDate, KST)可能不一致, 按 target_date±tolerance 过滤/标注
  • 缺源降级     : 某源抓取失败时, 不丢弃整条, 其余源照常出榜并标注 missingSources

仅依赖标准库 (difflib / re / json / dataclasses / datetime) 。无外部网络、无 Key。
"""
from __future__ import annotations
import difflib
import re
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# ----------------------------------------------------------------------
# 1. 实体归一 (artist 别名表, 实践中由 Wikidata 实体层生成; 这里给最小示例)
# ----------------------------------------------------------------------
ARTIST_ALIASES = {
    "bts": "bts", "bangtan boys": "bts", "방탄소년단": "bts",
    "newjeans": "newjeans", "뉴진스": "newjeans",
    "le sserafim": "le sserafim", "르세라핌": "le sserafim",
    "aespa": "aespa", "에스파": "aespa",
    "rosé": "rosé", "rose": "rosé", "로제": "rosé", "블랙핑크": "blackpink",
}

# 版本关键词: 命中即视为"版本后缀"而非不同歌
VERSION_PATTERNS = [
    r"remix", r"rmx", r"edit", r"spotify edit", r"japanese ver\.?", r"jp ver\.?",
    r"english ver\.?", r"kor ver\.?", r"acoustic", r"live", r"inst\.?", r"instrumental",
    r"reverb", r"nightbeat", r"summer ver\.?", r"prod\.?",
]


def extract_version(raw: str) -> Optional[str]:
    """从标题抽取版本标记 (remix / Spotify Edit / JP ver. 等); 无则 None。
    仅供标注展示, 不影响匹配(匹配用的 normalize_title 已去括号)。"""
    for m in re.finditer(r"\(([^)]*)\)", raw):
        inner = m.group(1).strip().lower()
        for p in VERSION_PATTERNS:
            if re.search(p, inner):
                return inner
    mm = re.search(r"\s[-–]\s*(.*(?:remix|edit|ver\.?)\S*)", raw.lower())
    if mm:
        return mm.group(1).strip()
    return None


def normalize_title(raw: str) -> str:
    """标题归一: 去括号、小写、压空白。版本括号一并剥掉(由 extract_version 另行记录)。"""
    t = raw.lower()
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"\b(feat|ft|with|prod)\.?\b.*", " ", t)
    t = re.sub(r"[^a-z0-9가-힣\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_artist(raw: str, aliases: Optional[dict] = None) -> str:
    aliases = aliases or ARTIST_ALIASES
    a = raw.lower()
    a = re.sub(r"\(.*?\)|\[.*?\]", " ", a)
    a = re.sub(r"[^a-z0-9가-힣\s]", " ", a)
    a = re.sub(r"\s+", " ", a).strip()
    for tok in a.split():
        if tok in aliases:
            return aliases[tok]
    return a


# ----------------------------------------------------------------------
# 2. 单源条目
# ----------------------------------------------------------------------
@dataclass
class ChartEntry:
    source: str                 # "circle" | "melon" | "bugs"
    rank: int
    title: str
    artist: str
    chart_date: str = ""        # 该榜单快照代表的日期 YYYY-MM-DD (KST) — 日期对齐用
    raw: dict = field(default_factory=dict)


@dataclass
class AlignedSong:
    key: str
    title: str
    artist: str
    ranks: dict                 # {"circle":1, "melon":3, "bugs":2}
    borda: float
    consensus_rank: int
    spread: int
    coverage: int               # 出现的源数 (1~3)
    versions: list = field(default_factory=list)      # 收集到的版本标记
    multi_version: bool = False
    date_mismatch: bool = False  # 跨源榜单日期不一致


# ----------------------------------------------------------------------
# 3. 跨源匹配 (identity resolution, 版本级归一)
# ----------------------------------------------------------------------
def _match_key(title: str, artist: str) -> str:
    return f"{normalize_title(title)}||{normalize_artist(artist)}"


def match_entries(entries: list[ChartEntry], fuzzy: bool = True) -> dict:
    """按 (归一标题, 归一艺人) 分组。版本括号已被 normalize_title 剥掉,
    故 SWIM 与 SWIM (Spotify Edit) 天然归为同一条; 版本标记在此收集。"""
    groups: dict[str, list[ChartEntry]] = {}
    for e in entries:
        groups.setdefault(_match_key(e.title, e.artist), []).append(e)

    if not fuzzy:
        return groups

    keys = list(groups.keys())
    merged: dict[str, list[ChartEntry]] = {}
    used = set()
    for ki in keys:
        if ki in used:
            continue
        base = list(groups[ki])
        used.add(ki)
        bt = ki.split("||")[0]
        ai = ki.split("||")[1]
        for kj in keys:
            if kj in used:
                continue
            if kj.split("||")[1] == ai and \
               difflib.SequenceMatcher(None, bt, kj.split("||")[0]).ratio() >= 0.85:
                base += groups[kj]
                used.add(kj)
        merged[ki] = base
    return merged


# ----------------------------------------------------------------------
# 4. 共识排名 (Borda count) + 分歧度 + 版本/日期标注
# ----------------------------------------------------------------------
def _borda_points(rank: int, n: int) -> float:
    return float(n - rank + 1) if 1 <= rank <= n else 0.0


def build_consensus(groups: dict, source_sizes: dict, target_date: str = "",
                    tolerance_days: int = 1) -> list[AlignedSong]:
    songs: list[AlignedSong] = []
    for key, entries in groups.items():
        ranks: dict[str, int] = {}
        title_disp, artist_disp = "", ""
        versions: list[str] = []
        chart_dates: set[str] = set()
        for e in entries:
            ranks[e.source] = e.rank
            chart_dates.add(e.chart_date)
            v = extract_version(e.title)
            if v and v not in versions:
                versions.append(v)
            if len(e.title) > len(title_disp):
                title_disp = e.title
            if len(e.artist) > len(artist_disp):
                artist_disp = e.artist
        borda = sum(_borda_points(ranks[s], source_sizes.get(s, 100)) for s in ranks)
        spread = (max(ranks.values()) - min(ranks.values())) if len(ranks) > 1 else 0
        songs.append(AlignedSong(
            key=key, title=title_disp, artist=artist_disp,
            ranks=ranks, borda=borda, consensus_rank=0, spread=spread,
            coverage=len(ranks),
            versions=versions,
            multi_version=len(versions) > 1,
            date_mismatch=(len(chart_dates) > 1),   # 跨源快照日期不一致
        ))
    songs.sort(key=lambda s: (-s.borda, s.spread))
    for i, s in enumerate(songs, 1):
        s.consensus_rank = i
    return songs


# ----------------------------------------------------------------------
# 5. 主入口: 对齐编排 (含 缺源降级 + 日期对齐过滤)
# ----------------------------------------------------------------------
def align_charts(entries: list[ChartEntry], source_sizes: dict,
                 target_date: str, expected_sources: tuple = ("circle", "melon", "bugs"),
                 tolerance_days: int = 1) -> tuple[list[AlignedSong], dict]:
    """对齐三源榜单。

    返回 (songs, meta):
      meta.missing_sources : 预期有但本次无数据的源 (缺源降级标注)
      meta.skipped_stale   : 因 chartDate 超 tolerance 被剔除的条目 (日期对齐)
      meta.in_window       : 实际参与共识的条目数
    """
    present = {e.source for e in entries}
    missing_sources = [s for s in expected_sources if s not in present]

    td = date.fromisoformat(target_date)
    in_window, skipped_stale = [], []
    for e in entries:
        if not e.chart_date:
            in_window.append(e)          # 无日期信息则宽容纳入
            continue
        delta = abs((date.fromisoformat(e.chart_date) - td).days)
        (in_window if delta <= tolerance_days else skipped_stale).append(e)

    groups = match_entries(in_window)
    songs = build_consensus(groups, source_sizes, target_date, tolerance_days)
    meta = {
        "missing_sources": missing_sources,
        "skipped_stale": [{"source": e.source, "title": e.title, "chartDate": e.chart_date}
                          for e in skipped_stale],
        "in_window": len(in_window),
    }
    return songs, meta


# ----------------------------------------------------------------------
# 6. 分歧标注
# ----------------------------------------------------------------------
def flag_discrepancy(s: AlignedSong, threshold: int = 15) -> Optional[str]:
    if s.spread >= threshold:
        return f"三源排名差 {s.spread} 位, 争议较大"
    top10 = [src for src, r in s.ranks.items() if r <= 10]
    low = [src for src, r in s.ranks.items() if r > 50]
    if top10 and low:
        return f"在 {','.join(top10)} 进前10, 但 {','.join(low)} 跌出50"
    return None


# ----------------------------------------------------------------------
# 7. 导出为日报 Item (对齐 AI HOT 的 report.sections[].items 结构)
# ----------------------------------------------------------------------
def to_chart_items(songs: list[AlignedSong], d: str, top_n: int = 30,
                   discovered_at: Optional[str] = None) -> list[dict]:
    items = []
    if discovered_at is None:
        discovered_at = f"{d}T07:00:00+09:00"   # 默认榜单 worker 运行时刻 (KST)
    for s in songs:
        if s.consensus_rank > top_n:
            break
        ranks_str = " · ".join(f"{k}#{v}" for k, v in sorted(s.ranks.items()))
        summary = f"共识第{s.consensus_rank}位 ({ranks_str})"
        if s.multi_version:
            summary += f"; 版本: {'/'.join(s.versions)}"
        if s.date_mismatch:
            summary += "; 跨源榜单日期不一致"
        note = flag_discrepancy(s)
        if note:
            summary += f"; {note}"
        items.append({
            "id": f"chart-{d}-{s.consensus_rank}",
            "title": f"{s.title} — {s.artist}",
            "summary": summary[:60],
            "source": {"name": "榜单交叉", "type": "chart"},
            "links": {"original": ""},
            "publishedAt": f"{d}T00:00:00+09:00",
            "discoveredAt": discovered_at,
            "category": "chart",
            "groups": [s.artist],
            "company": "",
            "selected": True,
            "lang": "en",
            "consensusRank": s.consensus_rank,
            "perSourceRank": s.ranks,
            "spread": s.spread,
            "coverage": s.coverage,
            "versions": s.versions,
            "multiVersion": s.multi_version,
            "dateMismatch": s.date_mismatch,
        })
    return items


# ----------------------------------------------------------------------
# 8. 演示 (覆盖三个增强场景)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    TARGET = "2026-08-14"
    # 场景: SWIM 在 Melon 写作 "SWIM (Spotify Edit)" (版本级归一);
    #       Melon 快照为 08-13 (比目标晚1天, tolerance=1 内, 日期对齐);
    #       Bugs 正常 08-14; Circle 正常 08-14。
    demo = [
        ChartEntry("circle", 1, "SWIM", "방탄소년단(BTS)", chart_date="2026-08-14"),
        ChartEntry("melon", 3, "SWIM (Spotify Edit)", "BTS", chart_date="2026-08-13"),
        ChartEntry("bugs", 2, "SWIM", "방탄소년단", chart_date="2026-08-14"),
        ChartEntry("circle", 5, "LOVE ATTACK", "RESCENE", chart_date="2026-08-14"),
        ChartEntry("melon", 1, "LOVE ATTACK", "RESCENE", chart_date="2026-08-14"),
        ChartEntry("bugs", 12, "LOVE ATTACK", "RESCENE", chart_date="2026-08-14"),
        ChartEntry("melon", 2, "LEMONADE", "aespa", chart_date="2026-08-14"),
        ChartEntry("bugs", 8, "LEMONADE", "aespa", chart_date="2026-08-14"),
        ChartEntry("circle", 9, "Supernova", "aespa", chart_date="2026-08-14"),
    ]
    source_sizes = {"circle": 100, "melon": 100, "bugs": 100}

    print("===== 场景1+2: 版本级归一 + 日期对齐 (tolerance=1) =====")
    songs, meta = align_charts(demo, source_sizes, TARGET, tolerance_days=1)
    print("meta:", json.dumps(meta, ensure_ascii=False))
    for s in songs:
        print(f"  #{s.consensus_rank} {s.title} — {s.artist} | "
              f"ranks={s.ranks} cov={s.coverage} ver={s.versions} dateMismatch={s.date_mismatch}")

    print("\n===== 场景2(严): tolerance=0, Melon(08-13) 应被剔除 =====")
    _, meta0 = align_charts(demo, source_sizes, TARGET, tolerance_days=0)
    print("skipped_stale:", json.dumps(meta0["skipped_stale"], ensure_ascii=False))

    print("\n===== 场景3: 缺源降级 (模拟 Bugs 抓取失败, 无 Bugs 条目) =====")
    demo_no_bugs = [e for e in demo if e.source != "bugs"]
    songs2, meta2 = align_charts(demo_no_bugs, source_sizes, TARGET, tolerance_days=1)
    print("meta:", json.dumps(meta2, ensure_ascii=False))
    print("=> 日报仍正常出榜, 仅 coverage 下降并标注 missingSources")

    print("\n===== 导出日报 Item 样例 (前2条) =====")
    print(json.dumps(to_chart_items(songs, TARGET)[:2], ensure_ascii=False, indent=2))
