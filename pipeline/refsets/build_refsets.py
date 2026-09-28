"""공개 참조 세트 세 개를 하나의 형식으로 합칩니다 (확장 계획 제안 1).

- OMOP reference set (Ryan et al. 2013): 양성 165 / 음성 234, 결과 4종. OHDSI MethodEvaluation, Apache-2.0
- EU-ADR reference set (Coloma et al. 2013): 양성 43 / 음성 50, 결과 10종. OHDSI MethodEvaluation, Apache-2.0
- Time-indexed reference standard (Harpaz et al. 2014): 양성 62 / 음성 75. figshare, CC0. 2013년 라벨 변경 월 포함

반응 정의(MedDRA PT 묶음)는 기억으로 채우지 않습니다.
1. Harpaz 세트가 준 정의(narrow)를 먼저 씁니다. 같은 개념의 OMOP·EU-ADR 결과에도 그 정의를 재사용합니다.
2. Harpaz 에 없는 결과는 우리 웨어하우스의 PT 어휘에 명시적 정규식을 적용해 묶고, 걸린 PT 목록을 그대로 공개합니다.

산출물: data/derived/refsets/pairs.parquet, events.json
"""
import json
import pathlib
import re

import duckdb
import pandas as pd
import pyreadr

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data/refsets"
OUT = ROOT / "data/derived/refsets"
OUT.mkdir(parents=True, exist_ok=True)
DB = ROOT / "data/derived/faers.duckdb"

# OMOP·EU-ADR 결과 -> 반응 정의. ("harpaz", 이름) 은 Harpaz 정의 재사용, ("regex", 패턴) 은 어휘 규칙입니다.
OUTCOME_DEFS = {
    "OMOP Acute Liver Failure 1": ("harpaz", "Liver damage"),
    "Anaphylaxis #1": ("harpaz", "Anaphylaxis"),
    "Stevens-Johnson Syndrome #1": ("harpaz", "Severe bullous dermatitis"),
    "OMOP Acute Renal Failure 1": ("regex", r"^(acute kidney injury|renal failure acute|renal failure|acute prerenal failure|"
                                            r"renal tubular necrosis|nephropathy toxic|renal injury)$"),
    "OMOP Acute myocardial Infarction  1": ("regex", r"^(acute myocardial infarction|myocardial infarction|"
                                                     r"silent myocardial infarction|acute coronary syndrome)$"),
    "HOI Upper GI #3": ("regex", r"^(upper gastrointestinal haemorrhage|gastrointestinal haemorrhage|gastric haemorrhage|"
                                 r"duodenal ulcer haemorrhage|gastric ulcer haemorrhage|peptic ulcer haemorrhage|haematemesis|"
                                 r"melaena|oesophageal haemorrhage|duodenal haemorrhage)$"),
    "OMOP Aplastic Anemia 1": ("regex", r"^(aplastic anaemia|bone marrow failure)$"),
    "Leukopenia Including Neutropenia and Agranulocytosis": ("regex", r"^(leukopenia|neutropenia|agranulocytosis|febrile neutropenia|"
                                                                        r"white blood cell count decreased|neutrophil count decreased|"
                                                                        r"granulocytopenia)$"),
    "Rhabdomyolysis #1": ("regex", r"^(rhabdomyolysis|myoglobinuria)$"),
    "Cardiac Valve Fibrosis #1": ("regex", r"^(cardiac valve disease|valvular heart disease|mitral valve incompetence|"
                                           r"aortic valve incompetence|tricuspid valve incompetence|pulmonary valve incompetence|"
                                           r"cardiac valve fibrosis|mitral valve disease|aortic valve disease|heart valve incompetence)$"),
}
LABEL_KO = {
    "OMOP Acute Liver Failure 1": "급성 간손상", "Anaphylaxis #1": "아나필락시스", "Stevens-Johnson Syndrome #1": "중증 수포성 피부반응",
    "OMOP Acute Renal Failure 1": "급성 신손상", "OMOP Acute myocardial Infarction  1": "급성 심근경색",
    "HOI Upper GI #3": "상부 위장관 출혈", "OMOP Aplastic Anemia 1": "재생불량성 빈혈",
    "Leukopenia Including Neutropenia and Agranulocytosis": "백혈구·호중구 감소", "Rhabdomyolysis #1": "횡문근융해",
    "Cardiac Valve Fibrosis #1": "심장판막 섬유화",
}


