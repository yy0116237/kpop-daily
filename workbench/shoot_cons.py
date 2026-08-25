# -*- coding: utf-8 -*-
"""渲染 Con 记忆区截图（Playwright）。"""
import os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8765/"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page(viewport={"width": 1180, "height": 1000}, device_scale_factor=2)
    pg.goto(URL)
    pg.wait_for_timeout(700)

    # 切到 Con 记忆 tab
    pg.click('.tab[data-view="cons"]')
    pg.wait_for_timeout(450)
    pg.screenshot(path=os.path.join(BASE, "v2_cons_all.png"), full_page=False)

    # 筛 LE SSERAFIM
    chips = pg.query_selector_all('#con-group-filters .chip')
    for c in chips:
        if c.inner_text().strip() == "LE SSERAFIM":
            c.click(); break
    pg.wait_for_timeout(350)
    pg.screenshot(path=os.path.join(BASE, "v2_cons_lsf.png"), full_page=False)

    # 回到全部，打开新增弹窗
    for c in pg.query_selector_all('#con-group-filters .chip'):
        if c.inner_text().strip() == "全部":
            c.click(); break
    pg.wait_for_timeout(250)
    pg.click('#btn-add-con')
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(BASE, "v2_cons_modal.png"), full_page=False)

    # 关闭，打开编辑（第一条 TWICE）
    pg.click('#c-cancel')
    pg.wait_for_timeout(300)
    edit = pg.query_selector('.con-card .mini.edit')
    if edit:
        edit.click()
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(BASE, "v2_cons_edit.png"), full_page=False)

    b.close()
    print("cons shots done")
