"""截两张图：首屏视口（展示布局意图）+ 整页（展示数据规模）。"""
import os
from playwright.sync_api import sync_playwright

URL = "http://localhost:8765/"
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workbench"))
os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page(viewport={"width": 1280, "height": 880}, device_scale_factor=1)
    pg.goto(URL)
    pg.wait_for_timeout(1500)
    # 截首屏
    pg.screenshot(path=os.path.join(OUT_DIR, "v2_top.png"), full_page=False)
    # 滚动到底部抓榜单区
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(OUT_DIR, "v2_bottom.png"), full_page=False)
    # 整页
    pg.screenshot(path=os.path.join(OUT_DIR, "v2_full.png"), full_page=True)
    print("done")
    b.close()
