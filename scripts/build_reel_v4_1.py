"""Project-FlyGate 쇼릴 v4.1.0 을 만듭니다. v4.0.0 을 더 빠른 호흡으로 다듬은 판입니다.

v4.0.0(255초)은 장면 안의 애니메이션이 일찍 끝나고 내레이션이 이어지는 동안 화면이 멈춰 있는 구간이 길었습니다
(ffmpeg freezedetect n=0.002 d=1.5 기준 44%). v4.1.0 은 다음을 바꿉니다.
  1) 장면 길이 = 내레이션 시간(초당 6.3음절) + 꼬리 0.8초 이하(마무리 장면은 7초 이하)로 다시 잽니다.
  2) v4.0.0 의 장면 애니메이션은 그대로 두고, 옛 박자 경계 → 새 박자 경계로 시간을 구간별 선형으로 옮깁니다(warp).
     효과음 큐도 같은 warp 로 옮기므로 소리와 화면이 계속 맞습니다.
  3) 템플릿(flygate_v4_1.template.html)에 늘 움직이는 층을 더합니다: 장면마다 느린 카메라 밀기,
     내레이션 박자에 맞춰 핵심 숫자 · 카드로 옮겨 가는 강조 틀, 배경 입자.
  4) 검증 장면(13)은 v3 처럼 참조 세트마다 막대 두 개(지식 기반 판별 · 최고 통계 지표)만 둡니다.

v4.0.0 의 파일(build_reel_v4.py, flygate_v4.template.html, 타임라인 · 대본 · 음원)은 고치지 않습니다.
데이터 함수와 음절 추정은 build_reel_v4 에서 그대로 가져다 씁니다.

사용:
  .venv/bin/python scripts/build_reel_v4_1.py [출력 경로]
출력:
  web/public/showreel/FlyGate_showreel_v4.1.0.html · scripts/reel/flygate_v4_1.timeline.json · docs/SHOWREEL_SCRIPT_v4.1.0.md
음원:
  .venv/bin/python scripts/reel/audio_v4_1.py
"""
import json
import math
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_reel_v3 as v3  # noqa: E402
import build_reel_v4 as v4  # noqa: E402  v4 의 데이터 함수 · 옛 시간표 · 음절 추정을 그대로 씁니다

VERSION = "4.1.0"
ROOT, PUB, REEL = v4.ROOT, v4.PUB, v4.REEL
TEMPLATE = REEL / "flygate_v4_1.template.html"
DEFAULT_OUT = PUB / f"showreel/FlyGate_showreel_v{VERSION}.html"
TIMELINE_OUT = REEL / "flygate_v4_1.timeline.json"
SCRIPT_OUT = ROOT / f"docs/SHOWREEL_SCRIPT_v{VERSION}.md"
AUDIO_REL = f"scripts/reel/FlyGate_showreel_v{VERSION}_audio.m4a"
FALLBACKS = v4.FALLBACKS
syllables, mmss = v4.syllables, v4.mmss

RATE = 6.3        # 초당 음절(창 안에서 이 속도를 넘지 않습니다)
GAP = 0.1         # 문장 사이 숨
LEAD = {"intro": 0.4, "close": 0.7}   # 첫 문장 시작(기본 0.3초). 인트로는 포스터 프레임, 마무리는 뇌가 먼저 떠오릅니다
TAIL = {"close": 0.9}                 # 마지막 문장 뒤 꼬리(기본 0.5초 · 0.8초 이하). 마무리는 페이드아웃 자리
CLOSE_MAX = 7.0


