"""쇼릴 특정 시점 프레임 캡처. 사용: shoot_reel.py OUTDIR t1 t2 ..."""
import asyncio
import sys

from playwright.async_api import async_playwright


async def main(out, ts):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"])
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        pg.on("pageerror", lambda e: print("pageerror", e))
        await pg.goto("http://127.0.0.1:5173/showreel/index.html?paused=1")
        await pg.wait_for_timeout(2500)
        for t in ts:
            await pg.evaluate(f"window.__reel.seek({t})")
            await pg.wait_for_timeout(1200)
            await pg.screenshot(path=f"{out}/reel_{t}.png")
            print("frame", t)
        await b.close()

asyncio.run(main(sys.argv[1], [float(x) for x in sys.argv[2:]]))
