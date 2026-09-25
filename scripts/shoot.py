"""대시보드 페이지 스크린샷 (Playwright, WebGL 사용). 사용: shoot.py OUTDIR page1 page2 ..."""
import asyncio
import sys

from playwright.async_api import async_playwright


async def main(out, pages, base="http://127.0.0.1:5173"):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"])
        pg = await b.new_page(viewport={"width": 1680, "height": 1050}, device_scale_factor=1)
        errs = []
        pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        for name in pages:
            await pg.goto(f"{base}/#/{name}")
            await pg.wait_for_timeout(9000)
            await pg.screenshot(path=f"{out}/{name}.png", full_page=True)
            print("shot", name)
        await b.close()
        print("\n".join(errs[:30]))


asyncio.run(main(sys.argv[1], sys.argv[2:]))
