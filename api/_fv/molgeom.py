"""FlyDiscovery 구조 계산을 순수 파이썬으로 합니다. 서버리스 함수에 numpy·RDKit 을 싣지 않기 위해서입니다.

- PDB · mmCIF · SDF 원자 읽기
- 원소와 연결만으로 두 리간드의 원자 대응을 모두 찾아(대칭 포함) 가장 작은 중원자 RMSD 를 냅니다.
  pipeline/discovery/redock.py 의 RDKit 골격 비교(결합 차수·방향족성·전하를 지운 부분구조 대응)와 같은 기준입니다.
- Kabsch 중첩(Horn 사원수 + Jacobi 고유값 분해)과 서열 정렬(Needleman-Wunsch)로 예측 구조와 결정 구조의 CA RMSD 를 잽니다.
"""
import math
import re

AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U", "PYL": "O"}
# 공유 반지름(Å). 근접 결합 판정에 씁니다
COV = {"H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "P": 1.07, "S": 1.05, "CL": 1.02, "BR": 1.20, "I": 1.39,
       "B": 0.84, "SE": 1.20}


def _el(name: str, element: str) -> str:
    e = (element or "").strip().upper()
    if e:
        return e
    n = re.sub(r"[^A-Za-z]", "", name or "").upper()
    return n[:2] if n[:2] in ("CL", "BR", "SE") else n[:1]


# ---------------------------------------------------------------- 파일 읽기
def parse_pdb(text: str) -> list[dict]:
    """ATOM/HETATM 줄을 읽습니다. 첫 MODEL 만 씁니다. b 는 B-factor 칸이며, OpenFold3 는 여기에 pLDDT 를 적습니다."""
    atoms = []
    for ln in text.splitlines():
        if ln.startswith("ENDMDL"):
            break
        if not (ln.startswith("ATOM") or ln.startswith("HETATM")):
            continue
        try:
            x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
        except ValueError:
            continue
        alt = ln[16:17]
        if alt not in (" ", "A", ""):
            continue
        b = ln[60:66].strip()
        atoms.append({"het": ln.startswith("HETATM"), "name": ln[12:16].strip(), "resn": ln[17:20].strip(),
                      "chain": ln[21:22], "resi": int(ln[22:26]) if ln[22:26].strip().lstrip("-").isdigit() else 0,
                      "el": _el(ln[12:16], ln[76:78]), "xyz": (x, y, z), "b": float(b) if b else 0.0})
    return atoms


def parse_mmcif(text: str) -> list[dict]:
    """mmCIF 의 _atom_site 루프를 읽습니다(Boltz-2 출력). 열 이름으로 찾기 때문에 열 순서가 달라도 됩니다."""
    lines = text.splitlines()
    atoms, cols, i = [], [], 0
    while i < len(lines):
        if lines[i].strip() == "loop_" and i + 1 < len(lines) and lines[i + 1].startswith("_atom_site."):
            i += 1
            while i < len(lines) and lines[i].startswith("_atom_site."):
                cols.append(lines[i].strip().split(".", 1)[1])
                i += 1
            break
        i += 1
    if not cols:
        return atoms
    ix = {c: k for k, c in enumerate(cols)}

    def get(row, *names, default=""):
        for n in names:
            if n in ix and ix[n] < len(row):
                return row[ix[n]]
        return default
    while i < len(lines):
        ln = lines[i].strip()
        i += 1
        if not ln or ln.startswith("#") or ln.startswith("loop_") or ln.startswith("_"):
            if atoms:
                break
            continue
        row = ln.split()
        try:
            x, y, z = float(get(row, "Cartn_x")), float(get(row, "Cartn_y")), float(get(row, "Cartn_z"))
        except ValueError:
            continue
        resi = get(row, "label_seq_id", "auth_seq_id", default="0")
        b = get(row, "B_iso_or_equiv", default="0")
        atoms.append({"het": get(row, "group_PDB") == "HETATM", "name": get(row, "label_atom_id", "auth_atom_id").strip('"'),
                      "resn": get(row, "label_comp_id", "auth_comp_id"),
                      "chain": get(row, "auth_asym_id", "label_asym_id"),
                      "resi": int(resi) if resi.lstrip("-").isdigit() else 0,
                      "el": _el(get(row, "label_atom_id"), get(row, "type_symbol")), "xyz": (x, y, z),
                      "b": float(b) if re.match(r"^-?\d+(\.\d+)?$", b) else 0.0})
    return atoms


