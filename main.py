"""
main.py — 전체 파이프라인 실행
  1. collect_data.py : yfinance + RSS 뉴스 수집
  2. analyze.py      : AI 분석 (Gemini or Mock)
  3. generate_html.py: data.json → index.html 주입

실행:
  python main.py          # 전체 파이프라인
  python main.py --mock   # Mock 모드 강제 (API 키 무시)
  python main.py --step 2 # 2단계(분석)만 재실행
"""

import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ══════════════════════════════════════════
# 실행 옵션 파싱
# ══════════════════════════════════════════

args      = sys.argv[1:]
MOCK_ONLY = "--mock"  in args
START_STEP = 1

if "--step" in args:
    idx = args.index("--step")
    try:
        START_STEP = int(args[idx + 1])
    except (IndexError, ValueError):
        START_STEP = 1

if MOCK_ONLY:
    os.environ["GEMINI_API_KEY"] = ""  # analyze.py가 Mock 모드로 돌도록

DATA_PATH = os.path.join("data", "data.json")


def step(n: int, label: str):
    print(f"\n{'='*50}")
    print(f"  STEP {n}: {label}")
    print(f"{'='*50}")


def save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════
# 파이프라인
# ══════════════════════════════════════════

def main():
    start_time = time.time()
    print(f"\n[START] 투자 대시보드 업데이트 시작")
    print(f"   모드: {'Mock' if MOCK_ONLY or not os.environ.get('GEMINI_API_KEY') else 'Gemini API'}")
    print(f"   시작 단계: STEP {START_STEP}")

    # ── STEP 1: 데이터 수집
    if START_STEP <= 1:
        step(1, "데이터 수집 (yfinance + Google News RSS)")
        import collect_data
        data = collect_data.run()
        save(data)
    else:
        print(f"\n[STEP 1 건너뜀] 기존 data.json 사용")
        data = load()

    # ── STEP 2: AI 분석
    if START_STEP <= 2:
        step(2, "AI 분석")
        import analyze
        data = analyze.run(data)
        save(data)
    else:
        print(f"\n[STEP 2 건너뜀]")
        data = load()

    # ── STEP 3: HTML 생성
    if START_STEP <= 3:
        step(3, "HTML 생성 → index.html 업데이트")
        import generate_html
        generate_html.run()

    elapsed = round(time.time() - start_time, 1)
    print(f"\n{'='*50}")
    print(f"[DONE] 완료! 총 소요시간: {elapsed}초")
    print(f"   -> index.html 을 브라우저에서 열어 확인하세요.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
