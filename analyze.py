"""
STAGE 5: AI 분석 모듈
- Gemini API로 뉴스 11개 항목 분석 + 종목 28개 항목 분석
- GEMINI_API_KEY 없으면 자동으로 Mock 응답 반환 (개발/테스트용)
"""

import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ══════════════════════════════════════════
# Gemini API 설정
# API 키는 환경변수에서 읽음 — 없으면 Mock 모드
# ══════════════════════════════════════════

# GEMINI_API_KEY = "여기에_키_입력"  # 직접 입력 시 주석 해제
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
USE_MOCK = not GEMINI_API_KEY

MODEL = "gemini-2.0-flash"

if USE_MOCK:
    print("[analyze] Gemini API 키 없음 → Mock 모드로 실행")
else:
    print(f"[analyze] Gemini API 연결됨 (모델: {MODEL})")


# ══════════════════════════════════════════
# Gemini API 호출 (키 있을 때만 실행)
# ══════════════════════════════════════════

def call_gemini(prompt: str, retries: int = 3) -> str:
    """Gemini API 호출 — 실패 시 재시도"""
    # import는 키 있을 때만
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }).encode("utf-8")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"  ⚠ Gemini 호출 오류 (시도 {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return ""


def parse_json_response(text: str, fallback: dict) -> dict:
    """AI 응답에서 JSON 파싱 — 실패 시 fallback 반환"""
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    print("  ⚠ JSON 파싱 실패, fallback 사용")
    return fallback


# ══════════════════════════════════════════
# 뉴스 분석 프롬프트 (11개 항목)
# ══════════════════════════════════════════

NEWS_ANALYSIS_KEYS = [
    "summary3", "why", "moneyFlow",
    "directBenefit", "indirectBenefit", "directDamage", "indirectDamage",
    "usStocks", "krStocks", "topBeneficiary", "hiddenPoint"
]

NEWS_FALLBACK = {k: "(분석 준비 중)" for k in NEWS_ANALYSIS_KEYS}


def analyze_news(title: str, summary: str) -> dict:
    """뉴스 1건 → 11개 항목 분석"""
    if USE_MOCK:
        return _mock_news_analysis(title)

    prompt = f"""
당신은 20년 경력의 기관투자자 애널리스트입니다. 다음 뉴스를 분석하고 반드시 JSON 형식으로만 답하세요.

뉴스 제목: {title}
뉴스 내용: {summary}
분석 날짜: 오늘

아래 JSON 형식을 정확히 지켜서 답하세요. 각 값은 한국어로, 2~4문장 이내로 작성하세요.

{{
  "summary3": "뉴스 핵심 3줄 요약",
  "why": "왜 지금 이런 뉴스가 나왔는지 배경과 맥락",
  "moneyFlow": "이 뉴스로 인해 돈이 어디서 어디로 이동하는지",
  "directBenefit": "직접 수혜 산업 및 이유",
  "indirectBenefit": "간접 수혜 산업 및 이유",
  "directDamage": "직접 피해 산업 및 이유",
  "indirectDamage": "간접 피해 산업 및 이유",
  "usStocks": "관련 미국 주식 티커 및 이유 (3~5개)",
  "krStocks": "관련 한국 주식 종목명(티커) 및 이유 (2~4개)",
  "topBeneficiary": "향후 1년간 가장 큰 수혜를 받을 가능성이 있는 기업 1곳과 이유",
  "hiddenPoint": "시장이 놓치고 있는 투자 포인트 — 반드시 구체적인 종목이나 섹터 언급"
}}
"""
    response = call_gemini(prompt)
    return parse_json_response(response, NEWS_FALLBACK.copy())


# ══════════════════════════════════════════
# 종목 분석 프롬프트 (28개 항목)
# ══════════════════════════════════════════

STOCK_ANALYSIS_KEYS = [
    "businessModel", "industryOutlook", "recentNews", "competitors",
    "moat", "aiBenefit", "recentEarnings", "financials", "valuation",
    "institutionalFlow", "insiderTrading", "options", "shortRatio",
    "earningsDate", "events", "dailyChart", "weeklyChart", "monthlyChart",
    "support", "resistance", "fairValue", "buyZone", "stopLoss",
    "target6m", "target1y", "bullCase", "bearCase",
    "opinion", "opinionClass", "opinionProb"
]

