"""FlyGate 에이전트 패키지(agent/)를 검증합니다. 네트워크와 API 키 없이 돕니다.

1. OpenShell 정책(agent/policy/flygate.yaml): 허용 호스트 목록, 와일드카드 없음, 목록 밖 호스트 차단, 쓰기 경로 제한, 비루트.
2. flygate CLI: 하위 명령이 모두 있고, 오프라인 명령이 근거 ID 가 붙은 JSON 을 냅니다.
3. OpenClaw 작업 공간 파일이 모두 있습니다.
"""
import importlib.util
import json
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ROOT / "agent" / "policy" / "flygate.yaml"

# 외부 API 다섯 곳과 허용하는 메서드·경로입니다. 이 밖은 열지 않습니다.
EXTERNAL = {
    "api.fda.gov": {("GET", "/drug/label.json"), ("GET", "/drug/event.json")},
    "eutils.ncbi.nlm.nih.gov": {("GET", "/entrez/eutils/esearch.fcgi"), ("GET", "/entrez/eutils/efetch.fcgi"),
                                ("GET", "/entrez/eutils/esummary.fcgi")},
    "api.typesafe.ai": {("POST", "/v1/systemone")},
    "integrate.api.nvidia.com": {("POST", "/v1/chat/completions"), ("GET", "/v1/models")},
    "health.api.nvidia.com": {("POST", "/v1/biology/colabfold/msa-search/predict"),
                              ("POST", "/v1/biology/openfold/openfold3/predict"),
                              ("POST", "/v1/biology/mit/diffdock"), ("POST", "/v1/biology/mit/boltz2/predict"),
                              ("GET", "/v1/status/**")},
}
# NemoClaw 하네스 내부 경로입니다(게이트웨이 가상 호스트, 샌드박스 브리지 주소). OpenClaw 실행 파일에만 묶입니다.
INTERNAL = {"inference.local", "10.200.0.2"}
PYTHON = {"/usr/bin/python3", "/usr/bin/python3.13"}
OPENCLAW = {"/usr/local/bin/openclaw", "/usr/local/bin/node"}
# 보고서나 데이터를 밖으로 내보낼 수 있는 곳입니다. 어느 것도 열려 있으면 안 됩니다.
FORBIDDEN = {"pastebin.com", "example.com", "github.com", "api.github.com", "gist.github.com", "raw.githubusercontent.com",
             "pypi.org", "files.pythonhosted.org", "slack.com", "hooks.slack.com", "smtp.gmail.com", "gmail.googleapis.com",
             "nedrug.mfds.go.kr", "clawhub.ai", "registry.npmjs.org"}
RW_ALLOWED = {"/tmp", "/dev/null", "/dev/pts", "/sandbox/.openclaw", "/sandbox/.nemoclaw"}


@pytest.fixture(scope="module")
def policy() -> dict:
    return yaml.safe_load(POLICY.read_text(encoding="utf-8"))


def _endpoints(policy):
    for key, block in policy["network_policies"].items():
        for ep in block["endpoints"]:
            yield key, block, ep


def test_schema_basics(policy):
    assert policy["version"] == 1
    assert set(policy) == {"version", "filesystem_policy", "landlock", "process", "network_policies"}
    assert policy["landlock"]["compatibility"] == "best_effort"
    for key, block in policy["network_policies"].items():
        assert block.get("name") and block.get("endpoints") and block.get("binaries"), key


def test_hosts_are_exactly_the_allowlist(policy):
    hosts = {ep["host"] for _, _, ep in _endpoints(policy)}
    assert hosts == set(EXTERNAL) | INTERNAL


def test_no_wildcard_hosts_or_ports(policy):
    for key, _, ep in _endpoints(policy):
        assert "*" not in ep["host"], key
        assert isinstance(ep["port"], int), key


@pytest.mark.parametrize("host", sorted(FORBIDDEN))
def test_forbidden_hosts_are_not_allowed(policy, host):
    assert host not in {ep["host"] for _, _, ep in _endpoints(policy)}


