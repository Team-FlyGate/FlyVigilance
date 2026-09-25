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
                   client: httpx.AsyncClient | None = None) -> dict:
    """NVIDIA NIM chat/completions. 모델 사슬을 따라 폴백하고 사고 과정은 끈다."""
    if not config.NVIDIA_API_KEY:
        raise NotConfigured("NVIDIA_API_KEY")
    own = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0))
    errors = []
    try:
        for model in models:
            for attempt in range(2):
                body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                        "temperature": temperature,
                        "chat_template_kwargs": {"enable_thinking": False}}
                t0 = time.perf_counter()
                try:
                    r = await client.post(f"{config.NIM_URL}/chat/completions", json=body,
                                          headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"})
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


def parse_json_block(text: str):
    """모델 응답에서 첫 JSON 객체를 꺼낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[s:e + 1])
