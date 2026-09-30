"""FlyGate 세로 숏폼(15초 · 30초 · 1분, 1080×1920)을 내레이션과 함께 파일 하나로 완결된 HTML 로 만듭니다.

5분 소개 영상(쇼릴 v4.3.0)과 같은 그림 언어 · 같은 실측 수치를 쓰고, 장면과 대본은 숏폼용으로 새로 짰습니다.
  - 첫 0.5초는 포스터입니다(메신저 · 피드는 커버 아트 대신 첫 프레임을 썸네일로 씁니다).
  - 장면 길이는 실제 내레이션 길이로 정합니다(Gemini TTS, 쇼릴과 같은 Puck 목소리 · 같은 검사).
  - 자막은 화면 아래 안전 영역 위에 크게 넣습니다(쇼츠 · 릴스 · 틱톡의 버튼과 제목이 덮는 자리를 비웁니다).

사용:
  .venv/bin/python scripts/build_short_v1.py [15|30|1min ...]      # 기본값: 15 30 1min
출력:
  web/public/showreel/FlyGate_short_{15,30}s_v1.0.0.html (세로) · FlyGate_intro_1min{,_vertical}_v1.0.0.html (가로 · 세로)
  scripts/reel/narrated/{15,30,1min}-ko-puck.{m4a,script.md}
MP4(세로)는 scripts/render_reel.py OUT.mp4 30 file://…html vertical 로 뽑아 m4a 와 합칩니다.
"""
import base64
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.argv, _argv = sys.argv[:1], sys.argv   # 쇼릴 빌더들이 가져올 때 sys.argv 를 읽지 않게 잠시 비웁니다
import build_reel_v4_3_final as B  # noqa: E402
import build_reel_v4_3_narrated as N  # noqa: E402
sys.argv = _argv

T = N.T
ROOT = B.ROOT
TEMPLATE = ROOT / "scripts/reel/flygate_short_v1.template.html"
VERSION = "1.0.0"
VOICE, LANG = "Puck", "ko"
POSTER = 0.5        # 첫 프레임 포스터
LEAD = 0.2          # 장면 시작 뒤 내레이션까지
TAIL = 0.3          # 내레이션 끝 뒤 다음 장면까지
END_HOLD = 1.1      # 마지막 장면의 여운
DUCK = 0.38


def numbers(d: dict) -> dict:
    fv, bl = d["fv"], d["fv"]["blind"]
    q = fv["ov"]["q_reports"]
    return {"q": q, "perDay": round(q / 91 / 100) * 100, "asof": fv["ov"]["asof"], "n": bl["n"], "serious": bl["serious"],
            "missB": bl["base"]["auto"], "missF": bl["fv"]["auto"], "overB": bl["base"]["over"], "overF": bl["fv"]["over"],
            "rmsd": d["disc"]["dd"]["redock"][0][1], "caught": d["disc"]["critic"]["caught"], "over": d["disc"]["critic"]["n_over"],
            "humanB": bl["base"]["human"], "humanF": bl["fv"]["human"], "judgeSec": f"{fv['jev_p50'] / 1000:.1f}",
            "rho": d["disc"]["bench"]["spearman"], "nBench": d["disc"]["bench"]["n"],
            "cmds": [c.split()[1] for c in d["cli"]["cmds"]]}


