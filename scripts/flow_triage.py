"""라이브 트리아지 전체 흐름을 브라우저에서 실행하고 스크린샷을 남긴다."""
import asyncio
import sys

from playwright.async_api import async_playwright

OUT = sys.argv[1]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"])
        pg = await b.new_page(viewport={"width": 1680, "height": 1050})
        pg.on("pageerror", lambda e: print("pageerror", e))
        await pg.goto("http://127.0.0.1:5173/#/triage")
        await pg.wait_for_timeout(4000)
        await pg.get_by_role("button", name="Reflex · Jev").click()
        await pg.wait_for_selector("text=Router decision", timeout=60000)
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f"{OUT}/triage_reflex.png", full_page=True)
        await pg.get_by_role("button", name="Deliberate · Nemotron").click()
        await pg.wait_for_selector("text=System-2 메모와 3단 크리틱", timeout=240000)
        await pg.wait_for_timeout(1500)
        await pg.get_by_role("button", name="크리틱에 주입").click()
        await pg.wait_for_selector("text=/Jev 판정/", timeout=120000)
        await pg.wait_for_timeout(1500)
        card = pg.locator("section.card", has_text="과잉해석 주입 테스트")
        await card.screenshot(path=f"{OUT}/triage_probe.png")
        memo = pg.locator("section.card", has_text="System-2 메모와 3단 크리틱")
        await memo.screenshot(path=f"{OUT}/triage_memo.png")
        print("ok")
        await b.close()

asyncio.run(main())