def parse_sdf(text: str) -> tuple[list[dict], list[tuple[int, int, int]]]:
    """V2000 molblock 하나를 읽습니다. 원자(el, xyz)와 결합(i, j, 차수, 0부터)을 돌려줍니다."""
    lines = text.splitlines()
    for k in range(min(len(lines), 6)):
        if "V2000" in lines[k]:
            head = k
            break
    else:
        head = 3
    counts = lines[head]
    na, nb = int(counts[0:3]), int(counts[3:6])
    atoms, bonds = [], []
    for ln in lines[head + 1: head + 1 + na]:
        atoms.append({"el": ln[31:34].strip().upper(), "xyz": (float(ln[0:10]), float(ln[10:20]), float(ln[20:30]))})
    for ln in lines[head + 1 + na: head + 1 + na + nb]:
        bonds.append((int(ln[0:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])))
    return atoms, bonds


# ---------------------------------------------------------------- 그래프
def heavy(atoms: list[dict], bonds: list[tuple] | None = None):
    """수소를 뺀 원자와, 남은 원자 사이의 결합을 새 번호로 돌려줍니다."""
    keep = [i for i, a in enumerate(atoms) if a["el"] != "H"]
    remap = {old: new for new, old in enumerate(keep)}
    hb = None
    if bonds is not None:
        hb = [(remap[i], remap[j], o) for i, j, o in bonds if i in remap and j in remap]
    return [atoms[i] for i in keep], hb


def dist2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def proximity_bonds(atoms: list[dict], tol: float = 0.45) -> list[tuple[int, int, int]]:
    """좌표만 있는 리간드(PDB HETATM)에 거리 기준으로 결합을 붙입니다. 차수는 1로 둡니다."""
    out = []
    for i in range(len(atoms)):
        ri = COV.get(atoms[i]["el"], 0.77)
        for j in range(i + 1, len(atoms)):
            lim = ri + COV.get(atoms[j]["el"], 0.77) + tol
            d = dist2(atoms[i]["xyz"], atoms[j]["xyz"])
            if 0.16 < d <= lim * lim:
                out.append((i, j, 1))
    return out


def _adj(n: int, bonds) -> list[set]:
    adj = [set() for _ in range(n)]
    for i, j, _ in bonds:
        adj[i].add(j)
        adj[j].add(i)
    return adj


def graph_matches(q_atoms, q_bonds, r_atoms, r_bonds, limit: int = 5000) -> list[list[int]]:
    """질의 그래프(q)의 원자마다 참조 그래프(r) 원자를 원소·연결이 맞게 대응시킨 목록을 모두 찾습니다(최대 limit 개).
    질의의 결합은 참조의 결합이어야 합니다(부분구조 대응). RDKit GetSubstructMatches(uniquify=False)와 같은 뜻입니다."""
    nq, nr = len(q_atoms), len(r_atoms)
    if nq == 0 or nq > nr:
        return []
    qa, ra = _adj(nq, q_bonds), _adj(nr, r_bonds)
    qel = [a["el"] for a in q_atoms]
    rel = [a["el"] for a in r_atoms]
    # 너비 우선 순서로 질의 원자를 놓아 가지치기를 일찍 합니다
    order, seen = [], set()
    for start in sorted(range(nq), key=lambda i: -len(qa[i])):
        if start in seen:
            continue
        queue = [start]
        seen.add(start)
        while queue:
            u = queue.pop(0)
            order.append(u)
            for v in sorted(qa[u], key=lambda i: -len(qa[i])):
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
    out: list[list[int]] = []
    m = [-1] * nq
    used = [False] * nr

    def ok(u, c):
        if used[c] or rel[c] != qel[u] or len(ra[c]) < len(qa[u]):
            return False
        for v in qa[u]:
            if m[v] >= 0 and m[v] not in ra[c]:
                return False
        return True

    def rec(k):
        if len(out) >= limit:
            return
        if k == nq:
            out.append(m[:])
            return
        u = order[k]
        mapped_nb = [v for v in qa[u] if m[v] >= 0]
        cands = ra[m[mapped_nb[0]]] if mapped_nb else range(nr)
        for c in cands:
            if ok(u, c):
                m[u] = c
                used[c] = True
                rec(k + 1)
                used[c] = False
                m[u] = -1
    rec(0)
    return out


def sym_rmsd(pose_xyz: list, ref_xyz: list, matches: list[list[int]]) -> float | None:
    """정렬 없이(재도킹 표준) 대응 가운데 가장 작은 RMSD."""
    if not matches:
        return None
    n = len(pose_xyz)
    best = min(sum(dist2(pose_xyz[i], ref_xyz[j]) for i, j in enumerate(mm)) for mm in matches)
    return round(math.sqrt(best / n), 3)


def ligand_rmsd(pose_atoms, pose_bonds, ref_atoms, ref_bonds=None) -> float | None:
    """포즈와 결정 리간드의 대칭 고려 중원자 RMSD. 참조 결합이 없으면 거리로 붙입니다."""
    pa, pb = heavy(pose_atoms, pose_bonds)
    ra, rb = heavy(ref_atoms, ref_bonds)
    if pb is None:
        pb = proximity_bonds(pa)
    if rb is None:
        rb = proximity_bonds(ra)
    mt = graph_matches(pa, pb, ra, rb)
    return sym_rmsd([a["xyz"] for a in pa], [a["xyz"] for a in ra], mt)