def script(sec: int, k: dict) -> list[dict]:
    """장면 = (id, 오른쪽 위 단계 칩, 내레이션 문장 목록).
    원칙(사용자 검토 2026-09-30): 문장마다 주어를 넣고, 무엇에 대한 수치인지 · '질문 하나'가 무엇인지 풀어 말합니다.
    STEP 1 은 크리틱보다 어떤 NVIDIA 기술을 썼는지를, 에이전트 장면은 FlyGate CLI 를 직접 개발했다는 점을 말합니다.
    FlyGate 는 TTS 가 한 낱말로 붙여 읽지 않게 '플라이게이트'로 적습니다(자막에는 FlyGate 로 나옵니다)."""
    per_day = f"{k['perDay']:,}"
    if sec == 15:
        return [
            {"id": "hook", "step": "", "vo": [f"시판 약의 부작용 보고는 하루 {per_day}건."]},
            {"id": "gate", "step": "STEP 2", "vo": ["플라이게이트는 그중 중대한 사례를 골라 먼저 검토에 올립니다."]},
            {"id": "proof", "step": "실측", "marks": {"missed": "놓친"}, "vo": [f"놓친 중대 사례는 {k['missB']}건에서 {k['missF']}건으로 줄었습니다."]},
            {"id": "cta", "step": "", "vo": ["근거가 먼저, 플라이게이트."]},
        ]
    if sec == 30:
        return [
            {"id": "hook", "step": "", "vo": [f"FDA에는 시판 약의 부작용 보고가 하루 평균 {per_day}건 들어옵니다."]},
            {"id": "intro", "step": "FlyGate", "vo": ["플라이게이트는 근거 없는 결론을 걸러내는 AI 신약 안전성 에이전트입니다."]},
            {"id": "step1", "step": "STEP 1", "vo": ["개발 단계에서 플라이게이트는 NVIDIA BioNeMo로 약물이 표적 단백질에 붙는 모습을 예측합니다."]},
            {"id": "gate", "step": "STEP 2", "vo": ["출시 후에는 플라이게이트가 부작용 보고 가운데 중대한 사례를 골라 먼저 검토에 올립니다."]},
            {"id": "proof", "step": "실측", "marks": {"missed": "놓친"}, "vo": [f"실제 보고로 시험해 보니, 놓친 중대 사례가 {k['missB']}건에서 {k['missF']}건으로 줄었습니다."]},
            {"id": "cta", "step": "", "vo": ["추론보다 근거가 먼저, 플라이게이트."]},
        ]
    # 1분 소개 영상: 사용자가 직접 쓴 대본(2026-09-30)을 그대로 씁니다(띄어쓰기만 맞춤법대로 고쳤습니다).
    # marks = 화면을 맞출 낱말(그 낱말이 들리는 때에 카드 · 칩이 나옵니다)
    return [
        {"id": "hook", "step": "", "vo": [f"미국 FDA에는 시판된 약의 부작용 보고가 하루 평균 {per_day}건씩 들어옵니다."]},
        {"id": "problem", "step": "문제", "marks": {"miss": "놓칠"},
         "vo": ["이 가운데 사망·입원 같은 중대한 부작용은 사람이 반드시 확인해야 하는데, 기계적으로 거르다 보면 수많은 부작용 사례들에 파묻혀 놓칠 수 있습니다."]},
        {"id": "intro", "step": "FlyGate", "marks": {"conn": "초파리", "fast": "빠른 판단 모델"},
         "vo": ["플라이게이트는 초파리 뇌 커넥톰 구조와 빠른 판단 모델을 적용해, 신약의 표적 결합부터 출시 후 부작용까지 근거로 검증하는 AI 에이전트입니다."]},
        {"id": "step1", "step": "STEP 1", "vo": ["신약 개발 단계에서 플라이게이트는 NVIDIA BioNeMo의 OpenFold3, DiffDock, Boltz-2로 약물이 표적 단백질에 붙는 모습을 예측합니다."]},
        {"id": "gate", "step": "STEP 2", "marks": {"judge": "일곱", "nemo": "NVIDIA Nemotron"},
         "vo": [f"신약 출시 후에는 플라이게이트의 빠르고 효율적인 판단 모델이 부작용 보고마다 일곱 가지 질문에 {k['judgeSec']}초 만에 답하고, 정밀 검토가 필요하면 NVIDIA Nemotron이 근거를 붙여 평가합니다."]},
        {"id": "proof", "step": "실측", "marks": {"missed": "놓친", "over": "중요하지 않은데"},
         "vo": [f"실제 보고 {k['n']}건으로 시험한 결과, 기계적으로 거를 때 놓친 중대 사례 {k['missB']}건이 플라이게이트에서는 {k['missF']}건으로 줄었으며, "
                f"중요하지 않은데 걸러지지 않는 사례 역시 {k['overB']}건에서 {k['overF']}건으로 줄었습니다."]},
        {"id": "stack", "step": "CLI", "marks": {"cmd": "명령 한 줄"},
         "vo": ["우리 팀은 이 기능을 모두 플라이게이트 CLI로 직접 개발해, NVIDIA NemoClaw 샌드박스에서 명령 한 줄로 실행되게 했습니다."]},
        {"id": "cta", "step": "", "vo": ["분자에서 환자까지, 추론보다 근거가 먼저. 플라이게이트."]},
    ]


