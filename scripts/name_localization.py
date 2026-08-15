# -*- coding: utf-8 -*-
"""
name_localization.py — KPOP 名词本地化
====================================================================
规则 (用户 2026-08-15 明确):
  • 人名/成员名(idol): 统一呈现「中文（English）」(全角括号)。
  • 团名(group):      保持英文, 不翻译、不包裹。
  • 歌名/专辑名:       保持原文(英文/韩文), 不被翻译改写。

实现:
  • NAME_ENTRIES: en=规范英文, zh=中文(无则等于 en), ko=韩文/别名。
  • GROUP_EN:      团体英文名集合 (排除本地化 + 翻译保护)。
  • localize_names(text):   仅把命中的 人名 替换为「中文（English）」(团名不动)。
  • detect_idols(text):     扫描成员名 -> 「中文（English）」列表。
  • unwrap_groups(text):    把已包裹的团名还原为英文 (用于修正历史 JSON)。
  • 翻译保护 (团名 + 引号内歌名/专辑名) 见 kpop_daily_proto.translate()。
"""
import re

# 团体(保持英文, 不包裹). 注意: IU 是 soloist 个人, 不在此列 -> 仍走人名规则.
GROUP_EN = {"BTS", "NewJeans", "LE SSERAFIM", "BLACKPINK", "Stray Kids", "aespa",
            "TWICE", "(G)I-DLE", "SEVENTEEN", "IVE", "Red Velvet"}

# 每条: en=规范英文(括号内显示), zh=中文(无则等于 en), ko=韩文/别名变体
NAME_ENTRIES = [
    # ---------- 团体 (团名保持英文) ----------
    {"en": "BTS", "zh": "防弹少年团", "ko": ["방탄소년단"]},
    {"en": "NewJeans", "zh": "新牛仔", "ko": ["뉴진스", "njz"],
     "note": "粉丝通用译名『新牛仔』(非官方)"},
    {"en": "LE SSERAFIM", "zh": "LE SSERAFIM", "ko": ["르세라핌"],
     "note": "无官方中文, 暂保留英文"},
    {"en": "BLACKPINK", "zh": "BLACKPINK", "ko": ["블랙핑크"],
     "note": "无官方中文, 粉丝常作『粉墨』, 暂保留英文"},
    {"en": "Stray Kids", "zh": "Stray Kids", "ko": ["스트레이 키즈", "skz"],
     "note": "无官方中文, 暂保留英文"},
    {"en": "aespa", "zh": "艾斯帕", "ko": ["에스파"],
     "note": "粉丝通用译名『艾斯帕』(非官方)"},
    {"en": "TWICE", "zh": "TWICE", "ko": ["트와이스"], "note": "无官方中文, 暂保留英文"},
    {"en": "(G)I-DLE", "zh": "(G)I-DLE", "ko": ["여자아이들"], "note": "无官方中文, 暂保留英文"},
    {"en": "SEVENTEEN", "zh": "SEVENTEEN", "ko": ["세븐틴"], "note": "无官方中文, 暂保留英文"},
    {"en": "IVE", "zh": "IVE", "ko": ["아이브"], "note": "无官方中文, 暂保留英文"},
    {"en": "Red Velvet", "zh": "Red Velvet", "ko": ["레드벨벳"], "note": "无官方中文, 暂保留英文"},
    {"en": "IU", "zh": "李知恩", "ko": ["아이유"]},

    # ---------- BTS 成员 ----------
    {"en": "RM", "zh": "金南俊", "ko": ["김남준"]},
    {"en": "Jin", "zh": "金硕珍", "ko": ["김석진"]},
    {"en": "SUGA", "zh": "闵玧其", "ko": ["민윤기"]},
    {"en": "j-hope", "zh": "郑号锡", "ko": ["정호석"]},
    {"en": "Jimin", "zh": "朴智旻", "ko": ["박지민"]},
    {"en": "V", "zh": "金泰亨", "ko": ["김태형"]},
    {"en": "Jungkook", "zh": "田柾国", "ko": ["전정국"]},

    # ---------- BLACKPINK 成员 ----------
    {"en": "Jennie", "zh": "金智妮", "ko": ["김제니"]},
    {"en": "Lisa", "zh": "Lisa", "ko": ["라리사", "랄리사"], "note": "本名 Lalisa Manoban, 无通用中文, 暂保留英文"},
    {"en": "Rosé", "zh": "朴彩英", "ko": ["박채영"]},
    {"en": "Jisoo", "zh": "金智秀", "ko": ["김지수"]},

    # ---------- NewJeans 成员 ----------
    {"en": "Minji", "zh": "金玟池", "ko": ["김민지"]},
    {"en": "Hanni", "zh": "Hanni", "ko": ["하니"], "note": "本名 Phạm Ngọc Hân, 无通用中文, 暂保留英文"},
    {"en": "Danielle", "zh": "Danielle", "ko": ["다니엘"], "note": "本名 Molly, 无通用中文, 暂保留英文"},
    {"en": "Haerin", "zh": "姜谐潾", "ko": ["강해린"]},
    {"en": "Hyein", "zh": "李惠仁", "ko": ["이혜인"]},

    # ---------- LE SSERAFIM 成员 ----------
    {"en": "Chaewon", "zh": "金采源", "ko": ["김채원"]},
    {"en": "Sakura", "zh": "宫胁咲良", "ko": ["미야와키 사쿠라", "사쿠라"]},
    {"en": "Yunjin", "zh": "许允真", "ko": ["허윤진"]},
    {"en": "Kazuha", "zh": "中村一叶", "ko": ["나카무라 카즈하", "카즈하"]},
    {"en": "Eunchae", "zh": "洪恩采", "ko": ["홍은채"]},

    # ---------- aespa 成员 ----------
    {"en": "Karina", "zh": "柳智敏", "ko": ["유지민"]},
    {"en": "Winter", "zh": "金旼炡", "ko": ["김민정"]},
    {"en": "Giselle", "zh": "内永枝利", "ko": ["내영지리", "지젤"]},
    {"en": "Ningning", "zh": "宁艺卓", "ko": ["닝닝"]},

    # ---------- Stray Kids 成员 ----------
    {"en": "Bang Chan", "zh": "方灿", "ko": ["방찬"]},
    {"en": "Lee Know", "zh": "李旻浩", "ko": ["이민호"]},
    {"en": "Changbin", "zh": "徐彰彬", "ko": ["서창빈"]},
    {"en": "Hyunjin", "zh": "黄铉辰", "ko": ["황현진"]},
    {"en": "Han", "zh": "韩知城", "ko": ["한지성"]},
    {"en": "Felix", "zh": "李龙馥", "ko": ["이용복"]},
    {"en": "Seungmin", "zh": "金昇玟", "ko": ["김승민"]},
    {"en": "I.N", "zh": "杨敬元", "ko": ["양경원"]},

    # ---------- (G)I-DLE 成员 (热门补充) ----------
    {"en": "Soyeon", "zh": "田小娟", "ko": ["전소연"]},
    {"en": "Miyeon", "zh": "曹薇娟", "ko": ["조미연"]},
    {"en": "Minnie", "zh": "Minnie", "ko": ["미니"], "note": "本名 Nicha Yontararak, 无通用中文, 暂保留英文"},
    {"en": "Yuqi", "zh": "宋雨琦", "ko": ["송우기"]},
    {"en": "Shuhua", "zh": "叶舒华", "ko": ["예수화"]},

    # ---------- IVE 成员 (热门补充) ----------
    {"en": "Wonyoung", "zh": "张元英", "ko": ["장원영"]},
    {"en": "Leeseo", "zh": "李瑞", "ko": ["이서"]},
]


