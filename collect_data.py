"""
STAGE 4: 데이터 수집 모듈
- yfinance: 주가/재무 데이터 (API 키 불필요)
- Google News RSS: 뉴스 수집 (API 키 불필요)
- 기술적 지표: RSI, MACD, 이동평균, 지지선/저항선
"""

import json
import os
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import feedparser
import numpy as np
import pandas as pd
import yfinance as yf

# ══════════════════════════════════════════
# 종목 목록
# ══════════════════════════════════════════

WATCHLIST = {
    "MSFT":      "Microsoft",
    "NVDA":      "Nvidia",
    "GOOGL":     "Alphabet",
    "AVGO":      "Broadcom",
    "TSM":       "TSMC",
    "TSLA":      "Tesla",
    # SpaceX 비상장 제외 — 뉴스 분석 시 언급만
    "IVV":       "iShares S&P 500 ETF",
    "SCHD":      "Schwab Dividend ETF",
    "000660.KS": "SK하이닉스",
    "005930.KS": "삼성전자",
    "012450.KS": "한화에어로스페이스",
    "005380.KS": "현대차",
    "034020.KS": "두산에너빌리티",
}

HOLDINGS = {
    "412570.KS": "Tiger 2차전지 TOP10 레버리지",
    "365340.KS": "성일하이텍",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "005490.KS": "POSCO홀딩스",
}

# ══════════════════════════════════════════
# 기술적 지표 계산
# ══════════════════════════════════════════

def calc_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not rsi.empty else None


def calc_macd(prices: pd.Series):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return {
        "macd":   round(float(macd.iloc[-1]), 4),
        "signal": round(float(signal.iloc[-1]), 4),
        "hist":   round(float(hist.iloc[-1]), 4),
    }


def calc_moving_averages(prices: pd.Series) -> dict:
    result = {}
    for period in [5, 20, 60, 120, 200]:
        if len(prices) >= period:
            val = prices.rolling(period).mean().iloc[-1]
            result[f"ma{period}"] = round(float(val), 4)
        else:
            result[f"ma{period}"] = None
    return result


def calc_support_resistance(prices: pd.Series, window: int = 20) -> dict:
    """최근 고점/저점으로 지지선/저항선 추정"""
    recent = prices.tail(90)
    if len(recent) < window:
        return {"support": [], "resistance": []}

    lows, highs = [], []
    for i in range(window, len(recent) - window):
        segment = recent.iloc[i - window: i + window]
        val = recent.iloc[i]
        if val == segment.min():
            lows.append(round(float(val), 2))
        if val == segment.max():
            highs.append(round(float(val), 2))

    # 현재가 기준 정렬
    current = float(prices.iloc[-1])
    support    = sorted(set([v for v in lows    if v < current]), reverse=True)[:3]
    resistance = sorted(set([v for v in highs   if v > current]))[:3]
    return {"support": support, "resistance": resistance}


def calc_change(current: float, prev: float) -> dict:
    change = current - prev
    pct = (change / prev * 100) if prev else 0
    return {
        "change":     round(change, 4),
        "change_pct": round(pct, 2),
    }


# ══════════════════════════════════════════
# 주가/재무 데이터 수집
# ══════════════════════════════════════════