def sub_text(vo: str) -> str:
    return vo.replace("플라이게이트", "FlyGate")


GAP = 0.15   # 한 장면 안 문장 사이 쉼
SUB_MAX = 42  # 자막 한 장에 넣는 글자 수(46px 두 줄). 넘으면 쉼표, 그다음 띄어쓰기에서 나눕니다


def sub_split(t: str) -> list[tuple[float, float, str]]:
    """자막을 (시작 비율, 끝 비율, 글) 목록으로 나눕니다. 모든 장이 SUB_MAX 자 이하가 될 때까지
    가운데에 가까운 쉼표에서, 쉼표가 없으면 가운데에 가까운 띄어쓰기에서 나눕니다. 비율은 글자 수로 셉니다"""
    def cut(a: int, b: int) -> list[tuple[int, int]]:
        seg = t[a:b]
        if len(seg.strip()) <= SUB_MAX:
            return [(a, b)]
        mid = (b - a) / 2
        inner = lambda ks: [k for k in ks if 0 < k < len(seg) and seg[:k].strip() and seg[k:].strip()]
        cands = inner([m.end() for m in re.finditer(r",\s", seg)]) or inner([m.start() + 1 for m in re.finditer(r"\s", seg)])
        if not cands:
            return [(a, b)]
        c = a + min(cands, key=lambda k: abs(k - mid))
        return cut(a, c) + cut(c, b)
    n = len(t)
    return [(a / n, b / n, t[a:b].strip()) for a, b in cut(0, n)]


def timeline(scenes: list[dict], durs: list[list[float]], sec: int | None) -> dict:
    lead, tail = LEAD, TAIL
    speech = sum(sum(d) + GAP * (len(d) - 1) for d in durs)
    # 목표 길이를 넘으면 쉼부터 줄입니다(말은 그대로 둡니다). 목표가 없으면(1분 소개 영상) 쉼을 그대로 둡니다
    budget = (sec if sec else 1e9) - POSTER - END_HOLD - speech
    gaps = len(scenes) * lead + (len(scenes) - 1) * tail
    if not sec:
        tail = 0.45
    elif budget < gaps:
        f = max(0.35, budget / gaps)
        lead, tail = lead * f, tail * f
    else:
        # 남는 시간은 장면 뒤 쉼에 나눠 숫자를 읽을 여유로 씁니다(목표보다 0.3초 짧게, 쉼은 1.0초까지)
        tail = min(1.0, tail + max(0.0, budget - gaps - 0.3) / max(1, len(scenes) - 1))
    out, t = [{"id": "poster", "step": "", "t0": 0.0, "t1": POSTER, "va": 0, "vb": 0, "vs": []}], POSTER
    subs = []
    for i, (s, ds) in enumerate(zip(scenes, durs)):
        last = i == len(scenes) - 1
        vs, a = [], lead
        for d in ds:
            vs.append([round(a, 3), round(a + d, 3)]); a += d + GAP
        va, vb = vs[0][0], vs[-1][1]
        t1 = t + vb + (END_HOLD if last else tail)
        # marks: 낱말이 들리는 장면 안 시각(그 문장 안 글자 위치 비율로 어림합니다)
        marks = {}
        for key, word in (s.get("marks") or {}).items():
            for line, (x, y) in zip(s["vo"], vs):
                if word in line:
                    marks[key] = round(x + (y - x) * line.index(word) / len(line), 3)
                    break
        out.append({"id": s["id"], "step": s["step"], "t0": round(t, 3), "t1": round(t1, 3), "va": va, "vb": vb, "vs": vs, "vo": s["vo"], "marks": marks})
        for n, (line, (x, y)) in enumerate(zip(s["vo"], vs)):
            end = y + (0.4 if last and n == len(vs) - 1 else (GAP * 0.8 if n < len(vs) - 1 else tail * 0.8))
            for p0, p1, txt in sub_split(sub_text(line)):
                # '한 줄' · '두 가지' 같은 관형사와 뒤 낱말은 자막 줄바꿈에서 떨어지지 않게 붙입니다(줄 바꿈은 보통 띄어쓰기에서만 합니다)
                txt = re.sub(r"(?<!\S)(한|두|세|네|일곱) (?=\S)", "\\1\u00a0", txt)
                subs.append([round(t + x - 0.05 + (y - x) * p0, 3), round(t + (x + (y - x) * p1 if p1 < 1 else end), 3), txt])
        t = t1
    return {"dur": round(t, 3), "scenes": out, "subs": subs}


