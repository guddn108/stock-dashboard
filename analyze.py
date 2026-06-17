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
MODEL = "gemini-2.0-flash"

# 키 로테이션: GEMINI_API_KEY_1 → _2 → _3 순서로 사용, 한도 초과 시 다음 키로 전환
_api_keys = [k for k in [
    os.environ.get("GEMINI_API_KEY_1", ""),
    os.environ.get("GEMINI_API_KEY_2", ""),
    os.environ.get("GEMINI_API_KEY_3", ""),
    os.environ.get("GEMINI_API_KEY_4", ""),
    os.environ.get("GEMINI_API_KEY_5", ""),
] if k]
_key_idx = 0

USE_MOCK = not _api_keys
_key_idx = 0

if USE_MOCK:
    print("[analyze] GEMINI_API_KEY 없음 → Mock 모드")
    print("[analyze] GitHub Secrets에 GEMINI_API_KEY_1 설정 필요")
else:
    print(f"[analyze] Gemini API 키 {len(_api_keys)}개 로드됨 (모델: {MODEL})")
    for i, k in enumerate(_api_keys, 1):
        print(f"  키{i}: {k[:8]}...{k[-4:]}")


# ══════════════════════════════════════════
# Gemini API 호출 (키 있을 때만 실행)
# ══════════════════════════════════════════

def call_gemini(prompt: str) -> str:
    """Gemini API 호출 — 오류 발생 시 다음 키로 순서대로 전환"""
    global _key_idx
    import urllib.request
    import urllib.error

    if not _api_keys:
        return ""

    # 5개 키를 순서대로 시도
    for _ in range(len(_api_keys)):
        key = _api_keys[_key_idx]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  Gemini 응답 길이: {len(text)}자 (키{_key_idx+1})")
                return text
        except Exception as e:
            code = getattr(e, "code", "?")
            print(f"  ⚠ Gemini 오류 키{_key_idx+1} [{code}]: {e}")
            if _key_idx + 1 < len(_api_keys):
                _key_idx += 1
                print(f"  🔄 키{_key_idx+1}로 전환")
            else:
                print(f"  ⛔ 모든 키({len(_api_keys)}개) 소진 → 건너뜀")
                return ""

    return ""


def parse_json_response(text: str, fallback: dict) -> dict:
    """AI 응답에서 JSON 파싱 — 실패 시 fallback 반환"""
    if not text:
        print("  ⚠ Gemini 응답 비어있음 → fallback")
        return fallback
    try:
        # ```json ... ``` 코드블록 제거
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(cleaned[start:end])
    except Exception as e:
        print(f"  ⚠ JSON 파싱 실패: {e}")
        print(f"  응답 앞부분: {text[:200]}")
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
    "opinion", "opinionClass", "opinionProb", "opinionSummary"
]

STOCK_FALLBACK = {k: "(분석 준비 중)" for k in STOCK_ANALYSIS_KEYS}
STOCK_FALLBACK.update({"opinion": "보유", "opinionClass": "op-hold", "opinionProb": 50, "opinionSummary": "데이터 수집 중"})


def _safe(v, suffix=""):
    """None/NaN 안전 포맷"""
    if v is None:
        return "N/A"
    try:
        f = float(v)
        if f != f:
            return "N/A"
        if suffix:
            return f"{f:.2f}{suffix}"
        return str(v)
    except (TypeError, ValueError):
        return str(v) if v else "N/A"


