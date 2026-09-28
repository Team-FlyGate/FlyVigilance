#!/usr/bin/env python3
"""FlyGate 에이전트 구성을 web/public/data/agent.json 으로 내보냅니다(웹의 에이전트 화면이 읽습니다).

읽는 것: agent/workspace/*.md, skills/*/SKILL.md 와 agent/skills/*/SKILL.md, agent/policy/flygate.yaml,
agent/flygate.py 의 CLI 파서, agent/evidence/openshell_smoke_*.txt(가장 최근 파일)의 RESULT 줄.
숫자는 이 파일들에서 읽고, 여기에는 설명 문장만 둡니다.

  .venv/bin/python agent/export_agent_json.py
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

import yaml

AGENT = pathlib.Path(__file__).resolve().parent
ROOT = AGENT.parent
OUT = ROOT / "web" / "public" / "data" / "agent.json"
POLICY = AGENT / "policy" / "flygate.yaml"

# OpenClaw 작업 공간 파일의 역할입니다(NemoClaw 과정 03b 의 대응표).
WORKSPACE = [
    ("SOUL.md", "성격, 경계, 말투, 가치입니다. 근거에 묶인 분석가이며 인과 단정·치료 조언·외부 발송을 하지 않습니다."),
    ("AGENTS.md", "작업 규칙입니다. 도구는 flygate CLI, 모든 주장에 근거 ID, 크리틱 규칙 R1–R13, 사람 승인이 필요한 일."),
    ("IDENTITY.md", "이름과 정체입니다."),
    ("USER.md", "함께 일하는 사람(규제기관·제약사 PV 평가자, 지역 약물감시센터, 신약 탐색 연구자)과 선호입니다."),
    ("TOOLS.md", "flygate 명령별 사용 메모입니다. 허용된 외부 API, 자격 증명 처리, 출력 키."),
    ("HEARTBEAT.md", "하트비트·cron 이 따르는 정기 점검 목록입니다. flygate watch 실행, 대기열 요약, 제출 금지."),
    ("MEMORY.md", "사람이 검토한 장기 기억입니다(메인 세션에서만 읽습니다). 숫자마다 출처 파일이 붙어 있습니다."),
]

# CLI 사용 예와 설명입니다. 키는 flygate.py 의 하위 명령과 같아야 합니다(아래에서 확인합니다).
CLI = {
    "triage": ("flygate triage <case.json> [--regime KR] [--no-outcome]",
               "ICSR 한 건 반사 판단: 규칙 게이트 → 라벨 근거 → 판단 모델의 타입 있는 확률 7개(한 번의 호출) → 결정 정책 + DME 안전망"),
    "grade": ("flygate grade <DRUG> \"<MedDRA PT>\"",
              "약물·반응 쌍의 PV 분류 후보(라벨 상태 × SDR)와 근거 등급: FAERS 3중 기준, 라벨 절, PubMed 문헌 읽기"),
    "signals": ("flygate signals <DRUG> [--pt 부분문자열]", "웨어하우스 추출본의 불균형 지표(a, PRR, ROR025, IC025)와 SDR 단계, 모델 미개입"),
    "kr-causality": ("flygate kr-causality <report.txt> --route",
                     "국내 보고를 Nemotron 으로 식약처 서식에 구조화하고 한국형 인과성 평가 ver 2.0 채점, 15일 신속보고 후보 라우팅"),
    "critic": ("flygate critic <claims.json>", "주장 목록을 크리틱 3단(근거 ID 규칙, 숫자 대조, 과잉해석 판단)과 주장별 NVIDIA Safety Guard 에 통과"),
    "discover": ("flygate discover parp1|xa|cox2",
                 "FlyDiscovery 실측(MSA-Search, OpenFold3, DiffDock, Boltz-2, ChEMBL)과 시판 전 크리틱 판정, STEP 2 인계"),
    "watch": ("flygate watch --memory-dir memory --workspace . [--online] [--triage N]",
              "하트비트·cron 정기 점검: 최신 분기 확인, 감시 목록 SDR 재계산, 새 사례 분류, 날짜별 메모, 사람 검토 대기열(제출 없음)"),
}

STACK = [
    ("LLM endpoints", "프롬프트와 도구 결과를 응답으로 바꿉니다. 세션 상태는 들고 있지 않습니다.",
     "NVIDIA build.nvidia.com NIM: Nemotron 3 Super(숙의 메모, 국내 보고 구조화), Nemotron Safety Guard(주장별 안전 검사), "
     "BioNeMo NIM 4종(MSA-Search, OpenFold3, DiffDock, Boltz-2). 비자기회귀 판단 모델(TypeSafe AI)이 타입 있는 확률 판단을 맡습니다."),
    ("OpenClaw harness", "세션 기록, 파일 기반 작업 공간, 도구 접근을 유지합니다.",
     "작업 공간 파일 {n_ws}개(SOUL, AGENTS, IDENTITY, USER, TOOLS, HEARTBEAT, MEMORY), Agent Skills {n_skills}개, "
     "도구는 flygate CLI 하위 명령 {n_cli}개(exec). 날짜별 메모는 flygate watch 가 memory/ 에 씁니다."),
    ("OpenShell sandbox", "실행 중인 에이전트가 닿을 수 있는 파일·네트워크·시스템 호출을 제한합니다.",
     "agent/policy/flygate.yaml: 외부 API {n_ext}곳을 파이썬 실행 파일에만 묶어 메서드·경로 단위로 허용, 쓰기는 /tmp, /sandbox/.openclaw, "
     "/sandbox/.nemoclaw, 작업 디렉터리, sandbox 사용자, Landlock best_effort. 라이브 점검 {smoke}."),
    ("NemoClaw blueprint", "OpenClaw 와 OpenShell 이 함께 돌도록 이미지, 정책, 추론 경로를 한 벌로 구성합니다.",
     "NemoClaw 청사진의 OpenClaw 샌드박스 이미지와 로컬 게이트웨이(nemoclaw-8090) 위에 올립니다. agent/deploy_nemoclaw.sh 가 "
     "정책 프리셋, 도구 묶음, 작업 공간, 스킬, cron 을 더합니다."),
]

TRIGGERS = [
    {"name": "Skill", "session": "부른 세션을 그대로 씁니다",
     "directive": "workspace/skills/<name>/SKILL.md (예: pv-reflex-triage, pv-critic, discovery-evidence)",
     "trigger": "사람이 요청하거나 에이전트가 description 을 보고 고를 때"},
    {"name": "Heartbeat", "session": "main",
     "directive": "HEARTBEAT.md: flygate watch 실행 → review_queue 를 근거 ID 와 함께 요약, 없으면 HEARTBEAT_OK",
     "trigger": "게이트웨이 타이머(기본 약 30분)"},
    {"name": "Cron", "session": "isolated (실행마다 새 세션)",
     "directive": "payload.message: HEARTBEAT.md 목록대로 점검, 제출 금지 (--tools exec,read,write --no-deliver)",
     "trigger": "0 7 * * * Asia/Seoul (openclaw cron add)"},
    {"name": "Sub-agent", "session": "새 세션, 부모가 핸들을 가짐",
     "directive": "부모가 준 과제 하나: 약물·반응 한 쌍의 flygate grade 또는 문헌 읽기, 결과는 근거 ID 가 붙은 JSON",
     "trigger": "부모 에이전트가 턴 중간에 결정(검토할 쌍이 여러 개일 때)"},
]

TRIFECTA = {
    "private_data": "ICSR(FAERS 사례와 국내 보고 서술의 나이·성별·약물·반응), 감시 목록과 날짜별 메모(memory/), 작업 공간 파일, "
                    "프록시가 넣는 API 자격 증명(샌드박스 안에는 자리표시자만 있습니다).",
    "untrusted_input": "PubMed 초록, openFDA 라벨 본문, 보고 서술 자유 텍스트, 외부 API 응답. 에이전트는 이것을 읽을 자료로만 다룹니다.",
    "external_comm": "허용 목록 {n_ext}곳뿐입니다: 조회(api.fda.gov, eutils) GET, 판단 API POST /v1/systemone, NVIDIA NIM "
                     "POST /v1/chat/completions·GET /v1/models, BioNeMo NIM 경로. 메일·메신저·GitHub·붙여넣기 사이트로 가는 길은 없습니다.",
    "mediation": "외부 통신 다리를 좁히고 결과 행동을 사람에게 둡니다. ① 판단 모델은 지시문이 아니라 타입 있는 확률(noul·choice·score)만 "
                 "돌려주므로 외부 텍스트가 행동을 바꿀 통로가 좁습니다. ② 주장은 근거 ID 카탈로그 안에서만 인용하고 크리틱 3단과 Safety Guard 를 "
                 "통과해야 합니다. ③ 허용 호스트는 파이썬에만 묶였고 메서드·경로가 고정되어 자유 형식 외부 전송이 없습니다(curl·목록 밖 호스트는 "
                 "라이브 점검에서 차단). ④ 보고 제출과 통보는 사람이 합니다: cron 은 --no-deliver, watch 의 submitted 는 늘 빈 목록입니다.",
}


def _modules(smoke: str) -> list[dict]:
    """NemoClaw 과정 01a–04c 를 FlyGate 의 파일·기능에 대응시킵니다. 상태어: implemented / partial / documented."""
    return [
        {"id": "01a", "title": "The Agent: 인지-판단-행동 루프",
         "ours": "implemented · ICSR 한 건을 인지(규칙 게이트, 라벨 근거) → 판단(타입 있는 확률 7개) → 행동(라우팅) 루프로 처리합니다.",
         "where": "api/_fv/triage.py · flygate triage"},
        {"id": "01b", "title": "ReAct 루프와 도구 호출",
         "ours": "implemented · OpenClaw 가 flygate 명령을 exec 도구로 부르고 JSON 결과를 읽어 다음 행동을 정합니다. 크리틱이 반려하면 사유대로 한 번 고칩니다.",
         "where": "agent/workspace/AGENTS.md · agent/flygate.py"},
        {"id": "01c", "title": "도구 확장: 함수 호출, 도구 계약, MCP",
         "ours": "implemented · 하위 명령 7개를 한 계약(JSON + evidence_ids)으로 묶고, 인자를 argparse 로 검증합니다. 역할별 지식은 Agent Skills 로 나눴습니다. "
                 "도구 경계는 MCP 서버 대신 CLI 계약으로 두었습니다.",
         "where": "agent/flygate.py · skills/*/SKILL.md · agent/skills/"},
        {"id": "02a", "title": "워크플로: ReWOO, 라우팅, 병렬 작업",
         "ours": "implemented · 결정 정책이 규칙으로 라우팅합니다(반사 → System-2 → 사람). 근거는 라벨과 문헌을 병렬로 모읍니다.",
         "where": "api/_fv/triage.py · api/_fv/evidence.py"},
        {"id": "02b", "title": "에이전트 RAG와 검색",
         "ours": "implemented · openFDA 라벨 절 검색, PubMed 검색과 초록 읽기, FAERS 2×2 SQL. 모델은 근거 카탈로그의 ID 만 인용합니다.",
         "where": "api/_fv/evidence.py · api/_fv/literature.py · pipeline/faers/"},
        {"id": "02c", "title": "딥 에이전트: 계획, 독립 작업자, 공유 저장소, 종합",
         "ours": "implemented · 근거 묶음이 공유 저장소(근거 ID 카탈로그)입니다. FAERS SQL, 라벨 조회, 문헌 읽기, 보고자 구성, DME 가 채우고 "
                 "Nemotron 이 종합한 뒤 크리틱이 검사합니다.",
         "where": "api/_fv/evidence.py::bundle · api/_fv/assess.py"},
        {"id": "03a", "title": "NemoClaw 스택 연결",
         "ours": f"implemented · 로컬 게이트웨이 nemoclaw-8090 에 FlyGate 샌드박스 flygate-smoke 를 만들고 exec 로 도구를 돌렸습니다({smoke}).",
         "where": "agent/openshell_smoke.sh · agent/evidence/"},
        {"id": "03b", "title": "OpenClaw 작업 공간",
         "ours": "implemented · 작업 공간 파일 7개를 샌드박스 /sandbox/.openclaw/workspace 에 올려 확인했습니다. 날짜별 메모는 flygate watch 가 씁니다.",
         "where": "agent/workspace/"},
        {"id": "03c", "title": "상시 실행: 스킬, 하트비트, cron, 하위 에이전트",
         "ours": "partial · 스킬 설치와 하트비트 점검(flygate watch)은 샌드박스 안에서 돌렸습니다. cron 등록과 하위 에이전트 위임은 배포 스크립트와 트리거 표에 정의했습니다.",
         "where": "agent/workspace/HEARTBEAT.md · agent/deploy_nemoclaw.sh"},
        {"id": "04a", "title": "OpenShell 샌드박스",
         "ours": f"implemented · 기본 거부 정책, 파이썬 바인딩, L7 메서드·경로 규칙, Landlock, 비루트, seccomp 를 실제 샌드박스에서 확인했습니다({smoke}).",
         "where": "agent/policy/flygate.yaml · tests/test_agent.py"},
        {"id": "04b", "title": "현대 CLI 에이전트",
         "ours": "implemented · 작업 디렉터리, 도구 팔레트, 기억, 무인 실행, 네트워크의 자유도를 flygate CLI 와 정책으로 하나씩 묶었습니다.",
         "where": "agent/flygate.py · agent/bin/flygate"},
        {"id": "04c", "title": "배포, 자체 데이터, 오픈 모델",
         "ours": "implemented · 자체 데이터(FAERS 2012Q4–2026Q2 웨어하우스, 공개 참조 세트)와 build.nvidia.com NIM, BioNeMo NIM 으로 배포 경로를 만들었습니다.",
         "where": "agent/deploy_nemoclaw.sh · pipeline/ · docs/AGENT.md"},
    ]


def _frontmatter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return yaml.safe_load(m.group(1)) if m else {}


def _skills() -> list[dict]:
    out = []
    for p in sorted(list((ROOT / "skills").glob("*/SKILL.md")) + list((AGENT / "skills").glob("*/SKILL.md"))):
        fm = _frontmatter(p)
        name = fm.get("name") or p.parent.name
        stage = ((fm.get("metadata") or {}).get("stage")
                 or ("shared" if name == "connectome-router" else "discovery" if name.startswith("discovery") else "vigilance"))
        out.append({"name": name, "description": " ".join(str(fm.get("description", "")).split()), "stage": stage,
                    "path": str(p.relative_to(ROOT))})
    return out


def _policy() -> dict:
    text = POLICY.read_text(encoding="utf-8")
    p = yaml.safe_load(text)
    egress = []
    for block in p["network_policies"].values():
        bins = [b["path"] for b in block["binaries"]]
        for ep in block["endpoints"]:
            rules = ep.get("rules") or []
            if rules:
                methods = sorted({r["allow"]["method"] for r in rules}, key=["GET", "POST", "HEAD"].index)
                paths = [f"{r['allow']['method']} {r['allow']['path']}" for r in rules]
            else:
                methods = [f"{ep.get('access', 'full')} (L4)"]
                paths = [f"L4 tunnel, allowed_ips {', '.join(ep.get('allowed_ips', []))}".strip()]
            egress.append({"host": ep["host"], "port": ep["port"], "methods": methods, "paths": paths, "binaries": bins})
    fs = p["filesystem_policy"]
    rw = list(fs["read_write"]) + (["/sandbox (include_workdir)"] if fs.get("include_workdir") else [])
    return {"yaml": text, "egress": egress, "filesystem": {"read_only": list(fs["read_only"]), "read_write": rw},
            "process": {"user": f"{p['process']['run_as_user']}:{p['process']['run_as_group']} (non-root)",
                        "seccomp": "OpenShell 런타임 필터 적용 (Seccomp 2, NoNewPrivs 1, CapEff 0 · 라이브 점검)"}}


# 스모크 검사 이름의 한국어 표시입니다(원문은 증거 파일에 그대로 있습니다). 없는 이름은 원문을 씁니다.
SMOKE_KO = {
    "non-root user": "비루트 사용자로 실행",
    "seccomp filter, no_new_privs, no capabilities": "seccomp 필터 · no_new_privs · 권한(capability) 없음",
    "allowed openFDA niraparib label": "허용: openFDA 니라파립 라벨 조회",
    "allowed PubMed esearch": "허용: PubMed 검색",
    "allowed NVIDIA NIM models": "허용: NVIDIA NIM 모델 목록",
    "allowed TypeSafe POST /v1/systemone (no key sent)": "허용: 판단 API POST /v1/systemone (키 없이 보내 원 서버 인증 오류 확인)",
    "denied example.com": "차단: example.com",
    "denied pastebin.com": "차단: pastebin.com",
    "denied curl to api.fda.gov (binary not bound)": "차단: 허용 호스트라도 curl 은 불가(실행 파일 바인딩)",
    "denied openFDA path not in rules (/drug/ndc.json)": "차단: 규칙에 없는 경로 /drug/ndc.json (L7)",
    "denied TypeSafe GET (method not in rules)": "차단: 규칙에 없는 메서드 GET /v1/systemone (L7)",
    "denied write /etc": "차단: /etc 쓰기",
    "denied write /usr": "차단: /usr 쓰기",
    "allowed write /tmp": "허용: /tmp 쓰기",
    "allowed write /sandbox/.openclaw": "허용: /sandbox/.openclaw 쓰기",
    "OpenClaw workspace files and skills in place": "OpenClaw 작업 공간 파일 7개와 스킬 설치",
    "flygate discover parp1 in sandbox": "샌드박스 안 flygate discover parp1",
    "flygate signals NIRAPARIB in sandbox": "샌드박스 안 flygate signals NIRAPARIB",
    "flygate grade NIRAPARIB thrombocytopenia --no-judge in sandbox (live openFDA + PubMed through the policy)":
        "샌드박스 안 flygate grade (정책을 거쳐 openFDA·PubMed 실시간 조회)",
    "flygate watch (heartbeat) in sandbox: memory note under /sandbox/.openclaw, nothing submitted":
        "샌드박스 안 하트비트 flygate watch (메모 기록, 제출 없음)",
}


EXPECT_KO = {
    "HTTP 200 + label JSON": "HTTP 200, 라벨 JSON",
    "origin auth error (request reached api.typesafe.ai)": "원 서버 인증 오류(요청이 api.typesafe.ai 까지 도달)",
    "CONNECT 403 for /usr/bin/curl": "/usr/bin/curl 은 CONNECT 403",
    "write ok": "쓰기 성공",
    "7 persona files + 12 skills": "작업 공간 파일 7개 + 스킬 12개",
    "JSON with evidence IDs": "근거 ID 가 붙은 JSON",
    "JSON with label and PubMed evidence IDs": "라벨·PubMed 근거 ID 가 붙은 JSON",
    "memory note written, submitted=[]": "메모 기록, submitted=[]",
}


def _short(s: str, n: int = 110) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _smoke() -> dict:
    files = sorted((AGENT / "evidence").glob("openshell_smoke_*.txt"))
    if not files:
        return {"ran": False, "when": None, "gateway": None, "sandbox": None, "results": [],
                "source": "agent/openshell_smoke.sh (not run yet)"}
    f = files[-1]
    text = f.read_text(encoding="utf-8")
    head = lambda key: (re.search(rf"^{key}:\s*(.+)$", text, re.M) or [None, None])[1]
    results = []
    for line in text.splitlines():
        if line.startswith("RESULT\t"):
            _, verdict, check, expect, observed = (line.split("\t") + [""] * 5)[:5]
            results.append({"check": SMOKE_KO.get(check, check), "expect": EXPECT_KO.get(expect, expect), "observed": _short(observed),
                            "pass": verdict == "PASS"})
    gw = re.search(r"Gateway:\s*(\S+)", text)
    sb = re.search(r"^sandbox:\s*(\S+)", text, re.M)
    return {"ran": True, "when": head("date_utc"), "gateway": gw.group(1) if gw else None, "sandbox": sb.group(1) if sb else None,
            "results": results, "source": str(f.relative_to(ROOT))}


def _cli() -> list[dict]:
    spec = importlib.util.spec_from_file_location("flygate", AGENT / "flygate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sub = next(a for a in mod.build_parser()._actions if a.dest == "cmd")
    assert set(sub.choices) == set(CLI), f"CLI 설명과 파서가 다릅니다: {set(sub.choices) ^ set(CLI)}"
    return [{"cmd": CLI[k][0], "what": CLI[k][1]} for k in sub.choices]


def build() -> dict:
    ws = [{"file": f, "role": role, "content": (AGENT / "workspace" / f).read_text(encoding="utf-8")} for f, role in WORKSPACE]
    skills, policy, smoke, cli = _skills(), _policy(), _smoke(), _cli()
    n_ext = len({e["host"] for e in policy["egress"] if "." in e["host"] and not e["host"].endswith(".local")
                 and not e["host"][0].isdigit()})
    ok = sum(r["pass"] for r in smoke["results"])
    smoke_txt = f"{ok}/{len(smoke['results'])} 통과, {smoke['when'][:10]}" if smoke["ran"] else "기록 없음"
    fill = {"n_ws": len(ws), "n_skills": len(skills), "n_cli": len(cli), "n_ext": n_ext, "smoke": smoke_txt}
    return {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stack": [{"layer": layer, "what": what, "ours": ours.format(**fill)} for layer, what, ours in STACK],
        "workspace": ws,
        "skills": skills,
        "policy": policy,
        "triggers": TRIGGERS,
        "cli": cli,
        "modules": _modules(smoke_txt),
        "smoke": smoke,
        "trifecta": {k: v.format(**fill) for k, v in TRIFECTA.items()},
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ok = sum(r["pass"] for r in data["smoke"]["results"])
    print(f"wrote {OUT.relative_to(ROOT)}: workspace {len(data['workspace'])}, skills {len(data['skills'])}, "
          f"egress {len(data['policy']['egress'])}, cli {len(data['cli'])}, modules {len(data['modules'])}, "
          f"smoke {ok}/{len(data['smoke']['results'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