def write_html(path: pathlib.Path, data: dict):
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    path.write_text(html)


# 영상 이름 → (목표 길이, 규격별 출력 파일). 15 · 30초판은 세로만, 1분 소개 영상은 가로 · 세로 두 가지입니다
SPECS = {
    "15": (15, {"vertical": "FlyGate_short_15s_v{v}.html"}),
    "30": (30, {"vertical": "FlyGate_short_30s_v{v}.html"}),
    "1min": (None, {"wide": "FlyGate_intro_1min_v{v}.html", "vertical": "FlyGate_intro_1min_vertical_v{v}.html"}),
}
SHOTS = {"start": "web/public/media/cli/v2.0.0/01-start.png", "result": "web/public/media/cli/v2.0.0/04-result.png"}   # FlyGate CLI 메인 화면 · 실행 결과(실제 캡처)


def shots() -> dict:
    out = {}
    for k, rel in SHOTS.items():
        src = ROOT / rel
        with tempfile.TemporaryDirectory() as td:
            f = pathlib.Path(td) / "s.webp"
            subprocess.run(["cwebp", "-quiet", "-q", "88", "-m", "6", str(src), "-o", str(f)], check=True)
            w, h = (int(x) for x in subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(src)], capture_output=True, text=True).stdout.split()[-3::2])
            out[k] = {"b64": base64.b64encode(f.read_bytes()).decode(), "w": w, "h": h}
    return out


def script_md(name: str, sec: int | None, tl: dict, k: dict, files: dict) -> str:
    rows = "\n".join(f"| {s['id']} | {s['t0']:.1f}–{s['t1']:.1f}초 | {' '.join(s['vo'])} |" for s in tl["scenes"][1:])
    vids = " · ".join(f"`web/public/showreel/{f.format(v=VERSION)}` ({'1920×1080' if fm == 'wide' else '1080×1920'})" for fm, f in files.items())
    return (f"# FlyGate {'1분 소개 영상' if sec is None else f'세로 숏폼 {sec}초'} v{VERSION} 대본\n\n"
            f"- 영상: {vids} · 30fps · 음원 `scripts/reel/narrated/{name}-ko-puck.m4a`\n"
            f"- **총 길이 {tl['dur']:.1f}초** · 내레이션 Gemini TTS({T.MODEL}) Puck · 빌더 `scripts/build_short_v1.py`\n"
            f"- 수치(저장소 JSON): FDA 한 분기 {k['q']:,}건(하루 평균 약 {k['perDay']:,}건) · 결과 코드를 가린 FAERS 실제 사례 {k['n']}건 · "
            f"놓친 중대 사례 {k['missB']} → {k['missF']} · 걸러지지 않은 비중대 사례 {k['overB']} → {k['overF']} · 재도킹 RMSD {k['rmsd']} Å · 결합 세기 순위 상관 {k['rho']}({k['nBench']}종)\n"
            f"- 첫 {POSTER}초는 포스터(썸네일)입니다.\n\n| 장면 | 시각 | 내레이션 |\n| --- | --- | --- |\n{rows}\n")


