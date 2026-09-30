"""FlyGate 세로 숏폼(15초 · 30초)의 음악 · 효과음을 외부 샘플 없이 합성합니다.

소리 부품은 쇼릴과 같습니다(audio_v4.py). 숏폼은 짧으므로 포스터가 끝나는 때부터 마무리 직전까지 리듬 베드를 계속 깔고,
장면마다 정수 박이 들어가게 박 길이를 조금씩 맞춰(120 BPM 안팎) 장면 전환이 늘 강박에 떨어지게 합니다.

사용:
  .venv/bin/python scripts/reel/audio_short_v1.py 빌드된_숏폼.html 출력.m4a
"""
import asyncio
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from playwright.async_api import async_playwright
from scipy.io import wavfile
from scipy.signal import fftconvolve

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import audio_v4 as A  # noqa: E402  소리 부품만 가져다 씁니다

SR = A.SR
S, midi, noise, filt, env, sine = A.S, A.midi, A.noise, A.filt, A.env, A.sine


async def read_timeline(path: pathlib.Path) -> dict:
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium")
        pg = await b.new_page(viewport={"width": 540, "height": 960})
        await pg.goto(path.resolve().as_uri() + "?paused=1", wait_until="load")
        out = await pg.evaluate("({ dur: window.__reel.DUR, cues: window.__reel.cues(), scenes: window.__reel.scenes() })")
        await b.close()
    return out


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
        pan = float(rs.uniform(-.5, .5))
        if ty == "count": put(A.count(d), t, .8, 0, .15)
        elif ty == "lock": put(A.lock(c.get("big")), t, .7, 0, .5)
        elif ty == "boom": put(A.boom(g, c.get("big")), t, .8, 0, .35)
        elif ty == "hit": put(A.hit(g), t, .7, 0, .3)
        elif ty == "whoosh": put(A.whoosh(d, c.get("up")), t, .5, 0, .3)
        elif ty == "riser": put(A.riser(d), t, .45, 0, .2)
        elif ty == "glitch": put(A.glitch(d), t, .35, 0, .1)
        elif ty == "pulse": put(A.pulse(), t, .7, pan * .3, .5)
        elif ty == "sweep": put(A.sweep(d), t, .7, 0, .5)
        elif ty == "scan": put(A.scan(d), t, .9, 0, .4)
        elif ty == "pad": put(A.pad(d, c.get("note", 0)), t, .9, 0, .6)
        elif ty == "tail": put(A.tail(d), t, 1, 0, .8)

    # 리듬 베드: 포스터 다음 장면부터 마무리 장면 시작까지(마무리는 패드와 여운만)
    scenes = tl["scenes"]
    for s in scenes[1:-1]:
        t0, t1 = s["t0"], s["t1"]
        nb = max(1, round((t1 - t0) / 0.5))
        beat = (t1 - t0) / nb
        for j in range(nb):
            b = t0 + j * beat
            put(A.kick(.95), b, .40 if j == 0 else .28, 0, .05)
            for k in range(4):   # 16분 하이햇, 세 번째는 오픈햇
                tt = b + k * beat / 4
                n = S(.06 if k != 2 else .16)
                put(filt(noise(n), "highpass", 7000) * env(n, .0005, .012 if k != 2 else .05), tt, (.07 if k != 2 else .09) * (1 if k else .7), .25 if k % 2 else -.25, .05)
            n = S(beat * .5); tb = np.arange(n) / SR   # 오프비트 서브 베이스
            bass = sine(midi(33 if j % 8 < 4 else 36), n) * np.minimum(1, tb / .03) * np.exp(-tb * 3)
            put(filt(bass + .3 * np.tanh(3 * bass), "lowpass", 180), b + beat / 2, .32, 0, 0)

    irn = S(2.2); ti = np.arange(irn) / SR
    irs = [filt(rs.standard_normal(irn) * np.exp(-ti * 2.6), "lowpass", 6000) for _ in range(2)]
    irs = [ir / np.sqrt((ir ** 2).sum()) for ir in irs]
    L += fftconvolve(VL, irs[0])[:len(L)] * .9; R += fftconvolve(VR, irs[1])[:len(R)] * .9
    mix = filt(np.stack([L, R], 1)[:N].T, "highpass", 25).T
    fade = np.ones(N); fn = S(.5); fade[-fn:] = np.linspace(1, 0, fn) ** 2
    mix *= fade[:, None]
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    return mix / (np.abs(mix).max() / .89)


def main():
    src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    mix = synth(asyncio.run(read_timeline(src)))
    with tempfile.TemporaryDirectory() as td:
        wav = pathlib.Path(td) / "mix.wav"
        wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(out)], check=True)


if __name__ == "__main__":
    main()
