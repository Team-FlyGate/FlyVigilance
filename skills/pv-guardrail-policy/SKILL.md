---
name: "pv-guardrail-policy"
title: "PV Guardrail Policy"
version: "1.0.0"
description: "Use when configuring or changing the FlyVigilance content-safety policy: the pharmacovigilance BYO policy (PV-1..PV-5 on top of the relevant Nemotron Content Safety V2 categories) that runs on nvidia/nemotron-3.5-content-safety via chat_template_kwargs.custom_policy, next to the stock Llama-3.1 Nemotron Safety Guard 8B v3. Do not use to judge a claim by hand; the critic calls the guards."
license: "Apache-2.0"
compatibility: "nvidia/nemotron-3.5-content-safety (custom_policy + /categories) and nvidia/llama-3.1-nemotron-safety-guard-8b-v3 via NVIDIA NIM integrate.api.nvidia.com/v1/chat/completions; Python 3.11+ with httpx; jsonschema for the policy schema test."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "critic guard (BYO safety policy)"
  model: "nvidia/nemotron-3.5-content-safety + nvidia/llama-3.1-nemotron-safety-guard-8b-v3"
  domain: "pharmacovigilance"
  based_on: "NVIDIA/skills nemotron-policy-generator v0.1.0"
  tags:
    - guardrails
    - nemotron-content-safety
    - byo-policy
    - custom-policy
    - pharmacovigilance
---

# PV Guardrail Policy

FlyVigilance 가 쓰는 약물감시 평가 메모의 주장 하나하나를 NVIDIA Nemotron 안전 가드 두 개로 검사하는 정책입니다.
정책은 NVIDIA 공식 Agent Skill `NVIDIA/skills nemotron-policy-generator` v0.1.0 의 6단계 워크플로를 그대로 따라 만들었습니다
(입력 분류 → V2 대응 판정 `v2_plus_custom` → 범주별 전체 필드 → 공통 절 → Markdown/JSON/프롬프트 생성 → 저장).

## 산출물

| 파일 | 내용 |
|---|---|
| `policy_taxonomy.json` | 범주 13개(사용자 정의 PV-1..PV-5 = S23..S27, V2 기반 8개)의 전체 필드. 생성기 스킬의 `assets/policy_json_schema.json` 으로 검증합니다 |
| `policy.md` | 서명용 정책 문서입니다. 생성기의 `policy_md_template.md` 절 구성(Assumptions, Allow-list, Refusal, Jurisdiction, Calibration, Categories, CoT, Change log)을 따릅니다 |
| `system_prompt.txt` | Nemotron-3.5 에 보내는 BYO 정책 문자열입니다. 생성기의 PATTERN E(범주 이름 + Allow-list)를 모델 카드의 custom_policy 머리말 안에 넣었습니다 |
| `render_policy.py` | JSON 에서 `policy.md`, `system_prompt.txt`, 배포용 사본 `api/_data/pv_guard_policy.txt` 를 만듭니다. `--check` 는 어긋남만 확인합니다 |
| `schema/policy_json_schema.json` | 생성기 스킬의 스키마 사본입니다(Apache-2.0, NVIDIA) |
| `evals/evals.json` | 생성기의 evals 형식(id, question, ground_truth, expected_behavior)을 따른 PV 범주별 손작성 주장 50개입니다(범주마다 위반 6, 인접 정상 4). 정책 보정에 쓰지 않은 보류 세트입니다 |

## 범주

| Sn | 범주 | 심각도 | V2 상위 범주 | FlyVigilance 규칙 | 집행 층 |
|---|---|---|---|---|---|
| S23 | PV-1 Individual Treatment Advice | S3 | Unauthorized Advice | R11 | 텍스트 분류기 |
| S24 | PV-2 Disproportionality Overclaim | S2 | Political/Misinformation/Conspiracy | R1 (R3, R4 포함) | 텍스트 분류기 |
| S25 | PV-3 Incidence Estimate from Spontaneous Reports | S2 | Political/Misinformation/Conspiracy | R2 | 텍스트 분류기 |
| S26 | PV-4 Re-identification of Reporter or Patient | S3 | PII/Privacy | PV-4 | 텍스트 분류기 + 런타임 |
| S27 | PV-5 Tool or Network Use Outside Allowed Hosts | S3 | Malware | PV-5 | 런타임(분류기는 보조) |

V2 기반으로는 약물감시 메모에 실제로 나올 수 있는 여덟 범주(S5, S6, S7, S9, S13, S15, S18, S20)만 정책 안에 둡니다.
나머지 V2 범주는 함께 도는 Safety Guard 8B v3 의 기본 분류 체계가 맡습니다. S7 은 생성기의 비협상 하한에 따라 S4 로 고정합니다.

PV-5 의 1차 집행은 에이전트 런타임의 호스트 허용 목록과 감사 기록입니다. 허용 호스트는
`api.fda.gov`, `eutils.ncbi.nlm.nih.gov`, `api.typesafe.ai`, `integrate.api.nvidia.com` 입니다.

## 모델에 정책을 넣는 방법

build.nvidia.com 의 `nvidia/nemotron-3.5-content-safety` 는 chat template 인자로 정책을 받습니다.

```json
{"model": "nvidia/nemotron-3.5-content-safety",
 "messages": [{"role": "user", "content": "<메모 주장 하나>"}],
 "max_tokens": 60, "temperature": 0,
 "chat_template_kwargs": {"custom_policy": "<system_prompt.txt>", "request_categories": "/categories", "enable_thinking": false}}
```

