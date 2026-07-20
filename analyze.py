"""
STAGE 5: AI 분석 모듈
- Groq API로 뉴스 11개 항목 분석 + 종목 28개 항목 분석
- GROQ_API_KEY 없으면 자동으로 Mock 응답 반환 (개발/테스트용)
"""

import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ══════════════════════════════════════════
# Groq API 설정
# API 키는 환경변수에서 읽음 — 없으면 Mock 모드
# ══════════════════════════════════════════

MODEL = "llama-3.3-70b-versatile"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
USE_MOCK = not GROQ_API_KEY

if USE_MOCK:
    print("[analyze] GROQ_API_KEY 없음 → Mock 모드")
    print("[analyze] GitHub Secrets에 GROQ_API_KEY 설정 필요")
else:
    print(f"[analyze] Groq API 키 로드됨 (모델: {MODEL})")
    print(f"  키: {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:]}")


# ══════════════════════════════════════════
# Groq API 호출
# ══════════════════════════════════════════

def call_groq(prompt: str) -> str:
    """Groq API 호출 — 429 시 자동 대기 후 재시도"""
    import urllib.request
    import urllib.error

    if not GROQ_API_KEY:
        return ""

    url  = "https://api.groq.com/openai/v1/chat/completions"
    body = json.dumps({
        "model":    MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens":  4096,
    }).encode("utf-8")

    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "User-Agent":    "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                text   = result["choices"][0]["message"]["content"]
                print(f"  Groq 응답 길이: {len(text)}자")
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 20 * (attempt + 1)
                print(f"  ⚠ 429 한도 초과 → {wait}초 대기 후 재시도 ({attempt+1}/3)")
                time.sleep(wait)
            else:
                print(f"  ✗ Groq 오류 [{e.code}]: {e}")
                return ""
        except Exception as e:
            print(f"  ✗ Groq 오류: {e}")
            return ""

    print("  ✗ 재시도 모두 실패 → Mock 응답 사용")
    return ""


def parse_json_response(text: str, fallback: dict) -> dict:
    """AI 응답에서 JSON 파싱 — 실패 시 fallback 반환"""
    if not text:
        print("  ⚠ 응답 비어있음 → fallback")
        return fallback
    try:
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
    "simpleSummary", "summary3", "why", "moneyFlow",
    "directBenefit", "indirectBenefit", "directDamage", "indirectDamage",
    "usStocks", "krStocks", "topBeneficiary", "hiddenPoint"
]

NEWS_FALLBACK = {k: "(분석 준비 중)" for k in NEWS_ANALYSIS_KEYS}