def build(name: str, d: dict, k: dict):
    sec, files = SPECS[name]
    scenes = script(sec or 60, k)
    texts = [[N.tts_text(v, LANG) for v in s["vo"]] for s in scenes]
    N.batch_clips([t for ts in texts for t in ts], VOICE, LANG)
    paths = [[N.clip(t, VOICE, LANG) for t in ts] for ts in texts]
    durs = [[N.wav_dur(p) for p in ps] for ps in paths]
    tl = timeline(scenes, durs, sec)
    print(f"{name} · speech {sum(map(sum, durs)):.1f} s · total {tl['dur']:.2f} s · " + " · ".join(f"{s['id']} {s['t1'] - s['t0']:.1f}" for s in tl["scenes"]))
    data = {"lang": LANG, "k": k, "disc": {"of3": d["disc"]["of3"]}, "brain": d["brain"], "tl": tl}
    if any(s["id"] == "stack" for s in scenes):
        data["shots"] = shots()
    td = pathlib.Path(tempfile.mkdtemp())
    write_html(td / "silent.html", dict(data, fmt=next(iter(files))))
    music = td / "music.m4a"
    subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/reel/audio_short_v1.py"), str(td / "silent.html"), str(music)], check=True)
    # 섞기: 내레이션 동안 음악을 줄입니다
    m = N.decode(music)
    n = int((tl["dur"] + 0.5) * N.MIX_SR)
    m = np.vstack([m, np.zeros((max(0, n - len(m)), 2), np.float32)])[:n]
    vo, duck = np.zeros(n, np.float32), np.ones(n, np.float32)
    for s, ps in zip(tl["scenes"][1:], paths):
        for (x0, _), p in zip(s["vs"], ps):
            a = int((s["t0"] + x0) * N.MIX_SR)
            x = N.read_wav48(p)
            e = min(n, a + len(x))
            vo[a:e] += x[: e - a]
            duck[max(0, a - int(0.1 * N.MIX_SR)):min(n, e + int(0.12 * N.MIX_SR))] = DUCK
    kk = int(0.2 * N.MIX_SR)
    duck = np.convolve(duck, np.ones(kk) / kk, mode="same").astype(np.float32)
    mix = m * duck[:, None] + vo[:, None]
    mix = mix / max(1.0, float(np.abs(mix).max()) / 0.97)
    wav = td / "mix.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(N.MIX_SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    N.NARR_DIR.mkdir(parents=True, exist_ok=True)
    hi = N.NARR_DIR / f"{name}-ko-puck.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-t", f"{tl['dur']:.3f}", "-c:a", "aac", "-b:a", "192k", str(hi)], check=True)
    lo = td / "embed.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-t", f"{tl['dur']:.3f}", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(lo)], check=True)
    data["audio"] = base64.b64encode(lo.read_bytes()).decode()
    for fmt, fname in files.items():
        out = B.PUB / "showreel" / fname.format(v=VERSION)
        write_html(out, dict(data, fmt=fmt))
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    (N.NARR_DIR / f"{name}-ko-puck.script.md").write_text(script_md(name, sec, tl, k, files))


def main():
    names = [a for a in sys.argv[1:] if a in SPECS] or list(SPECS)
    d = B.make_data()
    k = numbers(d)
    for name in names:
        build(name, d, k)


if __name__ == "__main__":
    main()
