#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_weight.py  —  "돈의 무게" (Weight of Money)
--------------------------------------------------
거래대금 상위 종목의 매수/매도 압력을 판독하고 랭킹화.
거래대금이 상승 방향에 실렸나(매수 압력) 하락 방향에 실렸나(매도 압력)를 본다.

출력:
  output/weight_output.json      — 압력 랭킹 (buyPressure / sellPressure)
  output/stocks_public/{code}.json — 종목별 상세 (kr-moneyflow와 공유)

대상: 오늘 거래대금 THRESHOLD(100억) 이상 종목
압력점수: 거래대금 점유율 변화 × 가격 방향 강도 (거래대금·가격 기반, 실제 순매수 아님)
표현: "매수/매도 압력 후보". "순유입/순유출" 금지. 참고지표.
비공개: 임계값·점수식 (결과 라벨/점수만 출력)
"""

import json, os, glob, sys
from datetime import datetime

KRX_DIR    = "/root/krx-moneyflow"
OHLCV_DIR  = os.path.join(KRX_DIR, "data", "ohlcv")
STOCKS_DIR = os.path.join(KRX_DIR, "data", "stocks")
OUT_DIR    = os.path.join(KRX_DIR, "output", "stocks_public")
WEIGHT_OUT = os.path.join(KRX_DIR, "output", "weight_output.json")

WINDOWS   = [15, 30, 60, 90]
AVG_N     = 3
SHARE_EPS = 0.02   # 점유율 dead zone (%p) — 비공개
PRICE_EPS = 1.0    # 가격 dead zone (%) — 비공개
TV_THRESHOLD = 100e8   # 거래대금 100억 이상만 대상
RANK_WINDOW  = 15      # 압력 랭킹 기준 기간

def safe_num(x):
    try:
        v = float(x)
        return 0.0 if v != v else v
    except (TypeError, ValueError):
        return 0.0

def avg_head(seq, n=AVG_N):
    if not seq: return 0.0
    s = seq[:n] if len(seq) >= n else seq
    return sum(s) / len(s)

def avg_tail(seq, n=AVG_N):
    if not seq: return 0.0
    s = seq[-n:] if len(seq) >= n else seq
    return sum(s) / len(s)

# ---------- 시장 전체 거래대금 시계열 ----------
def market_total_tv():
    files = sorted(glob.glob(os.path.join(OHLCV_DIR, "*.json")))
    total = {}
    for f in files:
        date = os.path.splitext(os.path.basename(f))[0]
        if not (len(date) == 8 and date.isdigit()):
            continue
        try:
            rows = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        s = 0.0
        for r in rows:
            s += safe_num(r.get("tradingValue"))
        total[date] = s
    return total

# ---------- 대상 종목 선정 (오늘 거래대금 THRESHOLD 이상) ----------
def target_codes():
    files = sorted(glob.glob(os.path.join(OHLCV_DIR, "*.json")))
    if not files:
        return {}, None
    latest = files[-1]
    rows = json.load(open(latest, encoding="utf-8"))
    codes = {}
    for r in rows:
        tv = safe_num(r.get("tradingValue"))
        if tv >= TV_THRESHOLD:
            code = str(r.get("code","")).strip()
            if code:
                codes[code] = {"name": r.get("name", code),
                               "market": r.get("market",""),
                               "changeRate": safe_num(r.get("changeRate")),
                               "tradingValue": tv}
    date = os.path.splitext(os.path.basename(latest))[0]
    return codes, date

# ---------- 압력 판독 ----------
def flow_state(share_delta_pp, price_change_pct):
    su = share_delta_pp > SHARE_EPS
    sd = share_delta_pp < -SHARE_EPS
    pu = price_change_pct > PRICE_EPS
    pd = price_change_pct < -PRICE_EPS
    if not (su or sd):
        return "neutral", "뚜렷한 방향 없음"
    if su and pu: return "up_concentration", "상승 거래대금 집중"
    if su and pd: return "down_concentration", "하락 거래대금 집중"
    if sd and pu: return "fade_up", "관심 둔화 속 상승"
    if sd and pd: return "fade_down", "관심·가격 동반 위축"
    if su: return "attention_up", "거래대금 관심 증가"
    return "attention_down", "거래대금 관심 감소"

def window_change(seq, w):
    if not seq: return 0.0
    seg = seq[-w:] if len(seq) >= w else seq
    then = avg_head(seg); now = avg_tail(seg)
    return round(now - then, 4)

def pressure_score(share_delta_pp, price_change_pct):
    """압력 점수: 거래대금 집중도 × 가격 방향 강도. 비공개 계산."""
    return round(abs(share_delta_pp) * price_change_pct, 2)

# ---------- 종목별 빌드 ----------
def build_stock(code, meta, mkt_total):
    path = os.path.join(STOCKS_DIR, f"{code}.json")
    if not os.path.exists(path):
        return None, None
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None, None
    bars = d.get("bars", [])
    if len(bars) < 15:
        return None, None

    dates, closes, shares = [], [], []
    close_raw = []
    base_close = None
    for b in bars:
        date = b.get("date")
        close = safe_num(b.get("close"))
        tv = safe_num(b.get("tradingValue"))
        mt = mkt_total.get(date, 0.0)
        share_pct = (tv / mt * 100.0) if mt > 0 else 0.0
        if base_close is None and close > 0:
            base_close = close
        close_idx = (close / base_close * 100.0) if base_close else 100.0
        dates.append(date); closes.append(round(close_idx, 2))
        shares.append(round(share_pct, 4)); close_raw.append(close)

    summary = {}
    for w in WINDOWS:
        sd = window_change(shares, w)
        seg = close_raw[-w:] if len(close_raw) >= w else close_raw
        p_then = avg_head(seg); p_now = avg_tail(seg)
        price_chg = round((p_now / p_then - 1) * 100, 2) if p_then > 0 else 0.0
        state, label = flow_state(sd, price_chg)
        summary[str(w)] = {
            "shareDeltaPp": round(sd, 3),
            "priceChangePct": price_chg,
            "flowState": state,
            "flowLabel": label
        }

    rep = summary[str(RANK_WINDOW)]
    stock_obj = {
        "code": code, "name": meta["name"], "market": d.get("market", meta["market"]),
        "startDate": dates[0] if dates else "", "endDate": dates[-1] if dates else "",
        "closeIndexSeries": [{"date": dt, "v": cv} for dt, cv in zip(dates, closes)],
        "tradingSharePctSeries": [{"date": dt, "v": sv} for dt, sv in zip(dates, shares)],
        "summary": summary,
        "repState": rep["flowState"], "repLabel": rep["flowLabel"]
    }
    # 랭킹용 요약 (RANK_WINDOW 기준)
    rank_obj = {
        "code": code, "name": meta["name"], "market": d.get("market", meta["market"]),
        "changeRate": round(meta["changeRate"], 2),
        "tradingValue": round(meta["tradingValue"]),
        "shareDeltaPp": rep["shareDeltaPp"],
        "priceChangePct": rep["priceChangePct"],
        "flowState": rep["flowState"],
        "flowLabel": rep["flowLabel"],
        "score": pressure_score(rep["shareDeltaPp"], rep["priceChangePct"])
    }
    return stock_obj, rank_obj

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    mkt_total = market_total_tv()
    codes, date = target_codes()
    ranks = []
    ok = 0
    for code, meta in codes.items():
        stock_obj, rank_obj = build_stock(code, meta, mkt_total)
        if stock_obj is None:
            continue
        with open(os.path.join(OUT_DIR, f"{code}.json"), "w", encoding="utf-8") as f:
            json.dump(stock_obj, f, ensure_ascii=False, separators=(",", ":"))
        ranks.append(rank_obj)
        ok += 1

    # 매수 압력 = 상승 거래대금 집중 (score 양수 큰 순)
    buy = [r for r in ranks if r["flowState"] == "up_concentration"]
    buy.sort(key=lambda x: -x["score"])
    # 매도 압력 = 하락 거래대금 집중 (score 음수 작은 순 = 절대값 큰 순)
    sell = [r for r in ranks if r["flowState"] == "down_concentration"]
    sell.sort(key=lambda x: x["score"])

    def slim(r):
        return {"code": r["code"], "name": r["name"], "market": r["market"],
                "changeRate": r["changeRate"],
                "shareDeltaPp": r["shareDeltaPp"], "priceChangePct": r["priceChangePct"],
                "flowLabel": r["flowLabel"]}

    out = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "date": date,
        "rankWindow": RANK_WINDOW,
        "note": "거래대금·가격 기준 참고지표",
        "targetCount": ok,
        "buyPressure": [slim(r) for r in buy[:20]],
        "sellPressure": [slim(r) for r in sell[:20]]
    }
    with open(WEIGHT_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print("weight OK")
    print(f"대상(거래대금 100억+): {len(codes)} / 생성: {ok}")
    print(f"매수 압력 종목: {len(buy)} / 매도 압력 종목: {len(sell)}")
    print("=== 매수 압력 TOP 5 ===")
    for r in buy[:5]:
        print(f"  {r['name']}: 점유율{r['shareDeltaPp']:+.2f}pp 가격{r['priceChangePct']:+.1f}% ({r['flowLabel']})")
    print("=== 매도 압력 TOP 5 ===")
    for r in sell[:5]:
        print(f"  {r['name']}: 점유율{r['shareDeltaPp']:+.2f}pp 가격{r['priceChangePct']:+.1f}% ({r['flowLabel']})")

if __name__ == "__main__":
    main()
