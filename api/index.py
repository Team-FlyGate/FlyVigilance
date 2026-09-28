"""FlyVigilance API. 로컬은 uvicorn, 배포는 Vercel Python Function 으로 같은 파일을 쓴다.

GET  /api/health          키 설정 여부, 데이터 기준일
GET  /api/cases           실제 FAERS 케이스 표본 (트리아지 데모용)
POST /api/triage          Jev System-1 실시간 판단 + 라우팅
POST /api/assess          근거 수집 + Nemotron System-2 메모 + 크리틱 3단
POST /api/critic          주어진 주장만 크리틱에 통과 (과잉해석 주입 테스트)
POST /api/triage?regime=KR 국내 신속보고 기준(중대 -> 15일)으로 라우팅
POST /api/kr/intake       국내 보고서식·자유 서술 -> 구조화 (Nemotron)
POST /api/kr/causality    한국형 인과성 평가 알고리즘 ver 2.0 (Jev) + WHO-UMC
GET  /api/grade           근거 등급 (FAERS 통계 + 라벨 절 + 문헌 읽기)
GET  /api/signals/{drug}  웨어하우스 불균형 지표 상위 반응
POST /api/dock            STEP 1 직접 도킹: 결정 구조 수용체 × SMILES 를 DiffDock NIM 으로 실시간 도킹
POST /api/dock/critic     STEP 1 도킹 주장을 크리틱 3단(1·2단 규칙 + 3단 도킹 해석 규칙 D1–D5, Jev)으로 판정
"""
import gzip
import json
import sys
import time
import pathlib
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from _fv import assess as assess_mod  # noqa: E402
from _fv import dock as dock_mod  # noqa: E402
from _fv import discovery as disc_mod  # noqa: E402
from _fv import clients, config, evidence, grade as grade_mod, knowledge, kr as kr_mod, literature, triage as triage_mod  # noqa: E402

app = FastAPI(title="FlyVigilance API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 공개 배포에서 유료 API 남용을 막는 간단한 IP 별 속도 제한
_hits: dict[str, deque] = {}
LIMIT = {"triage": (30, 60), "assess": (6, 60), "critic": (10, 60), "kr": (10, 60), "grade": (20, 60), "dock": (8, 60),
         "discovery": (12, 60), "discovery_status": (60, 60)}


def _rate(req: Request, key: str):
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "?").split(",")[0]
    n, window = LIMIT[key]
    q = _hits.setdefault(f"{key}:{ip}", deque())
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= n:
        raise HTTPException(429, f"rate limit: {n} {key} calls per {window}s")
    q.append(now)


def _cases():
    p = config.DATA / "cases.json.gz"
    if not p.exists():
        return []
    with gzip.open(p, "rt") as f:
        return json.load(f)


@app.get("/api/health")
def health():
    s = evidence._signals()
    return {"ok": True, "jev": bool(config.TYPESAFE_API_KEY), "nim": bool(config.NVIDIA_API_KEY),
            "signals_asof": s.get("asof"), "signal_drugs": len(s.get("drugs", {})), "cases": len(_cases()),
            "models": {"reflex": config.JEV_MODEL, "deliberate": config.MODEL_DELIBERATE,
                       "embed": config.MODEL_EMBED}}


@app.get("/api/cases")
def cases(limit: int = 60, bucket: str | None = None):
    rows = _cases()
    if bucket:
        rows = [r for r in rows if r.get("bucket") == bucket]
    return rows[: max(1, min(limit, 500))]


@app.post("/api/triage")
async def triage(req: Request):
    _rate(req, "triage")
    case = await req.json()
    regime = req.query_params.get("regime", "US").upper()
    try:
        return await triage_mod.triage(case, regime=regime)
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")


@app.post("/api/assess")
async def assess(req: Request):
    _rate(req, "assess")
    body = await req.json()
    case, tri = body["case"], body["triage"]
    t0 = time.perf_counter()
    bundle = await evidence.bundle(case, tri["suspect"])
    t_ev = (time.perf_counter() - t0) * 1000
    try:
        res = await assess_mod.assess(tri["state"], tri["jev"]["answers"], bundle)
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    res["evidence"] = bundle
    res["evidence_ms"] = round(t_ev, 1)
    return res


@app.post("/api/critic")
async def critic(req: Request):
    """적대적 주입: 주어진 주장만 크리틱 3단과 가드에 통과시킨다."""
    _rate(req, "critic")
    body = await req.json()
    try:
        return await assess_mod.critic_only(body["claims"], body["state"], body["bundle"])
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")


@app.post("/api/kr/intake")
async def kr_intake(req: Request):
    """국내 보고서식·자유 서술을 구조화합니다 (Nemotron)."""
    _rate(req, "kr")
    body = await req.json()
    try:
        return await kr_mod.intake(body["text"], body.get("form", "narrative"))
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(502, str(e))