# 참조 세트 이름과 FAERS 정규화 이름이 다른 경우의 명시적 동의어입니다. 추측으로 늘리지 않습니다.
DRUG_SYNONYMS = {
    "THYROXINE": "LEVOTHYROXINE", "CHLORAZEPATE": "CLORAZEPATE", "MEFENAMATE": "MEFENAMIC ACID",
    "TETRAHYDROCANNABINOL": "DRONABINOL", "REGULAR INSULIN, HUMAN": "INSULIN HUMAN",
    "ESTROGENS, CONJUGATED (USP)": "ESTROGENS, CONJUGATED",
}


def match_drugs(con, names: list[str]) -> dict[str, tuple[str | None, str]]:
    """참조 세트 약물명을 웨어하우스 약물명으로 맞춥니다. (이름, 방법)을 돌려줍니다."""
    sql = (ROOT / "pipeline/faers/model.sql").read_text()
    i, j = sql.index("CREATE OR REPLACE MACRO norm_drug0"), sql.index("-- 2014Q3")
    mem = duckdb.connect()  # 매크로는 읽기 전용 DB 가 아니라 메모리 연결에 만듭니다
    mem.execute(sql[i:j])
    n_drug = dict(con.execute("SELECT drug, n_drug FROM sig_drug_n").fetchall())
    out = {}
    for name in names:
        if name in n_drug:
            out[name] = (name, "exact")
            continue
        normed = mem.execute("SELECT regexp_replace(norm_drug(?, NULL), '-[A-Z]{4}$', '')", [name]).fetchone()[0]
        if normed in n_drug:
            out[name] = (normed, "salt-normalized")
            continue
        syn = DRUG_SYNONYMS.get(name)
        if syn and syn in n_drug:
            out[name] = (syn, "synonym")
            continue
        base = syn or name
        # 앞부분 일치는 뒤에 붙는 말이 염·수화물 이름(영문자 한 단어)일 때만 허용합니다
        pref = sorted(((d, n) for d, n in n_drug.items()
                       if d.startswith(base + " ") and re.fullmatch(r"[A-Z]+", d[len(base) + 1:])), key=lambda t: -t[1])
        out[name] = (pref[0][0], "prefix") if pref else (None, "unmatched")
    return out


