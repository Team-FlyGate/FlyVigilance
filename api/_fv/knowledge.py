"""FlyVigilance 지식 기반 판별입니다.

약과 반응의 이름을 그대로 주고, 이 약이 이 반응을 일으키는 것으로 알려져 있는지를 확률로 받습니다.
비자기회귀 판단 모델이 학습한 약물 지식(허가사항·문헌)을 쓰므로, 공인된 약물-이상반응 연관을 빠르게 알아봅니다.
참조 세트 검증(pipeline/refsets/evaluate.py)의 '지식 기반 판별'이 이 모듈의 질문과 상태를 그대로 씁니다.

역할 분담: 알려진 연관의 판별은 이 모듈이, 새 조합의 순위는 불균형 통계(SQL)가 맡고,
예측성(라벨 기재 여부)은 FDA 허가 라벨 조회가 정합니다.
"""
from . import clients

QUESTION = {"causes": {"type": "noul", "instructions": "Does this drug cause this adverse event in humans?"}}


def state(drug: str, event_label: str) -> str:
    return f"Drug: {drug.lower()}.\nAdverse event: {event_label}."


async def recognize(drug: str, event_label: str, client=None) -> dict:
    """{p, latency_ms}: 공인된 연관일 확률입니다. 집단 수준의 참고값이며 개별 사례의 인과가 아닙니다."""
    res = await clients.jev(state(drug, event_label), QUESTION, client=client)
    return {"p": round(res["answers"]["causes"]["noul"], 3), "latency_ms": res["latency_ms"],
            "mode": "knowledge", "question": QUESTION["causes"]["instructions"]}
