"""테스트는 네트워크와 API 키 없이 돕니다. api/ 를 import 경로에 넣습니다."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
