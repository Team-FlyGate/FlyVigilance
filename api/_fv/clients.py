"""Jev(System-1)와 NVIDIA NIM(System-2) 호출기. 지연과 토큰을 항상 함께 돌려준다."""
import asyncio
import json
import re
import time

import httpx

from . import config

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class NotConfigured(RuntimeError):
    pass


async def jev(state: str, questions: dict, client: httpx.AsyncClient | None = None) -> dict:
    """TypeSafe Jev systemone 호출. questions 는 {id: {type, instructions, criteria?}}."""
    if not config.TYPESAFE_API_KEY:
        raise NotConfigured("TYPESAFE_API_KEY")
    body = {"model": config.JEV_MODEL, "state": state, "questions": questions}
    own = client is None
    client = client or httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        for attempt in range(3):
            t0 = time.perf_counter()
            r = await client.post(config.JEV_URL, json=body,
                                  headers={"Authorization": f"Bearer {config.TYPESAFE_API_KEY}"})
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                await asyncio.sleep(0.6 * (attempt + 1))
                continue
            r.raise_for_status()
            d = r.json()
            return {"answers": d["answers"], "usage": d.get("usage", {}), "model": d.get("model"),
                    "latency_ms": round(ms, 1)}
    finally:
        if own:
            await client.aclose()


async def nim_chat(messages: list, models: list[str], max_tokens: int = 1200, temperature: float = 0.2,
                   client: httpx.AsyncClient | None = None, deadline: float | None = None, json_mode: bool = False,
                   template_kwargs: dict | None = None) -> dict:
    """NVIDIA NIM chat/completions. 모델 사슬을 따라 폴백하고 사고 과정은 끈다.

    deadline(time.monotonic 기준)이 있으면 모든 시도를 그 안에서 끝냅니다. 서버리스 함수 제한 시간을 넘기지 않으려는 장치입니다.
    시간 초과는 같은 모델로 다시 시도하지 않고 다음 모델로 넘어갑니다.
    json_mode 는 NIM 의 response_format(json_object)을 켭니다. 모델이 이를 거절하면(HTTP 400) 끄고 한 번 더 시도합니다.
    template_kwargs 는 chat_template_kwargs 에 덧붙입니다. Nemotron-3.5 Content Safety 의 BYO 정책(custom_policy,
    request_categories)이 이 경로로 들어갑니다. 이 모델의 chat template 은 system 메시지를 버리기 때문입니다.
    """
    if not config.NVIDIA_API_KEY:
        raise NotConfigured("NVIDIA_API_KEY")
    own = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0))
    errors = []
    try:
        for model in models:
            use_json = json_mode
            for attempt in range(2):
                left = None if deadline is None else deadline - time.monotonic()
                if left is not None and left < 3:
                    errors.append(f"{model}: time budget exhausted")
                    raise RuntimeError("all NIM models failed: " + "; ".join(errors))
                body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                        "temperature": temperature,
                        "chat_template_kwargs": {"enable_thinking": False, **(template_kwargs or {})}}
                if use_json:
                    body["response_format"] = {"type": "json_object"}
                t0 = time.perf_counter()
                try:
                    r = await client.post(f"{config.NIM_URL}/chat/completions", json=body,
                                          headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"},
                                          timeout=httpx.Timeout(min(90.0, left) if left else 90.0, connect=10.0))
                except httpx.TimeoutException as e:
                    errors.append(f"{model}: {type(e).__name__}")
                    break
                except httpx.HTTPError as e:
                    errors.append(f"{model}: {type(e).__name__}")
                    continue
                ms = (time.perf_counter() - t0) * 1000
                if r.status_code == 200:
                    d = r.json()
                    msg = d["choices"][0]["message"]
                    return {"content": msg.get("content") or "", "model": model, "usage": d.get("usage", {}),
                            "latency_ms": round(ms, 1), "fallbacks": errors}
                errors.append(f"{model}: HTTP {r.status_code}")
                if r.status_code == 400 and use_json and attempt == 0:
                    use_json = False
                    continue
                if r.status_code in (429, 503) and attempt == 0:
                    await asyncio.sleep(1.5)
                    continue
                break
        raise RuntimeError("all NIM models failed: " + "; ".join(errors))
    finally:
        if own:
            await client.aclose()


