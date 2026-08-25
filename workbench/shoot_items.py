# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import os

BASE = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8765/?v=2"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page(viewport={"width": 1180, "height": 1000}, device_scale_factor=2)
    pg.goto(URL)
    pg.wait_for_timeout(700)

    # 切到收藏 tab
    pg.click('.tab[data-view="items"]')
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(BASE, "v2_items_all.png"), full_page=False)

    # 放大截 toolbar 按钮区
    btn = pg.locator('.toolbar')
    btn.screenshot(path=os.path.join(BASE, "v2_items_toolbar.png"))

    # 滤镜：种草
    pg.click('#item-status-filters .chip[data-status="wishlist"]')
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(BASE, "v2_items_wish.png"), full_page=False)

    # 回到全部，打开新增弹窗
    pg.click('#item-status-filters .chip[data-status="all"]')
    pg.wait_for_timeout(200)
    pg.click('#btn-add-item')
    pg.wait_for_timeout(350)
    pg.screenshot(path=os.path.join(BASE, "v2_items_modal.png"), full_page=False)

    b.close()
    print("shots done")
