"""
STAGE 6: HTML 생성 모듈
- data/data.json (수집+분석 완료) → index.html 에 실제 데이터 주입
- index.html 의 LIVE_DATA_START/END 마커 사이를 교체
"""

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TEMPLATE_PATH = "index.html"
DATA_PATH     = os.path.join("data", "data.json")

MARKER_START = "// LIVE_DATA_START"
MARKER_END   = "// LIVE_DATA_END"


# ══════════════════════════════════════════
# data.json → 렌더 함수용 포맷 변환
# ══════════════════════════════════════════

def fmt_price(price, ticker: str) -> str:
    """주가를 통화 기호 포함 문자열로 변환"""
    try:
        if price is None:
            return "N/A"
        val = float(price)
        if val != val:  # NaN check
            return "N/A"
        is_kr = ticker.endswith(".KS")
        if is_kr:
            return f"₩{int(val):,}"
        return f"${val:,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def build_news_list(raw_news: list) -> list:
    """뉴스 원본 → 렌더용 포맷"""
    result = []
    for a in raw_news:
        item = {
            "title":   a.get("title", ""),
            "summary": a.get("summary", ""),
        }
        if a.get("analysis"):
            item["analysis"] = a["analysis"]
        result.append(item)
    return result


def build_stock_list(raw_stocks: dict) -> list:
    """종목 원본 딕셔너리 → 렌더용 리스트"""
    result = []
    for ticker, s in raw_stocks.items():
        if s.get("error"):
            continue

        an = s.get("analysis", {})
        price_str  = fmt_price(s.get("price"), ticker)
        change_val = s.get("change_pct", 0) or 0

        item = {
            "ticker":    ticker.replace(".KS", ""),
            "name":      s.get("name", ticker),
            "price":     price_str,
            "changeVal": round(float(change_val), 2),
            # 28개 분석 항목
            "businessModel":    an.get("businessModel",    "수집 중"),
            "industryOutlook":  an.get("industryOutlook",  "수집 중"),
            "recentNews":       an.get("recentNews",       "수집 중"),
            "competitors":      an.get("competitors",      "수집 중"),
            "moat":             an.get("moat",             "수집 중"),
            "aiBenefit":        an.get("aiBenefit",        "수집 중"),
            "recentEarnings":   an.get("recentEarnings",   "수집 중"),
            "financials":       an.get("financials",       "수집 중"),
            "valuation":        an.get("valuation",        "수집 중"),
            "institutionalFlow":an.get("institutionalFlow","수집 중"),
            "insiderTrading":   an.get("insiderTrading",   "수집 중"),
            "options":          an.get("options",          "수집 중"),
            "shortRatio":       an.get("shortRatio",       "수집 중"),
            "earningsDate":     an.get("earningsDate",     "수집 중"),
            "events":           an.get("events",           "수집 중"),
            "dailyChart":       an.get("dailyChart",       "수집 중"),
            "weeklyChart":      an.get("weeklyChart",      "수집 중"),
            "monthlyChart":     an.get("monthlyChart",     "수집 중"),
            "support":          an.get("support",          "수집 중"),
            "resistance":       an.get("resistance",       "수집 중"),
            "fairValue":        an.get("fairValue",        "수집 중"),
            "buyZone":          an.get("buyZone",          "수집 중"),
            "stopLoss":         an.get("stopLoss",         "수집 중"),
            "target6m":         an.get("target6m",         "수집 중"),
            "target1y":         an.get("target1y",         "수집 중"),
            "bullCase":         an.get("bullCase",         "수집 중"),
            "bearCase":         an.get("bearCase",         "수집 중"),
            "opinion":          an.get("opinion",          "보유"),
            "opinionClass":     an.get("opinionClass",     "op-hold"),
            "opinionProb":      an.get("opinionProb",      50),
        }
        result.append(item)
    return result


def build_dashboard_data(raw: dict) -> dict:
    """전체 data.json → DASHBOARD_DATA JS 객체"""
    return {
        "generated_at": raw.get("generated_at", ""),
        "news": {
            "kr": build_news_list(raw.get("news", {}).get("kr", [])),
            "us": build_news_list(raw.get("news", {}).get("us", [])),
        },
        "watchlist": build_stock_list(raw.get("stocks", {}).get("watchlist", {})),
        "holdings":  build_stock_list(raw.get("stocks", {}).get("holdings",  {})),
    }


# ══════════════════════════════════════════
# HTML 마커 교체
# ══════════════════════════════════════════

def inject_data(html: str, dashboard_data: dict) -> str:
    """LIVE_DATA_START ~ LIVE_DATA_END 사이를 실제 데이터로 교체"""
    data_json = json.dumps(dashboard_data, ensure_ascii=False, indent=2, default=str)

    new_block = (
        f"{MARKER_START} — generate_html.py 자동 생성\n"
        f"    const DASHBOARD_DATA = {data_json};\n"
        f"    // {MARKER_END}"
    )

    # 마커 사이 내용 교체 (줄바꿈 포함)
    pattern = re.compile(
        rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
        re.DOTALL
    )
    if not pattern.search(html):
        raise ValueError(f"index.html에서 마커를 찾을 수 없습니다: {MARKER_START}")

    return pattern.sub(new_block, html)


# ══════════════════════════════════════════
# 메인
# ══════════════════════════════════════════

def run():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"{DATA_PATH} 없음. collect_data.py → analyze.py 순서로 먼저 실행하세요.")

    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        html = f.read()

    print("[generate_html] 데이터 변환 중...")
    dashboard_data = build_dashboard_data(raw)
    print(f"  뉴스: KR {len(dashboard_data['news']['kr'])}개 / US {len(dashboard_data['news']['us'])}개")
    print(f"  관심종목: {len(dashboard_data['watchlist'])}개")
    print(f"  보유종목: {len(dashboard_data['holdings'])}개")

    print("[generate_html] HTML 주입 중...")
    new_html = inject_data(html, dashboard_data)

    with open(TEMPLATE_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"✅ index.html 업데이트 완료")
    return dashboard_data


if __name__ == "__main__":
    run()
