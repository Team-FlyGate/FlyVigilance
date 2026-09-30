"""Gemini TTS 로 쇼릴 내레이션 음성을 만듭니다.

키는 저장소 루트 .env 의 GEMINI_API_KEY 줄만 읽습니다(다른 줄은 읽지 않고, 키는 어디에도 출력하지 않습니다).
결과는 24kHz 16bit 모노 WAV 입니다.

사용:
  .venv/bin/python scripts/reel/tts_gemini.py sample OUTDIR          # 목소리 후보 샘플
  (전체 생성은 build 단계에서 synth() 를 불러 씁니다)
"""
import base64
import json
import re
import ssl
import pathlib
import sys
import time
import urllib.error
import urllib.request
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODEL = "gemini-3.8-flash-tts"
SR = 24000
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.strip().startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("GEMINI_API_KEY 가 .env 에 없습니다")


def synth(text: str, voice: str, style: str = "", model: str = MODEL, retries: int = 12) -> bytes:
    """text 를 읽은 PCM(24kHz 16bit 모노) 바이트를 돌려줍니다. style 은 읽는 방식 지시문입니다."""
    prompt = f"{style} {text}" if style else text
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(retries):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
                d = json.load(r)
            part = d["candidates"][0]["content"]["parts"][0]["inlineData"]
            return unwrap(base64.b64decode(part["data"]))
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="ignore")
            msg = raw[:300]
            if e.code in (429, 500, 503) and i + 1 < retries:
                # 분당 호출 한도(무료 등급 10회)에 걸리면 서버가 알려 준 시간만큼 기다렸다가 다시 부릅니다
                m = re.search(r'"retryDelay":\s*"(\d+)s"', raw)
                time.sleep((int(m.group(1)) + 2) if m else 8 * (i + 1))
                continue
            raise SystemExit(f"TTS 실패 {e.code}: {msg}")
    raise SystemExit("TTS 재시도 초과")


STT_MODEL = "gemini-3.5-transcribe"


def transcribe(pcm: bytes, model: str = STT_MODEL, retries: int = 6) -> str:
    """PCM(24kHz 16bit 모노)을 Gemini 받아쓰기 모델로 글로 옮깁니다"""
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(buf.getvalue()).decode()}}]}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(retries):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
                d = json.load(r)
            return " ".join(p.get("audioTranscription", {}).get("text", "") or p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and i + 1 < retries:
                time.sleep(4 * (i + 1))
                continue
            raise SystemExit(f"받아쓰기 실패 {e.code}: {e.read().decode(errors='ignore')[:300]}")
    raise SystemExit("받아쓰기 재시도 초과")


MULTI_STT_MODEL = "gemini-3.8-flash"


def transcribe_many(pcms: list[bytes], model: str = MULTI_STT_MODEL, retries: int = 6) -> list[str]:
    """조각 여러 개를 호출 한 번으로 받아 적어 조각별 글 목록을 돌려줍니다.
    gemini-3.5-transcribe 는 결제 등급에서도 하루 100회 한도라 조각마다 부르면 한 판에 다 씁니다"""
    import io
    parts = [{"text": f"Transcribe each of the {len(pcms)} audio clips below verbatim, in the spoken language, including any words that seem out of place. "
                      f"Write English words, acronyms and product names in Latin letters and numbers as digits. "
                      f"Return a JSON array with one object per clip: its clip number and its own transcript only. "
                      f"Never move words between clips."}]
    for k, pcm in enumerate(pcms):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
        parts += [{"text": f"Clip {k + 1}:"}, {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(buf.getvalue()).decode()}}]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": {"type": "ARRAY", "items": {
                "type": "OBJECT", "properties": {"clip": {"type": "INTEGER"}, "text": {"type": "STRING"}}, "required": ["clip", "text"]}}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(retries):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
                d = json.load(r)
            # 순서가 아니라 조각 번호로 맞춥니다(여러 조각을 한 번에 적을 때 한 칸씩 밀리는 일이 있었습니다)
            out = {o["clip"]: o["text"] for o in json.loads(d["candidates"][0]["content"]["parts"][0]["text"])}
            if set(out) == set(range(1, len(pcms) + 1)):
                return [out[k + 1] for k in range(len(pcms))]
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or i + 1 == retries:
                raise SystemExit(f"받아쓰기 실패 {e.code}: {e.read().decode(errors='ignore')[:300]}")
        except (KeyError, ValueError, TimeoutError, urllib.error.URLError):
            pass
        time.sleep(4 * (i + 1))
    raise SystemExit("받아쓰기 재시도 초과")


def unwrap(b: bytes) -> bytes:
    """이 모델은 PCM 이 아니라 WAV 파일(RIFF 머리말 + data + 끝의 C2PA 출처 메타데이터)을 돌려줍니다.
    data 조각만 꺼내 씁니다. 머리말 · 메타데이터를 소리로 틀면 문장 앞뒤에 '틱 · 지직' 잡음이 납니다"""
    if b[:4] != b"RIFF":
        return b
    i = 12
    while i + 8 <= len(b):
        cid, n = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], "little")
        if cid == b"data":
            return b[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    raise SystemExit("WAV 응답에서 data 조각을 찾지 못했습니다")


def write_wav(path: pathlib.Path, pcm: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)


def dur(pcm: bytes) -> float:
    return len(pcm) / 2 / SR


# 이 모델은 지시문을 따로 받지 않고(developer instruction 미지원), 문장 앞에 적은 지시문은 소리 내 읽습니다.
# 대괄호 오디오 태그는 읽지 않고 말투 · 속도에만 반영하므로 태그로 지시합니다
STYLE_KO = "[fast, energetic]"
STYLE_EN = "[fast, energetic]"

if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "sample":
    out = pathlib.Path(sys.argv[2])
    ko = "STEP 1 플라이디스커버리. MSA-Search가 PARP1 상동 서열 101개를 모읍니다."
    en = "STEP 1, FlyDiscovery. MSA-Search gathers 101 homologous sequences of PARP1."
    for v in sys.argv[3:] or ["Charon", "Kore", "Puck"]:
        for lang, text, st in (("ko", ko, STYLE_KO), ("en", en, STYLE_EN)):
            pcm = synth(text, v, st)
            write_wav(out / f"sample_{v}_{lang}.wav", pcm)
            print(f"{v:<8} {lang} {dur(pcm):.2f}s")