def analyze_news(title: str, summary: str) -> dict:
    """뉴스 1건 → 12개 항목 분석"""
    if USE_MOCK:
        return _mock_news_analysis(title)

    prompt = f"""
당신은 20년 경력의 기관투자자 애널리스트입니다. 다음 뉴스를 분석하고 반드시 JSON 형식으로만 답하세요.

뉴스 제목: {title}
뉴스 내용: {summary}
분석 날짜: 오늘

아래 JSON 형식을 정확히 지켜서 답하세요. 각 값은 한국어로, 2~4문장 이내로 작성하세요.

{{
  "simpleSummary": "초등학생도 이해할 수 있는 아주 쉬운 말로, 이 뉴스가 왜 중요한지 1문장 (전문 용어·티커 없이)",
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
    response = call_groq(prompt)
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
    "opinion", "opinionClass", "opinionProb", "opinionSimple", "opinionSummary"
]

STOCK_FALLBACK = {k: "(분석 준비 중)" for k in STOCK_ANALYSIS_KEYS}
STOCK_FALLBACK.update({
    "opinion": "보유", "opinionClass": "op-hold", "opinionProb": 50,
    "opinionSimple": "데이터를 모으고 있어요. 조금만 기다려주세요.",
    "opinionSummary": "데이터 수집 중",
})


def _safe(v, suffix=""):
    """None/NaN 안전 포맷"""
    if v is None:
        return "정보없음"
    try:
        f = float(v)
        if f != f:
            return "정보없음"
        if suffix:
            return f"{f:.2f}{suffix}"
        return str(v)
    except (TypeError, ValueError):
        return str(v) if v else "정보없음"


# ══════════════════════════════════════════
# 기술적 신호 → 매수/보유/매도 (규칙 기반, AI 관여 없음)
# 일봉(MA20) · 주봉(주간 MA20) · 월봉(월간 MA12) · MACD 4개 신호의
# 정합성으로 opinion/opinionProb를 계산하고, RSI 과열/과매도로 보정한다.
# ══════════════════════════════════════════

def compute_technical_signal(stock_data: dict) -> dict:
    price        = stock_data.get("price")
    rsi          = stock_data.get("rsi")
    ma           = stock_data.get("moving_averages", {}) or {}
    ma20         = ma.get("ma20")
    weekly_ma20  = stock_data.get("weekly_ma20")
    monthly_ma12 = stock_data.get("monthly_ma12")
    macd_hist    = (stock_data.get("macd") or {}).get("hist")
    stoch        = stock_data.get("stochastic") or {}
    stoch_k, stoch_d = stoch.get("k"), stoch.get("d")
    volume_ratio = stock_data.get("volume_ratio")

    def trend_of(ref):
        if price is None or ref is None:
            return None
        return "상승" if price > ref else "하락"

    daily_trend   = trend_of(ma20)
    weekly_trend  = trend_of(weekly_ma20)
    monthly_trend = trend_of(monthly_ma12)
    macd_trend    = None if macd_hist is None else ("상승" if macd_hist > 0 else "하락")
    stoch_trend   = None if stoch_k is None or stoch_d is None else ("상승" if stoch_k > stoch_d else "하락")

    # 일봉/주봉/월봉 추세 + MACD + 스토캐스틱, 5개 신호의 정합성으로 매수/보유/매도를 결정한다.
    # (RSI는 방향 투표에 넣지 않고, 과매수·과매도 구간일 때 확신도를 보정하는 용도로만 쓴다 — 이미 MACD/스토캐스틱이
    #  방향을 담당하므로 RSI까지 투표에 넣으면 "과열 경고" 역할과 "방향 투표" 역할이 겹친다.)
    signals   = {"일봉": daily_trend, "주봉": weekly_trend, "월봉": monthly_trend, "MACD": macd_trend, "스토캐스틱": stoch_trend}
    available = [v for v in signals.values() if v is not None]
    bull_count = sum(1 for v in available if v == "상승")
    total      = len(available)
    bull_ratio = (bull_count / total) if total else 0.5

    if total == 0 or 0.25 < bull_ratio < 0.75:
        opinion, opinion_cls, prob = "보유", "op-hold", 50
    elif bull_ratio >= 0.75:
        opinion, opinion_cls, prob = "매수", "op-buy", 85 if bull_ratio == 1 else 75
    else:
        opinion, opinion_cls, prob = "매도", "op-sell", 85 if bull_ratio == 0 else 75

    rsi_zone = None
    if rsi is not None:
        rsi_zone = "과매수" if rsi > 70 else ("과매도" if rsi < 30 else "중립")

    caveat = ""
    if rsi_zone == "과매수":
        if opinion == "매수":
            prob -= 10
            caveat = " 다만 RSI 과매수 구간이라 단기 조정 가능성에 유의."
        elif opinion == "매도":
            prob += 5
            caveat = " RSI 과매수까지 겹쳐 고점 매도 명분 강화."
    elif rsi_zone == "과매도":
        if opinion == "매도":
            prob -= 10
            caveat = " 다만 RSI 과매도 구간이라 기술적 반등 가능성에 유의."
        elif opinion == "매수":
            prob += 5
            caveat = " RSI 과매도까지 겹쳐 저점 매수 명분 강화."

    # 거래량은 방향 투표가 아니라 "그 방향에 실제 힘이 실렸는지" 확인하는 확신도 보정치.
    vol_zone = None
    vol_note = ""
    if volume_ratio is not None:
        vol_zone = "증가" if volume_ratio >= 1.15 else ("감소" if volume_ratio <= 0.85 else "보통")
        if opinion in ("매수", "매도"):
            if vol_zone == "증가":
                prob += 5
                vol_note = " 최근 거래량도 평균 대비 늘어 추세에 힘이 실림."
            elif vol_zone == "감소":
                prob -= 5
                vol_note = " 다만 거래량이 평균보다 줄어 추세 힘은 약한 편."

    prob = max(30, min(95, prob))

    def fmt(v):
        if v is None:
            return "정보없음"
        return f"{v:,.2f}" if isinstance(v, (int, float)) else str(v)

    detail = ", ".join(f"{label}{'↑' if v == '상승' else '↓'}" for label, v in signals.items() if v is not None)
    summary = f"기술 신호 {bull_count}/{total} 상승 ({detail}) → {opinion} (확신도 {prob}%).{caveat}{vol_note}" if total else \
              f"기술 지표 데이터 부족 → 판단 보류 (확신도 {prob}%)."

    # opinionSummary는 근거를 다 보고 싶을 때 볼 상세판, opinionSimple은 화면 맨 위에 항상 보이는
    # 쉬운말 한 줄 — 같은 판단을 쉬운 말로만 옮긴 것이라 서로 절대 모순되면 안 된다.
    if total == 0:
        plain = "기술 지표 데이터가 부족해서 판단을 보류했어요."
    elif opinion == "매수":
        plain = "여러 지표가 대부분 좋은 방향을 가리키고 있어서 지금은 사기 좋은 흐름이에요." if prob >= 80 \
            else "전체적으로 나쁘지 않은 흐름이라 매수 쪽으로 보여요."
        if rsi_zone == "과매수":
            plain += " 다만 최근 너무 빨리 올라서 잠깐 쉬어갈 수 있으니 서두르지 마세요."
        elif rsi_zone == "과매도":
            plain += " 많이 떨어졌다가 이제 막 돌아서는 시점이라 기회로 보여요."
        if vol_zone == "증가":
            plain += " 거래량도 늘고 있어서 힘이 실려 있어요."
        elif vol_zone == "감소":
            plain += " 다만 거래량이 적어서 힘은 약한 편이에요."
    elif opinion == "매도":
        plain = "여러 지표가 대부분 안 좋은 방향을 가리키고 있어서 지금은 조심하는 게 좋아요." if prob >= 80 \
            else "전체적으로 좋지 않은 흐름이라 매도 쪽으로 보여요."
        if rsi_zone == "과매도":
            plain += " 다만 너무 많이 떨어져서 곧 반등할 수 있으니 성급한 매도는 주의하세요."
        elif rsi_zone == "과매수":
            plain += " 많이 올랐다가 이제 꺾이는 시점이라 더 조심해야 해요."
        if vol_zone == "증가":
            plain += " 거래량도 늘고 있어서 하락에 힘이 실려 있어요."
        elif vol_zone == "감소":
            plain += " 다만 거래량이 적어서 힘은 약한 편이에요."
    else:
        plain = "오를지 내릴지 신호가 엇갈리고 있어서, 지금은 서두르지 않고 지켜보는 게 좋아요."

    return {
        "dailyChart":   f"현재가 {fmt(price)} vs 일봉 MA20 {fmt(ma20)} → {daily_trend or '정보없음'} · RSI {fmt(rsi)}({rsi_zone or '정보없음'}) · MACD {macd_trend or '정보없음'} · Stoch %K/%D {fmt(stoch_k)}/{fmt(stoch_d)}({stoch_trend or '정보없음'})",
        "weeklyChart":  f"현재가 {fmt(price)} vs 주간 MA20(20주선) {fmt(weekly_ma20)} → {weekly_trend or '정보없음'} · 거래량(5일/20일) 비율 {fmt(volume_ratio)}({vol_zone or '정보없음'})",
        "monthlyChart": f"현재가 {fmt(price)} vs 월간 MA12(12개월선) {fmt(monthly_ma12)} → {monthly_trend or '정보없음'}",
        "opinion":      opinion,
        "opinionClass": opinion_cls,
        "opinionProb":  prob,
        "opinionSimple":  plain,
        "opinionSummary": summary,
    }


def analyze_stock(ticker: str, name: str, stock_data: dict) -> dict:
    """종목 1개 → 28개 항목 분석. 매수/보유/매도 판단과 일/주/월봉 요약은
    AI가 아니라 compute_technical_signal()의 규칙 기반 계산이 전담한다."""
    technical = compute_technical_signal(stock_data)

    if USE_MOCK:
        result = _mock_stock_analysis(ticker, name, stock_data)
        result.update(technical)
        return result

    fin  = stock_data.get("financials", {})
    ma   = stock_data.get("moving_averages", {})

    recent_news_titles = stock_data.get("recent_news_titles", [])
    news_block = "\n".join(f"- {t}" for t in recent_news_titles[:5]) if recent_news_titles else "없음"

    s = _safe

    data_summary = f"""
