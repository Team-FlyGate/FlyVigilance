"""Project-FlyGate 쇼릴 v3 의 사운드를 외부 샘플 없이 합성합니다.

빌드된 쇼릴 HTML 을 Playwright 로 열어 window.__reel.cues() · scenes() · DUR 을 읽고, 영상 길이와 정확히 맞는
48 kHz 스테레오 음원을 만든 뒤 AAC(M4A)로 저장합니다. 소리 부품은 FDDD 쇼릴(build/synth.py)과 같은 방식입니다.
HTML 에는 소리를 넣지 않습니다(파일이 커지지 않게 합니다). 영상에 합치는 일은 렌더 뒤에 ffmpeg 로 합니다.

사용:
  .venv/bin/python scripts/reel/audio_v3.py [빌드된 HTML] [출력 .m4a]
  기본값: web/public/showreel/FlyGate_showreel_v3.0.0.html → scripts/reel/FlyGate_showreel_v3.0.0_audio.m4a

영상과 합치기(scripts/render_reel.py 로 MP4 를 만든 뒤):
  ffmpeg -i FlyGate_showreel_v3.0.0.mp4 -i scripts/reel/FlyGate_showreel_v3.0.0_audio.m4a \
         -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -shortest FlyGate_showreel_v3.0.0_av.mp4
"""
import asyncio
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from playwright.async_api import async_playwright
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web/public/showreel/FlyGate_showreel_v3.0.0.html"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "scripts/reel/FlyGate_showreel_v3.0.0_audio.m4a"
SR = 48000


async def read_timeline(path: pathlib.Path) -> dict:
    """쇼릴이 스스로 내보내는 큐와 장면 경계를 읽습니다(시간은 모두 초)."""
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chromium", args=["--use-angle=metal"])
        pg = await b.new_page(viewport={"width": 1280, "height": 720})
        await pg.goto(path.resolve().as_uri() + "?paused=1", wait_until="load")
        out = await pg.evaluate("({ dur: window.__reel.DUR, cues: window.__reel.cues(), scenes: window.__reel.scenes() })")
        await b.close()
    return out


# ---------------------------------------------------------------- 소리 부품
rs = np.random.default_rng(20260928)
S = lambda sec: int(sec * SR)
midi = lambda m: 440 * 2 ** ((m - 69) / 12)
noise = lambda n: rs.standard_normal(n)


def filt(x, kind, f, order=2):
    f = np.clip(np.atleast_1d(f), 20, SR / 2 - 100)
    return sosfilt(butter(order, f if len(f) > 1 else f[0], btype=kind, fs=SR, output="sos"), x)


def env(n, a=.002, d=.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(d, 1e-4))


def sine(f, n, ph=0.0):
    f = np.broadcast_to(f, (n,)).astype(float)
    return np.sin(2 * np.pi * np.cumsum(f) / SR + ph)


def saw(f, n):
    p = np.cumsum(np.broadcast_to(f, (n,)).astype(float)) / SR
    return 2 * (p - np.floor(p + .5))


def click(f=1.0):
    n = S(.012)
    return filt(noise(n), "highpass", 2500 * f) * env(n, .0003, .0022) + sine(3200 * f, n) * env(n, .0002, .003) * .6


def tick(f=1.0):
    n = S(.07)
    return sine(1600 * f, n) * env(n, .001, .012) + sine(3200 * f, n) * env(n, .0005, .005) * .3


def kick(g=1.0, n_sec=.45):
    n = S(n_sec); t = np.arange(n) / SR
    s = sine(42 + 110 * np.exp(-t * 32), n) * env(n, .001, .16)
    s += filt(noise(n), "bandpass", [1500, 6000]) * env(n, .0005, .006) * .35
    return np.tanh(s * 1.6 * g)


def boom(g=1.0, big=False):
    n = S(2.4 if big else 1.6); t = np.arange(n) / SR
    s = sine(30 + 70 * np.exp(-t * 5), n) * env(n, .004, .7 if big else .45) * 1.2
    s += filt(noise(n), "lowpass", 900) * env(n, .002, .25) * .8
    s += filt(noise(n), "bandpass", [2000, 9000]) * env(n, .0005, .03) * .3
    return np.tanh(s * 1.4) * g


