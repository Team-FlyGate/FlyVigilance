"""쇼릴을 30fps 프레임 단위로 렌더링해 MP4 로 만든다. 사용: render_reel.py OUT.mp4 [fps] [base_url]"""
import asyncio
import subprocess
import sys

from playwright.async_api import async_playwright

OUT = sys.argv[1]
FPS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
BASE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:5173"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"])
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.goto(f"{BASE}/showreel/index.html?paused=1", wait_until="domcontentloaded", timeout=60000)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(3000)
        await pg.add_style_tag(content="#hud{display:none!important}")
        dur = await pg.evaluate("window.__reel.DUR")
        n = int(dur * FPS)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", OUT],
                              stdin=subprocess.PIPE)
        for i in range(n + 1):
            await pg.evaluate(f"window.__reel.renderAt({i / FPS})")
            buf = await pg.screenshot(type="jpeg", quality=92)
            ff.stdin.write(buf)
            if i % (FPS * 10) == 0:
                print(f"{i / FPS:.0f}s", flush=True)
        ff.stdin.close()
        ff.wait()
        await b.close()
        print("done", OUT)

asyncio.run(main())