현재가: {s(stock_data.get('price'))}
전일 대비: {s(stock_data.get('change_pct'), '%')}
52주 고/저: {s(stock_data.get('high_52w'))} / {s(stock_data.get('low_52w'))}
RSI(14): {s(stock_data.get('rsi'))}
이동평균: MA20={s(ma.get('ma20'))}, MA60={s(ma.get('ma60'))}, MA200={s(ma.get('ma200'))}
주간 MA20(20주선): {s(stock_data.get('weekly_ma20'))} / 월간 MA12(12개월선): {s(stock_data.get('monthly_ma12'))}
MACD: {s((stock_data.get('macd') or {}).get('macd'))} / Signal: {s((stock_data.get('macd') or {}).get('signal'))} / Hist: {s((stock_data.get('macd') or {}).get('hist'))}
스토캐스틱 %K/%D: {s((stock_data.get('stochastic') or {}).get('k'))} / {s((stock_data.get('stochastic') or {}).get('d'))}
거래량(5일/20일 평균) 비율: {s(stock_data.get('volume_ratio'))}
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
실적 발표 예정일: {stock_data.get('earnings_dates', '정보없음')}
최근 관련 뉴스:
{news_block}

[기술적 신호 결론 — 아래 결론에 부합하도록 bullCase/bearCase/target6m/target1y/stopLoss/fairValue를 작성하세요]
{technical['opinionSummary']}
"""

    prompt = f"""당신은 20년 경력의 기관투자자 수석 애널리스트입니다.
