"""FlyDiscovery 라이브 경로를 네트워크 없이 검사합니다.

요청 본문은 NVIDIA 공식 스킬 규격과 맞는지, 응답 가공은 팀원이 남긴 원본 응답에서 측정값을 그대로 내는지,
계산 중(202)·장애는 각각 요청 ID 와 지난 측정으로 떨어지는지 봅니다.
"""
import asyncio
import json
import pathlib
import sys

import httpx
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
from _fv import discovery as disc  # noqa: E402
from _fv import molgeom as mg  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
NIM = ROOT / "fly_discovery" / "measurements" / "nim"


def raw(name):
    return json.loads((NIM / name).read_text())


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(disc.config, "NVIDIA_API_KEY", "test-secret")
    disc._MEM.clear()
    monkeypatch.delenv("FV_CACHE_DIR", raising=False)


# ---------------------------------------------------------------- 요청 본문 (공식 스킬 규격)
def test_msa_request_follows_skill():
    b = disc.build_msa("parp1")
    assert b["databases"] == ["Uniref30_2302"]  # envdb 는 호스팅 게이트웨이가 504 를 냅니다(선택으로 둡니다)
    assert disc.build_msa("parp1", disc.MSA_DATABASES_FULL)["databases"] == ["Uniref30_2302", "colabfold_envdb_202108"]
    assert b["e_value"] == 0.0001 and b["output_alignment_formats"] == ["a3m"]
    assert len(b["sequence"]) == 352 and b["sequence"].startswith("MKSKLPKPVQ")


def test_openfold3_request_carries_msa_and_ligand():
    b = disc.build_openfold3("parp1", "niraparib", ">query\nMKSK")
    inp = b["inputs"][0]
    assert len(b["inputs"]) == 1 and inp["output_format"] == "pdb"
    prot, lig = inp["molecules"]
    assert prot["type"] == "protein" and prot["diffusion_samples"] == 1
    assert prot["msa"]["uniref30"]["a3m"]["format"] == "a3m"
    assert prot["msa"]["uniref30"]["a3m"]["alignment"].startswith(">")
    assert lig["type"] == "ligand" and lig["smiles"]


def test_openfold3_without_msa_uses_query_only():
    b = disc.build_openfold3("parp1", None, None)
    a3m = b["inputs"][0]["molecules"][0]["msa"]["uniref30"]["a3m"]["alignment"]
    assert a3m.startswith(">query\n") and len(b["inputs"][0]["molecules"]) == 1


def test_diffdock_request_is_the_cli_body():
    b = disc.build_diffdock("parp1", "niraparib")
    assert b["ligand_file_type"] == "txt" and b["num_poses"] == disc.MAX_POSES
    assert b["time_divisions"] == 20 and b["steps"] == 18 and b["save_trajectory"] is False
    assert all(ln.startswith(("ATOM", "TER", "END")) for ln in b["protein"].splitlines() if ln.strip())
    assert disc.ENDPOINTS["diffdock"] == disc.docking.ENDPOINT


def test_boltz2_request_predicts_affinity_on_one_ligand():
    b = disc.build_boltz2("parp1", "niraparib", ">query\nMKSK")
    assert b["polymers"][0]["molecule_type"] == "protein"
    assert b["polymers"][0]["msa"]["msa_search"]["a3m"]["rank"] == 0
    assert len(b["ligands"]) == 1 and b["ligands"][0]["predict_affinity"] is True
    assert b["output_format"] == "mmcif" and b["diffusion_samples"] == 1


def test_request_summary_has_no_key_and_no_full_payload():
    for kind, params in [("msa", {}), ("openfold3", {"ligand": "niraparib"}),
                         ("diffdock", {"ligand": "niraparib"}), ("boltz2", {"ligand": "niraparib"})]:
        s = disc.request_summary(kind, disc.build_for(kind, {"target": "parp1", **params}))
        blob = json.dumps(s, ensure_ascii=False)
        assert "test-secret" not in blob and "ATOM" not in blob and len(blob) < 1200


# ---------------------------------------------------------------- 응답 가공 (측정값 재현)
def test_msa_processing_matches_measured_alignment():
    a3m = (NIM / "parp1.a3m").read_text()
    r = disc.process_msa({"alignments": {"Uniref30_2302": {"a3m": {"alignment": a3m, "format": "a3m"}}}},
                         {"target": "parp1"})
    assert r["sequences"] == 101 and r["homologs"] == 100  # 원본 a3m 은 질의 1 + 상동 100
    assert r["query_len"] == 352 and len(r["conservation"]) == 352 and len(r["depth"]) == 352
    assert r["rows"] and all(len(x["seq"]) == 352 for x in r["rows"]) and len(r["rows"]) <= 60
    assert 0 <= max(r["conservation"]) <= 1 and r["rows"][0]["identity"] >= r["rows"][-1]["identity"]


