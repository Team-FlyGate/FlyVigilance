"""Project-FlyGate 쇼릴 v4.3.0 의 사운드를 외부 샘플 없이 합성합니다.

합성 방식은 v4.1.0(audio_v4_1.py) · v4.2.0(audio_v4_2.py)과 같고, 읽는 HTML · 내보내는 파일만 v4.3.0 입니다.
v4.3.0 의 CLI 구간(cli_open … cli_line)은 HTML 이 새 시각으로 바로 적은 큐(글리치 컷 · 거대한 낱말 · 창 진입 · 줄 강조 · 확대 · 타자)를 그대로 씁니다.
v4.1.0 에서 이어 온 점:
  - 효과음 큐는 HTML 이 내보내는 새 시각을 그대로 씁니다(HTML 이 v4.0.0 큐를 새 박자로 옮겨 둡니다).
  - 리듬 베드를 장면마다 다시 맞춥니다. 장면 길이에 정수 박이 들어가도록 박 길이를 조금씩 조절해(100 BPM 안팎)
    모든 장면 전환이 강박(킥)에 떨어집니다.
  - 쉬는 구간(다리 장면의 문 통과 전, 커넥톰 장면)은 장면의 warp 기준점으로 새 시각에 맞춥니다.

사용:
  .venv/bin/python scripts/reel/audio_v4_3.py [빌드된 HTML] [출력 .m4a]
  기본값: web/public/showreel/FlyGate_showreel_v4.3.0.html → scripts/reel/FlyGate_showreel_v4.3.0_audio.m4a

영상과 합치기(scripts/render_reel.py 로 MP4 를 만든 뒤):
  ffmpeg -i silent.mp4 -i scripts/reel/FlyGate_showreel_v4.3.0_audio.m4a \\
         -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -shortest FlyGate_showreel_v4.3.0.mp4
"""
import asyncio
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from playwright.async_api import async_playwright
from scipy.io import wavfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import audio_v4 as A  # noqa: E402  소리 부품(click · kick · pad …)을 그대로 씁니다. audio_v4 는 가져오기만 해서는 아무것도 쓰지 않습니다

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web/public/showreel/FlyGate_showreel_v4.3.0.html"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "scripts/reel/FlyGate_showreel_v4.3.0_audio.m4a"
SR = A.SR
S, midi, noise, filt, env, sine = A.S, A.midi, A.noise, A.filt, A.env, A.sine


async def read_timeline(path: pathlib.Path) -> dict:
    """쇼릴이 스스로 내보내는 큐 · 장면 경계 · warp 기준점을 읽습니다(시간은 모두 초)."""
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal"])
        pg = await b.new_page(viewport={"width": 1280, "height": 720})
        await pg.goto(path.resolve().as_uri() + "?paused=1", wait_until="load")
        out = await pg.evaluate("({ dur: window.__reel.DUR, cues: window.__reel.cues(), scenes: window.__reel.scenes(), warp: window.__reel.warps() })")
        await b.close()
    return out


def new_local(knots, old_lt: float) -> float:
    """장면의 warp 기준점으로 옛 장면 안 시각을 새 장면 안 시각으로 옮깁니다."""
    o = [k[0] for k in knots]
    n = [k[1] for k in knots]
    return float(np.interp(old_lt, o, n))


