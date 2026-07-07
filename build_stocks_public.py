#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_stocks_public.py
----------------------
krx_output.json에 노출되는 종목만 대상으로, 종목별 "자금 압력 판독" 데이터 생성.
output/stocks_public/{code}.json

지표 (거래대금·가격 기반 — 실제 순매수 아님):
  closeIndexSeries    : 종가 첫날=100 정규화 (가격 흐름)
  tradingSharePctSeries: 종목 거래대금 / 시장 전체 거래대금 × 100 (관심도)
  summary{15,30,60,90}: 점유율 변화 + 가격 변화 + flowState(판독)

flowState (점유율 방향 × 가격 방향):
  점유율↑ + 가격↑ → 상승 거래대금 집중
  점유율↑ + 가격↓ → 하락 거래대금 집중
  점유율↓ + 가격↑ → 관심 둔화 속 상승
  점유율↓ + 가격↓ → 관심·가격 동반 위축
  미미           → 뚜렷한 방향 없음

표현: "순유입/순유출" 금지. "거래대금 집중/관심" 프레임.
비공개: 임계값·계산식 (결과 flowState/label만 출력)
"""

import json, os, glob, sys
from datetime import datetime

KRX_DIR    = "/root/krx-moneyflow"
OHLCV_DIR  = os.path.join(KRX_DIR, "data", "ohlcv")
STOCKS_DIR = os.path.join(KRX_DIR, "data", "stocks")
KRX_OUTPUT = os.path.join(KRX_DIR, "output", "krx_output.json")
OUT_DIR    = os.path.join(KRX_DIR, "output", "stocks_public")

WINDOWS = [15, 30, 60, 90]
AVG_N   = 3
SHARE_EPS = 0.02   # 점유율 변화 dead zone (%p) — 비공개
PRICE_EPS = 1.0    # 가격 변화 dead zone (%) — 비공개

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

def josa(w, wb, nb):
    if not w: return wb
    c = w[-1]
    if '가' <= c <= '힣':
        return wb if (ord(c) - 0xAC00) % 28 != 0 else nb
    return wb

# ---------- 노출 종목 수집 ----------
def collect_codes():
    d = json.load(open(KRX_OUTPUT, encoding="utf-8"))
    codes = {}
    for key in ['tradingValueTop','tradingValueUp','tradingValueDown',
                'contributionTop','contributionBottom','leaderCandidates','spikeCandidates']:
        for o in d.get(key, []):
            c = o.get('code')
            if c:
                codes[c] = o.get('name', c)
    return codes

# ---------- 시장 전체 거래대금 시계열 (ohlcv에서) ----------
def market_total_tv():
    files = sorted(glob.glob(os.path.join(OHLCV_DIR, "*.json")))
    total = {}  # date -> 전체 거래대금
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

# ---------- 압력 판독 ----------
def flow_state(share_delta_pp, price_change_pct):
    share_up = share_delta_pp > SHARE_EPS
    share_dn = share_delta_pp < -SHARE_EPS
    price_up = price_change_pct > PRICE_EPS
    price_dn = price_change_pct < -PRICE_EPS
    if not (share_up or share_dn):
        return "neutral", "뚜렷한 방향 없음"
    if share_up and price_up:
        return "up_concentration", "상승 거래대금 집중"
    if share_up and price_dn:
        return "down_concentration", "하락 거래대금 집중"
    if share_dn and price_up:
        return "fade_up", "관심 둔화 속 상승"
    if share_dn and price_dn:
        return "fade_down", "관심·가격 동반 위축"
    # 점유율만 움직이고 가격 보합
    if share_up:
        return "attention_up", "거래대금 관심 증가"
    return "attention_down", "거래대금 관심 감소"

def window_change(seq, w):
    """윈도우 구간의 시작 3일평균 → 최근 3일평균 변화"""
    if not seq: return 0.0, 0.0, 0.0
    seg = seq[-w:] if len(seq) >= w else seq
    then = avg_head(seg); now = avg_tail(seg)
    return round(then, 4), round(now, 4), round(now - then, 4)

def build_stock(code, name, mkt_total):
    path = os.path.join(STOCKS_DIR, f"{code}.json")
    if not os.path.exists(path):
        return None
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    bars = d.get("bars", [])
    if len(bars) < 15:
        return None

    dates, closes, shares, changes = [], [], [], []
    base_close = None
    for b in bars:
        date = b.get("date")
        close = safe_num(b.get("close"))
        tv = safe_num(b.get("tradingValue"))
        chg = safe_num(b.get("changeRate"))
        mt = mkt_total.get(date, 0.0)
        share_pct = (tv / mt * 100.0) if mt > 0 else 0.0
        if base_close is None and close > 0:
            base_close = close
        close_idx = (close / base_close * 100.0) if base_close else 100.0
        dates.append(date)
        closes.append(round(close_idx, 2))
        shares.append(round(share_pct, 4))
        changes.append(round(chg, 2))

    # 윈도우별 요약
    summary = {}
    price_series_raw = [safe_num(b.get("close")) for b in bars]
    for w in WINDOWS:
        # 점유율 변화 (%p)
        _sf, _sn, sd = window_change(shares, w)
        # 가격 변화 (%): 윈도우 시작가 대비 최근가
        seg = price_series_raw[-w:] if len(price_series_raw) >= w else price_series_raw
        p_then = avg_head(seg); p_now = avg_tail(seg)
        price_chg = round((p_now / p_then - 1) * 100, 2) if p_then > 0 else 0.0
        state, label = flow_state(sd, price_chg)
        summary[str(w)] = {
            "shareDeltaPp": round(sd, 3),
            "priceChangePct": price_chg,
            "flowState": state,
            "flowLabel": label
        }

    # 대표 상태 = 15일 기준 (화면 디폴트와 일치)
    rep = summary["15"]
    return {
        "code": code,
        "name": name,
        "market": d.get("market", ""),
        "startDate": dates[0] if dates else "",
        "endDate": dates[-1] if dates else "",
        "closeIndexSeries": [{"date": dt, "v": cv} for dt, cv in zip(dates, closes)],
        "tradingSharePctSeries": [{"date": dt, "v": sv} for dt, sv in zip(dates, shares)],
        "summary": summary,
        "repState": rep["flowState"],
        "repLabel": rep["flowLabel"]
    }

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    codes = collect_codes()
    mkt_total = market_total_tv()
    ok, fail = 0, 0
    states = {}
    for code, name in codes.items():
        obj = build_stock(code, name, mkt_total)
        if obj is None:
            fail += 1
            continue
        with open(os.path.join(OUT_DIR, f"{code}.json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        ok += 1
        states[obj["repState"]] = states.get(obj["repState"], 0) + 1
    # 검증 출력
    print("stocks_public OK")
    print(f"생성: {ok} / 실패: {fail} / 대상: {len(codes)}")
    print("대표 상태 분포(30일):")
    for s, c in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

if __name__ == "__main__":
    main()
