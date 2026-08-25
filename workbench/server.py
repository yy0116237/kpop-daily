#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KPOP DAILY 2.0 工作台 · 本地零依赖服务
=========================================
运行:  python server.py        (默认端口 8765，可用环境变量 KPOP_V2_PORT 改)
打开:  http://localhost:8765

- 数据: workbench/data.json  (个人记录，原子写入，可直接备份)
- 联动: 读取 ../dailies/*.json  (1.0 日报)
- API:  /api/events /api/cons /api/items  CRUD
        /api/daily  最新日报(联动)   /api/stats  账本聚合
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "data.json")
DAILIES_DIR = os.path.abspath(os.path.join(BASE, "..", "dailies"))
PORT = int(os.environ.get("KPOP_V2_PORT", "8765"))

DEFAULT = {
    "version": "2.0",
    "profile": {"nickname": "", "groups": [], "budget": {"year": 2026, "limit": 12000}},
    "events": [],
    "cons": [],
    "items": [],
}

RES = ("events", "cons", "items")
REQ = {
    "events": ["group", "type", "title", "startDate"],
    "cons": ["group", "title", "date"],
    "items": ["kind", "group", "name"],
}
ALLOWED = {
    "id", "createdAt", "updatedAt", "note", "group", "type", "title", "startDate",
    "endDate", "location", "ticketStatus", "repeat", "source",
    "date", "venue", "city", "seat", "ticketPrice", "ticketOriginal",
    "expenses", "mood", "review", "setlist", "seatImage",
    "kind", "name", "version", "purchasedDate", "amount",
    "originalAmount", "originalCurrency", "platform", "status", "image",
}
_lock = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load():
    if not os.path.exists(DATA_PATH):
        return json.loads(json.dumps(DEFAULT))
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    for k, v in DEFAULT.items():
        d.setdefault(k, json.loads(json.dumps(v)))
    return d


def save(d):
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)


def validate(res, rec, partial=False):
    """轻量契约校验（零依赖替代 jsonschema）。"""
    if not isinstance(rec, dict):
        raise ValueError("记录必须是 JSON 对象")
    for k in rec:
        if k not in ALLOWED:
            raise ValueError(f"未知字段: {k}")
    for k in REQ[res]:
        if not partial and (k not in rec or rec[k] in ("", None)):
            raise ValueError(f"缺少必填字段: {k}")
    if res == "events" and "type" in rec and rec["type"] not in REQ.get("_evt_types", ()):
        pass  # type 枚举宽松处理，前端已约束
    return True


def latest_daily():
    if not os.path.isdir(DAILIES_DIR):
        return None
    best = None
    for name in os.listdir(DAILIES_DIR):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.json", name)
        if not m:
            continue
        if best is None or m.group(1) > best[0]:
            best = (m.group(1), name)
    if not best:
        return None
    with open(os.path.join(DAILIES_DIR, best[1]), "r", encoding="utf-8") as f:
        return {"date": best[0], "daily": json.load(f)}


def compute_stats(d):
    """账本聚合：只统计 CNY 的 amount，original* 仅展示不汇总。"""
    total = 0.0
    by_cat = {}
    monthly = {}

    def add(amount, cat, ym=None):
        nonlocal total
        if not amount:
            return
        total += amount
        by_cat[cat] = round(by_cat.get(cat, 0) + amount, 2)
        if ym:
            monthly[ym] = round(monthly.get(ym, 0) + amount, 2)

    for c in d.get("cons", []):
        tp = c.get("ticketPrice") or 0
        add(tp, "演出票", (c.get("date") or "")[:7])
        for e in c.get("expenses", []):
            if e.get("type") == "ticket":
                # 票价已在 ticketPrice 单列；仅当用户没填 ticketPrice 时才用明细里的票计入，避免翻倍
                if not tp:
                    add(e.get("amount") or 0, "演出票", (c.get("date") or "")[:7])
                continue
            key = {"transport": "交通", "hotel": "住宿", "food": "餐饮",
                   "merch": "周边", "other": "其他"}.get(e.get("type"), "其他")
            add(e.get("amount") or 0, key, (c.get("date") or "")[:7])
    for it in d.get("items", []):
        if it.get("status") in ("wishlist", "sold"):
            continue
        add(it.get("amount") or 0, "专辑周边", (it.get("purchasedDate") or "")[:7])

    return {
        "total": round(total, 2),
        "byCategory": by_cat,
        "monthly": dict(sorted(monthly.items())),
        "conCount": len(d.get("cons", [])),
        "itemCount": len([x for x in d.get("items", []) if x.get("status") not in ("wishlist", "sold")]),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "KpopDailyV2/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, bytes):
            body = payload
        else:
            body = str(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ctype):
        p = os.path.join(BASE, name)
        if not os.path.isfile(p):
            self._send(404, {"error": "not found"})
            return
        with open(p, "rb") as f:
            self._send(200, f.read(), ctype)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("请求体不是合法 JSON")

    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p == "/":
                return self._file("index.html", "text/html; charset=utf-8")
            if p == "/style.css":
                return self._file("style.css", "text/css; charset=utf-8")
            if p == "/app.js":
                return self._file("app.js", "text/javascript; charset=utf-8")
            if p == "/api/data":
                with _lock:
                    return self._send(200, load())
            if p == "/api/daily":
                d = latest_daily()
                return self._send(200, d if d else {"date": None, "daily": None})
            if p == "/api/stats":
                with _lock:
                    return self._send(200, compute_stats(load()))
            if p.startswith("/file/"):
                rel = unquote(p[len("/file/"):])
                full = os.path.normpath(os.path.join(BASE, rel))
                try:
                    if os.path.commonpath([BASE, full]) == BASE and os.path.isfile(full):
                        ext = os.path.splitext(full)[1].lower()
                        ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                                 "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}\
                            .get(ext, "application/octet-stream")
                        return self._file(full, ctype)
                except ValueError:
                    pass
                return self._send(404, {"error": "not found"})
            m = re.fullmatch(r"/api/(events|cons|items)(?:/([A-Za-z0-9\-_]+))?", p)
            if m:
                res, rid = m.group(1), m.group(2)
                with _lock:
                    d = load()
                    if rid:
                        rec = next((x for x in d[res] if x.get("id") == rid), None)
                        return self._send(200, rec) if rec else self._send(404, {"error": "not found"})
                    return self._send(200, d[res])
            self._send(404, {"error": "no route"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        m = re.fullmatch(r"/api/(events|cons|items)", urlparse(self.path).path)
        if not m:
            return self._send(404, {"error": "no route"})
        try:
            rec = self._read_body()
            validate(m.group(1), rec)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        rec["id"] = uuid.uuid4().hex[:12]
        rec.setdefault("createdAt", now_iso())
        rec["updatedAt"] = now_iso()
        with _lock:
            d = load()
            d[m.group(1)].append(rec)
            save(d)
        self._send(201, rec)

    def do_PUT(self):
        m = re.fullmatch(r"/api/(events|cons|items)/([A-Za-z0-9\-_]+)", urlparse(self.path).path)
        if not m:
            return self._send(404, {"error": "no route"})
        try:
            patch = self._read_body()
            validate(m.group(1), patch, partial=True)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        with _lock:
            d = load()
            for x in d[m.group(1)]:
                if x.get("id") == m.group(2):
                    x.update(patch)
                    x["updatedAt"] = now_iso()
                    save(d)
                    return self._send(200, x)
        self._send(404, {"error": "not found"})

    def do_DELETE(self):
        m = re.fullmatch(r"/api/(events|cons|items)/([A-Za-z0-9\-_]+)", urlparse(self.path).path)
        if not m:
            return self._send(404, {"error": "no route"})
        with _lock:
            d = load()
            before = len(d[m.group(1)])
            d[m.group(1)] = [x for x in d[m.group(1)] if x.get("id") != m.group(2)]
            if len(d[m.group(1)]) == before:
                return self._send(404, {"error": "not found"})
            save(d)
        self._send(200, {"ok": True})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"KPOP DAILY 2.0 工作台已启动: http://localhost:{PORT}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
