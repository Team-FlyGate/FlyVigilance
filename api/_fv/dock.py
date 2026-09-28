"""STEP 1 직접 도킹: 결정 구조 수용체에 고른 약물을 DiffDock NIM 으로 실시간 도킹한다.

재도킹으로 이미 받아 둔 조합은 화면이 저장된 결과(redock_scenes.json)를 쓰고, 여기로는 새 조합만 온다.
수용체는 pipeline/discovery/build_dock_library.py 가 만든 _data/dock_receptors.json.gz 이고,
돌려주는 좌표는 화면 장면과 같게 결정 리간드 중심을 원점으로 옮긴다.
"""
import gzip
import json
import re
import time

import httpx

from . import calllog, config

DIFFDOCK_URL = "https://health.api.nvidia.com/v1/biology/mit/diffdock"
SMILES_OK = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$%/\\.:*]{1,300}$")
_receptors: dict | None = None
_cache: dict[tuple[str, str], dict] = {}


class DockError(Exception):
    pass


def receptors() -> dict:
    global _receptors
    if _receptors is None:
        with gzip.open(config.DATA / "dock_receptors.json.gz", "rt") as f:
            _receptors = json.load(f)
    return _receptors


def parse_sdf(block: str, center: list[float]) -> dict:
    """V2000 SDF 한 개를 중원자 좌표·원소·결합으로 바꾼다 (RDKit 없이 고정 열 형식을 읽는다)."""
    lines = block.splitlines()
    counts = lines[3]
    na, nb = int(counts[0:3]), int(counts[3:6])
    atoms, keep = [], {}
    for i in range(na):
        ln = lines[4 + i]
        el = ln[31:34].strip()
        if el == "H":
            continue
        keep[i] = len(atoms)
        atoms.append([round(float(ln[0:10]) - center[0], 2), round(float(ln[10:20]) - center[1], 2), round(float(ln[20:30]) - center[2], 2), el])
    bonds = []
    for j in range(nb):
        ln = lines[4 + na + j]
        a, b = int(ln[0:3]) - 1, int(ln[3:6]) - 1
        if a in keep and b in keep:
            bonds.append([keep[a], keep[b]])
    return {"atoms": atoms, "bonds": bonds}


