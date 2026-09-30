"""쇼릴을 30fps 프레임 단위로 렌더링해 MP4 로 만듭니다. 사용: render_reel.py OUT.mp4 [fps] [page_url] [wide|square|vertical]

규격(v4.3.0 최종본부터): square 는 1080×1080, vertical 은 1080×1920 창으로 열고 ?fmt= 를 붙입니다.

page_url 기본값은 개발 서버의 v3 쇼릴입니다. 쇼릴은 파일 하나로 완결되므로 file:// 주소를 그대로 줄 수 있습니다.
"""
import asyncio
import os
import subprocess
import sys

from playwright.async_api import async_playwright

OUT = sys.argv[1]
FPS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
PAGE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:5173/showreel/FlyGate_showreel_v3.0.0.html"
FMT = sys.argv[4] if len(sys.argv) > 4 else "wide"
VW, VH = {"wide": (1920, 1080), "square": (1080, 1080), "vertical": (1080, 1920)}[FMT]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-gpu"])
        pg = await b.new_page(viewport={"width": VW, "height": VH})
        await pg.goto(f"{PAGE}?paused=1" + ("" if FMT == "wide" else f"&fmt={FMT}"), wait_until="domcontentloaded", timeout=60000)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(3000)
        await pg.add_style_tag(content="#hud{display:none!important}")
        dur = await pg.evaluate("window.__reel.DUR")
        n = int(dur * FPS)
        # 나눠 렌더링: REEL_PART=k/W 이면 k번째 구간만 뽑습니다(여러 개를 동시에 돌린 뒤 ffmpeg concat 으로 잇습니다)
        k, w = map(int, os.environ.get("REEL_PART", "0/1").split("/"))
        f0, f1 = n * k // w, (n * (k + 1) // w if k + 1 < w else n + 1)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", OUT],
                              stdin=subprocess.PIPE)
        for i in range(f0, f1):
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
