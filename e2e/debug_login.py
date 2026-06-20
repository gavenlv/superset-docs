"""调试 6.0 登录页 DOM 结构。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context()
    page = ctx.new_page()
    page.goto("http://localhost:18089/login/", wait_until="load", timeout=30000)
    page.wait_for_timeout(5000)  # 等 5 秒让 JS 跑完
    print("--- input elements ---")
    inputs = page.locator("input").all()
    for i, inp in enumerate(inputs):
        try:
            name = inp.get_attribute("name")
            id_ = inp.get_attribute("id")
            type_ = inp.get_attribute("type")
            visible = inp.is_visible()
            print(f"[{i}] name={name!r} id={id_!r} type={type_!r} visible={visible}")
        except Exception as e:
            print(f"[{i}] err: {e}")
    print("--- forms ---")
    forms = page.locator("form").all()
    for f in forms:
        try:
            print("form:", f.get_attribute("name") or f.get_attribute("id"))
        except Exception:
            pass
    print("--- url ---", page.url)
    print("--- title ---", page.title())
    page.screenshot(path="/tmp/6.0_login.png", full_page=True)
    print("screenshot saved to /tmp/6.0_login.png")
    b.close()