def fetch_stock(ticker: str, name: str) -> dict:
    """yfinance로 단일 종목 데이터 수집"""
    print(f"  수집 중: {ticker} ({name})")
    try:
        tk = yf.Ticker(ticker)

        # 1년치 일봉
        hist = tk.history(period="1y", auto_adjust=True)
        if hist.empty:
            print(f"  ⚠ {ticker}: 데이터 없음")
            return {"ticker": ticker, "name": name, "error": "데이터 없음"}

        close = hist["Close"].dropna()
        if close.empty:
            print(f"  ⚠ {ticker}: Close 데이터 없음")
            return {"ticker": ticker, "name": name, "error": "Close 데이터 없음"}
        current_price = round(float(close.iloc[-1]), 4)
        prev_close    = round(float(close.iloc[-2]), 4) if len(close) > 1 else current_price

        # 52주 고/저
        high_52w = round(float(close.tail(252).max()), 4)
        low_52w  = round(float(close.tail(252).min()), 4)

        # 거래량 (5일 평균)
        vol_avg5 = round(float(hist["Volume"].tail(5).mean()), 0) if "Volume" in hist else None

        # 기술적 지표
        rsi       = calc_rsi(close)
        macd_data = calc_macd(close)
        ma_data   = calc_moving_averages(close)
        sr_data   = calc_support_resistance(close)
        chg       = calc_change(current_price, prev_close)

        # 재무 정보 (info)
        info = {}
        try:
            raw_info = tk.info or {}
            info = {
                "market_cap":        raw_info.get("marketCap"),
                "pe_ratio":          raw_info.get("trailingPE"),
                "forward_pe":        raw_info.get("forwardPE"),
                "pb_ratio":          raw_info.get("priceToBook"),
                "eps":               raw_info.get("trailingEps"),
                "dividend_yield":    raw_info.get("dividendYield"),
                "revenue":           raw_info.get("totalRevenue"),
                "net_income":        raw_info.get("netIncomeToCommon"),
                "operating_margin":  raw_info.get("operatingMargins"),
                "profit_margin":     raw_info.get("profitMargins"),
                "debt_to_equity":    raw_info.get("debtToEquity"),
                "current_ratio":     raw_info.get("currentRatio"),
                "roe":               raw_info.get("returnOnEquity"),
                "short_ratio":       raw_info.get("shortRatio"),
                "analyst_target":    raw_info.get("targetMeanPrice"),
                "analyst_rating":    raw_info.get("recommendationMean"),
                "earnings_date":     str(raw_info.get("earningsTimestamp", "")),
                "sector":            raw_info.get("sector", ""),
                "industry":          raw_info.get("industry", ""),
                "description":       raw_info.get("longBusinessSummary", "")[:300],
            }
        except Exception as e:
            print(f"  ⚠ {ticker} info 오류: {e}")

        # 기관/내부자 거래
        institutional = []
        try:
            inst = tk.institutional_holders
            if inst is not None and not inst.empty:
                top3 = inst.head(3).to_dict(orient="records")
                institutional = [
                    {
                        "holder": str(r.get("Holder", "")),
                        "shares": int(r.get("Shares", 0)),
                        "pct":    round(float(r.get("% Out", 0)) * 100, 2),
                    }
                    for r in top3
                ]
        except Exception:
            pass

        insider = []
        try:
            ins = tk.insider_transactions
            if ins is not None and not ins.empty:
                recent3 = ins.head(3).to_dict(orient="records")
                insider = [
                    {
                        "name":       str(r.get("Insider", "")),
                        "transaction": str(r.get("Transaction", "")),
                        "shares":      int(r.get("Shares", 0) or 0),
                        "value":       int(r.get("Value", 0) or 0),
                    }
                    for r in recent3
                ]
        except Exception:
            pass

        # 옵션 (미국 주식만)
        options_summary = {}
        if not ticker.endswith(".KS"):
            try:
                exps = tk.options
                if exps:
                    chain = tk.option_chain(exps[0])
                    call_vol = int(chain.calls["volume"].sum()) if not chain.calls.empty else 0
                    put_vol  = int(chain.puts["volume"].sum())  if not chain.puts.empty  else 0
                    ratio    = round(call_vol / put_vol, 2) if put_vol > 0 else None
                    options_summary = {
                        "call_volume": call_vol,
                        "put_volume":  put_vol,
                        "call_put_ratio": ratio,
                        "expiry": exps[0],
                    }
            except Exception:
                pass

        # 주봉/월봉 데이터 (최근 종가만)
        weekly_close  = hist["Close"].resample("W").last().tail(52)
        monthly_close = hist["Close"].resample("ME").last().tail(24)

        weekly_ma20  = round(float(weekly_close.rolling(20).mean().iloc[-1]), 4)  if len(weekly_close)  >= 20 else None
        monthly_ma12 = round(float(monthly_close.rolling(12).mean().iloc[-1]), 4) if len(monthly_close) >= 12 else None

        # 실적 발표 일정
        earnings_dates = []
        try:
            cal = tk.calendar
            if cal is not None and not cal.empty:
                earnings_dates = [str(d) for d in cal.index.tolist()[:2]]
        except Exception:
            pass

        # 종목별 최근 뉴스 헤드라인 (yfinance)
        recent_news_titles = []
        try:
            news = tk.news or []
            recent_news_titles = [
                n.get("content", {}).get("title") or n.get("title", "")
                for n in news[:5]
                if n.get("content", {}).get("title") or n.get("title")
            ]
        except Exception:
            pass

        return {
            "ticker":          ticker,
            "name":            name,
            "price":           current_price,
            "prev_close":      prev_close,
            "change":          chg["change"],
            "change_pct":      chg["change_pct"],
            "high_52w":        high_52w,
            "low_52w":         low_52w,
            "volume_avg5":     vol_avg5,
            "rsi":             rsi,
            "macd":            macd_data,
            "moving_averages": ma_data,
            "support":         sr_data["support"],
            "resistance":      sr_data["resistance"],
            "weekly_ma20":     weekly_ma20,
            "monthly_ma12":    monthly_ma12,
            "financials":      info,
            "institutional":   institutional,
            "insider":         insider,
            "options":         options_summary,
            "earnings_dates":       earnings_dates,
            "recent_news_titles":   recent_news_titles,
            "collected_at":    datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"  ✗ {ticker} 오류: {e}")
        return {"ticker": ticker, "name": name, "error": str(e)}


