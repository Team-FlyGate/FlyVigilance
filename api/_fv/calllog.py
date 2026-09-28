"""NVIDIA 호출 기록기입니다. 켜 두었을 때만 호출 한 건마다 JSON 한 줄을 덧붙입니다.

켜는 법: 환경변수 FV_CALL_LOG=<파일 경로> 를 줍니다. 없으면 record() 는 곧바로 돌아가므로 비용이 없습니다.
남기는 것은 메타데이터뿐입니다: 시각, 서비스, 엔드포인트 경로, 모델, 용도, HTTP 상태, 지연, 요청 ID(NVCF-REQID),
토큰 수, 주고받은 바이트 수, 캐시 적중 여부, 오류 종류, 호출한 코드 위치.
키, Authorization 헤더, 프롬프트와 응답 본문은 남기지 않습니다. 기록 중 어떤 오류가 나도 호출한 쪽으로 올리지 않습니다.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

ENV = "FV_CALL_LOG"
SERVICES = {
    "integrate.api.nvidia.com": "build.nvidia.com NIM",
    "health.api.nvidia.com": "BioNeMo NIM (health.api.nvidia.com)",
    "ai.api.nvidia.com": "NVIDIA Retrieval NIM (ai.api.nvidia.com)",
}
# extra 로 받을 수 있는 키입니다. 값은 짧은 숫자·참거짓·식별자만 받습니다(본문이 끼어들 틈을 두지 않습니다).
EXTRA_KEYS = {"json_mode", "attempt", "polls", "input_type", "n_inputs", "template", "max_tokens", "fallback_of",
              "response_id", "nvcf_status", "run_id"}
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:/@+\-]{0,120}$")
_SECRET = re.compile(r"nvapi-|bearer\s|authorization", re.I)
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SKIP_FILES = {pathlib.Path(__file__).resolve(), (pathlib.Path(__file__).parent / "clients.py").resolve()}
_LOCK = threading.Lock()


def target() -> str | None:
    """기록 파일 경로입니다. 꺼져 있으면 None 입니다."""
    return os.environ.get(ENV) or None


def enabled() -> bool:
    return bool(os.environ.get(ENV))


def service_of(url: str) -> tuple[str, str, str]:
    """(서비스 이름, 호스트, 경로)입니다. 쿼리 문자열은 버립니다."""
    u = urlsplit(url)
    return SERVICES.get(u.hostname or "", u.hostname or "unknown"), u.hostname or "", u.path


def usage_of(u) -> dict | None:
    """토큰 수만 꺼냅니다(정수 필드만)."""
    if not isinstance(u, dict):
        return None
    out = {k: v for k, v in u.items() if k in ("prompt_tokens", "completion_tokens", "total_tokens")
           and isinstance(v, int) and not isinstance(v, bool)}
    return out or None


def reqid_of(headers) -> str | None:
    """NVCF 요청 ID 입니다. 형식이 맞지 않으면 버립니다."""
    try:
        v = headers.get("nvcf-reqid") or headers.get("x-request-id")
    except Exception:  # noqa: BLE001
        return None
    return v if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", v) else None


def caller() -> str | None:
    """이 모듈과 clients.py 바깥에서 처음 만나는 저장소 안 호출 위치(파일:함수)입니다."""
    try:
        f = sys._getframe(1)
        while f is not None:
            p = pathlib.Path(f.f_code.co_filename).resolve()
            if p not in _SKIP_FILES and _ROOT in p.parents and ".venv" not in p.parts:
                return f"{p.relative_to(_ROOT).as_posix()}:{f.f_code.co_name}"
            f = f.f_back
    except Exception:  # noqa: BLE001
        return None
    return None


def _error_name(error) -> str | None:
    if error is None:
        return None
    name = type(error).__name__ if isinstance(error, BaseException) else str(error)
    name = name[:60]
    return name if _SAFE_TOKEN.match(name) else "Error"


def _clean_extra(extra: dict | None) -> dict:
    out = {}
    for k, v in (extra or {}).items():
        if k not in EXTRA_KEYS:
            continue
        if isinstance(v, bool) or (isinstance(v, (int, float)) and not isinstance(v, bool)):
            out[k] = v
        elif isinstance(v, str) and _SAFE_TOKEN.match(v) and not _SECRET.search(v):
            out[k] = v
    return out


def _response_meta(response) -> dict:
    """httpx.Response 에서 상태·요청 ID·바이트 수만 읽습니다. 본문과 요청 헤더는 읽지 않습니다."""
    meta: dict = {}
    if response is None:
        return meta
    try:
        meta["http_status"] = int(response.status_code)
    except Exception:  # noqa: BLE001
        pass
    meta["nvcf_reqid"] = reqid_of(getattr(response, "headers", {}))
    try:
        meta["bytes_in"] = len(response.content)
    except Exception:  # noqa: BLE001
        pass
    try:
        meta["bytes_out"] = len(response.request.content)
    except Exception:  # noqa: BLE001
        pass
    return meta


def build(*, url: str, model: str | None, purpose: str | None, response=None, http_status: int | None = None,
          latency_ms: float | None = None, reqid: str | None = None, usage=None, bytes_in: int | None = None,
          bytes_out: int | None = None, cache_hit: bool = False, error=None, code_path: str | None = None,
          extra: dict | None = None) -> dict:
    """기록 한 줄을 만듭니다. 허용한 필드만 들어갑니다."""
    svc, host, path = service_of(url)
    m = _response_meta(response)
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "service": svc, "host": host, "endpoint": path, "model": model, "purpose": purpose,
        "http_status": http_status if http_status is not None else m.get("http_status"),
        "latency_ms": None if latency_ms is None else round(float(latency_ms), 1),
        "nvcf_reqid": reqid if reqid and reqid_of({"nvcf-reqid": reqid}) else m.get("nvcf_reqid"),
        "usage": usage_of(usage),
        "bytes_out": bytes_out if bytes_out is not None else m.get("bytes_out"),
        "bytes_in": bytes_in if bytes_in is not None else m.get("bytes_in"),
        "cache_hit": bool(cache_hit), "error": _error_name(error),
        "code_path": code_path or caller(),
    }
    row.update(_clean_extra(extra))
    # 마지막 안전장치: 비밀처럼 보이는 문자열 값은 지웁니다
    for k, v in list(row.items()):
        if isinstance(v, str) and _SECRET.search(v):
            row[k] = "[redacted]"
    return row


def record(**kw) -> None:
    """FV_CALL_LOG 가 있으면 한 줄을 덧붙입니다. 없으면 아무것도 하지 않습니다. 절대 예외를 올리지 않습니다."""
    dest = os.environ.get(ENV)
    if not dest:
        return
    try:
        line = json.dumps(build(**kw), ensure_ascii=False, separators=(",", ":"))
        p = pathlib.Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001  기록 실패가 본 호출을 깨지 않게 합니다
        pass