STOCK_FALLBACK = {k: "(분석 준비 중)" for k in STOCK_ANALYSIS_KEYS}
STOCK_FALLBACK.update({"opinion": "보유", "opinionClass": "op-hold", "opinionProb": 50})


def analyze_stock(ticker: str, name: str, stock_data: dict) -> dict:
    """종목 1개 → 28개 항목 분석"""
    if USE_MOCK:
        return _mock_stock_analysis(ticker, name, stock_data)

    # 핵심 수치 요약 (프롬프트 길이 절약)
    fin  = stock_data.get("financials", {})
    ma   = stock_data.get("moving_averages", {})
    data_summary = f"""
현재가: {stock_data.get('price')}
전일 대비: {stock_data.get('change_pct')}%
52주 고/저: {stock_data.get('high_52w')} / {stock_data.get('low_52w')}
RSI(14): {stock_data.get('rsi')}
MACD: {stock_data.get('macd')}
이동평균: MA20={ma.get('ma20')}, MA60={ma.get('ma60')}, MA200={ma.get('ma200')}
지지선: {stock_data.get('support')}
저항선: {stock_data.get('resistance')}
시가총액: {fin.get('market_cap')}
PER: {fin.get('pe_ratio')} / Forward PER: {fin.get('forward_pe')}
PBR: {fin.get('pb_ratio')}
EPS: {fin.get('eps')}
영업이익률: {fin.get('operating_margin')}
ROE: {fin.get('roe')}
부채비율: {fin.get('debt_to_equity')}
공매도 비율: {fin.get('short_ratio')}
애널리스트 목표가: {fin.get('analyst_target')}
실적 발표: {stock_data.get('earnings_dates')}
"""

    prompt = f"""
당신은 20년 경력의 기관투자자 애널리스트입니다. 다음 종목을 분석하고 반드시 JSON 형식으로만 답하세요.
오늘 날짜 기준으로 분석하며 모든 수치에 확률(%)을 포함하세요.

종목: {name} ({ticker})
데이터:
{data_summary}

아래 JSON 형식을 정확히 지켜서 답하세요. 한국어로 작성하세요.

{{
  "businessModel": "사업 모델 요약 (2~3문장)",
  "industryOutlook": "산업 전망 (2~3문장)",
  "recentNews": "최근 뉴스 영향 (2~3문장)",
  "competitors": "경쟁사 비교 (2~3문장)",
  "moat": "경제적 해자 분석 (2~3문장)",
  "aiBenefit": "AI 수혜 여부 및 정도 (2~3문장)",
  "recentEarnings": "최근 실적 분석 (2~3문장)",
  "financials": "재무제표 분석 — PER/PBR/ROE/부채비율 포함 (3~4문장)",
  "valuation": "밸류에이션 분석 — 고평가/저평가 여부 (2~3문장)",
  "institutionalFlow": "기관 매수/매도 동향 (1~2문장)",
  "insiderTrading": "내부자 매수/매도 동향 (1~2문장)",
  "options": "옵션 시장 분석 — Call/Put 비율 포함 (1~2문장, 한국주식은 해당없음)",
  "shortRatio": "공매도 비율 및 해석 (1~2문장)",
  "earningsDate": "실적 발표 일정",
  "events": "주요 이벤트 일정 (컨퍼런스, 신제품, 규제 등)",
  "dailyChart": "일봉 분석 — 이평선, RSI, MACD 기반 (2문장)",
  "weeklyChart": "주봉 분석 — 추세 방향성 (2문장)",
  "monthlyChart": "월봉 분석 — 장기 추세 (2문장)",
  "support": "주요 지지선 2~3개 (가격만 나열, 예: $410, $395)",
  "resistance": "주요 저항선 2~3개 (가격만 나열)",
  "fairValue": "적정가 계산 범위 (예: $415~440)",
  "buyZone": "분할매수 구간 (1차/2차)",
  "stopLoss": "손절가",
  "target6m": "6개월 목표가",
  "target1y": "1년 목표가",
  "bullCase": "상승 시나리오 — 조건과 목표가, 확률(%) 포함",
  "bearCase": "하락 시나리오 — 조건과 목표가, 확률(%) 포함",
  "opinion": "매수 또는 보유 또는 매도 (셋 중 하나만)",
  "opinionClass": "op-buy 또는 op-hold 또는 op-sell (opinion과 일치)",
  "opinionProb": 현재 시점 의견에 대한 확신도 0~100 사이 숫자
}}
"""
    response = call_gemini(prompt)
    result = parse_json_response(response, STOCK_FALLBACK.copy())

    # opinionProb 숫자 보정
    try:
        result["opinionProb"] = int(result["opinionProb"])
    except Exception:
        result["opinionProb"] = 50

    return result