def centroid(pts) -> tuple[float, float, float]:
    n = max(1, len(pts))
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


# ---------------------------------------------------------------- 중첩
def _jacobi_max_eigvec(a: list[list[float]]) -> list[float]:
    """대칭 4x4 행렬의 가장 큰 고유값에 대한 고유벡터(Jacobi 회전)."""
    n = 4
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-18:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    i = max(range(n), key=lambda k: a[k][k])
    return [v[k][i] for k in range(n)]


def kabsch(mobile: list, target: list):
    """mobile 을 target 에 최소제곱으로 겹치는 회전 R(3x3)과 이동을 돌려줍니다. apply(p) 로 점을 옮깁니다."""
    cm, ct = centroid(mobile), centroid(target)
    s = [[0.0] * 3 for _ in range(3)]
    for p, q in zip(mobile, target):
        a = (p[0] - cm[0], p[1] - cm[1], p[2] - cm[2])
        b = (q[0] - ct[0], q[1] - ct[1], q[2] - ct[2])
        for i in range(3):
            for j in range(3):
                s[i][j] += a[i] * b[j]
    (sxx, sxy, sxz), (syx, syy, syz), (szx, szy, szz) = s
    nmat = [[sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
            [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
            [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
            [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz]]
    q0, q1, q2, q3 = _jacobi_max_eigvec(nmat)
    r = [[q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
         [2 * (q1 * q2 + q0 * q3), q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3, 2 * (q2 * q3 - q0 * q1)],
         [2 * (q1 * q3 - q0 * q2), 2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3]]

    def apply(p):
        a = (p[0] - cm[0], p[1] - cm[1], p[2] - cm[2])
        return (r[0][0] * a[0] + r[0][1] * a[1] + r[0][2] * a[2] + ct[0],
                r[1][0] * a[0] + r[1][1] * a[1] + r[1][2] * a[2] + ct[1],
                r[2][0] * a[0] + r[2][1] * a[1] + r[2][2] * a[2] + ct[2])
    return apply


def rmsd(a: list, b: list) -> float:
    return math.sqrt(sum(dist2(p, q) for p, q in zip(a, b)) / max(1, len(a)))


def align_seqs(a: str, b: str, match: int = 2, mismatch: int = -1, gap: int = -2) -> list[tuple[int, int]]:
    """전역 정렬로 같은 칸에 놓인 (a 위치, b 위치) 쌍을 돌려줍니다."""
    n, m = len(a), len(b)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * gap
    for j in range(1, m + 1):
        score[0][j] = j * gap
    for i in range(1, n + 1):
        ai, row, prev = a[i - 1], score[i], score[i - 1]
        for j in range(1, m + 1):
            d = prev[j - 1] + (match if ai == b[j - 1] else mismatch)
            u = prev[j] + gap
            left = row[j - 1] + gap
            row[j] = d if d >= u and d >= left else (u if u >= left else left)
    pairs, i, j = [], n, m
    while i > 0 and j > 0:
        s = score[i][j]
        if s == score[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif s == score[i - 1][j] + gap:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def ca_trace(atoms: list[dict], chain: str | None = None) -> list[dict]:
    """단백질 CA 를 잔기 순서대로. {resi, aa, xyz, b}."""
    out, seen = [], set()
    for a in atoms:
        if a["het"] or a["name"] != "CA" or a["resn"] not in AA3:
            continue
        if chain is not None and a["chain"] != chain:
            continue
        k = (a["chain"], a["resi"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"resi": a["resi"], "aa": AA3[a["resn"]], "xyz": a["xyz"], "b": a["b"], "chain": a["chain"]})
    return out


def superpose_ca(pred: list[dict], ref: list[dict]):
    """서열 정렬로 대응한 CA 쌍을 겹칩니다. (RMSD, 쌍 수, pred→ref 변환, ref→pred 변환, 쌍 목록)."""
    pairs = [(i, j) for i, j in align_seqs("".join(r["aa"] for r in pred), "".join(r["aa"] for r in ref))
             if pred[i]["aa"] == ref[j]["aa"]]
    if len(pairs) < 3:
        return None
    p = [pred[i]["xyz"] for i, _ in pairs]
    r = [ref[j]["xyz"] for _, j in pairs]
    to_ref = kabsch(p, r)
    to_pred = kabsch(r, p)
    return {"rmsd": round(rmsd([to_ref(x) for x in p], r), 3), "n": len(pairs), "to_ref": to_ref, "to_pred": to_pred,
            "pairs": pairs}