def test_openfold3_processing_reproduces_measured_rmsd():
    r = disc.process_openfold3(raw("openfold3_parp1_niraparib.json"), {"target": "parp1", "ligand": "niraparib"})
    assert r["scores"]["plddt"] == pytest.approx(95.95, abs=0.01)
    assert r["scores"]["ptm"] == pytest.approx(0.828, abs=0.001)
    assert r["ca_rmsd"] == pytest.approx(1.0, abs=0.01) and r["n_ca"] == 350
    assert r["ligand_rmsd"] == pytest.approx(1.16, abs=0.01)
    assert len(r["ca"]) == r["n_residues"] == 352 and len(r["plddt_per_residue"]) == 352
    assert len(r["ligand_atoms"]) == 24 and r["xtal_ligand"]["atoms"]


def test_diffdock_processing_reproduces_measured_redock():
    r = disc.process_diffdock(raw("diffdock_niraparib_parp1.json"), {"target": "parp1", "ligand": "niraparib"})
    assert r["redock"] is True and r["top1_success"] is True
    assert r["top1_confidence"] == pytest.approx(0.696, abs=0.001)
    assert r["top1_rmsd"] == pytest.approx(0.71, abs=0.01)
    assert [p["rank"] for p in r["poses"]] == [1, 2, 3, 4, 5]
    assert r["poses"][0]["pocket_dist"] is not None and len(r["poses"][0]["atoms"]) == 24


def test_diffdock_processing_marks_cross_dock_without_rmsd():
    r = disc.process_diffdock(raw("dd_factor-xa-2p16--niraparib.json"), {"target": "xa", "ligand": "niraparib"})
    assert r["redock"] is False and r["top1_rmsd"] is None and r["best_rmsd"] is None
    assert r["top1_confidence"] == pytest.approx(-0.044, abs=0.001)


def test_diffdock_rejects_a_broken_response():
    with pytest.raises(RuntimeError):
        disc.process_diffdock({"status": "success"}, {"target": "parp1", "ligand": "niraparib"})


def test_boltz2_processing_reproduces_measured_affinity():
    r = disc.process_boltz2(raw("boltz2_parp1-4r6e-chain-a--niraparib.json"), {"target": "parp1", "ligand": "niraparib"})
    assert r["affinity"]["pic50"] == pytest.approx(7.98, abs=0.01)
    assert r["affinity"]["probability_binary"] == pytest.approx(0.609, abs=0.001)
    assert r["scores"]["iptm"] == pytest.approx(0.9456, abs=0.001)
    assert r["n_residues"] == 352 and len(r["ligand_atoms"]) == 24
    assert r["chembl"]["median_pchembl"] == 7.79  # 예측이 아니라 측정값입니다


# ---------------------------------------------------------------- 기하 계산
def test_pure_python_geometry_matches_rdkit_panel():
    """RDKit 으로 잰 재도킹 패널(fly_discovery/measurements/redock.json)과 같은 RMSD 를 냅니다."""
    panel = json.loads((ROOT / "fly_discovery/measurements/redock.json").read_text())["results"]
    key = "jak2-6vgl--ruxolitinib"
    r = disc.process_diffdock(raw(f"dd_{key}.json"), {"target": key.split("--")[0], "ligand": "ruxolitinib"})
    want = [p["rmsd"] for p in panel[key]["poses"]]
    got = [p["rmsd"] for p in r["poses"]]
    assert got == pytest.approx(want, abs=0.01)


def test_superpose_is_translation_and_rotation_invariant():
    ca = [{"resi": i, "aa": "A", "xyz": (i * 1.0, (i % 3) * 1.5, (i % 5) * 0.7), "b": 50.0, "chain": "A"}
          for i in range(30)]
    moved = [{**a, "xyz": (a["xyz"][1] + 12, a["xyz"][2] + 3, a["xyz"][0] - 7)} for a in ca]
    fit = mg.superpose_ca(moved, ca)
    assert fit["n"] == 30 and fit["rmsd"] < 1e-3


# ---------------------------------------------------------------- 실행 경로 (모의 전송)
_ASYNC_CLIENT = httpx.AsyncClient


def _client(handler):
    return _ASYNC_CLIENT(transport=httpx.MockTransport(handler))


def test_run_returns_live_result_and_caches_it():
    calls = []

    def handle(req):
        calls.append(req.url.path)
        assert req.headers["authorization"] == "Bearer test-secret"
        assert req.headers["nvcf-poll-seconds"]
        return httpx.Response(200, json=raw("diffdock_niraparib_parp1.json"))
    out = run(disc.run("diffdock", {"target": "parp1", "ligand": "niraparib"}, _client(handle)))
    assert out["state"] == "done" and out["source"] == "live"
    assert out["result"]["top1_rmsd"] == pytest.approx(0.71, abs=0.01)
    assert out["measured"]["top1_rmsd"] == pytest.approx(0.71, abs=0.01)  # 지난 측정 비교값
    assert out["skills"][0]["repo"].startswith("NVIDIA")
    again = run(disc.run("diffdock", {"target": "parp1", "ligand": "niraparib"}, _client(handle)))
    assert again["source"] == "cache" and len(calls) == 1


