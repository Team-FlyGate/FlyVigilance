"""MaleCNS에서 FlyVigilance 라우터에 쓸 중앙뇌 부분그래프를 고른다.

산출물 (data/derived/connectome/)
  neurons.parquet : 선택된 뉴런과 주석, 신경전달물질, 부호(+1/-1)
  edges.parquet   : 선택된 뉴런 사이 연결 (시냅스 >= MIN_W, post 뉴런당 상위 TOP_IN 입력)
  swc_ids.txt     : 스켈레톤을 받을 bodyId 목록
"""
import pathlib

import duckdb
import pandas as pd
import pyarrow.feather as feather

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data/malecns/flat-connectome"
OUT = ROOT / "data/derived/connectome"
OUT.mkdir(parents=True, exist_ok=True)

KEEP_SUPERCLASS = {
    "cb_intrinsic", "cb_sensory", "descending_neuron", "ascending_neuron",
    "sensory_ascending", "sensory_descending", "cb_motor", "cb_endocrine", "visual_projection",
}
MIN_W = 5      # 시냅스 5개 미만 연결은 버린다
TOP_IN = 32    # post 뉴런마다 가장 강한 입력 32개만 남긴다

# 초파리에서 GABA와 글루탐산은 대체로 억제성으로 작동한다
NT_SIGN = {"acetylcholine": 1, "gaba": -1, "glutamate": -1, "dopamine": 1,
           "serotonin": 1, "octopamine": 1, "histamine": -1, "tyramine": 1}


def main():
    ann = pd.read_feather(SRC / "body-annotations-male-cns-v1.0-minconf-0.5.feather")
    ann = ann[(ann.status == "Traced") & ann.superclass.isin(KEEP_SUPERCLASS)]
    nt = pd.read_feather(SRC / "body-neurotransmitters-male-cns-v1.0.feather",
                         columns=["body", "consensus_nt", "predicted_nt"])
    nt = nt.rename(columns={"body": "bodyId"})
    ann = ann.merge(nt, on="bodyId", how="left")
    ann["nt"] = ann.consensus_nt.fillna(ann.predicted_nt).fillna("unknown").str.lower()
    ann["sign"] = ann.nt.map(NT_SIGN).fillna(1).astype("int8")

    cols = ["bodyId", "type", "instance", "superclass", "class", "subclass",
            "somaSide", "somaLocation", "nt", "sign", "flywireType", "hemibrainType"]
    ann = ann[cols].reset_index(drop=True)

    con = duckdb.connect()
    con.register("ids", pd.DataFrame({"bodyId": ann.bodyId}))
    w = feather.read_table(SRC / "connectome-weights-male-cns-v1.0-minconf-0.5.feather", memory_map=True)
    con.register("w", w)
    edges = con.execute(f"""
        WITH e AS (
          SELECT body_pre AS pre, body_post AS post, weight
          FROM w
          WHERE weight >= {MIN_W}
            AND body_pre IN (SELECT bodyId FROM ids)
            AND body_post IN (SELECT bodyId FROM ids)
        )
        SELECT pre, post, weight FROM (
          SELECT *, row_number() OVER (PARTITION BY post ORDER BY weight DESC) AS r FROM e
        ) WHERE r <= {TOP_IN}
    """).df()

    # 연결이 하나도 없는 뉴런은 뺀다
    used = set(edges.pre) | set(edges.post)
    ann = ann[ann.bodyId.isin(used)].reset_index(drop=True)
    edges = edges[edges.pre.isin(ann.bodyId) & edges.post.isin(ann.bodyId)].reset_index(drop=True)

    ann.to_parquet(OUT / "neurons.parquet")
    edges.to_parquet(OUT / "edges.parquet")
    (OUT / "swc_ids.txt").write_text("\n".join(map(str, ann.bodyId)) + "\n")
    print(f"neurons {len(ann):,}  edges {len(edges):,}  synapses {edges.weight.sum():,}")
    print(ann.superclass.value_counts().to_string())


if __name__ == "__main__":
    main()
