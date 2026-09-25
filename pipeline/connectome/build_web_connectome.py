"""선택한 MaleCNS 부분그래프를 브라우저 실시간 시뮬레이션용 바이너리로 만든다.

뉴런 위치: SWC 스켈레톤 노드 중심(8nm 복셀 -> um). 없으면 세포체, 그것도 없으면 연결 상대 평균.
점구름: 뉴런마다 스켈레톤 노드를 표본추출해 실제 신경망 모양을 그린다.
연결: post 뉴런 기준 입력 합으로 정규화한 부호 있는 가중치 (CSR, post 기준).

산출물 (web/public/data/connectome/)
  meta.json        : 뉴런 수, 층 정의, 채널 정의, 대표 뉴런, 경계상자
  neurons.bin      : Float32 x,y,z (n*3)  +  Uint8 layer (n)  +  Uint8 channel (n)
  cloud.bin        : Float32 x,y,z (m*3)  +  Uint32 owner (m)
  edges.bin        : Uint32 indptr (n+1)  +  Uint32 pre (e)  +  Float32 w (e)
  skeletons.json   : 대표 뉴런 스켈레톤 선분
"""
import json
import pathlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
DER = ROOT / "data/derived/connectome"
SWC = ROOT / "data/malecns/swc"
OUT = ROOT / "web/public/data/connectome"
OUT.mkdir(parents=True, exist_ok=True)

VOX_UM = 8 / 1000.0
PTS_PER_NEURON = 9
rng = np.random.default_rng(20260925)

# 약물감시 에이전트 층 <-> 초파리 해부학
LAYERS = [
    {"key": "sense",   "name": "Sensory Intake",       "brain": "Sensory neurons (ORN, GRN, JO, VPN)", "agent": "Data stream intake skills"},
    {"key": "encode",  "name": "Feature Encoding",     "brain": "Antennal lobe projection neurons",    "agent": "Normalize · dedupe · rule gate"},
    {"key": "reflex",  "name": "Reflex Judgment",      "brain": "Lateral horn (innate)",               "agent": "Jev System-1 typed decisions"},
    {"key": "memory",  "name": "Signal Memory",        "brain": "Mushroom body (KC · MBON · DAN)",     "agent": "Disproportionality + label memory"},
    {"key": "deliberate", "name": "Deliberation",      "brain": "Central complex",                     "agent": "Nemotron System-2 assessment"},
    {"key": "critic",  "name": "Inhibitory Critic",    "brain": "GABAergic interneurons",              "agent": "3-tier critic (rules · oracle · judge)"},
    {"key": "assoc",   "name": "Association",          "brain": "Protocerebrum intrinsic",             "agent": "Context integration"},
    {"key": "action",  "name": "Action Output",        "brain": "Descending neurons",                  "agent": "Escalate · report · monitor · close"},
    {"key": "feedback", "name": "Reviewer Feedback",   "brain": "Ascending neurons",                   "agent": "Human-in-the-loop reinforcement"},
]
LAYER_IDX = {l["key"]: i for i, l in enumerate(LAYERS)}

CHANNELS = [
    {"key": "none",       "name": "-",                        "modality": "-"},
    {"key": "faers",      "name": "FAERS spontaneous reports", "modality": "olfactory"},
    {"key": "literature", "name": "Literature (PubMed)",      "modality": "gustatory"},
    {"key": "trials",     "name": "Clinical trials / SUSAR",  "modality": "mechanosensory"},
    {"key": "label",      "name": "Label & regulatory updates", "modality": "hygro/thermo"},
    {"key": "digital",    "name": "Digital & social media",   "modality": "visual projection"},
    {"key": "other",      "name": "Other sources",            "modality": "other sensory"},
]
CH_IDX = {c["key"]: i for i, c in enumerate(CHANNELS)}


def role(row):
    sc, nt = row.superclass, row.nt
    cl = row["class"] if isinstance(row["class"], str) else ""
    ty = row.type if isinstance(row.type, str) else ""
    if sc in ("cb_sensory", "sensory_ascending", "sensory_descending"):
        ch = {"olfactory": "faers", "gustatory": "literature", "mechanosensory": "trials",
              "mechanosensory_proprioceptive": "trials", "mechanosensory_tbc": "trials",
              "hygrosensory": "label", "thermosensory": "label"}.get(cl, "other")
        return "sense", ch
    if sc == "visual_projection":
        return "sense", "digital"
    if sc == "descending_neuron":
        return "action", "none"
    if sc == "ascending_neuron":
        return "feedback", "none"
    if cl in ("ALPN", "ALLN", "ALIN", "ALON", "SEZPN"):
        return "encode", "none"
    if cl in ("Kenyon_Cell", "MBON", "DAN"):
        return "memory", "none"
    if cl == "CX":
        return "deliberate", "none"
    if ty.startswith("LH"):
        return "reflex", "none"
    if nt == "gaba":
        return "critic", "none"
    return "assoc", "none"


def read_swc(body):
    p = SWC / f"{body}.swc"
    if not p.exists():
        return None
    try:
        a = np.loadtxt(p, comments="#", usecols=(0, 2, 3, 4, 6), ndmin=2)
    except Exception:
        return None
    return a if len(a) else None


def summarize(body):
    a = read_swc(body)
    if a is None:
        return body, None, None
    xyz = a[:, 1:4] * VOX_UM
    k = min(PTS_PER_NEURON, len(xyz))
    idx = np.random.default_rng(body % 2**32).choice(len(xyz), size=k, replace=False)
    return body, xyz.mean(axis=0), xyz[idx]