# ══════════════════════════════════════════
# Mock 응답 (API 키 없을 때 사용)
# ══════════════════════════════════════════

def _mock_news_analysis(title: str) -> dict:
    return {
        "summary3":       f"[Mock] {title[:30]}... 핵심 3줄 요약입니다. 두 번째 줄. 세 번째 줄.",
        "why":            "[Mock] 글로벌 AI 인프라 투자 사이클 본격화로 관련 뉴스 증가.",
        "moneyFlow":      "[Mock] 채권 → 기술주·반도체로 자금 이동.",
        "directBenefit":  "[Mock] 반도체, 데이터센터",
        "indirectBenefit":"[Mock] 전력 인프라, 소재·부품",
        "directDamage":   "[Mock] 레거시 IT 서비스",
        "indirectDamage": "[Mock] 에너지 집약 산업",
        "usStocks":       "[Mock] NVDA, MSFT, AVGO",
        "krStocks":       "[Mock] 삼성전자(005930), SK하이닉스(000660)",
        "topBeneficiary": "[Mock] Nvidia — GPU 독점 + CUDA 생태계 락인",
        "hiddenPoint":    "[Mock] 전력 인프라 병목. Vertiv(VRT), Eaton(ETN) 주목.",
    }


def _mock_stock_analysis(ticker: str, name: str, data: dict) -> dict:
    price  = data.get("price", 0)
    rsi    = data.get("rsi", 50)
    ma     = data.get("moving_averages", {})
    ma20   = ma.get("ma20", price)
    sup    = data.get("support",    [round(price * 0.95, 2), round(price * 0.90, 2)])
    res    = data.get("resistance", [round(price * 1.05, 2), round(price * 1.10, 2)])
    fin    = data.get("financials", {})
    per    = fin.get("pe_ratio", "N/A")
    target = fin.get("analyst_target") or round(price * 1.15, 2)

    trend  = "상승" if price > (ma20 or price) else "하락"
    rsi_comment = "과매수 주의" if rsi and rsi > 70 else ("과매도 저점 탐색" if rsi and rsi < 30 else "중립")

    opinion      = "매수"   if rsi and rsi < 45 else ("매도"   if rsi and rsi > 75 else "보유")
    opinion_cls  = "op-buy" if opinion == "매수" else ("op-sell" if opinion == "매도" else "op-hold")
    opinion_prob = 70 if opinion == "매수" else (65 if opinion == "매도" else 55)

    is_kr = ticker.endswith(".KS")
    currency = "₩" if is_kr else "$"

    return {
        "businessModel":    f"[Mock] {name}의 핵심 사업 모델 요약.",
        "industryOutlook":  f"[Mock] {name} 속한 산업 중기 전망 긍정적.",
        "recentNews":       f"[Mock] 최근 뉴스가 {name}에 미치는 영향 분석.",
        "competitors":      f"[Mock] {name} 경쟁사 비교 및 차별점.",
        "moat":             f"[Mock] {name} 경제적 해자 — 브랜드/기술/규모의 경제.",
        "aiBenefit":        f"[Mock] AI 수혜 여부: {'직접 수혜' if ticker in ['NVDA','MSFT','GOOGL','AVGO','TSM'] else '간접 수혜'}.",
        "recentEarnings":   f"[Mock] 최근 분기 실적 분석.",
        "financials":       f"[Mock] PER {per}x, 재무 건전성 분석.",
        "valuation":        f"[Mock] 현재 밸류에이션 적정 여부 판단.",
        "institutionalFlow":"[Mock] 기관 최근 3개월 매수/매도 동향.",
        "insiderTrading":   "[Mock] 내부자 최근 거래 내역.",
        "options":          "[Mock] 해당없음 (한국주식)" if is_kr else "[Mock] Call/Put 비율 분석.",
        "shortRatio":       f"[Mock] 공매도 비율 {fin.get('short_ratio', 'N/A')}%.",
        "earningsDate":     "[Mock] 다음 실적 발표 일정.",
        "events":           "[Mock] 주요 이벤트 일정.",
        "dailyChart":       f"[Mock] 일봉: MA20 대비 {'위' if price > (ma20 or 0) else '아래'}, RSI {rsi} ({rsi_comment}).",
        "weeklyChart":      f"[Mock] 주봉: 중기 {trend} 추세.",
        "monthlyChart":     "[Mock] 월봉: 장기 추세 분석.",
        "support":          ", ".join([f"{currency}{v}" for v in sup]),
        "resistance":       ", ".join([f"{currency}{v}" for v in res]),
        "fairValue":        f"{currency}{round(price * 0.95, 2)} ~ {currency}{round(price * 1.15, 2)}",
        "buyZone":          f"1차 {currency}{sup[0] if sup else round(price*0.95,2)}, 2차 {currency}{sup[1] if len(sup)>1 else round(price*0.90,2)}",
        "stopLoss":         f"{currency}{round(price * 0.88, 2)}",
        "target6m":         f"{currency}{round(float(target) * 0.95, 2)}",
        "target1y":         f"{currency}{target}",
        "bullCase":         f"[Mock] 상승 시나리오: {currency}{round(price*1.25,2)} (확률 30%)",
        "bearCase":         f"[Mock] 하락 시나리오: {currency}{round(price*0.80,2)} (확률 20%)",
        "opinion":          opinion,
        "opinionClass":     opinion_cls,
        "opinionProb":      opinion_prob,
    }