def main():
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET memory_limit='8GB'")
    vocab = [r[0] for r in con.execute("SELECT pt FROM sig_pt_n").fetchall()]
    vocab_set = set(vocab)
    drugs = set(r[0] for r in con.execute("SELECT drug FROM sig_drug_n").fetchall())

    x = pd.read_excel(SRC / "timeIndexedReferenceStandard.xls", sheet_name=None)
    evd = x["Event Definitions"].copy()
    evd["EVENT_CONCEPT_NAME"] = evd["EVENT_CONCEPT_NAME"].ffill()
    harpaz_def = {}
    evd["EVENT_KEY"] = evd["EVENT_CONCEPT_NAME"].str.strip().str.lower()
    for ev, g in evd.groupby("EVENT_KEY"):
        harpaz_def[ev] = {lvl: sorted(set(g[g.DEFINITION_LEVEL == lvl].MEDDRA_PT.str.lower().str.strip()))
                          for lvl in ("narrow", "broad")}

    events = {}

    def add_event(key, source, name_ko, pts_narrow, pts_broad=None, note=""):
        n = sorted(p for p in pts_narrow if p in vocab_set)
        b = sorted(p for p in (pts_broad or []) if p in vocab_set)
        events[key] = {"key": key, "source": source, "label_ko": name_ko, "pts": n, "pts_broad": b,
                       "pts_defined": len(pts_narrow), "pts_in_faers": len(n), "note": note}

    for ev, d in harpaz_def.items():
        add_event(f"H:{ev}", "Harpaz 2014 event definition (narrow)", ev, d["narrow"], d["broad"])
    for outcome, (kind, arg) in OUTCOME_DEFS.items():
        if kind == "harpaz":
            d = harpaz_def[arg.lower()]
            add_event(f"O:{outcome}", f"Harpaz 2014 definition '{arg}' (narrow) 재사용", LABEL_KO[outcome], d["narrow"], d["broad"])
        else:
            pts = [p for p in vocab if re.search(arg, p)]
            add_event(f"O:{outcome}", "FlyVigilance 어휘 규칙 v1 (정규식, 목록 공개)", LABEL_KO[outcome], pts, note=arg)

    rows = []
    for name, fname in (("OMOP", "omopReferenceSet"), ("EU-ADR", "euadrReferenceSet")):
        df = list(pyreadr.read_r(SRC / f"{fname}.rda").values())[0]
        for r in df.itertuples():
            rows.append({"refset": name, "drug_name": r.exposureName, "event": f"O:{r.outcomeName}",
                         "truth": int(r.groundTruth), "change_month": None, "sections": None})
    rs = x["Reference Standard"]
    li = x[[k for k in x if k.startswith("Labeling")][0]]
    li.columns = [c.strip() for c in li.columns]
    lab = {(r.EVENT_CONCEPT_NAME.strip().lower(), r.DRUG_CONCEPT_NAME.strip().lower()): r for r in li.itertuples()}
    for r in rs.itertuples():
        info = lab.get((r.EVENT_CONCEPT_NAME.strip().lower(), r.DRUG_CONCEPT_NAME.strip().lower()))
        secs = None
        if info is not None:
            secs = [s for s, col in (("boxed_warning", "BW"), ("warnings", "W"), ("adverse_reactions", "AR"),
                                     ("postmarketing", "AR_POSTMARKETING")) if pd.notna(getattr(info, col, None))]
        rows.append({"refset": "Harpaz", "drug_name": r.DRUG_CONCEPT_NAME, "event": f"H:{r.EVENT_CONCEPT_NAME.strip().lower()}",
                     "truth": int(r.GROUND_TRUTH), "change_month": int(info.LABEL_CHANGE_MONTH) if info is not None else None,
                     "sections": secs})
    pairs = pd.DataFrame(rows)
    pairs["drug_ref"] = pairs.drug_name.str.upper().str.strip()
    m = match_drugs(con, sorted(pairs.drug_ref.unique()))
    pairs["drug"] = pairs.drug_ref.map(lambda d: m[d][0])
    pairs["drug_match"] = pairs.drug_ref.map(lambda d: m[d][1])
    pairs["drug_in_faers"] = pairs.drug.notna()
    pairs["event_pts"] = pairs.event.map(lambda e: len(events[e]["pts"]))
    pairs["evaluable"] = pairs.drug_in_faers & (pairs.event_pts > 0)
    pairs.to_parquet(OUT / "pairs.parquet")
    (OUT / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=1))
    print(pairs.groupby("refset").agg(n=("truth", "size"), pos=("truth", "sum"), evaluable=("evaluable", "sum")).to_string())
    print("match methods:", pairs.drop_duplicates("drug_ref").drug_match.value_counts().to_dict())
    print("non-exact:", sorted({(a, b, c) for a, b, c in pairs[pairs.drug_match != "exact"][["drug_ref", "drug", "drug_match"]].itertuples(index=False)}))
    for k, e in events.items():
        if k.startswith("O:"):
            print(k, e["pts_in_faers"], e["pts"][:8])


if __name__ == "__main__":
    main()
