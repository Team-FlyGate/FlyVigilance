"""Project-FlyGate 15초 티저의 사운드트랙을 외부 샘플 없이 합성합니다.

빌드된 티저 HTML 을 Playwright 로 열어 window.__reel.cues() · scenes() · DUR 을 읽고, 영상 길이와 정확히 맞는
48 kHz 스테레오 음원을 만든 뒤 AAC(M4A)로 저장합니다. 소리 부품은 쇼릴 v3(scripts/reel/audio_v3.py)와 같은 방식이고,
그 위에 120 BPM 음악 베드(킥 · 클랩 · 하이햇 · 펌핑 베이스 · 아르페지오 · 패드, Am–F–C–G 진행)를 깝니다.
티저의 컷은 모두 이 박자 격자(0.5초 + 0.5초 × n) 위에 있으므로 컷과 박이 맞습니다.
13.0초의 로고 장면 직전에 한 박을 비우고(드롭), 로고가 나올 때 A 장조 화음으로 끝냅니다.

사용:
  .venv/bin/python scripts/reel/audio_teaser15.py [빌드된 HTML] [출력 .m4a]
  기본값: web/public/showreel/FlyGate_teaser_15s_v1.0.0.html → scripts/reel/FlyGate_teaser_15s_v1.0.0_audio.m4a

영상과 합치기(scripts/render_reel.py 로 무음 MP4 를 만든 뒤):
  ffmpeg -i silent.mp4 -i scripts/reel/FlyGate_teaser_15s_v1.0.0_audio.m4a \
         -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -shortest FlyGate_teaser_15s_v1.0.0.mp4
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
SR = 48000
BPM = 120
BEAT = 60 / BPM
GRID0 = 0.5     # 첫 박(훅 장면 시작)
DROP = 12.5     # 이 박부터 킥을 빼고 스네어 롤 + 라이저로 로고 장면(13.0초)을 당깁니다
END0 = 13.0


async def read_timeline(path: pathlib.Path) -> dict:
    """티저가 스스로 내보내는 큐와 장면 경계를 읽습니다(시간은 모두 초)."""
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


def kick(g=1.0, n_sec=.4):
    n = S(n_sec); t = np.arange(n) / SR
    s = sine(45 + 120 * np.exp(-t * 35), n) * env(n, .001, .14)
    s += filt(noise(n), "bandpass", [1500, 6000]) * env(n, .0005, .005) * .4
    return np.tanh(s * 1.8 * g)


def clap(g=1.0):
    n = S(.35); s = np.zeros(n)
    for k, dt in enumerate([0, .008, .017, .026]):
        i = S(dt); m = n - i
        s[i:] += filt(noise(m), "bandpass", [900, 3500]) * env(m, .0004, .02 + k * .025)
    return np.tanh(s * 1.2) * g


def snare(g=1.0):
    n = S(.25)
    return (filt(noise(n), "bandpass", [1200, 7000]) * env(n, .0005, .06) + sine(190, n) * env(n, .001, .05) * .5) * g


def hat(open_=False):
    n = S(.18 if open_ else .05)
    return filt(noise(n), "highpass", 7500) * env(n, .0005, .05 if open_ else .012)


def boom(g=1.0, big=False):
    n = S(2.6 if big else 1.4); t = np.arange(n) / SR
    s = sine(32 + 80 * np.exp(-t * 5), n) * env(n, .003, .9 if big else .45) * 1.2
    s += filt(noise(n), "lowpass", 1000) * env(n, .002, .25) * .8
    s += filt(noise(n), "bandpass", [2000, 9000]) * env(n, .0005, .04) * .35
    return np.tanh(s * 1.5) * g


def hit(g=1.0):
    n = S(.5)
    s = kick(1.0, .5) * .9 + filt(noise(n), "bandpass", [900, 5000]) * env(n, .001, .09) * .7
    c = clap(.6); s[:len(c)] += c[:n] * .5
    return np.tanh(s * 1.3) * g


def slam(g=1.0):
    n = S(.3)
    return np.tanh((kick(1.0, .3) * .7 + filt(noise(n), "bandpass", [400, 3000]) * env(n, .001, .05) * .8) * 1.4) * g


def lock(f=1.0, big=False):
    n = S(1.4 if big else .6); s = np.zeros(n)
    for r, a in [(1, 1), (2.76, .5), (5.4, .25), (8.93, .12)]:
        s += sine(1046 * f * r, n) * env(n, .001, (.55 if big else .22) / r ** .5) * a
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


def glitch(d=.12):
    n = S(d); s = np.zeros(n); i = 0
    while i < n:
        m = S(rs.uniform(.006, .02)); f = rs.choice([180, 360, 720, 1440, 2880]) * rs.uniform(.9, 1.1)
        s[i:i + m] += (np.sign(sine(f, m)) * .25 * rs.uniform(.3, 1))[:max(0, min(m, n - i))]; i += m
    return s * np.linspace(1, .3, n)


def count(d=1.0, down=False):
    """오도미터 숫자 롤링에 맞춘 틱 연타(빠르게 시작해 느려집니다)."""
    n = S(d + .1); s = np.zeros(n)
    for k, tt in enumerate((1 - (1 - np.linspace(0, 1, 30)) ** 5) * d):
        b = tick((1.5 - k * .012) if down else (1.2 + k * .02)) * .35 * (1 - k / 45); i = S(tt); s[i:i + len(b)] += b[:max(0, n - i)]
    return s


def sweep(d=1.0):
    n = S(d); t = np.linspace(0, 1, n)
    return sine(500 * 2 ** (t * 1.8), n) * np.sin(np.pi * t) * .07


def scan(d=1.0):
    n = S(d); t = np.linspace(0, 1, n)
    return sine(2400 * 2 ** (-t * 1.2), n) * (.5 + .5 * np.sin(2 * np.pi * 26 * t * d)) * np.sin(np.pi * t) * .08


def tail(d, root=57):
    """A 장조 9화음 꼬리(로고 장면)."""
    n = S(d + 1.5); s = np.zeros(n)
    for m, a in [(root - 12, 1), (root - 5, .7), (root, .6), (root + 4, .5), (root + 7, .45), (root + 14, .3), (root + 19, .2)]:
        s += (saw(midi(m) * 1.002, n) + saw(midi(m) * .998, n)) * a
    s = filt(s, "lowpass", 2200) * env(n, .02, 1.8) * .035
    return s + sine(midi(root + 24), n) * env(n, .01, 1.2) * .05 + sine(midi(root + 31), n) * env(n, .01, .8) * .03


# ---------------------------------------------------------------- 음악 베드
# 마디(4박 = 2초)마다 화음: Am · F · C · G · Am · F (근음 MIDI, 3화음 구성음)
CHORDS = [(45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62]), (45, [57, 60, 64]), (41, [57, 60, 65]), (45, [57, 61, 64])]


def chord_at(t):
    return CHORDS[min(len(CHORDS) - 1, max(0, int((t - GRID0) // (BEAT * 4))))]


def music(put):
    """킥이 들어갈 때마다 베이스 · 패드 · 아르페지오를 눌러 주는(사이드체인) 120 BPM 베드."""
    beats = np.arange(GRID0, END0 - 1e-6, BEAT)
    # 패드: 마디마다 화음, 저역 통과
    for bi in range(len(CHORDS) - 1):
        t0 = GRID0 + bi * BEAT * 4
        if t0 >= END0:
            break
        d = min(BEAT * 4, END0 - t0) + .05
        n = S(d); tt = np.arange(n) / SR; s = np.zeros(n)
        for m in chord_at(t0 + .01)[1]:
            for det in (-.08, .08):
                s += saw(midi(m + det), n)
        cut = 900 if t0 < 7.5 else 1600
        s = filt(s, "lowpass", cut) * .016 * np.clip(np.minimum(tt / .05, (d - tt) / .05), 0, 1)
        put(s, t0, 1, 0, .5, duck=True)
    for b in beats:
        k = int(round((b - GRID0) / BEAT))   # 0부터 세는 박 번호
        drop = b >= DROP
        if not drop:
            put(kick(1.0), b, .62 if abs((b - GRID0) % (BEAT * 4)) < 1e-6 else .52, 0, .03)
        if b >= 2.5 and k % 2 == 1 and not drop:
            put(clap(1), b, .32, 0, .25)
        # 하이햇: 훅은 오프비트 8분, STEP 1 부터 16분, 실측 구간부터 오픈햇 추가
        for q in range(4):
            tq = b + q * BEAT / 4
            if tq >= END0:
                break
            if b < 2.5 and q != 2:
                continue
            if 2.5 <= b < 7.5 and q % 2 == 1 and q != 3:
                continue
            op = q == 2 and b >= 7.5
            put(hat(op), tq, (.09 if op else .06) * (1.0 if q == 2 else .75), .3 if q % 2 else -.3, .05)
        # 펌핑 베이스: 8분 음표, 근음
        root = chord_at(b)[0]
        if not drop:
            for h in (0, 1):
                n = S(BEAT / 2 * .95); tb = np.arange(n) / SR
                oct_ = 12 if (h == 1 and b >= 5.0) else 0
                x = saw(midi(root - 12 + oct_), n) * .6 + sine(midi(root - 12 + oct_), n)
                x = filt(x, "lowpass", 420 if b < 7.5 else 700) * np.minimum(1, tb / .004) * np.exp(-tb * 5)
                put(np.tanh(x * 1.4), b + h * BEAT / 2, .24, 0, 0, duck=True)
        # 아르페지오: STEP 1 부터 16분 음표로 화음 구성음을 오르내립니다
        if 2.5 <= b < DROP:
            tones = chord_at(b)[1]
            seq = [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 24] if b >= 7.5 else [tones[0] + 12, tones[1] + 12, tones[2] + 12, tones[1] + 12]
            for q in range(4):
                n = S(BEAT / 4 * .9); tn = np.arange(n) / SR
                x = (saw(midi(seq[q]) * 1.003, n) + saw(midi(seq[q]) * .997, n)) * .5
                x = filt(x, "lowpass", 2600 if b >= 7.5 else 1800) * np.exp(-tn * 18)
                put(x, b + q * BEAT / 4, .07, (-.4, .4, -.2, .2)[q], .45, duck=True)
    # 드롭: 스네어 롤 16분(점점 세게) + 위로 올라가는 휘익
    for q in range(8):
        tq = DROP + q * BEAT / 8
        put(snare(1), tq, .08 + q * .03, 0, .2)
    put(whoosh(END0 - DROP, up=True), DROP, .6, 0, .2)


def synth(tl: dict) -> np.ndarray:
    total = float(tl["dur"]); N = S(total)
    L = np.zeros(N + SR * 4); R = np.zeros_like(L); VL = np.zeros_like(L); VR = np.zeros_like(L)
    DL = np.zeros_like(L); DR = np.zeros_like(L)   # 사이드체인으로 눌러 줄 버스

    def put(sig, t, g=1.0, pan=0.0, send=0.0, duck=False):
        i = int(round(t * SR))
        if i >= len(L) or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        sig = sig[:len(L) - i]
        gl, gr = np.cos((pan + 1) * np.pi / 4) * g, np.sin((pan + 1) * np.pi / 4) * g
        (DL if duck else L)[i:i + len(sig)] += sig * gl; (DR if duck else R)[i:i + len(sig)] += sig * gr
        if send:
            VL[i:i + len(sig)] += sig * gl * send; VR[i:i + len(sig)] += sig * gr * send

    music(put)
    put(whoosh(GRID0, up=True), 0, .45, 0, .2)   # 포스터 프레임에서 첫 컷으로 당기는 소리

    for c in tl["cues"]:
        t, ty, g, d = c["t"], c["type"], c.get("g", 1.0), c.get("d") or .5
        pan = float(rs.uniform(-.5, .5))
        if ty == "click": put(click(c.get("f", 1)), t, .35 * g, pan, .3)
        elif ty == "tick": put(tick(c.get("f", 1)), t, .25 * g, pan * .5, .25)
        elif ty == "count": put(count(d, bool(c.get("down"))), t, .7, 0, .15)
        elif ty == "lock": put(lock(c.get("f", 1), bool(c.get("big"))), t, .7 if c.get("big") else .45, 0, .45)
        elif ty == "boom": put(boom(g, bool(c.get("big"))), t, .8, 0, .35)
        elif ty == "hit": put(hit(g), t, .55, 0, .25)
        elif ty == "slam": put(slam(g), t, .5, pan * .4, .2)
        elif ty == "whoosh": put(whoosh(d, bool(c.get("up"))), t, .5, 0, .3)
        elif ty == "riser": put(riser(d), t, .45, 0, .2)
        elif ty == "glitch": put(glitch(d), t, .3, 0, .1)
        elif ty == "sweep": put(sweep(d), t, .8, 0, .5)
        elif ty == "scan": put(scan(d), t, 1, 0, .4)
        elif ty == "tail": put(tail(d), t, 1, 0, .8)

    # 사이드체인: 킥 박마다 눌렀다가 풀어 줍니다(드롭 이후는 누르지 않습니다)
    gain = np.ones(len(L)); tt = np.arange(S(BEAT)) / SR
    shape = 1 - .75 * np.exp(-tt / .07)
    for b in np.arange(GRID0, DROP - 1e-6, BEAT):
        i = S(b); gain[i:i + len(shape)] = np.minimum(gain[i:i + len(shape)], shape[:len(gain) - i])
    L += DL * gain; R += DR * gain

    # 리버브 + 마스터
    irn = S(1.8); ti = np.arange(irn) / SR
    irs = [filt(rs.standard_normal(irn) * np.exp(-ti * 3.2), "lowpass", 6000) for _ in range(2)]
    irs = [ir / np.sqrt((ir ** 2).sum()) for ir in irs]
    L += fftconvolve(VL, irs[0])[:len(L)] * .8; R += fftconvolve(VR, irs[1])[:len(R)] * .8
    mix = filt(np.stack([L, R], 1)[:N].T, "highpass", 28).T
    fade = np.ones(N); fn = S(.35); fade[-fn:] = np.linspace(1, 0, fn) ** 2
    mix *= fade[:, None]
    mix = mix / (np.abs(mix).max() + 1e-9)
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)       # 소셜 피드용으로 조금 더 크게(부드러운 클리핑)
    return mix / (np.abs(mix).max() / .84)


def main():
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web/public/showreel/FlyGate_teaser_15s_v1.0.0.html"
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "scripts/reel/FlyGate_teaser_15s_v1.0.0_audio.m4a"
    tl = asyncio.run(read_timeline(src))
    mix = synth(tl)
    with tempfile.TemporaryDirectory() as td:
        wav = pathlib.Path(td) / "mix.wav"
        wavfile.write(wav, SR, (mix * 32767).astype(np.int16))
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB) · {tl['dur']} s · {len(tl['cues'])} cues")


if __name__ == "__main__":
    main()
