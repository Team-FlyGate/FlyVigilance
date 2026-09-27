"""FlyVigilance API. 로컬은 uvicorn, 배포는 Vercel Python Function 으로 같은 파일을 쓴다.

GET  /api/health          키 설정 여부, 데이터 기준일
GET  /api/cases           실제 FAERS 케이스 표본 (트리아지 데모용)
POST /api/triage          Jev System-1 실시간 판단 + 라우팅
POST /api/assess          근거 수집 + Nemotron System-2 메모 + 크리틱 3단
POST /api/critic          주어진 주장만 크리틱에 통과 (과잉해석 주입 테스트)
GET  /api/signals/{drug}  웨어하우스 불균형 지표 상위 반응
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
from _fv import clients, config, evidence, triage as triage_mod  # noqa: E402

app = FastAPI(title="FlyVigilance API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 공개 배포에서 유료 API 남용을 막는 간단한 IP 별 속도 제한
_hits: dict[str, deque] = {}
LIMIT = {"triage": (30, 60), "assess": (6, 60), "critic": (10, 60)}


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
    try:
        return await triage_mod.triage(case)
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


@app.get("/api/signals/{drug}")
def signals(drug: str, limit: int = 40):
    rows = evidence.drug_profile(drug, limit)
    if not rows:
        raise HTTPException(404, f"no signals for {drug}")
    return {"drug": drug.upper(), "asof": evidence._signals()["asof"], "rows": rows}