def fetch_all_stocks() -> dict:
    """전체 종목 수집"""
    print("\n[주가 데이터 수집 시작]")
    result = {"watchlist": {}, "holdings": {}}

    print("관심종목:")
    for ticker, name in WATCHLIST.items():
        result["watchlist"][ticker] = fetch_stock(ticker, name)
        time.sleep(0.5)  # yfinance rate limit 방지

    print("\n보유종목:")
    for ticker, name in HOLDINGS.items():
        result["holdings"][ticker] = fetch_stock(ticker, name)
        time.sleep(0.5)

    return result


# ══════════════════════════════════════════
# 뉴스 수집 (Google News RSS — API 키 불필요)
# ══════════════════════════════════════════

NEWS_FEEDS = {
    "kr": [
        "https://news.google.com/rss/search?q=한국+증시+주식+경제&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=코스피+코스닥+반도체&hl=ko&gl=KR&ceid=KR:ko",
    ],
    "us": [
        "https://news.google.com/rss/search?q=stock+market+economy+fed&hl=en&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=nasdaq+sp500+earnings&hl=en&gl=US&ceid=US:en",
    ],
}


def fetch_news(region: str, max_per_feed: int = 5) -> list:
    """Google News RSS로 뉴스 수집"""
    articles = []
    feeds = NEWS_FEEDS.get(region, [])

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    "title":     entry.get("title", ""),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary":   entry.get("summary", "")[:200],
                    "source":    entry.get("source", {}).get("title", ""),
                })
        except Exception as e:
            print(f"  ⚠ 뉴스 수집 오류 ({region}, {url}): {e}")

    # 중복 제목 제거
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:5]  # 최대 5개


def fetch_all_news() -> dict:
    print("\n[뉴스 수집 시작]")
    kr = fetch_news("kr")
    us = fetch_news("us")
    print(f"  한국 뉴스: {len(kr)}개 수집")
    print(f"  미국 뉴스: {len(us)}개 수집")
    return {"kr": kr, "us": us}


# ══════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════

def run():
    os.makedirs("data", exist_ok=True)

    stocks = fetch_all_stocks()
    news   = fetch_all_news()

    output = {
        "generated_at": datetime.now().isoformat(),
        "stocks": stocks,
        "news":   news,
    }

    out_path = os.path.join("data", "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ 저장 완료: {out_path}")
    print(f"   관심종목: {len(stocks['watchlist'])}개")
    print(f"   보유종목: {len(stocks['holdings'])}개")
    print(f"   뉴스: 한국 {len(news['kr'])}개 / 미국 {len(news['us'])}개")
    return output


if __name__ == "__main__":
    run()
