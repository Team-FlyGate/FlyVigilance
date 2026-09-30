"""Project-FlyGate 쇼릴 v4.3.0 내레이션판을 만듭니다(Gemini TTS 음성 + 음성 길이에 맞춘 장면 시간).

v4.3.0 최종본(build_reel_v4_3_final.py)과 같은 템플릿 · 대본을 쓰고, 다음만 다릅니다.
  1) 대본의 문장마다 Gemini TTS(scripts/reel/tts_gemini.py, gemini-3.8-flash-tts)로 음성을 만듭니다.
     읽기용 한글 표기(플라이게이트 등)는 영어 원문으로 되돌려 원어민 발음으로 읽게 하고, PARP1 은 글자를 하나씩 읽게 합니다.
  2) 문장마다 실제 음성 길이로 박자 길이를 다시 잡아(NARR_DUR) 장면 · 자막 · 강조가 음성과 맞습니다.
  3) 새 시간표로 음악 · 효과음(scripts/reel/audio_v4_3.py)을 다시 만들고, 내레이션이 나오는 동안 음악을 줄여 섞습니다.
  4) 섞은 음원을 AAC 로 HTML 안에 넣습니다(파일 하나로 완결). 페이지에서 '내레이션 켜고 보기' 를 누르면 소리와 함께 재생됩니다.

사용:
  .venv/bin/python scripts/build_reel_v4_3_narrated.py ko Aoede
  .venv/bin/python scripts/build_reel_v4_3_narrated.py en Puck
출력:
  web/public/showreel/FlyGate_showreel_v4.3.0[-en]-narrated-<voice>.html
  scripts/reel/narrated/<lang>-<voice>.m4a (MP4 용 192k) · scripts/reel/narrated/<lang>-<voice>.timeline.json
음성 조각은 data/cache/tts/ 에 모아 두고(저장소 밖), 같은 문장 · 목소리는 다시 부르지 않습니다.
"""
import base64
import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "reel"))
import build_reel_v4_3_final as B  # noqa: E402
import reel_v4_3_en as en  # noqa: E402
import tts_gemini as T  # noqa: E402

ROOT = B.ROOT
CACHE = ROOT / "data/cache/tts"
NARR_DIR = ROOT / "scripts/reel/narrated"
MIX_SR = 48000
DUCK = 0.32          # 내레이션이 나오는 동안 음악 · 효과음 크기
VO_GAIN = 1.0

# FlyGate 를 붙여 쓰면 한국어 문장 안에서 '플레이게이트' 로 들립니다(받아쓰기로 확인). 'Fly Gate' 로 띄어 씁니다
KO_FIX = [("프로젝트 플라이게이트", "Project Fly Gate"), ("플라이디스커버리", "FlyDiscovery"), ("플라이비질런스", "FlyVigilance"), ("플라이게이트", "Fly Gate")]


def tts_text(text: str, lang: str) -> str:
    """읽기용 한글 표기를 영어 원문으로 되돌리고, PARP1 은 글자를 하나씩 읽게 씁니다"""
    if lang == "ko":
        for a, b in KO_FIX:
            text = text.replace(a, b)
        text = text.replace("7문항", "일곱 문항")
    text = re.sub(r"\bFlyGate\b", "Fly Gate", text)
    return re.sub(r"\bPARP1\b", "P-A-R-P 1", text)


def clip_path(text: str, voice: str, lang: str) -> pathlib.Path:
    key = hashlib.sha1(f"{T.MODEL}|{voice}|{T.STYLE_KO if lang == 'ko' else T.STYLE_EN}|{text}".encode()).hexdigest()[:16]
    return CACHE / voice / lang / f"{key}.wav"


def clip(text: str, voice: str, lang: str) -> pathlib.Path:
    p = clip_path(text, voice, lang)
    if not p.exists():
        pcm = T.synth(text, voice, T.STYLE_KO if lang == "ko" else T.STYLE_EN)
        T.write_wav(p, trim(pcm))
    return p