def new_narration(d: dict) -> dict:
    """장면별 내레이션(합쇼체). 박자 수는 v4.0.0 과 같습니다(애니메이션 warp 의 기준점)."""
    ds, fv, pn, wh, tr, kr, bt, nv, ag = d["disc"], d["fv"], d["panel"], d["wh"], d["triage"], d["kr"], d["bt"], d["nvs"], d["agent"]
    b = fv["blind"]
    reach_fv = b["serious"] - b["fv"]["auto"]
    sets = {s["name"]: s for s in fv["val"]["sets"]}
    pro = fv["val"]["pro"] or {}
    ok_all = sum(1 for r in pn["redock"] if r["rmsd"] <= pn["thr"])
    smoke = (ag.get("smoke") or {}).get("total", 20)
    krt = f"{kr['total']}점, {kr['grade']}입니다" if kr else "점수와 등급을 매깁니다"
    man = v4.man
    return {
        "intro": ["프로젝트 플라이게이트입니다.",
                  "NVIDIA 스킬로 구성한 약물 안전성 에이전트 워크플로입니다."],
        "problem": ["도킹 점수도 보고 통계도 모두 실측입니다.",
                    "그런데 결론이 근거를 넘으면 반려해야 합니다.",
                    f"한 분기에만 {man(fv['ov']['q_reports'])} 건이 넘습니다."],
        "disc": [f"STEP 1 플라이디스커버리. MSA-Search가 PARP1 상동 서열 {ds['msa']['n']}개를 모읍니다.",
                 f"OpenFold3 복합체 예측은 결정 구조와 {ds['of3']['ca_rmsd_vs_4R6E']:.1f} 옹스트롬 차이입니다.",
                 f"DiffDock은 결합 자리를 {ds['dd']['redock'][0][1]} 옹스트롬 안으로 재현했습니다.",
                 f"Boltz-2 친화도 예측은 ChEMBL 실측과 순위 상관 {ds['bench']['spearman']:.3f}입니다.",
                 "결론이 근거를 넘으면 Nemotron 크리틱이 반려합니다."],
        "panel": [f"실제 사례의 의심약물 {len(pn['rows'])}종으로 패널을 넓힙니다.",
                  f"소분자는 DiffDock 재도킹으로 {len(pn['redock'])}개 중 {ok_all}개가 2옹스트롬 기준을 통과했습니다."],
        "bridge": ["데모는 같은 약으로 시판 후를 잇습니다.",
                   "이제 질문은, 누가 얼마나 빨리 봐야 하는가입니다."],
        "warehouse": ["STEP 2, 플라이비질런스입니다.",
                      f"FAERS {wh['quarters']}개 분기, 사례 {man(wh['cases'])} 건을 SQL로 집계합니다."],
        "flow": ["규칙으로 되는 일은 규칙으로, 판단은 모델로 나눕니다.",
                 "라벨 원문, FAERS 통계, 문헌을 모아 PV 분류를 매깁니다.",
                 f"글은 Nemotron이, 확률은 비자기회귀 모델이 맡아 {fv['questions']}문항을 {fv['jev_p50'] / 1000:.1f}초에 답합니다."],
        "triage": [f"실제 사례 한 건, {len(tr['probs'])}문항 판단이 {tr['jev_ms'] / 1000:.1f}초에 끝납니다.",
                   "중대하고 예상하지 못해 15일 신속보고 후보입니다.",
                   "Nemotron 메모는 크리틱이 한 번 되돌렸고, 고친 뒤 통과했습니다."],
        "korean": ["국내 보고는 Nemotron이 식약처 서식 여섯 절로 구조화합니다.",
                   f"한국형 인과성 평가 {len(kr['items']) if kr else 8}개 항목을 채점해 {krt}.",
                   "국내 규정은 예상 여부와 무관하게 중대하면 15일 보고입니다."],
        "signals": ["SDR은 인과가 아니라 검토의 출발점입니다.",
                    f"중대 의학 사건 {d['pvc']['dme_n']}개는 점수와 관계없이 사람이 봅니다.",
                    "변호사 보고가 몰린 쌍에는 편향 표시를 붙입니다."],
        "timemachine": ["타임머신은 분기마다 그 시점 데이터로 SDR을 다시 계산합니다.",
                        f"카나글리플로진 케톤산증은 FDA 조치보다 {bt['main']['lead']}일 먼저 SDR이 섰습니다."],
        "measure": [f"결과 코드를 가린 {b['n']}건에서 모델 단독 질문 하나와 비교했습니다.",
                    f"중대 사례 {reach_fv}건이 검토에 닿았고, 사람이 먼저 볼 양은 {b['base']['human']}건에서 {b['fv']['human']}건으로 줄었습니다.",
                    "모두 유의한 차이입니다."],
        "validated": [f"지식 기반 판별은 AUC {sets['OMOP']['kb']:.2f}, {sets['EU-ADR']['kb']:.2f}로 통계 지표를 앞섰습니다."
                      if "OMOP" in sets and "EU-ADR" in sets else "공개 참조 세트로 판별 성능을 검증했습니다.",
                      f"2013년 이전 보고만으로 라벨 변경 {pro.get('tp')}건을 미리 잡았고, 오경보는 {pro.get('fp')}건입니다."],
        "nvskills": ["NVIDIA 공식 Agent Skills 네 개를 적용했습니다.",
                     "정책 생성 스킬로 만든 PV 가드는 인과 단정과 없는 발생률을 잡습니다.",
                     f"Nemotron 리랭커는 관련 문헌 비율을 {nv['rerank']['p0']:.2f}에서 {nv['rerank']['p1']:.2f}로 올렸습니다."],
        "reviewed": [f"현업 약사 검토 의견 {d['pvc']['n_review']}개를 코드와 데이터에 반영했습니다.",
                     "SDR 용어, PV 분류, 결과 코드를 가린 평가가 그 결과입니다."],
        "arch": ["에이전트 경로는 초파리 커넥톰의 아홉 기능 층에 대응시켰습니다.",
                 "반사는 싸게, 숙고는 드물게, 억제는 늘 켜 둡니다."],
        "agent": ["에이전트는 NemoClaw로 OpenShell 샌드박스 안에서 늘 켜져 있습니다.",
                  f"허용한 호스트만 나가고, 샌드박스 점검 {smoke}개를 모두 통과했습니다."],
        "cli": [f"도구는 flygate 명령 {len(d['cli']['cmds'])}개이고, 모든 출력에 근거 ID가 붙습니다.",
                "매일 아침 cron이 새 분기를 점검하고, 제출은 사람이 합니다."],
        "close": ["반사는 싸게, 숙고는 드물게, 판단은 사람에게.",
                  "프로젝트 플라이게이트였습니다. 감사합니다."],
    }