- 응답은 `User Safety: unsafe` 와 `Safety Categories: PV-2` 형식입니다. 범주는 `PV-3` 처럼 번호로 오기도 하고 번호 없는 이름으로 오기도 합니다.
- 이 모델의 chat template 은 system 메시지를 버립니다. 정책을 system 메시지로 보내면 조용히 무시되므로 반드시 `custom_policy` 로 보냅니다.
- `custom_taxonomy`(범주 목록만 넣는 모드)도 있지만 시험 입력에서 사용자 정의 범주를 따르지 않아 쓰지 않습니다.
- 주장을 user 차례로 보낸 경우가 assistant 차례로 보낸 경우보다 정책 예시에서 재현율이 높았습니다(23/29 대 16/29).

## 런타임 연결 (`api/_fv/assess.py`)

- `policy_guard(text)` 가 위 요청을 `clients.nim_chat(..., template_kwargs=...)` 로 보내고 `parse_policy_guard` 로 읽습니다.
- `guard_claims` 는 주장마다 기본 가드 `guard()`(Safety Guard 8B v3, 실패 시 Nemotron-3.5 기본 분류 체계)와 `policy_guard()` 를 동시에 부릅니다. 단계 전체가 `timeout_s`(기본 20초) 안에서 끝납니다.
- 둘 중 하나라도 걸면 반려합니다. 어느 쪽도 걸지 않았는데 한쪽이라도 판정을 못 냈으면 '사람 확인'으로 둡니다.
- 결과에는 `by_guard`(가드별 flagged/unchecked)와 `fired`(주장, 가드, 범주, PV 번호)가 붙습니다. `guard_issues` 는 PV 범주를 규칙 코드(R1/R2/R11/PV-4/PV-5)로 바꿔 작성자에게 돌려줍니다.

## 측정 (`pipeline/bench/guard_policy_eval.py` → `web/public/data/guard_policy_eval.json`)

가드 층만 돌렸습니다. 저장된 주입 테스트 주장(`critic_probe.json`, 8개 케이스)과 `evals/evals.json` 50개를 씁니다.

주입 테스트 검출 수(걸린 수 / 주장 수):

| 주입 | Safety Guard 8B v3 기본 | Nemotron-3.5 기본 | Nemotron-3.5 + PV 정책 | 배포 결합(8B v3 또는 PV 정책) |
|---|---|---|---|---|
| p1 PRR → 인과 주장 | 0/7 | 2/7 | 7/7 | 7/7 |
| p2 지어낸 발생률 | 0/8 | 2/8 | 8/8 | 8/8 |
| p3 가짜 근거 ID | 0/8 | 0/8 | 0/8 | 0/8 |
| p4 치료 조언 | 8/8 | 8/8 | 8/8 | 8/8 |
| 대조군 오검출 | 0/6 | 0/6 | 1/6 | 1/6 |

p3 는 문장만 보면 정상이라 텍스트 가드의 대상이 아닙니다. 크리틱 1단(근거 ID 대조)이 8/8 을 잡습니다.
대조군 오검출 1건은 영아 사망 사례 문장을 PII/Privacy 로 본 것입니다.

PV 손작성 평가 정확도(재현율, 인접 정상 오검출률):

| 범주 | 8B v3 기본 | Nemotron-3.5 기본 | + PV 정책 (/no_think, 배포) | + PV 정책 (/think) |
|---|---|---|---|---|
| PV-1 | 0.60 (0.50, 0.25) | 1.00 (1.00, 0.00) | 0.90 (1.00, 0.25) | 0.90 (1.00, 0.25) |
| PV-2 | 0.40 (0.00, 0.00) | 0.50 (0.17, 0.00) | 0.90 (0.83, 0.00) | 1.00 (1.00, 0.00) |
| PV-3 | 0.40 (0.00, 0.00) | 0.40 (0.00, 0.00) | 0.40 (0.17, 0.25) | 0.67 (0.60, 0.25) |
| PV-4 | 0.90 (0.83, 0.00) | 0.90 (0.83, 0.00) | 1.00 (1.00, 0.00) | 0.90 (0.83, 0.00) |
| PV-5 | 0.60 (0.33, 0.00) | 0.80 (0.67, 0.00) | 1.00 (1.00, 0.00) | 1.00 (1.00, 0.00) |
| 전체 | 0.58 (0.33, 0.05) | 0.72 (0.53, 0.00) | 0.84 (0.80, 0.10) | 0.90 (0.90, 0.10) |

지연 중앙값은 8B v3 692 ms, Nemotron-3.5 기본 356 ms, PV 정책 /no_think 459 ms, /think 4,292 ms 입니다.
/think 는 한 건의 판정을 읽지 못해 49건 기준입니다. 배포는 지연을 고려해 /no_think 로 둡니다.
가장 큰 개선 여지는 PV-3(환자 단위 발생률 문장)입니다. 다음 판(v1.1.0)에서 PV-3 정의와 예시를 보강하고 /think 전환을 함께 재는 것이 다음 순서입니다.

## 정책을 고칠 때

1. `policy_taxonomy.json` 을 고치고 `version` 을 올립니다(semantic versioning).
2. `.venv/bin/python skills/pv-guardrail-policy/render_policy.py` 로 문서와 프롬프트를 다시 만듭니다.
3. `FV_CACHE_DIR=data/cache/api .venv/bin/python pipeline/bench/guard_policy_eval.py` 로 다시 잽니다.
4. `assess.PV_CATEGORIES` 와 `PV_POLICY_NAME` 을 맞추고 `.venv/bin/python -m pytest -q tests` 를 돌립니다. `tests/test_guard_policy.py` 가 스키마, 동기화, 대응표를 확인합니다.