async def dock(target: str, smiles: str, num_poses: int = 5) -> dict:
    smiles = smiles.strip()
    if not SMILES_OK.match(smiles):
        raise DockError("SMILES 형식이 아닙니다")
    rec = receptors().get(target)
    if rec is None:
        raise DockError(f"모르는 표적입니다: {target}")
    key = (target, smiles)
    if key in _cache:
        calllog.record(url=DIFFDOCK_URL, model="mit/diffdock", purpose="STEP 1 live docking (dashboard)", cache_hit=True)
        return {**_cache[key], "cached": True}
    if not config.NVIDIA_API_KEY:
        raise DockError("NVIDIA_API_KEY 가 없어 실시간 도킹을 할 수 없습니다")
    payload = {"protein": rec["protein"], "ligand": smiles, "ligand_file_type": "txt", "num_poses": num_poses,
               "time_divisions": 20, "steps": 18, "save_trajectory": False}
    headers = {"Authorization": f"Bearer {config.NVIDIA_API_KEY}", "Content-Type": "application/json", "NVCF-POLL-SECONDS": "100"}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(100.0, connect=10.0)) as c:
        polls, rid, bytes_out = 0, None, None
        try:
            r = await c.post(DIFFDOCK_URL, json=payload, headers=headers)
            rid = calllog.reqid_of(r.headers)
            bytes_out = len(r.request.content)
            while r.status_code == 202 and r.headers.get("nvcf-reqid"):
                polls += 1
                r = await c.get(f"https://health.api.nvidia.com/v1/status/{r.headers['nvcf-reqid']}", headers=headers)
        except httpx.HTTPError as e:
            calllog.record(url=DIFFDOCK_URL, model="mit/diffdock", purpose="STEP 1 live docking (dashboard)", reqid=rid,
                           latency_ms=(time.perf_counter() - t0) * 1000, error=e, extra={"polls": polls})
            raise
        calllog.record(url=DIFFDOCK_URL, model="mit/diffdock", purpose="STEP 1 live docking (dashboard)", response=r,
                       reqid=calllog.reqid_of(r.headers) or rid, bytes_out=bytes_out,
                       latency_ms=(time.perf_counter() - t0) * 1000,
                       error=None if r.status_code == 200 else f"HTTP{r.status_code}", extra={"polls": polls})
        if r.status_code != 200:
            raise DockError(f"DiffDock NIM HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
    poses = [parse_sdf(b, rec["center"]) for b in body.get("ligand_positions") or []]
    if not poses:
        raise DockError("DiffDock NIM 이 포즈를 돌려주지 않았습니다")
    conf = [round(float(c), 3) if isinstance(c, (int, float)) else None for c in body.get("position_confidence") or []]
    out = {"target": target, "smiles": smiles, "poses": poses, "confidence": conf,
           "seconds": round(time.perf_counter() - t0, 2), "endpoint": DIFFDOCK_URL}
    _cache[key] = out
    return {**out, "cached": False}


# ── 도킹 크리틱 ────────────────────────────────────────────────────────────────
# 약물감시 크리틱(assess.py)과 같은 3단 구조를 도킹 주장에 씁니다. 1·2단은 같은 규칙 함수를 쓰고,
# 3단만 도킹 해석 규칙(D1–D5)으로 Jev 가 판정합니다. Jev 를 쓸 수 없으면 같은 규칙을 키워드로 판정합니다.
DOCK_RULES = [
    ("D1", "A docking or pose confidence score is the likelihood that a pose is correct, not binding affinity or potency."),
    ("D2", "Scores from different protein targets are not comparable; they cannot establish selectivity between targets."),
    ("D3", "Reproducing a co-crystal ligand (redocking) validates the setup only, not the binding of a new molecule."),
    ("D4", "A predicted pose or predicted structure is not an experimentally determined complex."),
    ("D5", "Docking alone says nothing about efficacy, safety or dosing in patients."),
]
_KEYWORDS = {
    "D1": ["강하게 결합", "결합력", "친화도가 높", "잘 붙", "potent", "affinity", "억제력"],
    "D2": ["선택적", "선택성", "보다 더 잘", "selective"],
    "D3": ["새 후보", "새 분자도", "모든 분자"],
    "D4": ["실험적으로", "결정 구조로 확인", "증명", "확인되었"],
    "D5": ["효과가 있", "안전", "환자", "처방", "용량", "치료"],
}


async def critic(claims: list[dict], state: str, ids: list[str]) -> dict:
    from .assess import tier1_rules, tier2_oracle, _numbers  # 약물감시 크리틱과 같은 1·2단
    from . import clients
    t0 = time.perf_counter()
    t1 = tier1_rules(claims, set(ids))
    t2 = tier2_oracle(claims, _numbers(state))
    t3, judge, mode = [], {}, "jev"
    try:
        text = ("Docking interpretation rules:\n" + "\n".join(f"{k}: {v}" for k, v in DOCK_RULES) +
                "\n\nClaims written by an AI agent about one docking result:\n" + "\n".join(f"{c['id']}: {c['text']}" for c in claims))
        qs = {}
        for c in claims:
            qs[f"{c['id']}_violates"] = {"type": "noul", "instructions": f"Does claim {c['id']} violate any of the docking interpretation rules above?"}
            qs[f"{c['id']}_rule"] = {"type": "choice", "instructions": f"Which rule does claim {c['id']} most likely violate?",
                                     "criteria": {k: v for k, v in DOCK_RULES} | {"none": "no rule is violated"}}
        judge = await clients.jev(text, qs)
        for c in claims:
            p = judge["answers"][f"{c['id']}_violates"]["noul"]
            rule = judge["answers"][f"{c['id']}_rule"]["choice"]
            c["overclaim_p"] = p
            if p >= 0.5 and rule != "none":
                t3.append({"claim": c["id"], "tier": 3, "rule": rule, "p": p, "detail": dict(DOCK_RULES).get(rule, "")})
    except Exception:  # noqa: BLE001  Jev 키가 없거나 응답이 없으면 같은 규칙을 키워드로
        mode = "rules"
        for c in claims:
            for rule, words in _KEYWORDS.items():
                if any(w in c.get("text", "") for w in words):
                    t3.append({"claim": c["id"], "tier": 3, "rule": rule, "p": None, "detail": dict(DOCK_RULES)[rule]})
                    break
    return {"claims": claims, "issues": t1 + t2 + t3, "mode": mode, "judge_latency_ms": judge.get("latency_ms"),
            "total_ms": round((time.perf_counter() - t0) * 1000, 1), "rules": DOCK_RULES}
