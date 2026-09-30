"""로컬 Whisper 로 음성을 받아 적고 낱말별 시각을 돌려줍니다(내레이션 조각 확인용).

openai-whisper 가 설치된 파이썬(uv tool)으로 실행합니다. 모델은 ~/.cache/whisper 에 받아 둔 것을 씁니다.
사용: python stt_whisper.py WAV LANG [MODEL]  →  표준 출력으로 [{"w": 낱말, "s": 시작초, "e": 끝초}, ...] JSON
"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import whisper  # noqa: E402

wav, lang = sys.argv[1], sys.argv[2]
name = sys.argv[3] if len(sys.argv) > 3 else "medium"
model = whisper.load_model(name)
r = model.transcribe(wav, language=lang, word_timestamps=True, fp16=False, condition_on_previous_text=False)
words = [{"w": w["word"], "s": round(w["start"], 2), "e": round(w["end"], 2)} for seg in r["segments"] for w in seg.get("words", [])]
print(json.dumps(words, ensure_ascii=False))