아래 종목의 실제 데이터를 바탕으로 분석하고, 반드시 JSON 형식으로만 답하세요.
절대 필드명을 값으로 복사하지 마세요. 모든 값은 실제 분석 내용이어야 합니다.
매수/보유/매도 최종 판단은 이미 규칙 기반으로 확정되어 있으니 아래 항목들만 작성하세요.

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
  "support": "주요 지지선 2~3개 가격",
  "resistance": "주요 저항선 2~3개 가격",
  "fairValue": "DCF 또는 PER 기반 적정가 범위",
  "buyZone": "1차 매수 구간 / 2차 매수 구간 가격대",
  "stopLoss": "손절가와 이유",
  "target6m": "6개월 목표가와 근거",
  "target1y": "1년 목표가와 근거",
  "bullCase": "상승 시나리오 — 실현 조건, 목표가, 확률(%) 명시",
  "bearCase": "하락 시나리오 — 실현 조건, 목표가, 확률(%) 명시"
}}
"""
    response = call_groq(prompt)
    result   = parse_json_response(response, STOCK_FALLBACK.copy())
    result.update(technical)
    return result


# ══════════════════════════════════════════
# Mock 응답 (API 키 없을 때 사용)
# ══════════════════════════════════════════

def _mock_news_analysis(title: str) -> dict:
    return {
        "simpleSummary":  "(샘플) 이런 뉴스가 나오면 관련된 회사들의 주가가 오르거나 내릴 수 있어요.",
        "summary3":       f"(샘플) {title[:30]}... 핵심 3줄 요약입니다. 두 번째 줄. 세 번째 줄.",
        "why":            "(샘플) 글로벌 AI 인프라 투자 사이클 본격화로 관련 뉴스 증가.",
        "moneyFlow":      "(샘플) 채권 → 기술주·반도체로 자금 이동.",
        "directBenefit":  "(샘플) 반도체, 데이터센터",
        "indirectBenefit":"(샘플) 전력 인프라, 소재·부품",
        "directDamage":   "(샘플) 레거시 IT 서비스",
        "indirectDamage": "(샘플) 에너지 집약 산업",
        "usStocks":       "(샘플) NVDA, MSFT, AVGO",
        "krStocks":       "(샘플) 삼성전자(005930), SK하이닉스(000660)",
        "topBeneficiary": "(샘플) Nvidia — GPU 독점 + CUDA 생태계 락인",
        "hiddenPoint":    "(샘플) 전력 인프라 병목. Vertiv(VRT), Eaton(ETN) 주목.",
    }


def _mock_stock_analysis(ticker: str, name: str, data: dict) -> dict:
    price  = data.get("price", 0)
    sup    = data.get("support",    [round(price * 0.95, 2), round(price * 0.90, 2)])
    res    = data.get("resistance", [round(price * 1.05, 2), round(price * 1.10, 2)])
    fin    = data.get("financials", {})
    per    = fin.get("pe_ratio", "정보없음")
    target = fin.get("analyst_target") or round(price * 1.15, 2)
    is_kr        = ticker.endswith(".KS")
    currency     = "₩" if is_kr else "$"

    return {
        "businessModel":    f"(샘플) {name}의 핵심 사업 모델 요약.",
        "industryOutlook":  f"(샘플) {name} 속한 산업 중기 전망 긍정적.",
        "recentNews":       f"(샘플) 최근 뉴스가 {name}에 미치는 영향 분석.",
        "competitors":      f"(샘플) {name} 경쟁사 비교 및 차별점.",
        "moat":             f"(샘플) {name} 경제적 해자 — 브랜드/기술/규모의 경제.",
        "aiBenefit":        f"(샘플) AI 수혜 여부: {'직접 수혜' if ticker in ['NVDA','MSFT','GOOGL','AVGO','TSM'] else '간접 수혜'}.",
        "recentEarnings":   f"(샘플) 최근 분기 실적 분석.",
        "financials":       f"(샘플) PER {per}x, 재무 건전성 분석.",
        "valuation":        f"(샘플) 현재 밸류에이션 적정 여부 판단.",
        "institutionalFlow":"(샘플) 기관 최근 3개월 매수/매도 동향.",
        "insiderTrading":   "(샘플) 내부자 최근 거래 내역.",
        "options":          "(샘플) 해당없음 (한국주식)" if is_kr else "(샘플) Call/Put 비율 분석.",
        "shortRatio":       f"(샘플) 공매도 비율 {fin.get('short_ratio', '정보없음')}%.",
        "earningsDate":     "(샘플) 다음 실적 발표 일정.",
        "events":           "(샘플) 주요 이벤트 일정.",
        "support":          ", ".join([f"{currency}{v}" for v in sup]),
        "resistance":       ", ".join([f"{currency}{v}" for v in res]),
        "fairValue":        f"{currency}{round(price * 0.95, 2)} ~ {currency}{round(price * 1.15, 2)}",
        "buyZone":          f"1차 {currency}{sup[0] if sup else round(price*0.95,2)}, 2차 {currency}{sup[1] if len(sup)>1 else round(price*0.90,2)}",
        "stopLoss":         f"{currency}{round(price * 0.88, 2)}",
        "target6m":         f"{currency}{round(float(target) * 0.95, 2)}",
        "target1y":         f"{currency}{target}",
        "bullCase":         f"(샘플) 상승 시나리오: {currency}{round(price*1.25,2)} (확률 30%)",
        "bearCase":         f"(샘플) 하락 시나리오: {currency}{round(price*0.80,2)} (확률 20%)",
    }


# ══════════════════════════════════════════
# 전체 분석 실행
# ══════════════════════════════════════════

def run(data: dict, sections=("news", "stocks")) -> dict:
    """data.json을 분석하여 결과 반환. sections로 뉴스/종목 중 일부만 분석 가능"""
    print(f"\n[AI 분석 시작] 모드: {'Mock' if USE_MOCK else f'Groq ({MODEL})'} · 대상: {sections}")

    # ── 뉴스 분석
    if "news" in sections:
        print("\n뉴스 분석 중...")
        for region in ("kr", "us"):
            articles = data.get("news", {}).get(region, [])
            for i, article in enumerate(articles):
                print(f"  {region.upper()} 뉴스 {i+1}/{len(articles)}: {article['title'][:40]}...")
                article["analysis"] = analyze_news(article["title"], article.get("summary", ""))
                if not USE_MOCK:
                    time.sleep(4)

    # ── 종목 분석
    if "stocks" in sections:
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
                    time.sleep(4)

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
