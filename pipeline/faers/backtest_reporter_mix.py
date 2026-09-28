"""신호 타임머신(backtest.json) 사례마다 보고자 구성을 붙입니다.

첫 SDR 이 선 분기까지, 그리고 FDA 조치 전까지 누적된 사례가 누구에게서 왔는지(의료인·소비자·변호사)와
한 분기에 몰린 비율(일괄 제출 의심)을 계산합니다. 소비자 보고 급증이나 소송 보고로 선 SDR 은
'FDA 보다 먼저 알 수 있었다'는 주장의 근거가 약하므로 화면에 함께 보여 줍니다.

사용: .venv/bin/python pipeline/faers/backtest_reporter_mix.py
입력·산출: web/public/data/faers/backtest.json (items[*].reporters 를 채웁니다)
"""
import json
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
BT = ROOT / "web/public/data/faers/backtest.json"
HCP = ("MD", "PH", "HP", "OT", "RN")


def quarter_of(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def mix(rows: list[tuple]) -> dict | None:
    n = len(rows)
    if not n:
        return None
    occ = [r[1] for r in rows]
    return {"n": n, "hcp": round(sum(1 for o in occ if o in HCP) / n, 3), "cn": round(occ.count("CN") / n, 3),
            "lw": round(occ.count("LW") / n, 3)}


def main():
    bt = json.loads(BT.read_text())
    con = duckdb.connect(str(ROOT / "data/derived/faers.duckdb"), read_only=True)
    for it in bt["items"]:
        # 타임머신과 같이 사례가 처음 접수된 분기(core_case_version 의 최소 분기)로 셉니다
        rows = con.execute("""SELECT f.fq, c.occp_cod FROM sig_triplet t JOIN core_case c USING (primaryid)
                              JOIN (SELECT caseid, min(quarter) AS fq FROM core_case_version GROUP BY caseid) f ON f.caseid = c.caseid
                              WHERE t.drug = ? AND t.pt = ?""", [it["drug"], it["pt"]]).fetchall()
        first_q = it.get("first_signal_quarter")
        act_q = quarter_of(it["action"]) if it.get("action") else None
        by_q: dict[str, int] = {}
        for q, _ in rows:
            by_q[q] = by_q.get(q, 0) + 1
        peak_q, peak_n = max(by_q.items(), key=lambda kv: kv[1]) if by_q else (None, 0)
        it["reporters"] = {
            "all": mix(rows),
            "to_first_sdr": mix([r for r in rows if first_q and r[0] <= first_q]),
            "pre_action": mix([r for r in rows if act_q and r[0] < act_q]),
            "peak_quarter": peak_q, "peak_share": round(peak_n / len(rows), 3) if rows else None,
        }
        r = it["reporters"]
        print(f"{it['drug']:>14} · {it['pt']:<26} all {r['all']} first {r['to_first_sdr']} pre {r['pre_action']} "
              f"peak {peak_q} {r['peak_share']}")
    bt["reporter_note"] = ("첫 SDR 까지와 FDA 조치 전 누적 사례의 보고자 구성입니다(의료인 MD·PH·HP·OT·RN, 소비자 CN, 변호사 LW). "
                           "소비자·변호사 보고가 대부분이거나 한 분기에 몰린 경우 선행 일수를 조심해 읽어야 합니다.")
    BT.write_text(json.dumps(bt, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