def hit(g=1.0):
    n = S(.5)
    s = kick(1.0, .5) * .9 + filt(noise(n), "bandpass", [900, 5000]) * env(n, .001, .09) * .7
    clap = np.zeros(n)
    for k, dt in enumerate([0, .009, .019]):
        i = S(dt); m = n - i
        clap[i:] += filt(noise(m), "bandpass", [1000, 3000]) * env(m, .0005, .025 + k * .02)
    return np.tanh((s + clap * .5) * 1.3) * g


def lock(big=False):
    n = S(1.4 if big else .9); s = np.zeros(n)
    for r, a in [(1, 1), (2.76, .5), (5.4, .25), (8.93, .12)]:
        s += sine(1046 * r, n) * env(n, .001, (.5 if big else .3) / r ** .5) * a
    if big:
        k = kick(.8, .3); s[:len(k)] += k * .5
    return s * .5


def whoosh(d=1.0, up=False):
    n = S(d); x = noise(n); t = np.linspace(0, 1, n)
    lo, hi = filt(x, "bandpass", [150, 900]), filt(x, "bandpass", [1500, 9000])
    k = t ** 1.5 if up else 1 - (1 - t) ** 2
    shape = t ** 2.2 * (1 - np.clip((t - .97) / .03, 0, 1)) if up else np.sin(np.pi * t) ** 1.5
    return (lo * (1 - k) + hi * k) * shape * .5


def riser(d=1.0):
    n = S(d); t = np.linspace(0, 1, n)
    s = filt(noise(n), "highpass", 800) * t ** 2.5 * .4 + saw(220 * 2 ** (t * 2.2), n) * t ** 3 * .12 + sine(110 * 2 ** (t * 2), n) * t ** 2 * .2
    return s * (1 - np.clip((t - .985) / .015, 0, 1))


def glitch(d=.2):
    n = S(d); s = np.zeros(n); i = 0
    while i < n:
        m = S(rs.uniform(.008, .03)); f = rs.choice([180, 360, 720, 1440, 2880]) * rs.uniform(.9, 1.1)
        seg = np.sign(sine(f, m)) * .25 * rs.uniform(.3, 1)
        s[i:i + m] += seg[:max(0, min(m, n - i))]; i += m
    return s * np.linspace(.4, 1, n)


def count(d=1.0):
    """오도미터 숫자 롤링에 맞춘 틱 연타(빠르게 시작해 느려집니다)."""
    n = S(d + .1); s = np.zeros(n)
    for k, tt in enumerate((1 - (1 - np.linspace(0, 1, 42)) ** 5) * d):
        b = tick(1.3 + k * .02) * .35 * (1 - k / 60); i = S(tt); s[i:i + len(b)] += b[:max(0, n - i)]
    return s


def pulse():
    n = S(1.4); t = np.arange(n) / SR
    return (sine(98, n) * env(n, .01, .5) * .6 + sine(196 * (1 + .003 * np.sin(t * 30)), n) * env(n, .02, .35) * .25
            + filt(noise(n), "bandpass", [3000, 8000]) * env(n, .001, .05) * .15)


def sweep(d=1.0):
    n = S(d); t = np.linspace(0, 1, n)
    return sine(600 * 2 ** (t * 1.5), n) * np.sin(np.pi * t) * .06


def scan(d=1.0):
    n = S(d); t = np.linspace(0, 1, n)
    return sine(2400 * 2 ** (-t * 1.2), n) * (.5 + .5 * np.sin(2 * np.pi * 26 * t * d)) * np.sin(np.pi * t) * .08


def pad(d, note):
    n = S(d); t = np.arange(n) / SR; s = np.zeros(n)
    for iv, a in [(0, 1), (7, .7), (12, .6), (15, .45), (19, .35), (26, .2)]:
        for det in (-.07, .07):
            s += saw(midi(45 + note + iv + det), n) * a
    return filt(s, "lowpass", 900) * .018 * np.clip(np.minimum(1, np.minimum(t / .4, (d - t) / .4)), 0, 1)