# ══════════════════════════════════════════
# 전체 분석 실행
# ══════════════════════════════════════════

def run(data: dict) -> dict:
    """data.json 전체를 분석하여 결과 반환"""
    print(f"\n[AI 분석 시작] 모드: {'Mock' if USE_MOCK else 'Gemini API'}")

    # ── 뉴스 분석
    print("\n뉴스 분석 중...")
    for region in ("kr", "us"):
        articles = data.get("news", {}).get(region, [])
        for i, article in enumerate(articles):
            print(f"  {region.upper()} 뉴스 {i+1}/{len(articles)}: {article['title'][:40]}...")
            article["analysis"] = analyze_news(article["title"], article.get("summary", ""))
            if not USE_MOCK:
                time.sleep(1)  # API rate limit

    # ── 종목 분석
    print("\n종목 분석 중...")
    for group in ("watchlist", "holdings"):
        stocks = data.get("stocks", {}).get(group, {})
        total  = len(stocks)
        for idx, (ticker, stock_data) in enumerate(stocks.items(), 1):
            name = stock_data.get("name", ticker)
            if stock_data.get("error"):
                print(f"  [{idx}/{total}] {ticker} 건너뜀 (데이터 오류)")
                continue
            print(f"  [{idx}/{total}] {ticker} ({name}) 분석 중...")
            stock_data["analysis"] = analyze_stock(ticker, name, stock_data)
            if not USE_MOCK:
                time.sleep(1.5)  # API rate limit

    print("\n✅ 분석 완료")
    return data


if __name__ == "__main__":
    data_path = os.path.join("data", "data.json")
    if not os.path.exists(data_path):
        print("❌ data/data.json 없음. 먼저 collect_data.py를 실행하세요.")
    else:
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        result = run(data)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ 분석 결과 저장: {data_path}")