def split_scene(pcm: bytes, texts: list[str]) -> list[bytes] | None:
    """장면 전체를 한 번에 읽은 음성을 문장 사이 쉼(가장 긴 무음 n-1 곳)에서 나눕니다.
    나눈 조각의 길이 비율이 글자 수 비율과 크게 어긋나면 None 을 돌려 문장별로 다시 부르게 합니다"""
    n = len(texts)
    a = np.frombuffer(pcm, dtype=np.int16)
    if n == 1:
        return [trim(pcm)]
    hop = int(0.01 * T.SR)
    env = np.array([np.abs(a[i:i + hop]).max() if len(a[i:i + hop]) else 0 for i in range(0, len(a), hop)])
    quiet = env < 400
    gaps, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if i > 0 and j < len(quiet):
                gaps.append((j - i, (i + j) // 2))
            i = j
        else:
            i += 1
    if len(gaps) < n - 1:
        return None
    cuts = sorted(c for _, c in sorted(gaps, reverse=True)[: n - 1])
    bounds = [0] + [c * hop for c in cuts] + [len(a)]
    segs = [trim(a[bounds[k]:bounds[k + 1]].tobytes()) for k in range(n)]
    L = np.array([len(t) for t in texts], float)
    D = np.array([len(x) / 2 / T.SR for x in segs])
    r = (D / D.sum()) / (L / L.sum())
    return segs if r.min() > 0.55 and r.max() < 1.8 else None


def split_whole(pcm: bytes, texts: list[str]) -> list[bytes | None]:
    """대본 전체를 한 번에 읽은 음성을 문장별로 나눕니다.
    문장 k 의 끝은 앞 경계 + (글자 수 비례 예상 길이) 근처(0.5~1.7배)에서 가장 긴 쉼으로 고릅니다.
    나눈 조각의 길이 비율이 글자 수 비율과 크게 어긋나면 그 조각은 None 으로 돌려 장면 단위로 다시 부르게 합니다"""
    a = np.frombuffer(pcm, dtype=np.int16)
    hop = int(0.01 * T.SR)
    env = np.array([np.abs(a[i:i + hop]).max() for i in range(0, len(a) - hop, hop)])
    quiet = env < 400
    gaps, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if i > 0 and j < len(quiet) and j - i >= 8:
                gaps.append(((i + j) // 2 * hop, (j - i) * hop))
            i = j
        else:
            i += 1
    L = np.array([len(t.replace(" ", "")) for t in texts], float)
    rate = len(a) / L.sum()
    cuts, prev = [], 0
    for k in range(len(texts) - 1):
        exp = L[k] * rate
        cand = [g for g in gaps if prev + 0.5 * exp < g[0] < prev + 1.7 * exp]
        cut = max(cand, key=lambda g: g[1] / T.SR - 0.6 * abs(g[0] - prev - exp) / exp)[0] if cand else int(prev + exp)
        cuts.append(cut)
        prev = cut
    bounds = [0] + cuts + [len(a)]
    segs = [trim(a[bounds[k]:bounds[k + 1]].tobytes()) for k in range(len(texts))]
    D = np.array([len(x) / 2 / T.SR for x in segs])
    r = (D / D.sum()) / (L / L.sum())
    return [x if 0.55 < rk < 1.8 else None for x, rk in zip(segs, r)]


def whole_clips(scenes: list, voice: str, lang: str):
    """판 하나의 대본 전체를 한 번에 불러 문장별로 나눠 캐시에 둡니다(호출 1번). 나누기에 실패한 장면은 캐시에 두지 않습니다"""
    texts = [t for _, ts in scenes for t in ts]
    if all(clip_path(t, voice, lang).exists() for t in texts):
        return
    style = T.STYLE_KO if lang == "ko" else T.STYLE_EN
    pcm = T.synth("\n\n".join(texts), voice, style)
    segs = split_whole(pcm, texts)
    print(f"  whole: {len(pcm) / 2 / T.SR:.1f} s · 문장 {len(texts)} · 나누기 성공 {sum(x is not None for x in segs)}")
    k = 0
    for _, ts in scenes:
        part = segs[k:k + len(ts)]
        k += len(ts)
        if all(x is not None for x in part):
            for t, x in zip(ts, part):
                if not clip_path(t, voice, lang).exists():
                    T.write_wav(clip_path(t, voice, lang), x)


def scene_clips(texts: list[str], voice: str, lang: str) -> list[pathlib.Path]:
    """장면의 문장들을 한 번에 불러 문장별 조각으로 나눠 캐시에 둡니다. 이미 있는 문장은 부르지 않습니다"""
    ps = [clip_path(t, voice, lang) for t in texts]
    if all(p.exists() for p in ps):
        return ps
    style = T.STYLE_KO if lang == "ko" else T.STYLE_EN
    pcm = T.synth("\n\n".join(texts), voice, style)
    segs = split_scene(pcm, texts)
    if segs is None:
        print(f"  · 장면을 문장별로 나누지 못해 문장마다 다시 부릅니다: {texts[0][:30]}…")
        return [clip(t, voice, lang) for t in texts]
    for p, x in zip(ps, segs):
        T.write_wav(p, x)
    return ps


def trim(pcm: bytes, th: int = 300) -> bytes:
    """앞뒤 무음을 잘라 박자 시작에 바로 말이 나오게 합니다(앞 0.03초 · 끝 0.10초 여유, 경계는 섞을 때 페이드로 다듬습니다)"""
    a = np.frombuffer(pcm, dtype=np.int16)
    idx = np.nonzero(np.abs(a) > th)[0]
    if not len(idx):
        return pcm
    s, e = max(0, idx[0] - int(0.03 * T.SR)), min(len(a), idx[-1] + int(0.10 * T.SR))
    return a[s:e].tobytes()


def wav_dur(p: pathlib.Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def read_wav48(p: pathlib.Path) -> np.ndarray:
    """모노 24kHz 조각을 48kHz 로 올려 float 배열로 돌려줍니다"""
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    x = np.arange(len(a) * 2) / 2
    y = np.interp(x, np.arange(len(a)), a).astype(np.float32)
    # 조각의 앞뒤를 파형 중간에서 자르면 문장 끝마다 '틱' 소리가 납니다. 앞 10ms · 뒤 40ms 를 서서히 줄여 이어 붙입니다
    fi, fo = min(len(y), int(0.010 * MIX_SR)), min(len(y), int(0.040 * MIX_SR))
    y[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    y[len(y) - fo:] *= np.linspace(1, 0, fo, dtype=np.float32) ** 2
    return y


def decode(p: pathlib.Path) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "2", "-ar", str(MIX_SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).reshape(-1, 2).copy()


BATCH = 8                      # 한 번에 부르는 문장 수
SEP = " [long pause] "         # 문장 사이에 긴 쉼을 넣는 오디오 태그(소리 내 읽지 않습니다). 문장 사이 쉼 0.7~0.9초 · 문장 안 쉼 0.25초 이하로 갈립니다
CHECK_MODEL = "gemini-3.8-flash"


def batch_split(pcm: bytes, n: int) -> list[bytes] | None:
    """문장 n개를 이어 읽은 음성을 가장 긴 쉼 n-1 곳에서 자릅니다. 문장 사이 쉼이 문장 안 쉼보다 뚜렷하게 길지 않으면 None"""
    if n == 1:
        return [trim(pcm)]
    a = np.frombuffer(pcm, dtype=np.int16)
    hop = int(0.01 * T.SR)
    env = np.array([np.abs(a[i:i + hop]).max() for i in range(0, len(a) - hop, hop)])
    quiet = env < 400
    gaps, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if i > 0 and j < len(quiet):
                gaps.append((j - i, (i + j) // 2 * hop))
            i = j
        else:
            i += 1
    if len(gaps) < n - 1:
        return None
    gaps.sort(reverse=True)
    chosen, rest = gaps[:n - 1], gaps[n - 1:]
    if chosen[-1][0] < 35:   # 문장 사이 쉼은 0.35초 이상이어야 합니다
        print(f"  · 쉼 부족 {[g[0] for g in gaps[:n + 1]]}")
        return None
    cuts = sorted(c for _, c in chosen)
    bounds = [0] + cuts + [len(a)]
    segs = [trim(a[bounds[k]:bounds[k + 1]].tobytes()) for k in range(n)]
    batch_split.bounds = bounds
    # 문장 사이 쉼이 문장 안 쉼보다 뚜렷하게(1.5배 이상) 길면 '깨끗한 자르기' 로 표시합니다
    batch_split.clear = not rest or chosen[-1][0] >= 1.5 * rest[0][0]
    return segs


def _norm(t: str, lang: str) -> str:
    return re.sub(r"[^가-힣]", "", t) if lang == "ko" else re.sub(r"[^a-z]", "", t.lower())


def verify_batch(segs: list[bytes], texts: list[str], lang: str) -> bool:
    """조각마다 그 번호의 대본 문장을 읽은 것이 맞는지 판단 모델에 한 번에 묻습니다(true/false 배열).
    글자 비교는 영어 낱말을 한글로 받아 적는 차이(FlyVigilance ↔ 플라이 비질런스) 때문에 틀린 불일치를 내어 쓰지 않습니다"""
    import io, time, urllib.error, urllib.request
    parts = [{"text": "대본 문장:\n" + "\n".join(f"[{k}] {t}" for k, t in enumerate(texts, 1)) + "\n\n음성 조각:"}]
    for k, x in enumerate(segs, 1):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(T.SR); w.writeframes(x)
        parts += [{"text": f"[{k}]"}, {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(buf.getvalue()).decode()}}]
    parts.append({"text": f"음성 조각 [k]가 대본 문장 [k] 하나를 처음부터 끝까지 읽은 것이면 true, 다른 문장이거나 일부가 빠지거나 다른 문장이 섞였으면 false 입니다. "
                          f"영어 낱말을 한국어식으로 읽거나 숫자를 읽는 방식 차이는 괜찮습니다. 불리언 {len(segs)}개의 JSON 배열로만 답하세요."})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}
    for i in range(6):
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{CHECK_MODEL}:generateContent", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "x-goog-api-key": T.api_key()})
            d = json.load(urllib.request.urlopen(req, context=T.CTX, timeout=180))
            got = json.loads(d["candidates"][0]["content"]["parts"][0]["text"])
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503):
                time.sleep(20); continue
            print(f"  · 확인 실패 {e.code}"); return False
        except (KeyError, IndexError, ValueError):
            time.sleep(3); continue
    else:
        print("  · 확인 응답 없음"); return False
    if not isinstance(got, list) or len(got) != len(texts):
        print(f"  · 확인 응답 개수 불일치 {got}"); return False
    if not all(got):
        print(f"  · 불일치 조각 {[k + 1 for k, v in enumerate(got) if not v]}")
    return all(got)


WHISPER_PY = pathlib.Path.home() / ".local/share/uv/tools/openai-whisper/bin/python"
STT = ROOT / "scripts/reel/stt_whisper.py"


# 받아쓰기와 대본을 같은 표기로 맞춥니다(고유명사는 한글로 들리든 영문으로 적히든 같은 글자로)
NAME_FOLD = [("플라이 게이트", "flygate"), ("플라이게이트", "flygate"), ("플라이디스커버리", "flydiscovery"), ("플라이 디스커버리", "flydiscovery"),
             ("플라이비질런스", "flyvigilance"), ("플라이 비질런스", "flyvigilance"), ("네모트론", "nemotron"), ("스텝", "step"), ("페어스", "faers")]
STYLE_LEAK = re.compile(r"fast|energetic|패스트|에너제틱|에너지틱|빠르게|활기|long ?pause|롱 ?포즈", re.I)


def _norm(t: str, lang: str) -> str:
    t = t.lower()
    for a, b in NAME_FOLD:
        t = t.replace(a, b)
    return re.sub(r"[^가-힣a-z0-9]" if lang == "ko" else r"[^a-z0-9]", "", t)


def edges(pcm: bytes, gap: float = 0.25, most: float = 2.0) -> tuple[bytes | None, bytes | None]:
    """조각의 앞머리 · 끝부분(쉼 앞 · 뒤 2초 이내의 짧은 말)을 따로 잘라 돌려줍니다.
    문장 전체를 받아 적으면 모델이 앞머리의 'Fast. Energetic.' 같은 말을 빼고 적어서 따로 확인합니다"""
    a = np.frombuffer(pcm, np.int16).astype(float)
    hop = 240
    if len(a) < hop * 20:
        return None, None
    e = np.sqrt(np.mean(a[:len(a) // hop * hop].reshape(-1, hop) ** 2, 1))
    q = e < 0.02 * e.max()
    runs, i = [], 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]:
                j += 1
            if i > 0 and j < len(q) and (j - i) * hop / T.SR >= gap:
                runs.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    head = a[:runs[0][0]] if runs and runs[0][0] / T.SR <= most else None
    tail = a[runs[-1][1]:] if runs and (len(a) - runs[-1][1]) / T.SR <= most else None
    return tuple(None if x is None else x.astype(np.int16).tobytes() for x in (head, tail))


def speech_problem(got: str, text: str, near: list[str], lang: str, head: str | None = None, tail: str | None = None) -> str | None:
    """조각 하나의 받아쓰기를 대본과 대조해 문제를 한 줄로 돌려줍니다(없으면 None).
    - 다른 문장이 들어감: 자기 문장보다 앞뒤 문장과 더 비슷함
    - 말투 태그 낭독: fast · energetic 이 들림(앞머리 · 끝부분을 따로 받아 적은 것까지)
    - 대본에 없는 말: 앞머리 · 끝부분이 대본의 시작 · 끝과 닮지 않았거나,
      전체 받아쓰기에서 앞 · 뒤에 5자(영어 8자) 이상, 가운데 8자(영어 14자) 이상 덧붙음"""
    import difflib
    g, t = _norm(got, lang), _norm(text, lang)
    sim = lambda x, y: difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()
    own = sim(g, t)
    nb = max([sim(g, _norm(x, lang)) for x in near] or [0])
    if own < 0.35 or own < nb:
        return f"다른 문장({own:.2f}<{nb:.2f})"
    if any(STYLE_LEAK.search(x or "") for x in (got, head, tail)) and not STYLE_LEAK.search(text):
        return f"말투 태그 낭독 '{head or tail or got}'"[:60]
    for piece, ref in ((head, lambda n: t[:n + 4]), (tail, lambda n: t[-(n + 4):])):
        pn = _norm(piece or "", lang)
        if len(pn) >= 2 and sim(pn, ref(len(pn))) < 0.4:
            return f"대본에 없는 말 '{piece}'"
    edge, mid = (5, 8) if lang == "ko" else (8, 14)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, t, g, autojunk=False).get_opcodes():
        extra = (j2 - j1) - (i2 - i1 if op == "replace" else 0)
        if op in ("insert", "replace") and extra >= (edge if j1 == 0 or j2 == len(g) else mid):
            return f"대본에 없는 말 '{g[j1:j2]}'"
    return None


def listen(segs: list[bytes], texts: list[str], lang: str) -> list[str | None]:
    """조각 전체와 앞머리 · 끝부분을 호출 한 번으로 받아 적고, 조각마다 문제(없으면 None)를 돌려줍니다"""
    parts, idx = list(segs), []
    for x in segs:
        h, tl = edges(x)
        idx.append([None, None])
        for n, p in enumerate((h, tl)):
            if p is not None:
                idx[-1][n] = len(parts)
                parts.append(p)
    got = T.transcribe_many(parts)
    pick = lambda n: None if n is None else got[n]
    return [speech_problem(got[k], texts[k], [texts[j] for j in (k - 1, k + 1) if 0 <= j < len(texts)], lang,
                           pick(idx[k][0]), pick(idx[k][1])) for k in range(len(segs))]


def stt_check(pcm: bytes, bounds: list[int], texts: list[str], lang: str) -> bool:
    """자른 조각을 한 번의 Gemini 호출(gemini-3.8-flash)로 받아 적어 대본과 대조합니다(listen)"""
    segs = [trim(pcm[bounds[k] * 2:bounds[k + 1] * 2]) for k in range(len(texts))]
    bad = [(k + 1, why) for k, why in enumerate(listen(segs, texts, lang)) if why]
    if bad:
        print(f"  · 받아쓰기 불일치 {bad}")
    return not bad


def audit(lang: str, voice: str, fix: bool):
    """이미 만든 문장 캐시를 12개씩 한 번에 받아 적어 문제 조각을 찾습니다. fix 면 그 조각 캐시를 지웁니다"""
    data = B.make_data()
    items = [((s["id"], i), tts_text(en.VO_EN[(s["id"], i)][1] if lang == "en" else s["beats"][i]["vo"], lang))
             for s in B.timeline(data) for i in range(len(s["beats"]))]
    miss = [k for k, t in items if not clip_path(t, voice, lang).exists()]
    if miss:
        print(f"  아직 없는 문장 {len(miss)}개(다음 빌드에서 만듭니다) {miss}")
    items = [(k, t) for k, t in items if clip_path(t, voice, lang).exists()]
    texts = [t for _, t in items]
    pcms = []
    for t in texts:
        with wave.open(str(clip_path(t, voice, lang))) as w:
            pcms.append(w.readframes(w.getnframes()))
    chunks = [range(k, min(k + 12, len(items))) for k in range(0, len(items), 12)]
    with cf.ThreadPoolExecutor(len(chunks)) as ex:
        whys = sum(ex.map(lambda r: listen([pcms[k] for k in r], [texts[k] for k in r], lang), chunks), [])
    bad = 0
    for ((sid, i), t), why in zip(items, whys):
        if why:
            bad += 1
            print(f"  {sid}-{i} {why}")
            if fix:
                clip_path(t, voice, lang).unlink()
    print(f"audit {lang} {voice}: {len(items)}문장 중 {bad}개 문제" + (" · 캐시를 지웠습니다" if fix and bad else ""))


LEAD = {"ko": "자, 시작합니다.", "en": "Here we go."}


def batch_clips(texts: list[str], voice: str, lang: str):
    """문장 여러 개를 한 번에 불러 쉼 태그 자리에서 자르고, 받아쓰기로 확인한 뒤 문장별 캐시에 둡니다.
    자르기나 확인에 실패하면 반으로 나눠 다시 부릅니다(끝내 한 문장이면 한 문장씩)"""
    todo = [t for t in texts if not clip_path(t, voice, lang).exists()]
    for k in range(0, len(todo), BATCH):
        _batch(todo[k:k + BATCH], voice, lang)


def _batch(texts: list[str], voice: str, lang: str, tries: int = 3):
    if len(texts) == 1:
        clip(texts[0], voice, lang)
        return
    style = T.STYLE_KO if lang == "ko" else T.STYLE_EN
    lead = LEAD[lang]
    for attempt in range(1, tries + 1):
        # 말투 태그를 모델이 가끔 소리 내 읽거나(영어 그대로 · 우리말로 옮겨) 발표자 흉내 말을 지어 붙입니다.
        # 언제나 첫 문장 앞에 붙으므로, 버릴 첫 문장을 하나 두고 그 조각은 잘라 버립니다
        pcm = T.synth(SEP.join([lead] + texts), voice, style)
        segs = batch_split(pcm, len(texts) + 1)
        if segs is None:
            print(f"  batch {len(texts)} 쉼 부족 · 다시 받기 {attempt}/{tries}")
            continue
        segs = segs[1:]
        batch_split.bounds = batch_split.bounds[1:]
        pcm_ok = pcm
        L = np.array([len(re.sub(r"\s", "", t)) for t in texts], float)
        D = np.array([len(x) / 2 / T.SR for x in segs])
        r = (D / D.sum()) / (L / L.sum())
        clean = getattr(batch_split, "clear", False) and r.min() > 0.6 and r.max() < 1.7
        # 배치 하나를 Gemini 받아쓰기 한 번으로 확인하고, 통과하면 바로 씁니다
        if stt_check(pcm_ok, batch_split.bounds, texts, lang):
            for t, x in zip(texts, segs):
                T.write_wav(clip_path(t, voice, lang), x)
            print(f"  batch {len(texts)} ok (시도 {attempt} · 깨끗 {clean})")
            return
        print(f"  batch {len(texts)} 다시 받기 {attempt}/{tries}")
    print(f"  batch {len(texts)} 반으로 나눕니다")
    h = len(texts) // 2
    _batch(texts[:h], voice, lang)
    _batch(texts[h:], voice, lang)


def main():
    if sys.argv[1] == "audit":
        audit(sys.argv[2], sys.argv[3], "--fix" in sys.argv)
        return
    lang, voice = sys.argv[1], sys.argv[2]
    assert lang in ("ko", "en")
    tag = f"{'-en' if lang == 'en' else ''}-narrated-{voice.lower()}"
    out_html = B.PUB / f"showreel/FlyGate_showreel_v{B.VERSION}{tag}.html"
    if voice == "Puck":
        # 사용자 지정: Puck 판이 정식 파일입니다(한국어 v4.3.0.html · 영어 v4.3.0-en.html, 대시보드 버튼이 가리키는 파일)
        out_html = B.PUB / f"showreel/FlyGate_showreel_v{B.VERSION}{'-en' if lang == 'en' else ''}.html"
    NARR_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 대본(박자별 문장)
    data = B.make_data()
    base = B.timeline(data)
    scenes = []
    for s in base:
        keys = [(s["id"], i) for i in range(len(s["beats"]))]
        texts = [tts_text(en.VO_EN[k][1] if lang == "en" else s["beats"][k[1]]["vo"], lang) for k in keys]
        scenes.append((keys, texts))
    # 2) 음성
    #    대본 전체(whole_clips) · 장면(scene_clips)을 한 번에 부르고 쉼에서 자르는 방식은 문장 경계를 잘못 잡아
    #    다른 문장의 음성이 들어가는 일이 있었습니다(받아쓰기로 확인). 길이 비율 검사로는 걸러지지 않아 쓰지 않습니다
    #    그래서 문장 사이에 긴 쉼 태그를 넣어 여러 문장을 한 번에 부르고(batch_clips), 조각마다 받아쓰기로 확인합니다
    items = [(k, t) for keys, texts in scenes for k, t in zip(keys, texts)]
    batch_clips([t for _, t in items], voice, lang)
    paths = {k: clip(t, voice, lang) for k, t in items}
    B.NARR_DUR.clear()
    B.NARR_DUR.update({k: wav_dur(p) for k, p in paths.items()})
    print(f"clips {len(paths)} · speech {sum(B.NARR_DUR.values()):.1f} s")

    # 3) 음성 길이로 다시 잡은 시간표로 HTML(음원 없이)을 먼저 써서, 그 큐로 음악을 만듭니다
    B.TIMELINE_OUT = NARR_DIR / f"{lang}-{voice.lower()}.timeline.json"
    B.TIMELINE_OUT_EN = B.TIMELINE_OUT
    td = pathlib.Path(tempfile.mkdtemp())
    B.SCRIPT_OUT = NARR_DIR / f"{lang}-{voice.lower()}.script.md"
    B.SCRIPT_OUT_EN = B.SCRIPT_OUT
    sys.argv = [sys.argv[0], str(td / "silent.html")] + (["--en"] if lang == "en" else [])
    B.EXTRA.clear()
    B.main()
    tl = json.loads(B.TIMELINE_OUT.read_text())
    dur = tl["dur"]
    music_m4a = td / "music.m4a"
    subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/reel/audio_v4_3.py"), str(td / "silent.html"), str(music_m4a)], check=True, capture_output=True)

    # 4) 섞기: 음악을 내레이션 동안 줄이고(부드러운 엔벌로프), 내레이션을 박자 시작에 놓습니다
    music = decode(music_m4a)
    n = int((dur + 1.0) * MIX_SR)
    if len(music) < n:
        music = np.vstack([music, np.zeros((n - len(music), 2), np.float32)])
    music = music[:n]
    vo = np.zeros(n, np.float32)
    duck = np.ones(n, np.float32)
    for s in tl["scenes"]:
        for i, bt in enumerate(s["beats"]):
            a = int((s["t0"] + bt["a"]) * MIX_SR)
            x = read_wav48(paths[(s["id"], i)])
            e = min(n, a + len(x))
            vo[a:e] += x[: e - a] * VO_GAIN
            duck[max(0, a - int(0.12 * MIX_SR)):min(n, e + int(0.15 * MIX_SR))] = DUCK
    k = int(0.25 * MIX_SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same").astype(np.float32)
    mix = music * duck[:, None] + vo[:, None]
    mix = mix / max(1.0, float(np.abs(mix).max()) / 0.97)
    wav = td / "mix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(MIX_SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    m4a_hi = NARR_DIR / f"{lang}-{voice.lower()}.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-t", f"{dur:.3f}", "-c:a", "aac", "-b:a", "192k", str(m4a_hi)], check=True)
    m4a_lo = td / "embed.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-t", f"{dur:.3f}", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(m4a_lo)], check=True)

    # 5) 음원을 넣은 최종 HTML
    B.EXTRA.update({"audio": base64.b64encode(m4a_lo.read_bytes()).decode(), "narrated": {"voice": voice, "model": T.MODEL}})
    sys.argv = [sys.argv[0], str(out_html)] + (["--en"] if lang == "en" else [])
    B.main()
    print(f"narrated {lang} {voice}: {dur:.1f} s · {out_html.relative_to(ROOT)} · {m4a_hi.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
