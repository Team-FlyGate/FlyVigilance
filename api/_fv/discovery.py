"""FlyDiscovery 라이브 실행: NVIDIA BioNeMo NIM(MSA-Search, OpenFold3, DiffDock, Boltz-2)과 Nemotron 크리틱을 실제로 부릅니다.

요청 형식은 NVIDIA 공식 Agent Skills 를 따릅니다.
- MSA-Search → OpenFold3 : NVIDIA/skills `bionemo-msa-structure-prediction-pipeline`, BioNeMo `msa-search-nim`, `openfold3-nim`
- DiffDock : BioNeMo `diffdock-nim` (SMILES 는 ligand_file_type="txt", 수용체는 ATOM 줄만)
- Boltz-2  : BioNeMo `boltz2-nim` (predict_affinity 는 리간드 하나에만, A3M 은 msa_search.a3m{alignment, format, rank})

서버리스 함수(120초 제한) 안에서 끝내기 위해 NVCF 비동기 규약을 씁니다.
시작 요청은 짧은 NVCF-POLL-SECONDS 로 보내고, 202 가 오면 요청 ID 를 돌려줍니다. 화면은 /api/discovery/status/{id} 로 이어서 묻습니다.
결과는 입력 해시로 캐시합니다(메모리, FV_CACHE_DIR). 화면에 보낼 때는 3D 표시에 필요한 좌표만 추려 보냅니다.
"""
import asyncio
import functools
import gzip
import hashlib
import io
import json
import math
import os
import pathlib
import re
import time
import zipfile

import httpx

from . import clients, config, docking, molgeom as mg

HEALTH = "https://health.api.nvidia.com/v1"
ENDPOINTS = {
    "msa": f"{HEALTH}/biology/colabfold/msa-search/predict",
    "openfold3": f"{HEALTH}/biology/openfold/openfold3/predict",
    # DiffDock 요청 본문·응답 검사·엔드포인트는 CLI 실행기(api/_fv/docking.py)와 한 벌로 씁니다
    "diffdock": docking.ENDPOINT,
    "boltz2": f"{HEALTH}/biology/mit/boltz2/predict",
}
STATUS_URL = docking.STATUS
NIM_KINDS = tuple(ENDPOINTS)

_BNAT = "https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit/tree/main/nim-skills/"
_NVSK = "https://github.com/NVIDIA/skills/tree/main/skills/"
SKILLS = {
    "msa": [{"name": "bionemo-msa-structure-prediction-pipeline", "repo": "NVIDIA/skills", "url": _NVSK + "bionemo-msa-structure-prediction-pipeline",
             "step": "Step 1: MSA-Search (Uniref30_2302, e_value 1e-4, a3m) → a3m 정렬을 2단계로 넘깁니다"},
            {"name": "msa-search-nim", "repo": "NVIDIA-BioNeMo/bionemo-agent-toolkit", "url": _BNAT + "msa-search-nim",
             "step": "hosted standard MSA · result.alignments[db].a3m.alignment"}],
    "openfold3": [{"name": "bionemo-msa-structure-prediction-pipeline", "repo": "NVIDIA/skills", "url": _NVSK + "bionemo-msa-structure-prediction-pipeline",
                   "step": "Step 2: OpenFold3 with msa.uniref30.a3m"},
                  {"name": "openfold3-nim", "repo": "NVIDIA-BioNeMo/bionemo-agent-toolkit", "url": _BNAT + "openfold3-nim",
                   "step": "hosted predict · inputs[0].molecules[].msa · structures_with_scores"}],
    "diffdock": [{"name": "diffdock-nim", "repo": "NVIDIA-BioNeMo/bionemo-agent-toolkit", "url": _BNAT + "diffdock-nim",
                  "step": "수용체는 ATOM 줄만, SMILES 는 ligand_file_type=txt, ligand_positions·position_confidence 는 같은 순위 목록"}],
    "boltz2": [{"name": "boltz2-nim", "repo": "NVIDIA-BioNeMo/bionemo-agent-toolkit", "url": _BNAT + "boltz2-nim",
                "step": "polymers + ligands, predict_affinity 는 리간드 하나 · affinity_pic50 · affinity_probability_binary"}],
    "critic": [{"name": "pv-critic", "repo": "Team-FlyGate/Project-FlyGate", "url": "https://github.com/Team-FlyGate/Project-FlyGate/tree/main/skills/pv-critic",
                "step": "1단 근거 ID · 2단 숫자 오라클 · 3단 Nemotron 과잉해석 판정"}],
}
MODEL_CRITIC = ["nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3-ultra-550b-a55b"]

# 서열 하나를 다시 접는 데 걸리는 시간은 NIM 큐 상태에 따라 달라집니다. 시작 요청은 짧게 기다리고 나머지는 상태 조회로 넘깁니다
START_POLL = {"msa": 20, "openfold3": 20, "diffdock": 20, "boltz2": 20}
STATUS_POLL = 15
MAX_POSES = 5