async def nim_embed(texts: list[str], input_type: str = "query") -> dict:
    if not config.NVIDIA_API_KEY:
        raise NotConfigured("NVIDIA_API_KEY")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        t0 = time.perf_counter()
        r = await c.post(f"{config.NIM_URL}/embeddings",
                         json={"model": config.MODEL_EMBED, "input": texts, "input_type": input_type},
                         headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"})
        r.raise_for_status()
        d = r.json()
        return {"vectors": [x["embedding"] for x in d["data"]], "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "usage": d.get("usage", {})}


async def nim_embed_many(texts: list[str], input_type: str, client: httpx.AsyncClient,
                         model: str | None = None) -> list[list[float]]:
    """여러 글을 한 번에 임베딩합니다. input_type 은 query 또는 passage 이고, 긴 글은 서버가 뒤를 자릅니다(truncate=END)."""
    if not config.NVIDIA_API_KEY:
        raise NotConfigured("NVIDIA_API_KEY")
    r = await client.post(f"{config.NIM_URL}/embeddings",
                          json={"model": model or config.MODEL_EMBED, "input": texts, "input_type": input_type, "truncate": "END"},
                          headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"}, timeout=_TIMEOUT)
    r.raise_for_status()
    return [x["embedding"] for x in sorted(r.json()["data"], key=lambda x: x.get("index", 0))]


def parse_rerank(body, n: int) -> list[float]:
    """리랭커 응답({"rankings": [{"index", "logit"}]})을 입력 순서의 점수 목록으로 풉니다.
    색인이 범위를 벗어나거나, 겹치거나, 빠지거나, 점수가 숫자가 아니면 ValueError 를 냅니다(호출한 쪽이 PubMed 순서로 돌아갑니다)."""
    ranks = body.get("rankings") if isinstance(body, dict) else None
    if not isinstance(ranks, list):
        raise ValueError("no rankings in rerank response")
    scores: list[float | None] = [None] * n
    for r in ranks:
        i = r.get("index") if isinstance(r, dict) else None
        s = r.get("logit", r.get("score")) if isinstance(r, dict) else None
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < n or scores[i] is not None:
            raise ValueError(f"bad rerank index {i!r}")
        if not isinstance(s, (int, float)) or isinstance(s, bool) or s != s:
            raise ValueError(f"bad rerank score for index {i}")
        scores[i] = float(s)
    if any(s is None for s in scores):
        raise ValueError("rerank response missing passages")
    return scores


async def nim_rerank(query: str, passages: list[str], client: httpx.AsyncClient, timeout: float = 4.0) -> dict:
    """Nemotron 리랭커로 질의–글 쌍의 관련도 점수(logit)를 받습니다. 글은 서버가 뒤를 자릅니다(truncate=END).
    돌려주는 scores 는 passages 와 같은 순서입니다."""
    if not config.NVIDIA_API_KEY:
        raise NotConfigured("NVIDIA_API_KEY")
    t0 = time.perf_counter()
    r = await client.post(config.RERANK_URL,
                          json={"model": config.MODEL_RERANK, "query": {"text": query},
                                "passages": [{"text": p} for p in passages], "truncate": "END"},
                          headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}", "Accept": "application/json"},
                          timeout=httpx.Timeout(timeout, connect=min(timeout, 3.0)))
    r.raise_for_status()
    return {"scores": parse_rerank(r.json(), len(passages)), "model": config.MODEL_RERANK,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def parse_json_block(text: str):
    """모델 응답에서 첫 JSON 객체를 꺼낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError("no JSON object in model output")
    blob = text[s:e + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError as err:
        # FAERS 복합제 이름(DARATUMUMAB\HYALURONIDASE)의 역슬래시를 이스케이프 없이 옮기는 경우를 고쳐 읽습니다
        if "escape" not in str(err):
            raise
        # 이미 이스케이프된 쌍(역슬래시 두 개)은 그대로 두고, 뒤에 이스케이프 문자가 없는 홑 역슬래시만 두 개로 바꿉니다
        return json.loads(re.sub(r'\\\\|\\(?![/"bfnrtu])', lambda m: m.group(0) if len(m.group(0)) == 2 else "\\\\", blob))
