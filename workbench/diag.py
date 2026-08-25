from playwright.sync_api import sync_playwright
import os
BASE = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page(viewport={"width": 1180, "height": 800})
    pg.goto("http://localhost:8765/")
    pg.wait_for_timeout(600)
    pg.click('.tab[data-view="items"]')
    pg.wait_for_timeout(300)
    info = pg.evaluate("""() => {
        const btn = document.getElementById('btn-add-item');
        const cs = getComputedStyle(btn);
        return {
            text: btn.textContent,
            innerHTML: btn.innerHTML,
            color: cs.color, bg: cs.backgroundImage || cs.backgroundColor,
            fontSize: cs.fontSize, fontWeight: cs.fontWeight, padding: cs.padding,
            width: btn.getBoundingClientRect().width, height: btn.getBoundingClientRect().height,
            display: cs.display, visibility: cs.visibility, overflow: cs.overflow
        };
    }""")
    print("BUTTON DIAG:", info)
    # Also check what the thumbnail height is
    thumb = pg.evaluate("""() => {
        const t = document.querySelector('.ithumb');
        const r = t.getBoundingClientRect();
        return {w: r.width, h: r.height};
    }""")
    print("THUMB:", thumb)
    b.close()