def new_vis(d: dict) -> dict:
    """화면 설명을 바꾸는 박자만 적습니다(나머지는 v4.0.0 과 같습니다)."""
    fv = d["fv"]
    sets = fv["val"]["sets"]
    pro = fv["val"]["pro"] or {}
    bars = " · ".join(f"{s['name']} {s['kb']:.3f} 대 {s['best']['auc']:.3f} {s['best']['name']}" for s in sets)
    return {
        ("validated", 0): f"참조 세트마다 막대 두 개: FlyVigilance 지식 기반 판별(약·반응 이름 사용) 대 최고 통계 지표(PRR·ROR·IC·χ² 중) · {bars}",
        ("validated", 1): f"Harpaz 전향 {pro.get('tp')}/{pro.get('pos')} · 오경보 {pro.get('fp')}/{pro.get('neg')} · PPV {pro.get('ppv', 0):.2f} · 문헌 설계 분류 · 크리틱 주입 시험",
    }


def ceil1(x: float) -> float:
    return math.ceil(x * 10 - 1e-9) / 10


def timeline(d: dict) -> list[dict]:
    """v4.0.0 시간표(옛 박자)를 기준으로 새 박자를 잽니다. 각 장면에 warp 기준점 [옛 시각, 새 시각] 을 붙입니다."""
    old = v4.timeline(d)
    vo, vis = new_narration(d), new_vis(d)
    labels = {"validated": "공개 참조 세트 검증"}
    out, t = [], 0.0
    for s in old:
        sid, ob = s["id"], s["beats"]
        lines = vo[sid]
        assert len(lines) == len(ob), f"{sid}: 박자 수가 v4.0.0 과 달라집니다"
        a = LEAD.get(sid, 0.3)
        beats, knots = [], [[0.0, 0.0]]
        for i, (bo, line) in enumerate(zip(ob, lines)):
            w = ceil1(syllables(line) / RATE + (GAP if i < len(ob) - 1 else 0))
            bb = round(a + w, 2)
            beats.append({"a": round(a, 2), "b": bb, "vis": vis.get((sid, i), bo["vis"]), "vo": line})
            knots += [[bo["a"], a], [bo["b"], bb]]
            a = bb
        dur = round(a + TAIL.get(sid, 0.5), 1)
        if sid == "close":
            dur = min(dur, CLOSE_MAX)
        old_dur = s["t1"] - s["t0"]
        knots.append([old_dur, dur])
        # 기준점은 두 축 모두 늘어나야 합니다
        kn = []
        for o, n in knots:
            if kn and (o <= kn[-1][0] + 1e-6 or n <= kn[-1][1] + 1e-6):
                continue
            kn.append([round(o, 3), round(n, 3)])
        out.append({"id": sid, "t0": round(t, 3), "t1": round(t + dur, 3), "name": s["name"], "label": labels.get(sid, s["label"]),
                    "step": s["step"], "old_t0": s["t0"], "old_t1": s["t1"], "warp": kn, "beats": beats})
        t += dur
    return out