def test_external_endpoints_are_narrowed_to_method_and_path(policy):
    for key, block, ep in _endpoints(policy):
        if ep["host"] in INTERNAL:
            continue
        assert "access" not in ep, f"{key}: access 대신 rules 로 메서드와 경로를 좁힙니다"
        assert ep["protocol"] == "rest" and ep["enforcement"] == "enforce", key
        assert ep["port"] == 443, key
        got = {(r["allow"]["method"], r["allow"]["path"]) for r in ep["rules"]}
        assert got == EXTERNAL[ep["host"]], ep["host"]


def test_external_endpoints_bind_only_python(policy):
    for key, block, ep in _endpoints(policy):
        bins = {b["path"] for b in block["binaries"]}
        if ep["host"] in INTERNAL:
            assert bins <= OPENCLAW, key
        else:
            assert bins == PYTHON, f"{key}: 외부 API 는 파이썬에만 묶습니다 ({bins})"
            assert "/usr/bin/curl" not in bins


def test_internal_routes_stay_internal(policy):
    blocks = {ep["host"]: (block, ep) for _, block, ep in _endpoints(policy)}
    _, dial = blocks["10.200.0.2"]
    assert dial["allowed_ips"] == ["10.200.0.2"] and dial["port"] in (18789, 18790)


def test_write_paths_are_limited(policy):
    fs = policy["filesystem_policy"]
    rw = set(fs["read_write"])
    assert rw <= RW_ALLOWED, rw - RW_ALLOWED
    assert {"/tmp", "/sandbox/.openclaw", "/sandbox/.nemoclaw"} <= rw
    assert fs["include_workdir"] is True
    for p in ("/", "/etc", "/usr", "/lib", "/proc", "/sandbox"):
        assert p not in rw, p
    for p in ("/usr", "/lib", "/etc", "/proc"):
        assert p in fs["read_only"], p


def test_runs_as_non_root(policy):
    proc = policy["process"]
    assert proc["run_as_user"] == "sandbox" and proc["run_as_group"] == "sandbox"
    assert str(proc["run_as_user"]) not in ("0", "root")


# ---------------------------------------------------------------- CLI
@pytest.fixture(scope="module")
def flygate():
    spec = importlib.util.spec_from_file_location("flygate", ROOT / "agent" / "flygate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_has_all_subcommands(flygate):
    parser = flygate.build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    assert set(sub.choices) == {"login", "chat", "triage", "grade", "signals", "kr-causality", "critic", "discover", "watch"}


def test_discover_parp1_offline(flygate, capsys):
    flygate.main(["discover", "parp1"])
    out = json.loads(capsys.readouterr().out)
    assert out["cmd"] == "discover" and out["target"] == "PARP1"
    assert out["structure"]["plddt"] == 95.95 and out["structure"]["msa_homologs"] == 101
    assert out["affinity_benchmark"]["n"] == 39
    nira = next(c for c in out["candidates"] if c["ligand"] == "niraparib")
    assert nira["diffdock_rmsd_to_xtal_A"] == 0.71
    cross = [c for c in out["critic"]["measured"] if c["rule"] == "cross-target"]
    assert cross and cross[0]["expected"] == "REJECT"
    assert "openfold3:parp1/4R6E-A" in out["evidence_ids"]
    assert out["handoff_to_vigilance"]["molecule"] == "NIRAPARIB"


def test_critic_offline_never_passes(flygate, capsys):
    flygate.main(["critic", str(ROOT / "agent" / "examples" / "claims_niraparib.json"), "--offline"])
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] in ("returned", "human_check")
    assert any(i["rule"] == "unknown_evidence" for i in out["issues"])


def test_watch_offline_writes_note_and_submits_nothing(flygate, capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("FV_CACHE_DIR", raising=False)
    flygate.main(["watch", "--memory-dir", str(tmp_path), "--warehouse", str(tmp_path / "none.duckdb"),
                  "--date", "2026-09-28", "--workspace", str(ROOT / "agent" / "workspace")])
    out = json.loads(capsys.readouterr().out)
    assert out["submitted"] == []
    assert (tmp_path / "2026-09-28.md").exists()
    assert out["watchlist"] and all(r["evidence_ids"] for r in out["watchlist"])
    assert all(v["same"] for v in out["workspace"].values())


def test_workspace_files_exist():
    ws = ROOT / "agent" / "workspace"
    for f in ("SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md", "TOOLS.md", "HEARTBEAT.md", "MEMORY.md"):
        assert (ws / f).is_file(), f