def _wrap(form):
    """拉丁字母形式的艺名加词边界(且避开半/全角括号及 / . 等分隔符, 防止误伤
    Converse/Vermilion 以及 M/V、M.V 这类写法); 中日韩(韩文/中文)形式无需边界,
    直接字面匹配。"""
    esc = re.escape(form)
    if form.isascii() and re.search(r"[A-Za-z0-9]", form):
        return r"(?<![A-Za-z0-9/.（(])" + esc + r"(?![A-Za-z0-9])"
    return esc


# 预编译: 仅 人名(idol) 条目 (排除 GROUP_EN 团体), 命中即替换为 "zh（en）"
_COMPILED = []
for _e in NAME_ENTRIES:
    if _e["en"] in GROUP_EN:
        continue  # 团名保持英文, 跳过包裹
    _zh = _e["zh"]
    if _zh == _e["en"]:
        continue  # 无中文可补, 跳过
    _forms = [_e["en"], _zh] + list(_e.get("ko", []))
    _forms = sorted({f for f in _forms if f}, key=len, reverse=True)
    _alt = "|".join(_wrap(f) for f in _forms)
    _COMPILED.append((re.compile(_alt, re.I), _zh, _e["en"]))

# 团名 所有形态(小写) -> 英文规范名 (用于翻译保护 + 历史还原)
GROUP_FORMS = {}
for _e in NAME_ENTRIES:
    if _e["en"] not in GROUP_EN:
        continue
    for _f in [_e["en"], _e["zh"]] + list(_e.get("ko", [])):
        if _f:
            GROUP_FORMS[_f.lower()] = _e["en"]

# 团名「中文（English）」 -> 英文 (用于把已成型 JSON 里的包裹还原)
GROUP_WRAPPED = {}
for _e in NAME_ENTRIES:
    if _e["en"] in GROUP_EN and _e["zh"] != _e["en"]:
        GROUP_WRAPPED["%s（%s）" % (_e["zh"], _e["en"])] = _e["en"]


def localize_names(text):
    """把文本中命中的 人名 统一替换为「中文（English）」(全角括号)。团名不动。

    同一条目变体用单个 alternation 正则一次性替换, re.sub 不回扫已插入文本, 不会嵌套括号。"""
    if not text:
        return text
    out = text
    for rx, zh, en in _COMPILED:
        out = rx.sub(lambda m, z=zh, e=en: "%s（%s）" % (z, e), out)
    return out


def localize_label(en_name):
    """仅用于人名; 团名请直接保留英文, 勿调用本函数。"""
    if not en_name:
        return en_name
    for rx, zh, en in _COMPILED:
        if en == en_name:
            return "%s（%s）" % (zh, en)
    return en_name


def localize_groups(groups):
    """团名保持英文, 不做包裹, 原样返回。"""
    return list(groups or [])


def unwrap_groups(text):
    """把文本里已成型的「中文（English）」团名还原为英文; 人名包裹不受影响。"""
    if not text:
        return text
    out = text
    for wrapped, en in GROUP_WRAPPED.items():
        out = out.replace(wrapped, en)
    return out


def detect_idols(text):
    """从原文扫描成员名, 返回去重后的本地化列表 (顺序按首次出现)。

    用 _COMPILED 的边界正则, 避免把 Converse/Vermilion 里的 V/RM 误判为成员。"""
    if not text:
        return []
    seen, res = set(), []
    for rx, zh, en in _COMPILED:
        if rx.search(text) and en not in seen:
            seen.add(en)
            res.append("%s（%s）" % (zh, en))
    return res


def safe_summary(s, limit=60):
    """截断到 limit, 避免中文括号半开 (结尾恰为 '（' 则舍弃)。"""
    if not s:
        return s
    s = s[:limit]
    if s.endswith("（"):
        s = s[:-1]
    return s
