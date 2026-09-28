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

from . import config

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
        return {**_cache[key], "cached": True}
    if not config.NVIDIA_API_KEY:
        raise DockError("NVIDIA_API_KEY 가 없어 실시간 도킹을 할 수 없습니다")
    payload = {"protein": rec["protein"], "ligand": smiles, "ligand_file_type": "txt", "num_poses": num_poses,
               "time_divisions": 20, "steps": 18, "save_trajectory": False}
    headers = {"Authorization": f"Bearer {config.NVIDIA_API_KEY}", "Content-Type": "application/json", "NVCF-POLL-SECONDS": "100"}
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(100.0, connect=10.0)) as c:
        r = await c.post(DIFFDOCK_URL, json=payload, headers=headers)
        while r.status_code == 202 and r.headers.get("nvcf-reqid"):
            r = await c.get(f"https://health.api.nvidia.com/v1/status/{r.headers['nvcf-reqid']}", headers=headers)
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