def drone(d):
    n = S(d); t = np.linspace(0, 1, n)
    return (sine(55, n) * .25 + filt(saw(55.3, n), "lowpass", 300) * .08 + filt(noise(n), "bandpass", [200, 600]) * .02) * t ** .7


def tail(d):
    n = S(d + 1.5); s = np.zeros(n)
    for m, a in [(45, 1), (52, .7), (57, .6), (61, .5), (64, .45), (71, .3), (76, .2)]:   # A 메이저 9
        s += (saw(midi(m) * 1.001, n) + saw(midi(m) * .999, n)) * a
    s = filt(s, "lowpass", 1600) * env(n, .05, 1.6) * .03
    return s + sine(midi(81), n) * env(n, .01, 1.2) * .05 + sine(midi(88), n) * env(n, .01, .8) * .03


def synth(tl: dict) -> np.ndarray:
    total = float(tl["dur"]); N = S(total)
    L = np.zeros(N + SR * 4); R = np.zeros_like(L); VL = np.zeros_like(L); VR = np.zeros_like(L)

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
        if ty == "click": put(click(c.get("f", 1)), t, .35 * g, pan, .3)
        elif ty == "tick": put(tick(c.get("f", 1)), t, .22 * g, pan * .5, .25)
        elif ty == "count": put(count(d), t, .8, 0, .15)
        elif ty == "lock": put(lock(c.get("big")), t, .9 if c.get("big") else .6, 0, .5)
        elif ty == "boom": put(boom(g, c.get("big")), t, .8, 0, .35)
        elif ty == "hit": put(hit(g), t, .7, 0, .3)
        elif ty == "whoosh": put(whoosh(d, c.get("up")), t, .55, 0, .3)
        elif ty == "riser": put(riser(d), t, .5, 0, .2)
        elif ty == "glitch": put(glitch(d), t, .35, 0, .1)
        elif ty == "pulse": put(pulse(), t, .7, pan * .3, .5)
        elif ty == "sweep": put(sweep(d), t, .8, 0, .5)
        elif ty == "scan": put(scan(d), t, 1, 0, .4)
        elif ty == "pad": put(pad(d, c.get("note", 0)), t, 1, 0, .6)
        elif ty == "drone": put(drone(d), t, .8, 0, .3)
        elif ty == "tail": put(tail(d), t, 1, 0, .8)

    # 리듬 베드: STEP 1 부터 마무리 직전까지 100 BPM. 장면이 바뀌는 첫 박에는 킥을 조금 세게 둡니다.
    sc = {s["id"]: (s["t0"], s["t1"]) for s in tl["scenes"]}
    start, stop = sc.get("disc", (0, 0))[0], sc.get("close", (total, total))[0]
    beat = 60 / 100
    starts = {round(s["t0"], 3) for s in tl["scenes"]}
    for b in np.arange(start, stop - 1e-6, beat):
        accent = any(abs(b - s0) < beat / 2 for s0 in starts)
        put(kick(.9), b, .36 if accent else .24, 0, .05)
        for k in range(4):   # 16분 하이햇, 세 번째는 오픈햇
            tt = b + k * beat / 4
            if tt >= stop:
                break
            n = S(.06 if k != 2 else .16)
            put(filt(noise(n), "highpass", 7000) * env(n, .0005, .012 if k != 2 else .05), tt, (.06 if k != 2 else .085) * (1 if k else .7), .25 if k % 2 else -.25, .05)
        n = S(beat * .5); tb = np.arange(n) / SR   # 오프비트 서브 베이스
        bass = sine(midi(33), n) * np.minimum(1, tb / .03) * np.exp(-tb * 3)
        put(filt(bass + .3 * np.tanh(3 * bass), "lowpass", 180), b + beat / 2, .3, 0, 0)

    # 리버브 + 마스터
    irn = S(2.6); ti = np.arange(irn) / SR
    irs = [filt(rs.standard_normal(irn) * np.exp(-ti * 2.4), "lowpass", 6000) for _ in range(2)]
    irs = [ir / np.sqrt((ir ** 2).sum()) for ir in irs]
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