def write_script(tl: list[dict], dur: float, built: str):
    total_syl = sum(syllables(bt["vo"]) for s in tl for bt in s["beats"])
    lines = [
        f"# Project-FlyGate 쇼릴 v{VERSION} 내레이션 대본", "",
        f"- 영상: `web/public/showreel/FlyGate_showreel_v{VERSION}.html` (1920×1080, 30fps) · 음원 `{AUDIO_REL}`",
        f"- **총 길이 {int(dur // 60)}분 {dur % 60:.0f}초 ({dur:.1f}초)** · 장면 {len(tl)}개 · 내레이션 {total_syl}음절(추정) · v4.0.0(4분 15초)을 빠른 호흡으로 다듬은 판입니다",
        f"- 이 대본은 `scripts/build_reel_v4_1.py` 가 영상과 같은 장면 시간표(`scripts/reel/flygate_v4_1.timeline.json`)로 생성합니다. 손으로 고치지 말고 빌더의 `new_narration()` 을 고친 뒤 다시 빌드합니다.",
        f"- 수치는 빌드 시점({built})의 저장소 JSON · 측정 파일 값입니다.",
        f"- 장면 길이는 내레이션 시간(초당 {RATE}음절, 문장 사이 {GAP}초 숨)에 꼬리 0.8초 이하를 더한 값입니다(마무리 장면은 {CLOSE_MAX:.0f}초 이하). 음절 수는 숫자와 영문을 소리 나는 대로 센 추정값입니다. 영문 고유명사는 괄호 안 읽기대로 읽습니다: FlyGate(플라이게이트), FlyDiscovery(플라이디스커버리), FlyVigilance(플라이비질런스), Nemotron(네모트론), NemoClaw(네모클로), OpenShell(오픈셸), FAERS(페어스), SDR(에스디알).",
        "", "## 장면 한눈에 보기", "",
        "| # | 장면 | 시작 | 끝 | 길이 |", "| --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(tl, 1):
        lines.append(f"| {i:02d} | {s['label']} | {mmss(s['t0'])} | {mmss(s['t1'])} | {s['t1'] - s['t0']:.1f}초 |")
    lines.append(f"| | **합계** | 00:00.0 | {mmss(dur)} | **{dur:.1f}초** |")
    for i, s in enumerate(tl, 1):
        lines += ["", f"## {i:02d} · {s['label']} ({mmss(s['t0'])}–{mmss(s['t1'])})", "",
                  "| 시간 | 화면 | 내레이션 | 속도 |", "| --- | --- | --- | --- |"]
        for bt in s["beats"]:
            a, bb = s["t0"] + bt["a"], s["t0"] + bt["b"]
            syl = syllables(bt["vo"])
            lines.append(f"| {mmss(a)}–{mmss(bb)} | {bt['vis']} | {bt['vo']} | {syl}음절 · {syl / (bb - a):.1f}/초 |")
    lines += ["", "## 읽을 때", "",
              "- 장면이 바뀌는 순간(각 표의 첫 줄 시작 시각)에 첫 문장을 시작하면 화면의 숫자가 나타나는 때와 맞습니다.",
              "- 문장 사이 숨은 짧게 둡니다. 화면의 강조 틀이 지금 읽는 숫자 · 카드로 옮겨 가므로 틀을 따라 읽으면 박자가 맞습니다.",
              "- Jev(TypeSafe AI)는 기술 구성 크레딧에서만 이름을 읽고, 본문에서는 '비자기회귀 판단 모델'로 부릅니다. 비교 기준선은 '모델 단독 · 질문 하나'입니다.", ""]
    SCRIPT_OUT.write_text("\n".join(lines))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = pathlib.Path(args[0]) if args else DEFAULT_OUT
    fv = v3.fv_part()
    disc = v3.disc_part()
    val = v4.jload_opt(PUB / "data/validation.json")
    fv["val"] = v4.val4_part(val)   # 옛 시간표(v4.timeline)가 같은 모양을 기대합니다. 화면은 kb · best 두 막대만 씁니다
    data = {
        "meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "repo": v3.REPO, "live": v3.LIVE, "version": VERSION},
        "disc": disc, "nir": v3.nir_part(), "fv": fv, "agent": v3.agent_part(fv["skills"]), "brain": v3.brain_part(),
        "panel": v4.panel_part(disc), "wh": v4.warehouse_part(), "triage": v4.triage_part(), "kr": v4.kr_part(), "pvc": v4.pv_class_part(),
        "bt": v4.backtest_part(), "nvs": v4.nvskills_part(disc), "arch": v4.arch_part(), "cli": v4.cli_part(),
    }
    tl = timeline(data)
    dur = tl[-1]["t1"]
    for s in data["fv"]["val"]["sets"]:
        s.pop("stat", None)
    data["tl"] = {"dur": dur, "scenes": [{k: s[k] for k in ("id", "t0", "t1", "name", "label", "step", "old_t0", "old_t1", "warp")} for s in tl],
                  "beats": {s["id"]: [[bt["a"], bt["b"]] for bt in s["beats"]] for s in tl}}
    html = TEMPLATE.read_text()
    marker = "/*__DATA__*/null"
    assert html.count(marker) == 1, "template data marker missing"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace(marker, blob))
    TIMELINE_OUT.write_text(json.dumps({"version": VERSION, "built": data["meta"]["built"], "dur": dur, "rate": RATE,
                                        "scenes": [{k: v for k, v in s.items()} for s in tl]}, ensure_ascii=False, indent=1) + "\n")
    write_script(tl, dur, data["meta"]["built"])
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) · {len(tl)} scenes · {dur:.1f} s")
    print(f"wrote {TIMELINE_OUT.relative_to(ROOT)} · {SCRIPT_OUT.relative_to(ROOT)}")
    # 음절 속도 · 꼬리 점검: 창 안 속도가 RATE 를 넘거나, 마지막 문장 뒤 꼬리가 0.8초(마무리는 CLOSE_MAX 안)를 넘으면 알립니다
    for s in tl:
        for bt in s["beats"]:
            r = syllables(bt["vo"]) / (bt["b"] - bt["a"])
            if r > RATE + 1e-6:
                print(f"  ! narration fast ({r:.2f} syl/s) {s['id']}: {bt['vo']}")
        tail = (s["t1"] - s["t0"]) - s["beats"][-1]["b"]
        if tail > (1.0 if s["id"] == "close" else 0.8) + 1e-6:
            print(f"  ! scene tail {tail:.1f} s {s['id']}")
        if s["id"] == "close" and s["t1"] - s["t0"] > CLOSE_MAX + 1e-6:
            print(f"  ! close scene longer than {CLOSE_MAX} s")
    for s in tl:
        syl = sum(syllables(bt["vo"]) for bt in s["beats"])
        print(f"  {s['id']:<12} {s['t1'] - s['t0']:5.1f} s  {syl:3d} syl  {syl / (s['beats'][-1]['b'] - s['beats'][0]['a']):.2f} syl/s")
    print("  fallbacks: " + ("; ".join(FALLBACKS) if FALLBACKS else "none"))


if __name__ == "__main__":
    main()