@functools.lru_cache(maxsize=1)
def data() -> dict:
    """타깃 서열·수용체·결정 구조 묶음(scripts/build_discovery_data.py 가 만듭니다)."""
    with gzip.open(config.DATA / "discovery.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def measured() -> dict:
    """지난 측정(fly_discovery/measurements 의 원본 응답을 같은 함수로 가공한 값)."""
    p = config.DATA / "discovery_measured.json.gz"
    if not p.exists():
        return {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 캐시
_MEM: dict[str, dict] = {}


def _cache_dir() -> pathlib.Path | None:
    d = os.environ.get("FV_CACHE_DIR")
    if not d:
        return None
    p = pathlib.Path(d) / "discovery"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_key(kind: str, payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return f"{kind}-{hashlib.sha256(blob).hexdigest()[:20]}"


def cache_get(key: str) -> dict | None:
    if key in _MEM:
        return _MEM[key]
    d = _cache_dir()
    f = d / f"{key}.json.gz" if d else None
    if f and f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            v = json.load(fh)
        _MEM[key] = v
        return v
    return None


def cache_put(key: str, value: dict) -> None:
    if len(_MEM) > 64:
        _MEM.pop(next(iter(_MEM)))
    _MEM[key] = value
    d = _cache_dir()
    if d:
        with gzip.open(d / f"{key}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False)


# ---------------------------------------------------------------- NVCF 호출
class Pending(Exception):
    """NIM 이 아직 계산 중입니다. 요청 ID 로 이어서 묻습니다."""

    def __init__(self, req_id: str):
        super().__init__(req_id)
        self.req_id = req_id


def _headers(poll: int) -> dict:
    if not config.NVIDIA_API_KEY:
        raise clients.NotConfigured("NVIDIA_API_KEY")
    return {"Content-Type": "application/json", "Accept": "application/json",
            "Authorization": f"Bearer {config.NVIDIA_API_KEY}", "NVCF-POLL-SECONDS": str(poll)}


def _body(r: httpx.Response) -> dict:
    """응답 본문. 일부 NIM 은 결과를 zip 으로 돌려주므로 안의 JSON 을 꺼냅니다."""
    ctype = r.headers.get("content-type", "")
    if "zip" in ctype:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            name = next((n for n in z.namelist() if n.endswith(".json")), z.namelist()[0])
            return json.loads(z.read(name).decode())
    return r.json()


async def nvcf_post(kind: str, body: dict, client: httpx.AsyncClient, poll: int | None = None) -> dict:
    """NIM 에 요청을 보냅니다. 끝났으면 결과를, 계산 중이면 Pending(요청 ID)을 냅니다."""
    poll = poll if poll is not None else START_POLL.get(kind, 20)
    r = await client.post(ENDPOINTS[kind], json=body, headers=_headers(poll),
                          timeout=httpx.Timeout(poll + 25, connect=10.0))
    if r.status_code == 202:
        req_id = r.headers.get("nvcf-reqid") or r.headers.get("NVCF-REQID")
        if not req_id:
            raise RuntimeError("NIM 이 202 를 주었으나 요청 ID 가 없습니다")
        raise Pending(req_id)
    if r.status_code != 200:
        raise RuntimeError(f"{kind} HTTP {r.status_code}: {r.text[:300]}")
    return _body(r)


async def nvcf_status(req_id: str, client: httpx.AsyncClient, poll: int = STATUS_POLL) -> dict:
    r = await client.get(STATUS_URL + req_id, headers=_headers(poll),
                         timeout=httpx.Timeout(poll + 25, connect=10.0))
    if r.status_code == 202:
        raise Pending(req_id)
    if r.status_code != 200:
        raise RuntimeError(f"status HTTP {r.status_code}: {r.text[:300]}")
    return _body(r)


# ---------------------------------------------------------------- 요청 만들기 (NVIDIA 공식 스킬 규격)
def target_of(key: str) -> dict:
    t = data()["targets"].get(key)
    if not t:
        raise KeyError(f"unknown target {key}")
    return t


def ligand_of(key: str) -> dict:
    lg = data()["ligands"].get(key)
    if not lg:
        raise KeyError(f"unknown ligand {key}")
    return lg


# 공식 스킬의 예시는 Uniref30_2302 + colabfold_envdb_202108 이지만, 호스팅 게이트웨이가 envdb 를 얹으면
# 7초 만에 504 를 돌려주는 것을 2026-09-28 에 확인했습니다(요청 ID 도 상태 조회에 없습니다).
# 구조 예측에 넣는 정렬은 Uniref30 이므로 기본값은 Uniref30_2302 하나로 두고, 나머지는 선택으로 둡니다.
MSA_DATABASES = ["Uniref30_2302"]
MSA_DATABASES_FULL = ["Uniref30_2302", "colabfold_envdb_202108"]


def build_msa(target: str, databases: list[str] | None = None) -> dict:
    return {"sequence": target_of(target)["sequence"],
            "databases": list(databases or MSA_DATABASES),
            "e_value": 0.0001, "output_alignment_formats": ["a3m"]}


def build_openfold3(target: str, ligand: str | None, a3m: str | None) -> dict:
    seq = target_of(target)["sequence"]
    alignment = a3m or f">query\n{seq}"
    protein = {"type": "protein", "id": "A", "sequence": seq, "diffusion_samples": 1,
               "msa": {"uniref30": {"a3m": {"alignment": alignment, "format": "a3m"}}}}
    molecules = [protein]
    if ligand:
        molecules.append({"type": "ligand", "id": "L", "smiles": ligand_of(ligand)["smiles"]})
    return {"inputs": [{"input_id": f"{target}_{ligand or 'apo'}", "output_format": "pdb", "molecules": molecules}]}


def build_diffdock(target: str, ligand: str, num_poses: int = MAX_POSES, protein: str | None = None) -> dict:
    rec = protein if protein is not None else target_of(target)["receptor_pdb"]
    return docking.build_body(rec, ligand_of(ligand)["smiles"], "txt", num_poses)


def build_boltz2(target: str, ligand: str, a3m: str | None = None) -> dict:
    seq = target_of(target)["sequence"]
    polymer = {"id": "A", "molecule_type": "protein", "sequence": seq}
    if a3m:
        polymer["msa"] = {"msa_search": {"a3m": {"alignment": a3m, "format": "a3m", "rank": 0}}}
    return {"polymers": [polymer],
            "ligands": [{"id": "L", "smiles": ligand_of(ligand)["smiles"], "predict_affinity": True}],
            "recycling_steps": 3, "sampling_steps": 50, "diffusion_samples": 1, "step_scale": 1.638,
            "output_format": "mmcif"}


BUILD = {"msa": build_msa, "openfold3": build_openfold3, "diffdock": build_diffdock, "boltz2": build_boltz2}


def request_summary(kind: str, body: dict) -> dict:
    """화면 옆에 보여 줄 요청 요약입니다. 키는 절대 담지 않습니다."""
    if kind == "msa":
        return {"sequence_len": len(body["sequence"]), "databases": body["databases"], "e_value": body["e_value"],
                "output_alignment_formats": body["output_alignment_formats"]}
    if kind == "openfold3":
        inp = body["inputs"][0]
        mols = [{"type": m["type"], "id": m.get("id"), "len": len(m.get("sequence", "")) or None,
                 "smiles": m.get("smiles"), "msa_rows": (m.get("msa", {}).get("uniref30", {}).get("a3m", {}).get("alignment", "").count(">") or None)}
                for m in inp["molecules"]]
        return {"input_id": inp["input_id"], "output_format": inp["output_format"], "molecules": mols}
    if kind == "diffdock":
        return {"protein_atoms": body["protein"].count("\n") + 1, "ligand": body["ligand"],
                "ligand_file_type": body["ligand_file_type"], "num_poses": body["num_poses"],
                "time_divisions": body["time_divisions"], "steps": body["steps"]}
    p = body["polymers"][0]
    return {"sequence_len": len(p["sequence"]), "msa": "a3m" if "msa" in p else "none",
            "ligand": body["ligands"][0]["smiles"], "predict_affinity": True,
            "recycling_steps": body["recycling_steps"], "sampling_steps": body["sampling_steps"],
            "diffusion_samples": body["diffusion_samples"], "output_format": body["output_format"]}


# ---------------------------------------------------------------- 응답 가공
def _r(v, n=2):
    return None if v is None else round(float(v), n)


def _xyz(p, n=2):
    return [round(p[0], n), round(p[1], n), round(p[2], n)]


def parse_a3m(a3m: str) -> list[tuple[str, str]]:
    out, name, buf = [], None, []
    for line in a3m.splitlines():
        if line.startswith(">"):
            if name is not None:
                out.append((name, "".join(buf)))
            name, buf = line[1:].strip(), []
        elif line.strip():
            buf.append(line.strip())
    if name is not None:
        out.append((name, "".join(buf)))
    return out


def process_msa(resp: dict, req: dict) -> dict:
    """정렬 깊이, 열별 보존도, 표시용 행을 냅니다. 화면의 정렬 애니메이션이 이 값을 씁니다."""
    aligns = resp.get("alignments") or {}
    db = "Uniref30_2302" if "Uniref30_2302" in aligns else (next(iter(aligns)) if aligns else None)
    a3m = (aligns.get(db, {}).get("a3m", {}) or {}).get("alignment", "") if db else ""
    recs = parse_a3m(a3m)
    if not recs:
        raise RuntimeError("MSA 응답에 정렬이 없습니다")
    # a3m 의 소문자는 질의에 없는 삽입이므로 지워서 열을 질의 잔기에 맞춥니다
    rows = [(n, re.sub("[a-z]", "", s)) for n, s in recs]
    qname, query = rows[0]
    L = len(query)
    rows = [(n, s) for n, s in rows if len(s) == L]
    depth = [0] * L
    same = [0] * L
    for _, s in rows[1:]:
        for i, ch in enumerate(s):
            if ch not in "-.":
                depth[i] += 1
                if ch == query[i]:
                    same[i] += 1
    n_hom = len(rows) - 1
    cons = [round(same[i] / depth[i], 3) if depth[i] else 0.0 for i in range(L)]

    def ident(s):
        m = sum(1 for a, b in zip(s, query) if a == b and a not in "-.")
        return round(m / L, 3)
    shown = sorted(rows[1:], key=lambda r: -ident(r[1]))[:60]
    return {"database": db, "homologs": n_hom, "sequences": len(rows), "query_len": L, "query": query, "query_name": qname,
            "depth": depth, "conservation": cons, "mean_depth": round(sum(depth) / max(1, L), 1),
            "coverage": round(sum(1 for d in depth if d > 0) / max(1, L), 3),
            "rows": [{"name": n[:48], "seq": s, "identity": ident(s)} for n, s in shown],
            "databases_returned": sorted(aligns), "a3m_chars": len(a3m), "target": req.get("target")}


def process_openfold3(resp: dict, req: dict) -> dict:
    """구조를 결정 구조에 겹쳐 CA RMSD 를 재고, pLDDT 와 좌표를 화면 크기로 줄입니다."""
    out = (resp.get("outputs") or [{}])[0]
    samples = out.get("structures_with_scores") or []
    if not samples:
        raise RuntimeError("OpenFold3 응답에 구조가 없습니다")
    s = samples[0]
    atoms = mg.parse_pdb(s["structure"])
    pred = mg.ca_trace(atoms)
    lig = [a for a in atoms if a["het"]]
    t = target_of(req["target"])
    ref = [{"resi": r[0], "aa": r[1], "xyz": (r[2], r[3], r[4]), "b": 0.0, "chain": t["chain"]} for r in t["xtal_ca"]]
    fit = mg.superpose_ca(pred, ref) if ref else None
    ca_rmsd = fit["rmsd"] if fit else None
    to_ref = fit["to_ref"] if fit else (lambda p: p)
    lig_rmsd = None
    if lig and t.get("xtal_ligand") and t.get("xtal_drug") == req.get("ligand") and fit:
        moved = [{"el": a["el"], "xyz": to_ref(a["xyz"])} for a in lig]
        xl = t["xtal_ligand"]
        ref_lig = [{"el": a[0], "xyz": (a[1], a[2], a[3])} for a in xl["atoms"]]
        lig_rmsd = mg.ligand_rmsd(moved, None, ref_lig, [(i, j, 1) for i, j in xl["bonds"]])
    plddt = [round(r["b"], 1) for r in pred]
    lig_heavy, _ = mg.heavy(lig)
    return {"target": req.get("target"), "ligand": req.get("ligand"), "msa_source": req.get("msa_source"),
            "scores": {"confidence": _r(s.get("confidence_score"), 4), "plddt": _r(s.get("complex_plddt_score"), 2),
                       "ptm": _r(s.get("ptm_score"), 4), "iptm": _r(s.get("iptm_score"), 4),
                       "pde": _r(s.get("complex_pde_score"), 4)},
            "ca_rmsd": ca_rmsd, "n_ca": fit["n"] if fit else 0, "ligand_rmsd": lig_rmsd,
            "n_residues": len(pred), "plddt_per_residue": plddt,
            "mean_plddt": round(sum(plddt) / max(1, len(plddt)), 2),
            "ca": [_xyz(to_ref(r["xyz"])) for r in pred],
            "xtal_ca": [_xyz((r[2], r[3], r[4])) for r in t["xtal_ca"]],
            "ligand_atoms": [[a["el"], *_xyz(to_ref(a["xyz"]))] for a in lig_heavy],
            "ligand_bonds": [[i, j] for i, j, _ in mg.proximity_bonds(lig_heavy)],
            "xtal_ligand": {"atoms": t["xtal_ligand"]["atoms"], "bonds": t["xtal_ligand"]["bonds"]} if t.get("xtal_ligand") else None,
            "input_id": out.get("input_id"), "structure_format": s.get("format")}


def process_diffdock(resp: dict, req: dict) -> dict:
    """포즈마다 결정 리간드와의 대칭 고려 중원자 RMSD(정렬 없음)와 주머니 중심 거리를 냅니다."""
    try:  # 응답 형태 검사는 CLI 실행기와 같은 함수를 씁니다(api/_fv/docking.py)
        poses_sdf, conf = docking.validate_result(resp)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"DiffDock 응답을 쓸 수 없습니다: {e}") from None
    t = target_of(req["target"])
    xl = t.get("xtal_ligand")
    ref = [{"el": a[0], "xyz": (a[1], a[2], a[3])} for a in xl["atoms"]] if xl else []
    ref_bonds = [(i, j, 1) for i, j in xl["bonds"]] if xl else []
    ref_c = mg.centroid([a["xyz"] for a in ref]) if ref else None
    is_redock = t.get("xtal_drug") == req.get("ligand")
    poses = []
    for i, sdf in enumerate(poses_sdf[:MAX_POSES]):
        atoms, bonds = mg.parse_sdf(sdf)
        heavy, hb = mg.heavy(atoms, bonds)
        c = mg.centroid([a["xyz"] for a in heavy])
        rms = mg.ligand_rmsd(atoms, bonds, ref, ref_bonds) if (ref and is_redock) else None
        poses.append({"rank": i + 1, "confidence": _r(conf[i], 3) if i < len(conf) else None,
                      "rmsd": rms, "pocket_dist": _r(math.sqrt(mg.dist2(c, ref_c)), 2) if ref_c else None,
                      "atoms": [[a["el"], *_xyz(a["xyz"])] for a in heavy],
                      "bonds": [[i2, j2] for i2, j2, _ in hb], "centroid": _xyz(c)})
    rms = [p["rmsd"] for p in poses if p["rmsd"] is not None]
    return {"target": req.get("target"), "ligand": req.get("ligand"), "receptor_source": req.get("receptor_source"),
            "redock": is_redock, "n_poses": len(poses_sdf), "poses": poses,
            "top1_confidence": poses[0]["confidence"], "top1_rmsd": poses[0]["rmsd"],
            "best_rmsd": min(rms) if rms else None,
            "top1_success": bool(poses[0]["rmsd"] is not None and poses[0]["rmsd"] <= 2.0),
            "criterion": "top-1 중원자 RMSD ≤ 2.0 Å (대칭 고려, 정렬 없음)",
            "status": resp.get("status"), "xtal_ligand": {"atoms": xl["atoms"], "bonds": xl["bonds"]} if xl else None}


def process_boltz2(resp: dict, req: dict) -> dict:
    """친화도 예측과 복합체 구조를 냅니다. pIC50 은 예측값이며 측정값이 아닙니다."""
    st = (resp.get("structures") or [{}])[0]
    text = st.get("structure", "")
    atoms = mg.parse_mmcif(text) if text else []
    ca = mg.ca_trace(atoms)
    lig = [a for a in atoms if a["het"]]
    lig_heavy, _ = mg.heavy(lig)
    aff = (resp.get("affinities") or {}).get("L") or {}

    def first(name):
        v = aff.get(name)
        return _r(v[0], 4) if isinstance(v, list) and v else _r(v, 4)
    plddt = [round(r["b"], 1) for r in ca]
    return {"target": req.get("target"), "ligand": req.get("ligand"), "msa_source": req.get("msa_source"),
            "affinity": {"pic50": first("affinity_pic50"), "pred_value": first("affinity_pred_value"),
                         "probability_binary": first("affinity_probability_binary")},
            "scores": {"confidence": _r((resp.get("confidence_scores") or [None])[0], 4),
                       "plddt": _r((resp.get("complex_plddt_scores") or [None])[0], 4),
                       "iptm": _r((resp.get("iptm_scores") or [None])[0], 4),
                       "ptm": _r((resp.get("ptm_scores") or [None])[0], 4),
                       "pde": _r((resp.get("complex_pde_scores") or [None])[0], 4)},
            "n_residues": len(ca), "ca": [_xyz(r["xyz"]) for r in ca], "plddt_per_residue": plddt,
            "ligand_atoms": [[a["el"], *_xyz(a["xyz"])] for a in lig_heavy],
            "ligand_bonds": [[i, j] for i, j, _ in mg.proximity_bonds(lig_heavy)],
            "metrics": {k: _r(v, 2) for k, v in (resp.get("metrics") or {}).items()},
            "chembl": _chembl_for(req.get("target"), req.get("ligand")), "structure_format": st.get("format")}


def _chembl_for(target: str | None, ligand: str | None):
    """같은 분자의 ChEMBL 실측 중앙값입니다(예측과 대조하기 위한 값, 측정치입니다)."""
    p = data()["pairs"].get(f"{target}--{ligand}") or {}
    if p.get("chembl_median") is None:
        return None
    return {"median_pchembl": p["chembl_median"], "n": p.get("chembl_n"), "source": "ChEMBL"}


PROCESS = {"msa": process_msa, "openfold3": process_openfold3, "diffdock": process_diffdock, "boltz2": process_boltz2}


def scene(target: str) -> dict:
    """3D 화면 배경(결정 구조 CA 골격과 결합 주머니 중원자)입니다. 실행마다 다시 보내지 않도록 따로 냅니다."""
    t = target_of(target)
    xl = t.get("xtal_ligand") or {"atoms": [], "bonds": []}
    ref_c = mg.centroid([(a[1], a[2], a[3]) for a in xl["atoms"]]) if xl["atoms"] else None
    rec = mg.parse_pdb(t["receptor_pdb"])
    ca = [a for a in rec if a["name"] == "CA" and not a["het"]]
    pocket = []
    if ref_c:
        near = [a for a in rec if a["el"] != "H" and mg.dist2(a["xyz"], ref_c) <= 13.0 ** 2]
        pocket = [[a["el"], *_xyz(a["xyz"])] for a in near[:1200]]
    return {"target": target, "label": t["label"], "pdb": t["pdb"], "chain": t["chain"], "organism": t["organism"],
            "desc": t["desc"], "xtal_drug": t.get("xtal_drug"), "xtal_ligand": xl,
            "ca": [_xyz(a["xyz"]) for a in ca], "pocket": pocket, "pocket_center": _xyz(ref_c) if ref_c else None,
            "sequence_len": len(t["sequence"]) if t.get("sequence") else None}


def catalog() -> dict:
    """화면이 고를 수 있는 타깃·리간드·쌍 목록입니다."""
    d = data()
    return {"targets": {k: {kk: v[kk] for kk in ("label", "gene", "pdb", "chain", "organism", "desc", "kind", "xtal_drug")}
                        | {"sequence_len": len(v["sequence"]) if v.get("sequence") else None} for k, v in d["targets"].items()},
            "ligands": d["ligands"], "pairs": {k: {kk: v.get(kk) for kk in ("target", "ligand", "role", "redock", "vina",
                                                                            "chembl_median", "chembl_n")}
                                               for k, v in d["pairs"].items()},
            "benchmark": d["benchmark"], "measured": {
                "msa": d["msa_measured"], "openfold3": d["openfold3_measured"], "openfold2_failed": d["openfold2_failed"],
                "critic": d["critic_measured"], "critic_lightning": d["critic_lightning"]},
            "skills": SKILLS, "endpoints": ENDPOINTS, "source": d["source"]}


# ---------------------------------------------------------------- 실행
def measured_for(kind: str, params: dict) -> dict | None:
    m = measured().get(kind) or {}
    if kind == "msa":
        return m.get(params.get("target"))
    return m.get(f"{params.get('target')}--{params.get('ligand')}")


def _a3m_store(a3m: str) -> str:
    key = "a3m-" + hashlib.sha256(a3m.encode()).hexdigest()[:20]
    cache_put(key, {"a3m": a3m})
    return key


def resolve_a3m(params: dict) -> str | None:
    """단계를 이을 때 앞 단계의 정렬을 찾습니다. 본문에 실려 오면 그대로, 열쇠만 오면 캐시에서, 둘 다 없으면 없음(단일 서열)입니다."""
    if params.get("a3m"):
        return params["a3m"]
    key = params.get("a3m_key")
    if key:
        v = cache_get(key)
        if v:
            return v["a3m"]
    if params.get("a3m_measured") and params.get("target") == "parp1":
        return data()["a3m_measured"]
    return None


def build_for(kind: str, params: dict) -> dict:
    t = params.get("target", "parp1")
    if kind == "msa":
        return build_msa(t, params.get("databases"))
    if kind == "openfold3":
        return build_openfold3(t, params.get("ligand"), resolve_a3m(params))
    if kind == "diffdock":
        return build_diffdock(t, params["ligand"], int(params.get("num_poses", MAX_POSES)))
    return build_boltz2(t, params["ligand"], resolve_a3m(params))


def _envelope(kind: str, params: dict, body: dict) -> dict:
    return {"kind": kind, "endpoint": ENDPOINTS[kind], "skills": SKILLS[kind], "params": params,
            "request": request_summary(kind, body), "measured": measured_for(kind, params)}


def _finish(kind: str, params: dict, resp: dict, env: dict, t0: float, source: str) -> dict:
    res = PROCESS[kind](resp, {**params, "msa_source": "a3m" if resolve_a3m(params) else "single-sequence",
                               "receptor_source": "crystal"})
    if kind == "msa":
        a3m = (resp.get("alignments", {}).get(res["database"], {}).get("a3m", {}) or {}).get("alignment", "")
        res["a3m_key"] = _a3m_store(a3m)
        res["a3m"] = a3m if len(a3m) <= 900_000 else None
    return {**env, "state": "done", "source": source, "elapsed_s": round(time.monotonic() - t0, 1), "result": res}


def _fallback(kind: str, params: dict, env: dict, t0: float, err: str) -> dict:
    m = env.get("measured")
    if not m:
        raise RuntimeError(err)
    return {**env, "state": "done", "source": "measured", "elapsed_s": round(time.monotonic() - t0, 1),
            "result": m, "error": err[:300],
            "note": "라이브 호출이 끝나지 않아 지난 측정 응답을 보여 드립니다(fly_discovery/measurements 의 원본)."}


# 게이트웨이가 502·503·504 를 내면 예측 계열은 한 번만 다시 보냅니다. 같은 입력을 다시 접는 것이라 부작용이 없습니다.
# DiffDock 은 다시 보내지 않습니다(api/_fv/docking.py 의 약속: 시간 초과가 이미 접수된 작업을 뜻할 수 있습니다).
RETRY_KINDS = ("msa", "openfold3", "boltz2")


async def _post_with_retry(kind: str, body: dict, client: httpx.AsyncClient) -> dict:
    try:
        return await nvcf_post(kind, body, client)
    except (Pending, clients.NotConfigured):
        raise
    except RuntimeError as e:
        transient = any(f"HTTP {c}" in str(e) for c in (429, 500, 502, 503, 504))
        if kind not in RETRY_KINDS or not transient:
            raise
    await asyncio.sleep(2.0)
    return await nvcf_post(kind, body, client)


async def run(kind: str, params: dict, client: httpx.AsyncClient | None = None) -> dict:
    """한 NIM 을 실제로 부릅니다. 끝나면 결과를, 계산 중이면 요청 ID 를, 실패하면 지난 측정을 돌려줍니다."""
    if kind not in NIM_KINDS:
        raise KeyError(kind)
    t0 = time.monotonic()
    body = build_for(kind, params)
    env = _envelope(kind, params, body)
    ckey = cache_key(kind, body)
    hit = cache_get(ckey)
    if hit is not None and not params.get("no_cache"):
        return {**env, "state": "done", "source": "cache", "elapsed_s": 0.0, "result": hit}
    own = client is None
    client = client or httpx.AsyncClient()
    try:
        resp = await _post_with_retry(kind, body, client)
    except Pending as p:
        _MEM["req-" + p.req_id] = {"kind": kind, "params": params, "cache_key": ckey, "started": time.time()}
        return {**env, "state": "pending", "req_id": p.req_id, "elapsed_s": round(time.monotonic() - t0, 1),
                "poll_url": f"/api/discovery/status/{p.req_id}"}
    except clients.NotConfigured:
        raise
    except Exception as e:  # noqa: BLE001  장애는 숨기지 않고 사유와 함께 지난 측정으로 내립니다
        return _fallback(kind, params, env, t0, f"{type(e).__name__}: {e}")
    finally:
        if own:
            await client.aclose()
    out = _finish(kind, params, resp, env, t0, "live")
    cache_put(ckey, out["result"])
    return out


async def poll(req_id: str, kind: str | None = None, params: dict | None = None) -> dict:
    """계산 중인 요청을 이어서 묻습니다. kind·params 를 주지 않으면 이 인스턴스가 기억한 값을 씁니다."""
    saved = _MEM.get("req-" + req_id) or {}
    kind = kind or saved.get("kind")
    params = params if params is not None else saved.get("params", {})
    if not kind:
        raise KeyError("kind unknown for this request id")
    t0 = time.monotonic()
    env = _envelope(kind, params, build_for(kind, params))
    async with httpx.AsyncClient() as client:
        try:
            resp = await nvcf_status(req_id, client)
        except Pending:
            return {**env, "state": "pending", "req_id": req_id, "elapsed_s": round(time.monotonic() - t0, 1),
                    "poll_url": f"/api/discovery/status/{req_id}",
                    "waited_s": round(time.time() - saved["started"], 1) if saved.get("started") else None}
        except Exception as e:  # noqa: BLE001
            return _fallback(kind, params, env, t0, f"{type(e).__name__}: {e}")
    out = _finish(kind, params, resp, env, t0, "live")
    if saved.get("cache_key"):
        cache_put(saved["cache_key"], out["result"])
    if saved.get("started"):
        out["elapsed_s"] = round(time.time() - saved["started"], 1)
    return out


# ---------------------------------------------------------------- 크리틱 3단
DISCOVERY_RULES = [
    ("D1", "Docking scores from different proteins are not comparable; do not infer selectivity from them."),
    ("D2", "DiffDock confidence is a pose-ranking score, not binding strength or affinity."),
    ("D3", "A Boltz-2 pIC50 is a prediction, never a measured affinity."),
    ("D4", "Do not compute or quote a correlation over fewer than eight paired points."),
    ("D5", "Redocking a co-crystal ligand is a setup control, not a prospective prediction."),
    ("D6", "An exploratory cross-docking pose is not evidence that the molecule binds that target."),
    ("D7", "A result from a non-human protein (COX-2 3LN1 is mouse) does not transfer to humans."),
    ("D8", "pLDDT and structure confidence say nothing about binding strength."),
    ("D9", "A public crystal structure may be in the model's training data; do not present it as blind prediction."),
]
RULES_KO = {
    "D1": "다른 단백질의 도킹 점수는 교차 비교하지 않습니다(선택성은 측정 친화도로만 말합니다).",
    "D2": "DiffDock 신뢰도는 포즈 순위 점수이며 결합 세기가 아닙니다.",
    "D3": "Boltz-2 pIC50 은 예측값이며 측정값이 아닙니다.",
    "D4": "쌍이 8개 미만이면 상관계수를 내지 않습니다.",
    "D5": "공결정 재도킹은 설정 대조이며 전향적 예측이 아닙니다.",
    "D6": "탐색적 교차 도킹 포즈는 결합 근거가 아닙니다.",
    "D7": "사람이 아닌 단백질(COX-2 3LN1 은 쥐)의 결과를 사람으로 옮기지 않습니다.",
    "D8": "pLDDT 와 구조 신뢰도는 결합 세기를 말하지 않습니다.",
    "D9": "공개 결정 구조는 학습 데이터에 있었을 수 있으므로 맹검 예측으로 제시하지 않습니다.",
}
CRITIC_SYSTEM = """You are the inhibitory critic of a pre-market drug discovery workbench (FlyDiscovery).
Judge whether each claim stays inside what the measurements can support. The numbers themselves were already
verified against the raw NIM responses by a separate numeric oracle, so judge the INTERPRETATION only.
Interpretation limits:
""" + "\n".join(f"{k}: {v}" for k, v in DISCOVERY_RULES) + """
Return ONLY JSON: {"verdicts":[{"id":"c1","verdict":"PASS"|"REJECT","rule":"D1".."D9"|"none","why":"<=25 words"}]}
Judge every claim. REJECT only when a listed limit is actually violated."""


def bundle_from_runs(runs: dict) -> dict:
    """라이브 결과에서 인용 가능한 근거 ID 와 숫자를 뽑습니다. 좌표는 넣지 않습니다(숫자 오라클이 무의미해지기 때문입니다)."""
    catalog_rows, nums = [], []
    d = data()

    def add(eid, what, values):
        catalog_rows.append({"id": eid, "what": what})
        nums.extend([v for v in values if isinstance(v, (int, float))])
    for kind, r in (runs or {}).items():
        if not isinstance(r, dict):
            continue
        tgt, lig = r.get("target"), r.get("ligand")
        if kind == "msa" and r.get("homologs") is not None:
            add(f"msa:{tgt}", f"MSA-Search {r.get('database')} 상동 서열 {r['homologs']}개, 질의 {r.get('query_len')}잔기",
                [r["homologs"], r.get("query_len"), r.get("mean_depth")])
        elif kind == "openfold3" and r.get("scores"):
            s = r["scores"]
            add(f"openfold3:{tgt}/{lig}", f"OpenFold3 pLDDT {s.get('plddt')}, pTM {s.get('ptm')}, ipTM {s.get('iptm')}, "
                                          f"결정 구조 대비 CA RMSD {r.get('ca_rmsd')} Å (CA {r.get('n_ca')}개), 리간드 {r.get('ligand_rmsd')} Å",
                [s.get("plddt"), s.get("ptm"), s.get("iptm"), r.get("ca_rmsd"), r.get("n_ca"), r.get("ligand_rmsd")])
        elif kind == "diffdock" and r.get("poses"):
            p = r["poses"][0]
            add(f"diffdock:{tgt}/{lig}", f"DiffDock 1순위 신뢰도 {p.get('confidence')}, 결정 포즈 대비 RMSD {p.get('rmsd')} Å, "
                                          f"주머니 중심 거리 {p.get('pocket_dist')} Å, 포즈 {len(r['poses'])}개",
                [p.get("confidence"), p.get("rmsd"), p.get("pocket_dist"), r.get("best_rmsd")] +
                [q.get("confidence") for q in r["poses"]] + [q.get("rmsd") for q in r["poses"]])
        elif kind == "boltz2" and r.get("affinity"):
            a, s = r["affinity"], r.get("scores", {})
            add(f"boltz2:{tgt}/{lig}", f"Boltz-2 예측 pIC50 {a.get('pic50')}, 결합 확률 {a.get('probability_binary')}, "
                                        f"ipTM {s.get('iptm')}, pLDDT {s.get('plddt')}",
                [a.get("pic50"), a.get("probability_binary"), s.get("iptm"), s.get("plddt")])
            ch = r.get("chembl")
            if ch:
                add(f"chembl:{lig}/{tgt}", f"ChEMBL 실측 pChEMBL 중앙값 {ch['median_pchembl']} (활성 {ch['n']}건)",
                    [ch["median_pchembl"], ch["n"]])
    b = d["benchmark"]
    add("boltz2:parp1/chembl-benchmark-39", f"Boltz-2 친화도 벤치마크 n={b['n']}, Spearman {b['spearman']}, MAE {b['mae']} log",
        [b["n"], b["spearman"], b["pearson"], b["mae"], b["ef_top25"], b["sens"], b["spec"]])
    for row in d["vina_table"]:
        k, vina, dd_conf, pic50, p_bind, chembl, n = row
        lig, tgt = k.split("@")
        add(f"vina:{tgt}/{lig}", f"{k} Vina {vina} kcal/mol (지난 측정)", [vina, dd_conf, pic50, p_bind, chembl, n])
    return {"catalog": catalog_rows, "ids": [c["id"] for c in catalog_rows], "numbers": nums}


def default_claims(runs: dict) -> list[dict]:
    """화면에 미리 채워 두는 주장입니다. 정상 주장과 과잉해석을 섞어 크리틱이 실제로 거르는지 보입니다."""
    d = data()
    vina = {r[0]: r for r in d["vina_table"]}
    dd = (runs or {}).get("diffdock") or {}
    of3 = (runs or {}).get("openfold3") or {}
    bz = (runs or {}).get("boltz2") or {}
    msa = (runs or {}).get("msa") or {}
    tgt = dd.get("target") or of3.get("target") or bz.get("target") or "parp1"
    lig = dd.get("ligand") or bz.get("ligand") or "niraparib"
    out = []
    if msa.get("homologs") is not None:
        out.append({"id": "c1", "text": f"MSA-Search 가 {msa['database']} 에서 상동 서열 {msa['homologs']}개를 찾아 OpenFold3 입력으로 썼습니다.",
                    "evidence": [f"msa:{tgt}"], "kind": "valid"})
    if of3.get("ca_rmsd") is not None:
        out.append({"id": f"c{len(out) + 1}", "text": f"OpenFold3 예측 구조는 결정 구조 대비 CA RMSD {of3['ca_rmsd']} Å 로 맞았고 pLDDT 는 {of3['scores']['plddt']} 입니다.",
                    "evidence": [f"openfold3:{tgt}/{of3.get('ligand')}"], "kind": "valid"})
        out.append({"id": f"c{len(out) + 1}", "text": f"pLDDT {of3['scores']['plddt']} 이므로 이 리간드는 강하게 결합합니다.",
                    "evidence": [f"openfold3:{tgt}/{of3.get('ligand')}"], "kind": "overclaim", "expect": "D8"})
    if dd.get("top1_rmsd") is not None:
        out.append({"id": f"c{len(out) + 1}", "text": f"DiffDock 이 공결정 리간드를 RMSD {dd['top1_rmsd']} Å 로 재현해 도킹 설정이 작동함을 확인했습니다.",
                    "evidence": [f"diffdock:{tgt}/{lig}"], "kind": "valid"})
    if dd.get("top1_confidence") is not None:
        out.append({"id": f"c{len(out) + 1}", "text": f"DiffDock 신뢰도 {dd['top1_confidence']} 이므로 이 화합물의 친화도가 더 높습니다.",
                    "evidence": [f"diffdock:{tgt}/{lig}"], "kind": "overclaim", "expect": "D2"})
    if bz.get("affinity", {}).get("pic50") is not None:
        p = bz["affinity"]["pic50"]
        ch = bz.get("chembl")
        if ch:
            out.append({"id": f"c{len(out) + 1}", "text": f"Boltz-2 는 pIC50 {p} 를 예측했고 ChEMBL 실측 중앙값은 {ch['median_pchembl']} 입니다.",
                        "evidence": [f"boltz2:{tgt}/{lig}", f"chembl:{lig}/{tgt}"], "kind": "valid"})
        out.append({"id": f"c{len(out) + 1}", "text": f"Boltz-2 예측 pIC50 {p} 는 이 화합물의 측정된 친화도입니다.",
                    "evidence": [f"boltz2:{tgt}/{lig}"], "kind": "overclaim", "expect": "D3"})
    a, b = vina.get("niraparib@parp1"), vina.get("niraparib@xa")
    if a and b:
        out.append({"id": f"c{len(out) + 1}", "text": f"니라파립은 PARP1 {a[1]}, Factor Xa {b[1]} 이므로 PARP1 에 선택적입니다.",
                    "evidence": ["vina:parp1/niraparib", "vina:xa/niraparib"], "kind": "overclaim", "expect": "D1"})
    return out or [{"id": "c1", "text": "아직 실행 결과가 없습니다.", "evidence": [], "kind": "valid"}]


ENTITY_NUMBERS = re.compile(
    r"(?i)(boltz-?2|openfold-?[23]|alphafold-?\d|nemotron[\w.-]*|msa-search|diffdock|colabfold_envdb_\d+|uniref30_\d+|"
    r"parp-?1|cox-?2|factor\s*xa|jak-?2|pd-?l?1|p?ic50|ec50|kd|ki|(?<![\d.])\b[1-9][a-z][a-z0-9]{2}\b(?![\d.])|"
    r"chembl\d*|step\s*\d|\d+\s*단|3단)")


def strip_entity_numbers(text: str) -> str:
    """모델·타깃·구조 이름 안의 숫자를 지웁니다. 숫자 오라클이 이름을 측정값으로 오해하지 않게 하기 위해서입니다."""
    return ENTITY_NUMBERS.sub(" ", text)


async def tier3_nemotron(claims: list[dict], bundle: dict, deadline: float | None = None) -> dict:
    lines = "\n".join(f"{c['id']}: {c['text']}" for c in claims)
    ev = "\n".join(f"- {c['id']} :: {c['what']}" for c in bundle["catalog"])
    out = await clients.nim_chat(
        [{"role": "system", "content": CRITIC_SYSTEM},
         {"role": "user", "content": f"EVIDENCE (measured):\n{ev}\n\nCLAIMS:\n{lines}"}],
        MODEL_CRITIC, max_tokens=900, temperature=0.0, json_mode=True, deadline=deadline)
    try:
        parsed = clients.parse_json_block(out["content"])
    except Exception as e:  # noqa: BLE001
        return {"verdicts": [], "model": out["model"], "latency_ms": out["latency_ms"], "error": str(e)[:120]}
    return {"verdicts": parsed.get("verdicts", []), "model": out["model"], "latency_ms": out["latency_ms"],
            "usage": out.get("usage", {}), "fallbacks": out.get("fallbacks", [])}


async def critic(claims: list[dict], runs: dict, budget_s: float = 70.0) -> dict:
    """1단 근거 ID · 2단 숫자 오라클 · 3단 Nemotron 과잉해석 판정을 차례로 돌립니다."""
    from . import assess as assess_mod
    t0 = time.monotonic()
    bundle = bundle_from_runs(runs)
    ids = set(bundle["ids"])
    t1 = assess_mod.tier1_rules(claims, ids)
    # 이름에 든 숫자(Boltz-2, PARP1, 4R6E, pIC50 …)는 측정값이 아니므로 숫자 오라클에서 뺍니다
    t2 = assess_mod.tier2_oracle([{**c, "text": strip_entity_numbers(c.get("text", ""))} for c in claims],
                                 bundle["numbers"])
    try:
        judge = await tier3_nemotron(claims, bundle, deadline=time.monotonic() + budget_s)
    except Exception as e:  # noqa: BLE001
        judge = {"verdicts": [], "error": f"{type(e).__name__}: {e}"[:160], "model": None}
    by_id = {v.get("id"): v for v in judge.get("verdicts", []) if isinstance(v, dict)}
    t3 = []
    for c in claims:
        v = by_id.get(c["id"]) or {}
        rule = str(v.get("rule") or "none")
        c["verdict"] = str(v.get("verdict") or ("PASS" if not v else "PASS")).upper()
        c["why"] = v.get("why")
        c["rule"] = rule if rule != "none" else None
        if c["verdict"] == "REJECT":
            t3.append({"claim": c["id"], "tier": 3, "rule": rule, "detail": v.get("why") or dict(DISCOVERY_RULES).get(rule, ""),
                       "detail_ko": RULES_KO.get(rule)})
    issues = t1 + t2 + t3
    caught = sum(1 for c in claims if c.get("kind") == "overclaim" and c.get("verdict") == "REJECT")
    n_over = sum(1 for c in claims if c.get("kind") == "overclaim")
    passed = sum(1 for c in claims if c.get("kind") == "valid" and c.get("verdict") != "REJECT")
    n_valid = sum(1 for c in claims if c.get("kind") == "valid")
    return {"verdict": "pass" if not issues else "returned", "claims": claims, "issues": issues,
            "tiers": {"tier1": t1, "tier2": t2, "tier3": t3}, "judge": {k: v for k, v in judge.items() if k != "verdicts"},
            "bundle": {"catalog": bundle["catalog"], "ids": bundle["ids"]},
            "score": {"caught": caught, "n_over": n_over, "passed": passed, "n_valid": n_valid},
            "rules": [{"id": k, "text": v, "ko": RULES_KO.get(k)} for k, v in DISCOVERY_RULES],
            "measured": data()["critic_measured"], "measured_lightning": data()["critic_lightning"],
            "skills": SKILLS["critic"], "endpoint": f"{config.NIM_URL}/chat/completions",
            "total_ms": round((time.monotonic() - t0) * 1000, 1)}