def test_run_returns_request_id_while_the_nim_is_still_working():
    def handle(req):
        return httpx.Response(202, headers={"nvcf-reqid": "job-42"})
    out = run(disc.run("boltz2", {"target": "parp1", "ligand": "niraparib"}, _client(handle)))
    assert out["state"] == "pending" and out["req_id"] == "job-42"
    assert out["poll_url"] == "/api/discovery/status/job-42"
    assert disc._MEM["req-job-42"]["kind"] == "boltz2"


def test_status_finishes_a_pending_request(monkeypatch):
    def start(req):
        return httpx.Response(202, headers={"nvcf-reqid": "job-7"})
    run(disc.run("boltz2", {"target": "parp1", "ligand": "niraparib"}, _client(start)))
    seen = []

    def status(req):
        seen.append(str(req.url))
        return httpx.Response(200, json=raw("boltz2_parp1-4r6e-chain-a--niraparib.json"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _client(status))
    out = run(disc.poll("job-7"))
    assert out["state"] == "done" and out["result"]["affinity"]["pic50"] == pytest.approx(7.98, abs=0.01)
    assert seen and seen[0].endswith("/v1/status/job-7")


def test_gateway_timeout_is_retried_once_for_predictions():
    """게이트웨이 504 는 예측 계열에서 한 번 더 보냅니다. DiffDock 은 약속대로 다시 보내지 않습니다."""
    calls = []

    def flaky(req):
        calls.append(req.url.path)
        return httpx.Response(200, json=raw("openfold3_parp1_niraparib.json")) if len(calls) > 1 else httpx.Response(504, text="gateway timeout")
    out = run(disc.run("openfold3", {"target": "parp1", "ligand": "niraparib"}, _client(flaky)))
    assert len(calls) == 2 and out["source"] == "live"
    calls.clear()
    out = run(disc.run("diffdock", {"target": "parp1", "ligand": "niraparib"}, _client(flaky)))
    assert len(calls) == 1 and out["source"] == "measured"


def test_failure_falls_back_to_the_measured_response_with_a_reason():
    def handle(req):
        return httpx.Response(500, text="upstream is down")
    out = run(disc.run("openfold3", {"target": "parp1", "ligand": "niraparib"}, _client(handle)))
    assert out["state"] == "done" and out["source"] == "measured"
    assert "지난 측정" in out["note"] and out["error"]
    assert out["result"]["scores"]["plddt"] == pytest.approx(95.95, abs=0.01)


def test_missing_key_is_reported_not_silently_faked(monkeypatch):
    monkeypatch.setattr(disc.config, "NVIDIA_API_KEY", None)
    with pytest.raises(disc.clients.NotConfigured):
        run(disc.run("msa", {"target": "parp1"}, _client(lambda r: httpx.Response(200, json={}))))


# ---------------------------------------------------------------- 크리틱
def _runs():
    return {"msa": disc.process_msa({"alignments": {"Uniref30_2302": {"a3m": {"alignment": (NIM / "parp1.a3m").read_text(),
                                                                              "format": "a3m"}}}}, {"target": "parp1"}),
            "diffdock": disc.process_diffdock(raw("diffdock_niraparib_parp1.json"), {"target": "parp1", "ligand": "niraparib"}),
            "boltz2": disc.process_boltz2(raw("boltz2_parp1_niraparib.json"), {"target": "parp1", "ligand": "niraparib"})}


def test_bundle_lists_citable_ids_without_coordinates():
    b = disc.bundle_from_runs(_runs())
    assert "diffdock:parp1/niraparib" in b["ids"] and "boltz2:parp1/niraparib" in b["ids"]
    assert "chembl:niraparib/parp1" in b["ids"] and "boltz2:parp1/chembl-benchmark-39" in b["ids"]
    assert len(b["numbers"]) < 200 and 0.71 in [round(x, 2) for x in b["numbers"]]


def test_default_claims_mix_valid_and_overclaims():
    claims = disc.default_claims(_runs())
    kinds = {c["kind"] for c in claims}
    assert kinds == {"valid", "overclaim"} and len(claims) >= 5
    assert any(c.get("expect") == "D1" for c in claims)


def test_tier1_and_tier2_reject_before_any_model_call(monkeypatch):
    async def no_model(*a, **k):
        raise AssertionError("3단은 부르지 않아야 합니다")
    claims = [{"id": "c1", "text": "DiffDock 재도킹 RMSD 는 12.34 Å 입니다.", "evidence": ["diffdock:parp1/niraparib"], "kind": "valid"},
              {"id": "c2", "text": "근거 없이 좋습니다.", "evidence": ["diffdock:made-up"], "kind": "valid"}]
    monkeypatch.setattr(disc, "tier3_nemotron", no_model)
    out = run(disc.critic(claims, _runs()))
    assert out["verdict"] == "returned"
    rules = {i["rule"] for i in out["issues"]}
    assert "number_mismatch" in rules and "unknown_evidence" in rules
    assert out["judge"].get("error")


def test_tier3_verdicts_are_applied(monkeypatch):
    async def judge(claims, bundle, deadline=None):
        return {"verdicts": [{"id": "c1", "verdict": "REJECT", "rule": "D1", "why": "교차 단백질 비교"},
                             {"id": "c2", "verdict": "PASS", "rule": "none", "why": ""}],
                "model": "nvidia/nemotron-3-super-120b-a12b", "latency_ms": 900.0}
    monkeypatch.setattr(disc, "tier3_nemotron", judge)
    claims = [{"id": "c1", "text": "니라파립은 PARP1 -10.178, Factor Xa -7.967 이므로 선택적입니다.",
               "evidence": ["vina:parp1/niraparib", "vina:xa/niraparib"], "kind": "overclaim", "expect": "D1"},
              {"id": "c2", "text": "MSA-Search 가 상동 서열 100개를 찾았습니다.", "evidence": ["msa:parp1"], "kind": "valid"}]
    out = run(disc.critic(claims, _runs()))
    assert out["verdict"] == "returned" and out["score"] == {"caught": 1, "n_over": 1, "passed": 1, "n_valid": 1}
    assert out["tiers"]["tier3"][0]["rule"] == "D1" and out["tiers"]["tier3"][0]["detail_ko"]
    assert out["measured"]["caught"] == 4  # 지난 측정: Nemotron 3 Super 가 과잉해석 4/4 를 걸렀습니다


# ---------------------------------------------------------------- 목록과 장면
def test_catalog_lists_targets_ligands_and_official_skills():
    c = disc.catalog()
    assert {"parp1", "xa", "cox2"} <= set(c["targets"])
    assert c["targets"]["cox2"]["organism"] == "Mus musculus"
    assert "niraparib" in c["ligands"] and c["ligands"]["niraparib"]["ko"] == "니라파립"
    assert c["benchmark"]["n"] == 39 and c["benchmark"]["spearman"] == 0.767
    names = {s["name"] for v in c["skills"].values() for s in v}
    assert "bionemo-msa-structure-prediction-pipeline" in names and "diffdock-nim" in names
    assert json.dumps(c, ensure_ascii=False).find("test-secret") == -1


def test_scene_gives_a_pocket_and_a_backbone():
    s = disc.scene("parp1")
    assert s["pdb"] == "4R6E" and s["chain"] == "A" and s["xtal_drug"] == "niraparib"
    assert 300 < len(s["ca"]) < 400 and 100 < len(s["pocket"]) <= 1200
    assert len(s["pocket_center"]) == 3 and s["xtal_ligand"]["atoms"]


def test_entity_names_are_not_read_as_measurements():
    """Boltz-2, PARP1, 4R6E, pIC50 의 숫자는 측정값이 아니므로 숫자 오라클에서 뺍니다."""
    from _fv import assess as assess_mod
    cleaned = disc.strip_entity_numbers("Boltz-2 는 PARP1 4R6E 체인 A 에서 pIC50 8.9086 을 예측했습니다.")
    assert assess_mod._numbers(cleaned) == [8.9086]
    claims = [{"id": "c1", "text": "Boltz-2 예측 pIC50 8.9086 는 측정값입니다.", "evidence": ["boltz2:parp1/niraparib"],
               "kind": "overclaim"}]

    async def judge(*a, **k):
        return {"verdicts": [{"id": "c1", "verdict": "REJECT", "rule": "D3", "why": "예측값입니다"}], "model": "m"}
    old = disc.tier3_nemotron
    disc.tier3_nemotron = judge
    try:
        out = disc_run_critic(claims)
    finally:
        disc.tier3_nemotron = old
    assert [i["rule"] for i in out["issues"]] == ["D3"]


def disc_run_critic(claims):
    return run(disc.critic(claims, _runs()))


def test_measured_only_endpoint_needs_no_key():
    from fastapi.testclient import TestClient
    import index
    c = TestClient(index.app)
    r = c.get("/api/discovery/measured/diffdock", params={"target": "parp1", "ligand": "niraparib"})
    assert r.status_code == 200 and r.json()["measured"] is not None
    assert c.get("/api/discovery/measured/msa").json()["measured"] is not None
    assert c.get("/api/discovery/measured/nope").status_code == 404