def synth(tl: dict) -> np.ndarray:
    total = float(tl["dur"]); N = S(total)
    L = np.zeros(N + SR * 4); R = np.zeros_like(L); VL = np.zeros_like(L); VR = np.zeros_like(L)
    rs = A.rs

    def put(sig, t, g=1.0, pan=0.0, send=0.0):
        i = int(round(t * SR))
        if i >= len(L) or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        sig = sig[:len(L) - i]
        gl, gr = np.cos((pan + 1) * np.pi / 4) * g, np.sin((pan + 1) * np.pi / 4) * g
        L[i:i + len(sig)] += sig * gl; R[i:i + len(sig)] += sig * gr
        if send:
            VL[i:i + len(sig)] += sig * gl * send; VR[i:i + len(sig)] += sig * gr * send

    for c in tl["cues"]:
        t, ty, g, d = c["t"], c["type"], c.get("g", 1.0), c.get("d") or .5
        pan = float(rs.uniform(-.6, .6))
        if ty == "click": put(A.click(c.get("f", 1)), t, .35 * g, pan, .3)
        elif ty == "tick": put(A.tick(c.get("f", 1)), t, .22 * g, pan * .5, .25)
        elif ty == "count": put(A.count(d), t, .8, 0, .15)
        elif ty == "lock": put(A.lock(c.get("big")), t, .9 if c.get("big") else .6, 0, .5)
        elif ty == "boom": put(A.boom(g, c.get("big")), t, .8, 0, .35)
        elif ty == "hit": put(A.hit(g), t, .7, 0, .3)
        elif ty == "whoosh": put(A.whoosh(d, c.get("up")), t, .55, 0, .3)
        elif ty == "riser": put(A.riser(d), t, .5, 0, .2)
        elif ty == "glitch": put(A.glitch(d), t, .35, 0, .1)
        elif ty == "pulse": put(A.pulse(), t, .7, pan * .3, .5)
        elif ty == "sweep": put(A.sweep(d), t, .8, 0, .5)
        elif ty == "scan": put(A.scan(d), t, 1, 0, .4)
        elif ty == "pad": put(A.pad(d, c.get("note", 0)), t, 1, 0, .6)
        elif ty == "drone": put(A.drone(d), t, .8, 0, .3)
        elif ty == "tail": put(A.tail(d), t, 1, 0, .8)

    # 리듬 베드: STEP 1 부터 마무리 직전까지. 장면마다 정수 박이 들어가게 박 길이를 맞춰(100 BPM 안팎) 장면 전환이 늘 강박입니다.
    scenes = tl["scenes"]
    sc = {s["id"]: s for s in scenes}
    warp = tl["warp"]
    ids = [s["id"] for s in scenes]
    i0, i1 = ids.index("disc"), ids.index("close")
    rest = []
    if "bridge" in sc:   # 다리 장면: 분자가 문을 통과하는 순간(옛 3.1초)까지 비웁니다
        br = sc["bridge"]; rest.append((br["t0"], br["t0"] + new_local(warp["bridge"], 3.1)))
    if "arch" in sc:     # 커넥톰 장면은 통째로 비웁니다
        rest.append((sc["arch"]["t0"], sc["arch"]["t1"]))
    for s in scenes[i0:i1]:
        t0, t1 = s["t0"], s["t1"]
        nb = max(1, round((t1 - t0) / 0.6))
        beat = (t1 - t0) / nb
        for j in range(nb):
            b = t0 + j * beat
            if any(a <= b < z - 1e-6 for a, z in rest):
                continue
            accent = j == 0
            put(A.kick(.9), b, .36 if accent else .24, 0, .05)
            for k in range(4):   # 16분 하이햇, 세 번째는 오픈햇
                tt = b + k * beat / 4
                n = S(.06 if k != 2 else .16)
                put(filt(noise(n), "highpass", 7000) * env(n, .0005, .012 if k != 2 else .05), tt, (.06 if k != 2 else .085) * (1 if k else .7), .25 if k % 2 else -.25, .05)
            n = S(beat * .5); tb = np.arange(n) / SR   # 오프비트 서브 베이스
            bass = sine(midi(33), n) * np.minimum(1, tb / .03) * np.exp(-tb * 3)
            put(filt(bass + .3 * np.tanh(3 * bass), "lowpass", 180), b + beat / 2, .3, 0, 0)

    # 리버브 + 마스터 (v4.0.0 과 같습니다)
    irn = S(2.6); ti = np.arange(irn) / SR
    irs = [filt(rs.standard_normal(irn) * np.exp(-ti * 2.4), "lowpass", 6000) for _ in range(2)]
    irs = [ir / np.sqrt((ir ** 2).sum()) for ir in irs]
    from scipy.signal import fftconvolve
    L += fftconvolve(VL, irs[0])[:len(L)] * .9; R += fftconvolve(VR, irs[1])[:len(R)] * .9
    mix = filt(np.stack([L, R], 1)[:N].T, "highpass", 25).T
    fade = np.ones(N); fn = S(.6); fade[-fn:] = np.linspace(1, 0, fn) ** 2
    mix *= fade[:, None]
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    return mix / (np.abs(mix).max() / .89)


def main():
    tl = asyncio.run(read_timeline(SRC))
    mix = synth(tl)
    with tempfile.TemporaryDirectory() as td:
        wav = pathlib.Path(td) / "mix.wav"
        wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "160k", str(OUT)], check=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) · {tl['dur']} s · {len(tl['cues'])} cues")


if __name__ == "__main__":
    main()
