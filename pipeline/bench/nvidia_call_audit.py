"""NVIDIA 호출 감사: 이 프로젝트가 쓰는 NVIDIA 모델·엔드포인트를 하나씩 한 번 실제로 부르고 호출 기록을 남깁니다.

심사자가 "어떤 NVIDIA 기술을 어떻게 썼는지"를 호출 기록으로 확인할 수 있게 하려는 스크립트입니다.
- 가능한 한 저장소의 실제 코드 경로(api/_fv/*)로 부릅니다. 캐시는 모두 우회합니다(FV_CACHE_DIR 해제, 메모리 캐시 비움).
- 입력은 작고 민감하지 않은 데모 값입니다: PARP1 촉매 도메인 + 니라파립, 합성(가상) 약물감시 주장.
- 호출 기록은 api/_fv/calllog.py 가 FV_CALL_LOG 파일에 한 줄씩 남깁니다. 키·Authorization 헤더·프롬프트·응답 본문은 남기지 않습니다.
- BioNeMo 구조 NIM(MSA-Search, OpenFold3, Boltz-2)은 저장소에 런타임 클라이언트가 없어(원래 측정은 원본 응답만 남겼습니다)
  이 스크립트의 작은 NVCF 호출기(nvcf_call)로 부릅니다. 202 응답이면 /v1/status/<요청 ID> 를 폴링합니다.
- 실패(예: OpenFold3 504)는 그대로 기록합니다. 다시 시도해 성공한 것처럼 꾸미지 않습니다.

산출물
- data/logs/nvidia_calls_<날짜>.jsonl : 호출 기록 원본(.gitignore 대상)
- web/public/data/nvidia_calls.json   : 커밋하는 요약. 호출마다 시각·서비스·모델·엔드포인트·용도·상태·지연·요청 ID·토큰·
                                        코드 경로·대시보드 화면. 저장소에 이미 있는 이전 실측 원본을 'archived' 로 함께 적습니다.

사용: FV_CALL_LOG=data/logs/x.jsonl .venv/bin/python pipeline/bench/nvidia_call_audit.py [--only msa,of3] [--skip-structure]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import glob
import json
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
os.environ.pop("FV_CACHE_DIR", None)  # 캐시 우회
os.environ["FV_RERANK"] = "1"

import httpx  # noqa: E402

from _fv import assess, calllog, clients, config, dock, literature  # noqa: E402

NIM = ROOT / "fly_discovery/measurements/nim"
OUT_JSON = ROOT / "web/public/data/nvidia_calls.json"
HEALTH = "https://health.api.nvidia.com/v1"
MSA_URL = f"{HEALTH}/biology/colabfold/msa-search/predict"
OF3_URL = f"{HEALTH}/biology/openfold/openfold3/predict"
BOLTZ_URL = f"{HEALTH}/biology/mit/boltz2/predict"
NIRAPARIB = "C1CC(CNC1)C2=CC=C(C=C2)N3C=C4C=CC=C(C4=N3)C(=O)N"
PARP1 = (NIM / "parp1_seq.txt").read_text().strip() if (NIM / "parp1_seq.txt").exists() else ""

# 합성(가상) 사례입니다. 실제 환자 정보가 아닙니다.
SYN_STATE = ("SYNTHETIC DEMO CASE (not a real patient). Suspect drug: NIRAPARIB (PS, oral). "
             "Reaction: thrombocytopenia. Outcome: hospitalization.")
SYN_BUNDLE = {"catalog": [
    {"id": "faers:2x2:NIRAPARIB:thrombocytopenia", "what": "FAERS 2x2 for NIRAPARIB + thrombocytopenia: a=812, PRR 9.41, ROR 10.2, IC025 2.9"},
    {"id": "label:NIRAPARIB:warnings", "what": "FDA label warnings_and_cautions lists thrombocytopenia (myelosuppression)"},
]}
SYN_CLAIM_ADVICE = "The patient should stop niraparib today and take 50 mg of prednisone instead."
SYN_CLAIM_CAUSAL = "A PRR of 9.41 proves that niraparib caused thrombocytopenia in this patient."

# 호출 단계: (id, 기술 이름, 서비스 묶음, 실제 코드 경로, 대시보드 화면)
STEPS = {
    "super": ("Nemotron 3 Super 120B (JSON mode)", "nim", "api/_fv/assess.py:assess -> api/_fv/clients.py:nim_chat",
              ["#/triage", "#/korea"]),
    "ultra": ("Nemotron 3 Ultra 550B", "nim", "api/_fv/config.py:MODEL_DELIBERATE[1] (fallback) -> api/_fv/clients.py:nim_chat",
              ["#/triage"]),
    "lightning": ("Nemotron 3.5 Lightning 30B", "nim", "api/_fv/config.py:MODEL_DELIBERATE[2], MODEL_FAST -> api/_fv/clients.py:nim_chat",
                  ["#/triage", "#/bench"]),
    "guard": ("Nemotron Safety Guard 8B v3", "nim", "api/_fv/assess.py:guard (guard_claims)", ["#/triage", "#/skills"]),
    "policy": ("Nemotron 3.5 Content Safety + PV custom_policy", "nim", "api/_fv/assess.py:policy_guard (guard_claims)",
               ["#/triage", "#/skills"]),
    "rerank": ("Nemotron Rerank VL 1B v2", "retrieval", "api/_fv/literature.py:rerank -> api/_fv/clients.py:nim_rerank",
               ["#/signals", "#/triage"]),
    "embed": ("Nemotron 3 Embed 1B", "nim", "api/_fv/clients.py:nim_embed, nim_embed_many (pipeline/bench/literature_rerank_eval.py)", ["#/calls"]),
    "msa": ("BioNeMo MSA-Search (ColabFold)", "bionemo", "pipeline/bench/nvidia_call_audit.py:nvcf_call", ["#/d-msa"]),
    "of3": ("BioNeMo OpenFold3", "bionemo", "pipeline/bench/nvidia_call_audit.py:nvcf_call", ["#/d-of3"]),
    "diffdock": ("BioNeMo DiffDock", "bionemo", "api/_fv/dock.py:dock (POST /api/dock); CLI: api/_fv/docking.py:execute",
                 ["#/d-diffdock", "#/cli"]),
    "boltz": ("BioNeMo Boltz-2", "bionemo", "pipeline/bench/nvidia_call_audit.py:nvcf_call", ["#/d-boltz"]),
}


def git_date(path: pathlib.Path) -> str | None:
    """파일이 저장소에 처음 들어온 커밋 시각(ISO)입니다."""
    try:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%aI", "--", str(path.relative_to(ROOT))],
                             cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
        return out[-1] if out else None
    except Exception:  # noqa: BLE001
        return None


def lines(path: pathlib.Path) -> int:
    return len(path.read_text().splitlines()) if path.exists() else 0


async def nvcf_call(url: str, payload: dict, model: str, purpose: str, budget_s: float = 600.0) -> dict:
    """health.api.nvidia.com 호출 한 번. 202 면 NVCF 상태 엔드포인트를 폴링합니다. 기록은 한 줄(최종 상태 기준)입니다."""
    headers = {"Authorization": f"Bearer {config.NVIDIA_API_KEY}", "Content-Type": "application/json",
               "Accept": "application/json", "NVCF-POLL-SECONDS": "300"}
    t0, polls, rid, bout, r, err = time.perf_counter(), 0, None, None, None, None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(min(budget_s, 400.0), connect=15.0)) as c:
            r = await c.post(url, json=payload, headers=headers)
            bout = len(r.request.content)
            rid = calllog.reqid_of(r.headers)
            while r.status_code == 202 and time.perf_counter() - t0 < budget_s:
                rid = calllog.reqid_of(r.headers) or rid
                polls += 1
                r = await c.get(f"{HEALTH}/status/{rid}", headers=headers)
    except httpx.HTTPError as e:
        err = e
    ms = (time.perf_counter() - t0) * 1000
    calllog.record(url=url, model=model, purpose=purpose, response=r, reqid=(calllog.reqid_of(r.headers) if r is not None else None) or rid,
                   bytes_out=bout, latency_ms=ms, extra={"polls": polls},
                   error=err if err else (None if r is not None and r.status_code == 200 else f"HTTP{r.status_code if r is not None else 0}"))
    body = None
    if r is not None and r.status_code == 200:
        try:
            body = r.json()
        except ValueError:
            body = None
    return {"status": None if r is None else r.status_code, "body": body, "ms": ms, "error": type(err).__name__ if err else None}


# ------------------------------------------------------------------ 단계별 호출
async def step_chat(model: str, purpose: str, json_mode: bool) -> dict:
    msgs = [{"role": "system", "content": assess.SYSTEM},
            {"role": "user", "content": assess._user_prompt(SYN_STATE, {"serious": 0.93}, SYN_BUNDLE)}]
    out = await clients.nim_chat(msgs, [model], max_tokens=1000, temperature=0.0, json_mode=json_mode, purpose=purpose)
    try:
        memo = clients.parse_json_block(out["content"])
        n = len(memo.get("claims", []))
    except Exception:  # noqa: BLE001
        n = None
    return {"claims_parsed": n, "json_ok": n is not None}


async def step_guard() -> dict:
    v = await assess.guard(SYN_CLAIM_ADVICE)
    return {"verdict": {True: "safe", False: "unsafe", None: "unknown"}[v.get("safe")], "model": v.get("model"),
            "categories": v.get("categories")}


async def step_policy() -> dict:
    v = await assess.policy_guard(SYN_CLAIM_CAUSAL)
    return {"verdict": {True: "safe", False: "unsafe", None: "unknown"}[v.get("safe")], "pv": v.get("pv"), "rule": v.get("rule"),
            "policy": v.get("policy")}


async def step_rerank() -> dict:
    literature._RERANK_MEMO.clear()
    arts = [{"pmid": f"SYN{i}", "title": t, "abstract": a} for i, (t, a) in enumerate([
        ("Niraparib-induced thrombocytopenia in ovarian cancer: a case series", "We report thrombocytopenia after niraparib maintenance."),
        ("Weather patterns in Seoul", "Seasonal rainfall analysis."),
        ("Hematologic adverse events of PARP inhibitors: pharmacovigilance study", "FAERS disproportionality for niraparib and platelets."),
        ("Docking of small molecules", "A benchmark of docking programs."),
        ("Platelet count monitoring with niraparib", "Clinical trial data on dose interruption for thrombocytopenia."),
        ("Coffee consumption and sleep", "A cohort study."),
        ("Anemia with olaparib", "Case report of anemia."),
        ("Niraparib pharmacokinetics", "Exposure and body weight."),
    ])]
    async with httpx.AsyncClient() as c:
        picked, meta = await literature.rerank("NIRAPARIB", "thrombocytopenia", arts, 3, c)
    return {"order": meta.get("order"), "picked_pubmed_ranks": meta.get("pubmed_ranks"), "error": meta.get("rerank_error")}


async def step_embed() -> dict:
    out = await clients.nim_embed(["niraparib thrombocytopenia case report"], "query", purpose="embedding: literature query (bench)")
    return {"dim": len(out["vectors"][0]) if out["vectors"] else None}


def a3m_from(body: dict | None) -> str | None:
    """MSA-Search 응답에서 Uniref30 a3m 정렬을 찾습니다."""
    if not isinstance(body, dict):
        return None
    al = body.get("alignments") or {}
    for db in al.values():
        a = (db or {}).get("a3m") if isinstance(db, dict) else None
        if isinstance(a, dict) and a.get("alignment"):
            return a["alignment"]
    return None


async def step_msa(ctx: dict) -> dict:
    payload = {"sequence": PARP1, "e_value": 0.0001, "iterations": 1, "databases": ["Uniref30_2302"],
               "search_type": "alphafold2", "output_alignment_formats": ["a3m"], "max_msa_sequences": 128}
    r = await nvcf_call(MSA_URL, payload, "colabfold/msa-search", "MSA-Search: PARP1 homolog alignment (STEP 1 · 01)")
    a3m = a3m_from(r["body"])
    ctx["a3m"] = a3m
    return {"http": r["status"], "homologs": a3m.count(">") - 1 if a3m else None, "error": r["error"]}


async def step_of3(ctx: dict) -> dict:
    a3m = ctx.get("a3m") or (NIM / "parp1.a3m").read_text()
    payload = {"request_id": "flygate-audit", "inputs": [{"input_id": "parp1_niraparib", "molecules": [
        {"type": "protein", "id": "A", "sequence": PARP1, "msa": {"main_db": {"a3m": {"alignment": a3m, "format": "a3m"}}}},
        {"type": "ligand", "id": "B", "smiles": NIRAPARIB}], "output_format": "pdb"}]}
    r = await nvcf_call(OF3_URL, payload, "openfold/openfold3", "OpenFold3: PARP1 + niraparib complex (STEP 1 · 02)", budget_s=420)
    out = {"http": r["status"], "error": r["error"], "msa_source": "live" if ctx.get("a3m") else "stored parp1.a3m"}
    try:
        s = r["body"]["outputs"][0]["structures_with_scores"][0]
        out.update(plddt=round(float(s["complex_plddt_score"]), 2), iptm=round(float(s["iptm_score"]), 3))
    except Exception:  # noqa: BLE001
        pass
    return out


async def step_diffdock() -> dict:
    dock._cache.clear()
    try:
        r = await dock.dock("parp1-4r6e--niraparib", NIRAPARIB, num_poses=3)
        return {"poses": len(r["poses"]), "top_confidence": r["confidence"][0] if r["confidence"] else None}
    except dock.DockError as e:
        return {"error": str(e)[:80]}


async def step_boltz() -> dict:
    payload = {"polymers": [{"id": "A", "molecule_type": "protein", "sequence": PARP1}],
               "ligands": [{"id": "L", "smiles": NIRAPARIB, "predict_affinity": True}],
               "recycling_steps": 3, "sampling_steps": 50, "diffusion_samples": 1, "output_format": "mmcif"}
    r = await nvcf_call(BOLTZ_URL, payload, "mit/boltz2", "Boltz-2: PARP1 + niraparib structure & affinity (STEP 1 · 04)", budget_s=420)
    out = {"http": r["status"], "error": r["error"]}
    try:
        out["pic50"] = round(float(r["body"]["affinities"]["L"]["affinity_pic50"][0]), 3)
    except Exception:  # noqa: BLE001
        pass
    return out


def plan(skip_structure: bool) -> list[tuple[str, callable]]:
    p = [
        ("super", lambda ctx: step_chat("nvidia/nemotron-3-super-120b-a12b", "System-2 assessment memo (evidence-cited claims, JSON)", True)),
        ("ultra", lambda ctx: step_chat("nvidia/nemotron-3-ultra-550b-a55b", "System-2 memo fallback #2 (Ultra)", True)),
        ("lightning", lambda ctx: step_chat("nvidia/nemotron-3.5-lightning-30b-a3b", "System-2 memo fallback #3 / fast lane (Lightning)", True)),
        ("guard", lambda ctx: step_guard()),
        ("policy", lambda ctx: step_policy()),
        ("rerank", lambda ctx: step_rerank()),
        ("embed", lambda ctx: step_embed()),
        ("diffdock", lambda ctx: step_diffdock()),
    ]
    if not skip_structure:
        p += [("msa", step_msa), ("of3", step_of3), ("boltz", lambda ctx: step_boltz())]
    return p


# ------------------------------------------------------------------ 이전 실측(archived)
def archived() -> list[dict]:
    out = []

    def add(**kw):
        out.append({"ts": None, "service": None, "model": None, "endpoint": None, "purpose": None, "status": None,
                    "latency_ms": None, "nvcf_reqid": None, "tokens": None, "n_calls": 1, "source": None, "note": None, **kw})

    # DiffDock CLI 실행 기록(manifest 에 요청 ID 가 남습니다). data/ 는 .gitignore 이므로 로컬 기록입니다
    for m in sorted(glob.glob(str(ROOT / "data/discovery-runs/*/manifest.json"))):
        d = json.loads(pathlib.Path(m).read_text())
        lat = None
        try:
            lat = round((dt.datetime.fromisoformat(d["finished_at"]) - dt.datetime.fromisoformat(d["created_at"])).total_seconds() * 1000, 1)
        except Exception:  # noqa: BLE001
            pass
        add(ts=d.get("created_at"), service=calllog.SERVICES["health.api.nvidia.com"], model="mit/diffdock",
            endpoint="/v1/biology/mit/diffdock", purpose="CLI discover: fresh DiffDock run (flygate discover --live)",
            status=d.get("status"), latency_ms=lat, nvcf_reqid=d.get("request_id"),
            source=str(pathlib.Path(m).relative_to(ROOT)), code_path="api/_fv/docking.py:execute",
            note=f"{len(d.get('poses') or [])} poses · response_sha256 {str(d.get('response_sha256'))[:12]} · local run dir (gitignored)")

    # FlyDiscovery 원본 응답(fly_discovery/measurements/nim). 요청 ID 는 원본에 없어 커밋 시각과 파일로 대조합니다
    def nimfile(pattern, model, endpoint, purpose, note_fn=None, code="fly_discovery/measurements/nim (raw response)"):
        for f in sorted(NIM.glob(pattern)):
            try:
                body = json.loads(f.read_text()) if f.suffix == ".json" else None
            except ValueError:
                body = None
            note, status, lat = (note_fn(body, f) if note_fn else (None, "200 (response saved)", None))
            add(ts=git_date(f), service=calllog.SERVICES["health.api.nvidia.com"], model=model, endpoint=endpoint, purpose=purpose,
                status=status, latency_ms=lat, source=str(f.relative_to(ROOT)), code_path=code, note=note)

    def dd_note(b, f):
        if not isinstance(b, dict):
            return None, "saved", None
        return f"{len(b.get('ligand_positions') or [])} poses · {b.get('details') or b.get('status')}", "200 (response saved)", None

    def bz_note(b, f):
        try:
            m = b["metrics"]
            p = b["affinities"]["L"]["affinity_pic50"][0]
            return f"pred pIC50 {p:.2f}", "200 (response saved)", round(float(m.get("total_time_seconds")) * 1000, 1) if m.get("total_time_seconds") else None
        except Exception:  # noqa: BLE001
            return None, "200 (response saved)", None

    def of3_note(b, f):
        try:
            s = b["outputs"][0]["structures_with_scores"][0]
            return f"pLDDT {float(s['complex_plddt_score']):.2f} · ipTM {float(s['iptm_score']):.3f}", "200 (response saved)", None
        except Exception:  # noqa: BLE001
            return None, "200 (response saved)", None

    nimfile("dd_*--*.json", "mit/diffdock", "/v1/biology/mit/diffdock", "STEP 1 redocking (13 targets, crystal ligands)", dd_note,
            "pipeline/discovery/redock.py (collaborator)")
    nimfile("diffdock_niraparib_parp1.json", "mit/diffdock", "/v1/biology/mit/diffdock", "STEP 1 hero docking: niraparib @ PARP1 4R6E", dd_note)
    nimfile("boltz2_*--*.json", "mit/boltz2", "/v1/biology/mit/boltz2/predict", "STEP 1 affinity prediction (Boltz-2)", bz_note)
    nimfile("boltz2_parp1_niraparib.json", "mit/boltz2", "/v1/biology/mit/boltz2/predict", "STEP 1 affinity: niraparib @ PARP1", bz_note)
    nimfile("openfold3_parp1_niraparib.json", "openfold/openfold3", "/v1/biology/openfold/openfold3/predict",
            "STEP 1 complex structure: PARP1 + niraparib", of3_note)
    nimfile("parp1.a3m", "colabfold/msa-search", "/v1/biology/colabfold/msa-search/predict", "STEP 1 MSA for OpenFold3 (Uniref30_2302)",
            lambda b, f: (f"{f.read_text().count('>') - 1} homologs + query (a3m) · 63.6 s per fly_discovery/README.md", "200 (alignment saved)", 63600.0))
    nimfile("openfold2_resp.json", "openfold/openfold2", "/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template",
            "STEP 1 OpenFold2 attempt (replaced by OpenFold3)", lambda b, f: ("server CUDA error after 6 attempts", "HTTP 500", None))

    # FlyDiscovery 크리틱 평가(주장 8건)와 주제 게이트 시험(질문 6건). 모델별 합계 시간입니다
    try:
        cv = json.loads((NIM / "critic_v2.json").read_text())
        for m, v in cv.items():
            add(ts=git_date(NIM / "critic_v2.json"), service=calllog.SERVICES["integrate.api.nvidia.com"], model=m,
                endpoint="/v1/chat/completions", purpose="FlyDiscovery critic evaluation (4 overclaims + 4 valid claims)",
                status="200 (batch)", latency_ms=round(v["sec"] * 1000, 1), n_calls=v["n_over"] + v["n_valid"],
                source="fly_discovery/measurements/nim/critic_v2.json", code_path="fly_discovery (collaborator run)",
                note=f"caught {v['caught']}/{v['n_over']} overclaims · passed {v['passed']}/{v['n_valid']} valid · total time")
        tg = json.loads((NIM / "topic_gate_llm.json").read_text())
        for m, rows in tg.items():
            add(ts=git_date(NIM / "topic_gate_llm.json"), service=calllog.SERVICES["integrate.api.nvidia.com"], model=m,
                endpoint="/v1/chat/completions", purpose="FlyDiscovery topic-gate trial (off-topic question filter)",
                status=f"{sum(1 for r in rows if r.get('ok'))}/{len(rows)} correct", latency_ms=round(sum(r["ms"] for r in rows) / max(1, len(rows)), 1),
                n_calls=len(rows), source="fly_discovery/measurements/nim/topic_gate_llm.json", code_path="fly_discovery (collaborator run)",
                note="mean latency; includes timeouts")
    except Exception:  # noqa: BLE001
        pass

    # 대시보드가 보여 주는 측정 파일(web/public/data). 호출마다 요청 ID 는 저장하지 않았고 모델·지연·토큰을 남겼습니다
    pub = ROOT / "web/public/data"
    try:
        d = json.loads((pub / "demo_case_v2.json").read_text())
        for r in d["assess"]["rounds"]:
            add(ts=d.get("recorded") + " (KST)", service=calllog.SERVICES["integrate.api.nvidia.com"], model=r["model"],
                endpoint="/v1/chat/completions", purpose=f"System-2 assessment memo, round {r['round']} (recorded demo case)",
                status="200", latency_ms=r["latency_ms"], tokens=r.get("usage"), source="web/public/data/demo_case_v2.json",
                code_path="api/_fv/assess.py:assess", note="dashboard replays this recorded run")
    except Exception:  # noqa: BLE001
        pass
    try:
        g = json.loads((pub / "guard_policy_eval.json").read_text())
        models = {"a_safety_guard_8b_v3": config.MODEL_SAFETY, "b_ncs35_default": config.MODEL_SAFETY_FALLBACK,
                  "c_ncs35_pv_policy": config.MODEL_SAFETY_FALLBACK, "d_ncs35_pv_policy_think": config.MODEL_SAFETY_FALLBACK}
        for k, ms in g["latency_median_ms"].items():
            add(ts=g["generated"] + " (KST)", service=calllog.SERVICES["integrate.api.nvidia.com"], model=models.get(k, k),
                endpoint="/v1/chat/completions", purpose=f"guard evaluation: {g['guards'].get(k, k)}", status="200 (batch)",
                latency_ms=ms, n_calls=len(g.get("items") or []), source="web/public/data/guard_policy_eval.json",
                code_path="pipeline/bench/guard_policy_eval.py", note="median latency over the batch")
    except Exception:  # noqa: BLE001
        pass
    try:
        r = json.loads((pub / "literature_rerank_eval.json").read_text())
        lat = r["rerank_latency_ms"]
        add(ts=r["generated"] + " (KST)", service=calllog.SERVICES["ai.api.nvidia.com"], model=r["rerank_model"],
            endpoint="/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking", purpose="literature rerank evaluation (30 pairs, 575 papers)",
            status="200 (batch)", latency_ms=lat.get("p50"), n_calls=lat.get("n"), source="web/public/data/literature_rerank_eval.json",
            code_path="pipeline/bench/literature_rerank_eval.py", note=f"p50 {lat.get('p50')} ms · max {lat.get('max')} ms")
        for m in r.get("embed_models") or []:
            add(ts=r["generated"] + " (KST)", service=calllog.SERVICES["integrate.api.nvidia.com"], model=m, endpoint="/v1/embeddings",
                purpose="embedding baseline in the rerank evaluation", status="200 (batch)", n_calls=r.get("pairs"),
                source="web/public/data/literature_rerank_eval.json", code_path="pipeline/bench/literature_rerank_eval.py:nim_embed_many")
    except Exception:  # noqa: BLE001
        pass
    try:
        b = json.loads((pub / "bench.json").read_text())["nemotron"]
        for k in ("blind", "triage"):
            add(ts=json.loads((pub / "bench.json").read_text())["generated"] + " (KST)", service=calllog.SERVICES["integrate.api.nvidia.com"],
                model=b["model"], endpoint="/v1/chat/completions", purpose=f"benchmark: Nemotron {k} on FAERS sample",
                status=f"200 x{b[k]['n']} · errors {b['errors'][k]}", latency_ms=b[k]["latency_ms"]["p50"], n_calls=b["sample"],
                source="web/public/data/bench.json", code_path="pipeline/bench/bench.py", note="p50 latency")
    except Exception:  # noqa: BLE001
        pass
    # OpenShell 샌드박스 안에서 integrate.api.nvidia.com 에 닿는지 확인한 기록
    smoke = ROOT / "agent/evidence/openshell_smoke_2026-09-28.txt"
    if smoke.exists():
        t = smoke.read_text()
        m = re.search(r"date_utc: (\S+)", t)
        ok = re.search(r"RESULT\tPASS\tallowed NVIDIA NIM models", t)
        add(ts=m.group(1) if m else None, service=calllog.SERVICES["integrate.api.nvidia.com"], model="(models list)",
            endpoint="/v1/models", purpose="OpenShell sandbox egress check (NemoClaw policy allows NIM)", status="200" if ok else "?",
            source=str(smoke.relative_to(ROOT)), code_path="agent/openshell_smoke.sh")
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="쉼표로 구분한 단계 id (super,ultra,lightning,guard,policy,rerank,embed,diffdock,msa,of3,boltz)")
    ap.add_argument("--skip-structure", action="store_true", help="MSA-Search · OpenFold3 · Boltz-2 를 건너뜁니다")
    ap.add_argument("--no-summary", action="store_true")
    ap.add_argument("--summary-only", action="store_true", help="호출 없이 요약 JSON 의 archived 부분만 다시 만듭니다")
    a = ap.parse_args()
    if a.summary_only:
        prev = json.loads(OUT_JSON.read_text())
        prev.update(privacy="Metadata only. API keys, auth headers, prompts and response bodies are never logged. Inputs are synthetic demo values (PARP1 + niraparib, synthetic claims).",
                    steps={k: {"technology": v[0], "group": v[1], "code_path": v[2], "pages": v[3]} for k, v in STEPS.items()},
                    archived=archived())
        for r in prev["live"]:  # 코드 경로 · 화면 열은 STEPS 를 따릅니다
            r["code_path"], r["pages"] = STEPS[r["step"]][2], STEPS[r["step"]][3]
        OUT_JSON.write_text(json.dumps(prev, ensure_ascii=False, indent=1) + "\n")
        print(f"summary rebuilt: {len(prev['live'])} live rows, {len(prev['archived'])} archived")
        return
    if not config.NVIDIA_API_KEY:
        sys.exit("NVIDIA_API_KEY 가 없습니다(.env)")
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    log = pathlib.Path(os.environ.get(calllog.ENV) or ROOT / f"data/logs/nvidia_calls_{today}.jsonl")
    if not log.is_absolute():
        log = ROOT / log
    os.environ[calllog.ENV] = str(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    ctx: dict = {}
    live = []
    started = dt.datetime.now(dt.timezone.utc)
    for sid, fn in plan(a.skip_structure):
        if only and sid not in only:
            continue
        before = lines(log)
        t0 = time.perf_counter()
        try:
            outcome = await fn(ctx)
        except Exception as e:  # noqa: BLE001  실패도 기록합니다
            outcome = {"exception": type(e).__name__}
        rows = [json.loads(x) for x in log.read_text().splitlines()[before:]] if log.exists() else []
        name, group, code, pages = STEPS[sid]
        print(f"[{sid}] {name}: {len(rows)} call(s) · {round(time.perf_counter() - t0, 1)} s · {outcome}", flush=True)
        for r in rows:
            live.append({"step": sid, "technology": name, "group": group, "ts": r["ts_utc"], "service": r["service"], "model": r["model"],
                         "endpoint": r["endpoint"], "purpose": r["purpose"], "status": r["http_status"], "error": r["error"],
                         "latency_ms": r["latency_ms"], "nvcf_reqid": r["nvcf_reqid"], "tokens": r["usage"],
                         "bytes_out": r["bytes_out"], "bytes_in": r["bytes_in"], "cache_hit": r["cache_hit"],
                         "polls": r.get("polls"), "json_mode": r.get("json_mode"), "template": r.get("template"),
                         "logged_code_path": r["code_path"], "code_path": code, "pages": pages, "outcome": outcome})
    if a.no_summary:
        return
    prev = json.loads(OUT_JSON.read_text()) if OUT_JSON.exists() and only else None
    if prev:  # 일부 단계만 다시 돌렸으면 이전 기록(실패 포함)을 지우지 않고 뒤에 덧붙입니다
        live = prev.get("live", []) + live
    summary = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "run_started_utc": (prev or {}).get("run_started_utc") or started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "script": "pipeline/bench/nvidia_call_audit.py",
        "logger": "api/_fv/calllog.py (FV_CALL_LOG)",
        "reproduce": "FV_CALL_LOG=data/logs/x.jsonl .venv/bin/python pipeline/bench/nvidia_call_audit.py",
        "privacy": "Metadata only. API keys, auth headers, prompts and response bodies are never logged. Inputs are synthetic demo values (PARP1 + niraparib, synthetic claims).",
        "steps": {k: {"technology": v[0], "group": v[1], "code_path": v[2], "pages": v[3]} for k, v in STEPS.items()},
        "live": live,
        "archived": archived(),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print(f"log: {log.relative_to(ROOT) if ROOT in log.parents else log}\nsummary: {OUT_JSON.relative_to(ROOT)} "
          f"({len(live)} live rows, {len(summary['archived'])} archived)")


if __name__ == "__main__":
    asyncio.run(main())