@app.post("/api/kr/causality")
async def kr_causality(req: Request):
    """한국형 인과성 평가 알고리즘 ver 2.0 (Jev 판단 + 규칙 합산)과 WHO-UMC 를 따로 냅니다."""
    _rate(req, "kr")
    body = await req.json()
    try:
        return await kr_mod.causality_kr(body["case"], triage_mod.case_state(body["case"]), body.get("narrative"))
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")


@app.get("/api/grade")
async def grade(req: Request, drug: str, pt: str, route: str | None = None):
    """PV 분류 (규칙) = FAERS 통계 + FDA 허가 라벨 + 문헌 읽기, 그리고 지식 기반 판별(참고 축)을 함께 돌려줍니다."""
    _rate(req, "grade")
    import asyncio
    import httpx

    async def know(c):
        try:
            return await knowledge.recognize(drug, pt, c)
        except Exception as e:  # 판단 모델 장애는 분류에 영향을 주지 않습니다
            return {"p": None, "error": type(e).__name__}
    async with httpx.AsyncClient() as c:
        lab, lit, kn = await asyncio.gather(evidence.label_lookup(drug, [pt], c, route), literature.read(drug, pt, c), know(c))
    g = grade_mod.grade_pair(drug, pt, evidence.faers_2x2(drug, pt), lab, lit)
    g["axes"]["knowledge"] = kn
    return {**g, "literature": lit, "label": lab}


@app.get("/api/discovery/catalog")
def discovery_catalog():
    """STEP 1 화면이 고를 수 있는 타깃·리간드·쌍과 따라간 NVIDIA 공식 스킬입니다."""
    return disc_mod.catalog()


@app.get("/api/discovery/scene/{target}")
def discovery_scene(target: str):
    """3D 배경(결정 구조 CA 골격, 결합 주머니, 공결정 리간드)입니다."""
    try:
        return disc_mod.scene(target)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/discovery/measured/{kind}")
def discovery_measured(kind: str, target: str = "parp1", ligand: str | None = None):
    """지난 측정만 돌려줍니다(NIM 을 부르지 않음). 단계 페이지가 실행 전 · 실패 시에도 비교 열을 채우는 데 씁니다."""
    if kind not in disc_mod.NIM_KINDS:
        raise HTTPException(404, f"unknown step {kind}")
    return {"kind": kind, "measured": disc_mod.measured_for(kind, {"target": target, "ligand": ligand})}


@app.post("/api/discovery/{kind}")
async def discovery_run(kind: str, req: Request):
    """NVIDIA BioNeMo NIM 을 실제로 부릅니다(kind: msa | openfold3 | diffdock | boltz2), 또는 크리틱을 돌립니다."""
    _rate(req, "discovery")
    body = await req.json() if await req.body() else {}
    if kind == "critic":
        claims = body.get("claims") or disc_mod.default_claims(body.get("runs") or {})
        try:
            return await disc_mod.critic(claims, body.get("runs") or {})
        except clients.NotConfigured as e:
            raise HTTPException(503, f"{e} not configured")
    if kind not in disc_mod.NIM_KINDS:
        raise HTTPException(404, f"unknown step {kind}")
    try:
        return await disc_mod.run(kind, body)
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")
    except KeyError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.get("/api/discovery/status/{req_id}")
async def discovery_status(req_id: str, req: Request, kind: str | None = None, target: str | None = None,
                           ligand: str | None = None):
    """계산 중인 NIM 요청을 이어서 묻습니다 (health.api.nvidia.com/v1/status/{req_id})."""
    _rate(req, "discovery_status")
    params = None
    if kind:
        params = {k: v for k, v in (("target", target), ("ligand", ligand)) if v}
    try:
        return await disc_mod.poll(req_id, kind, params)
    except clients.NotConfigured as e:
        raise HTTPException(503, f"{e} not configured")
    except KeyError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.get("/api/signals/{drug}")
def signals(drug: str, limit: int = 40):
    rows = evidence.drug_profile(drug, limit)
    if not rows:
        raise HTTPException(404, f"no signals for {drug}")
    return {"drug": drug.upper(), "asof": evidence._signals()["asof"], "rows": rows}


@app.post("/api/dock")
async def dock(req: Request):
    """STEP 1 직접 도킹. 이미 받아 둔 재도킹 조합은 화면이 저장된 결과를 쓰므로 새 조합만 온다."""
    _rate(req, "dock")
    body = await req.json()
    try:
        return await dock_mod.dock(str(body.get("target", "")), str(body.get("smiles", "")))
    except dock_mod.DockError as e:
        raise HTTPException(400, str(e))


@app.post("/api/dock/critic")
async def dock_critic(req: Request):
    """STEP 1 직접 도킹 결과에 대해 에이전트(또는 사람)가 쓴 주장을 크리틱 3단으로 판정한다."""
    _rate(req, "critic")
    body = await req.json()
    claims = [{"id": str(c.get("id", f"c{i+1}"))[:8], "text": str(c.get("text", ""))[:400], "evidence": list(c.get("evidence") or [])[:5]}
              for i, c in enumerate((body.get("claims") or [])[:8])]
    return await dock_mod.critic(claims, str(body.get("state", ""))[:4000], [str(x) for x in (body.get("ids") or [])][:20])