def analyze_stock(ticker: str, name: str, stock_data: dict) -> dict:
    """종목 1개 → 28개 항목 분석"""
    if USE_MOCK:
        return _mock_stock_analysis(ticker, name, stock_data)

    fin  = stock_data.get("financials", {})
    ma   = stock_data.get("moving_averages", {})

    # 종목별 최근 뉴스 헤드라인 (yfinance)
    recent_news_titles = stock_data.get("recent_news_titles", [])
    news_block = "\n".join(f"- {t}" for t in recent_news_titles[:5]) if recent_news_titles else "없음"

    s = _safe

    data_summary = f"""
현재가: {s(stock_data.get('price'))}
전일 대비: {s(stock_data.get('change_pct'), '%')}
52주 고/저: {s(stock_data.get('high_52w'))} / {s(stock_data.get('low_52w'))}
RSI(14): {s(stock_data.get('rsi'))}
이동평균: MA20={s(ma.get('ma20'))}, MA60={s(ma.get('ma60'))}, MA200={s(ma.get('ma200'))}
지지선: {stock_data.get('support', [])}
저항선: {stock_data.get('resistance', [])}
시가총액: {s(fin.get('market_cap'))}
PER: {s(fin.get('pe_ratio'))} / Forward PER: {s(fin.get('forward_pe'))}
PBR: {s(fin.get('pb_ratio'))}
EPS: {s(fin.get('eps'))}
영업이익률: {s(fin.get('operating_margin'), '%')}
ROE: {s(fin.get('roe'), '%')}
부채비율: {s(fin.get('debt_to_equity'))}
공매도 비율: {s(fin.get('short_ratio'), '%')}
애널리스트 컨센서스 목표가: {s(fin.get('analyst_target'))}
실적 발표 예정일: {stock_data.get('earnings_dates', 'N/A')}
최근 관련 뉴스:
{news_block}
"""

    ctx = f"종목: {name} ({ticker})\n{data_summary}"

    prompt = f"""당신은 20년 경력의 기관투자자 수석 애널리스트입니다.
아래 종목의 실제 데이터를 바탕으로 분석하고, 반드시 JSON 형식으로만 답하세요.
절대 필드명을 값으로 복사하지 마세요. 모든 값은 실제 분석 내용이어야 합니다.

종목: {name} ({ticker})
{data_summary}

JSON 형식으로만 답하세요 (```json 코드블록 없이 순수 JSON):

{{
  "businessModel": "{name}의 핵심 사업 구조와 주요 수익원 2~3문장",
  "industryOutlook": "{name}이 속한 산업의 향후 2~3년 전망 2~3문장",
  "recentNews": "위 최근 뉴스 헤드라인을 기반으로 {name}에 미치는 영향 2~3문장",
  "competitors": "{name}의 주요 경쟁사 2~3곳과 {name}만의 차별점",
  "moat": "{name}의 경제적 해자 — 전환비용/네트워크효과/브랜드/원가우위 중 해당 항목과 이유",
  "aiBenefit": "AI 트렌드가 {name}에 직접/간접 수혜를 주는 메커니즘",
  "recentEarnings": "최근 분기 EPS {s(fin.get('eps'))} 기준 실적 흐름과 전년비 비교",
  "financials": "PER {s(fin.get('pe_ratio'))}x, PBR {s(fin.get('pb_ratio'))}x, ROE {s(fin.get('roe'))}, 부채비율 {s(fin.get('debt_to_equity'))} — 재무 건전성 판단",
  "valuation": "현재 PER/PBR을 업종 평균과 비교해 고평가/저평가 여부 판단",
  "institutionalFlow": "기관 보유 비중 변화와 최근 순매수/순매도 방향",
  "insiderTrading": "내부자 최근 거래 내역과 해석",
  "options": "Call/Put 비율과 주요 행사가 분포 분석 (한국주식이면 '해당없음')",
  "shortRatio": "공매도 비율 {s(fin.get('short_ratio'))}% — 높은지 낮은지, 숏스퀴즈 가능성",
  "earningsDate": "다음 실적 발표 예정일과 시장 컨센서스 EPS 예상치",
  "events": "향후 3~6개월 내 주가에 영향 줄 주요 이벤트",
  "dailyChart": "RSI {s(stock_data.get('rsi'))}, MA20={s(ma.get('ma20'))} 기준 일봉 기술적 상태",
  "weeklyChart": "MA60={s(ma.get('ma60'))} 기준 주봉 중기 추세",
  "monthlyChart": "MA200={s(ma.get('ma200'))} 기준 장기 추세",
  "support": "주요 지지선 2~3개 가격",
  "resistance": "주요 저항선 2~3개 가격",
  "fairValue": "DCF 또는 PER 기반 적정가 범위",
  "buyZone": "1차 매수 구간 / 2차 매수 구간 가격대",
  "stopLoss": "손절가와 이유",
  "target6m": "6개월 목표가와 근거",
  "target1y": "1년 목표가와 근거",
  "bullCase": "상승 시나리오 — 실현 조건, 목표가, 확률(%) 명시",
  "bearCase": "하락 시나리오 — 실현 조건, 목표가, 확률(%) 명시",
  "opinion": "매수 또는 보유 또는 매도",
  "opinionClass": "op-buy 또는 op-hold 또는 op-sell",
  "opinionProb": 확신도 숫자만 (0~100),
  "opinionSummary": "왜 지금 매수/보유/매도인지 핵심 근거 1~2문장"
}}
"""
    response = call_gemini(prompt)
    result = parse_json_response(response, STOCK_FALLBACK.copy())

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
        "opinionSummary":   f"RSI {rsi} ({rsi_comment}), MA20 대비 {'위' if price > (ma20 or 0) else '아래'} — {opinion} 구간 판단",
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
                time.sleep(5)  # 15 RPM 한도 = 최소 4초 간격

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
            try:
                stock_data["analysis"] = analyze_stock(ticker, name, stock_data)
            except Exception as e:
                print(f"  ✗ {ticker} 분석 실패: {e}")
                stock_data["analysis"] = STOCK_FALLBACK.copy()
            if not USE_MOCK:
                time.sleep(5)  # 15 RPM 한도 = 최소 4초 간격

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
