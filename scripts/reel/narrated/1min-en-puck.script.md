# FlyGate 1분 소개 영상 v1.0.0 대본

- 영상: `web/public/showreel/FlyGate_intro_1min_v1.0.0-en.html` (1920×1080) · `web/public/showreel/FlyGate_intro_1min_vertical_v1.0.0-en.html` (1080×1920) · 30fps · 음원 `scripts/reel/narrated/1min-en-puck.m4a` · 영어 내레이션
- **총 길이 63.4초** · 내레이션 Gemini TTS(gemini-3.8-flash-tts) Puck · 빌더 `scripts/build_short_v1.py`
- 수치(저장소 JSON): FDA 한 분기 422,459건(하루 평균 약 4,600건) · 결과 코드를 가린 FAERS 실제 사례 440건 · 놓친 중대 사례 16 → 3 · 걸러지지 않은 비중대 사례 68 → 3 · 재도킹 RMSD 0.71 Å · 결합 세기 순위 상관 0.767(39종)
- 첫 0.5초는 포스터(썸네일)입니다.

| 장면 | 시각 | 내레이션 |
| --- | --- | --- |
| hook | 0.5–6.4초 | The US FDA receives about 4,600 adverse-event reports on marketed drugs every day. |
| problem | 6.4–14.3초 | Serious reactions, like deaths and hospitalizations, must be checked by a person, but with mechanical filtering they can get buried under countless reports and missed. |
| intro | 14.3–23.3초 | FlyGate applies the structure of the fruit-fly brain connectome and a fast judgment model to verify, on evidence, everything from a new drug's target binding to its side effects after launch. |
| step1 | 23.3–31.3초 | During drug development, FlyGate uses NVIDIA BioNeMo's OpenFold3, DiffDock and Boltz-2 to predict how a drug binds its target protein. |
| gate | 31.3–41.8초 | After launch, FlyGate's fast, efficient judgment model answers seven questions for every adverse-event report in 0.3 seconds, and when expert review is needed, NVIDIA Nemotron evaluates it with cited evidence. |
| proof | 41.8–52.2초 | On 440 real reports, mechanical filtering missed 16 serious cases; FlyGate missed only 3. Unimportant cases that were not filtered out also fell from 68 to 3. |
| stack | 52.2–58.7초 | Our team built all of this into the FlyGate CLI, so each step runs with one command inside an NVIDIA NemoClaw sandbox. |
| cta | 58.7–63.4초 | From molecule to patient, evidence before inference. FlyGate. |