def main():
    neu = pd.read_parquet(DER / "neurons.parquet")
    edges = pd.read_parquet(DER / "edges.parquet")
    roles = neu.apply(role, axis=1, result_type="expand")
    neu["layer"], neu["channel"] = roles[0], roles[1]
    n = len(neu)
    idx = pd.Series(np.arange(n), index=neu.bodyId)

    with ProcessPoolExecutor() as ex:
        res = list(ex.map(summarize, neu.bodyId.tolist(), chunksize=256))
    cen = {b: c for b, c, _ in res if c is not None}
    samples = {b: s for b, _, s in res if s is not None}
    print(f"skeletons parsed {len(cen):,}/{n:,}")

    pos = np.full((n, 3), np.nan)
    for i, (b, soma) in enumerate(zip(neu.bodyId, neu.somaLocation)):
        if b in cen:
            pos[i] = cen[b]
        elif soma is not None and len(soma) == 3:
            pos[i] = np.array(soma) * VOX_UM
    # 남은 뉴런은 연결 상대 위치 평균으로 채운다
    pre_i = idx[edges.pre].to_numpy()
    post_i = idx[edges.post].to_numpy()
    for _ in range(3):
        missing = np.isnan(pos[:, 0])
        if not missing.any():
            break
        df = pd.DataFrame({"a": np.r_[pre_i, post_i], "b": np.r_[post_i, pre_i]})
        df = df[missing[df.a] & ~missing[df.b]]
        m = pd.DataFrame(pos[df.b], columns=list("xyz")).groupby(df.a.to_numpy()).mean()
        pos[m.index] = m.to_numpy()
    pos[np.isnan(pos)] = np.nanmean(pos)

    # 점구름
    cloud, owner = [], []
    for i, b in enumerate(neu.bodyId):
        s = samples.get(b)
        if s is None:
            s = pos[i][None, :]
        cloud.append(s)
        owner.append(np.full(len(s), i, dtype=np.uint32))
    cloud = np.vstack(cloud).astype(np.float32)
    owner = np.concatenate(owner)

    # 부호 있는 정규화 가중치, post 기준 CSR
    sign = neu.sign.to_numpy()[pre_i]
    w = edges.weight.to_numpy().astype(np.float64)
    tot = np.bincount(post_i, weights=w, minlength=n)
    wn = (sign * w / np.maximum(tot[post_i], 1)).astype(np.float32)
    order = np.lexsort((pre_i, post_i))
    post_s, pre_s, w_s = post_i[order], pre_i[order], wn[order]
    indptr = np.zeros(n + 1, dtype=np.uint32)
    np.add.at(indptr, post_s + 1, 1)
    indptr = np.cumsum(indptr).astype(np.uint32)

    layer = neu.layer.map(LAYER_IDX).to_numpy().astype(np.uint8)
    chan = neu.channel.map(CH_IDX).to_numpy().astype(np.uint8)
    with open(OUT / "neurons.bin", "wb") as f:
        f.write(pos.astype(np.float32).tobytes()); f.write(layer.tobytes()); f.write(chan.tobytes())
    with open(OUT / "cloud.bin", "wb") as f:
        f.write(cloud.tobytes()); f.write(owner.tobytes())
    with open(OUT / "edges.bin", "wb") as f:
        f.write(indptr.tobytes()); f.write(pre_s.astype(np.uint32).tobytes()); f.write(w_s.tobytes())

    # 대표 뉴런 스켈레톤 (층마다 몇 개) - 선분으로 저장
    showcase_types = ["DNp01", "MBON01", "MBON06", "EPG", "PEN_a(PEN1)", "PFL3", "DA1_lPN", "VA1v_adPN", "LHAV4a4", "PAM01", "APL", "DPM"]
    skel = []
    for t in showcase_types:
        rows = neu[neu.type == t].head(2)
        for _, r in rows.iterrows():
            a = read_swc(r.bodyId)
            if a is None:
                continue
            ids = {int(x): k for k, x in enumerate(a[:, 0])}
            seg = [[*(a[k, 1:4] * VOX_UM), *(a[ids[int(p)], 1:4] * VOX_UM)]
                   for k, p in enumerate(a[:, 4]) if int(p) in ids]
            seg = np.round(np.array(seg), 2)[::2]
            skel.append({"bodyId": int(r.bodyId), "type": t, "layer": r.layer, "segments": seg.flatten().tolist()})

    lo, hi = pos.min(0), pos.max(0)
    counts = neu.layer.value_counts().to_dict()
    ch_counts = neu[neu.channel != "none"].channel.value_counts().to_dict()
    for l in LAYERS:
        l["neurons"] = int(counts.get(l["key"], 0))
    for c in CHANNELS:
        c["neurons"] = int(ch_counts.get(c["key"], 0))
    types = neu.type.fillna("").tolist()
    meta = {
        "source": "MaleCNS v1.0 (Janelia FlyEM, CC-BY 4.0), minconf 0.5",
        "neurons": n, "edges": int(len(pre_s)), "synapses": int(edges.weight.sum()),
        "cloudPoints": int(len(cloud)), "bbox": [lo.tolist(), hi.tolist()],
        "layers": LAYERS, "channels": CHANNELS,
        "nt": neu.nt.value_counts().to_dict(),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    (OUT / "types.json").write_text(json.dumps({"bodyId": neu.bodyId.tolist(), "type": types}))
    (OUT / "skeletons.json").write_text(json.dumps(skel))
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:16s} {p.stat().st_size/1e6:7.2f} MB")
    print(json.dumps({l['key']: l['neurons'] for l in LAYERS}))


if __name__ == "__main__":
    main()
