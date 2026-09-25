"""MaleCNS 뇌 neuropil ROI 메시(neuroglancer legacy)를 웹용 GLB 하나로 합친다.

좌표는 nm 에서 um 로 바꾸고 원점은 그대로 둔다 (뉴런 좌표와 같은 틀).
산출물: web/public/data/brain_rois.glb, data/derived/connectome/rois.json
"""
import json
import pathlib
import struct

import fast_simplification
import numpy as np
import trimesh

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data/malecns/rois/fullbrain-roi-v4"
OUT_GLB = ROOT / "web/public/data/brain_rois.glb"
OUT_META = ROOT / "data/derived/connectome/rois.json"
TARGET_FACES = 2500  # ROI 하나당 목표 삼각형 수


def read_ngmesh(path):
    b = path.read_bytes()
    n = struct.unpack("<I", b[:4])[0]
    v = np.frombuffer(b, dtype="<f4", count=n * 3, offset=4).reshape(-1, 3)
    f = np.frombuffer(b, dtype="<u4", offset=4 + n * 12).reshape(-1, 3)
    return v.astype(np.float64) / 1000.0, f.astype(np.int64)


def main():
    props = json.loads((SRC / "segment_properties/info").read_text())["inline"]
    names = dict(zip(props["ids"], props["properties"][0]["values"]))
    scene = trimesh.Scene()
    meta = []
    for seg_id, name in names.items():
        frag_file = SRC / "mesh" / f"{seg_id}:0"
        if not frag_file.exists():
            continue
        frags = json.loads(frag_file.read_text())["fragments"]
        parts = [read_ngmesh(SRC / "mesh" / fr) for fr in frags]
        v = np.vstack([p[0] for p in parts])
        offs = np.cumsum([0] + [len(p[0]) for p in parts[:-1]])
        f = np.vstack([p[1] + o for p, o in zip(parts, offs)])
        if len(f) > TARGET_FACES:
            ratio = 1 - TARGET_FACES / len(f)
            v, f = fast_simplification.simplify(v.astype(np.float32), f.astype(np.int32), target_reduction=ratio)
        mesh = trimesh.Trimesh(vertices=v, faces=f, process=True)
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        c = mesh.bounds.mean(axis=0)
        meta.append({"id": int(seg_id), "name": name, "center": [round(x, 2) for x in c],
                     "faces": int(len(mesh.faces)), "volume_um3": round(float(abs(mesh.volume)), 1)})
    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    scene.export(OUT_GLB)
    OUT_META.write_text(json.dumps(meta, indent=1))
    print(f"{len(meta)} ROIs -> {OUT_GLB} ({OUT_GLB.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
