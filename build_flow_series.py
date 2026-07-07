#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_flow_series.py
--------------------
data/ohlcv/{basDt}.json (일별 전체 종목 스냅샷) 90개를 통째로 rebuild 하여
output/flow_series.json (15/30/60/90일 자금흐름 시계열) 생성.

핵심 지표:
  ① 시장 거래대금 총량 + 점유율 (KOSPI / KOSDAQ)
  ② 테마 거래대금 점유율 (shareOfMarket, shareOfCoveredThemes)
  ③ 테마 netFlow (거래대금 가중 방향성, ±0.3% dead zone)
비교: 최근 3거래일 평균 vs 윈도우 시작 3거래일 평균
배지: 표본부족 → 대장주단독 → netFlow(유입/분배/혼조)

방식: 매일 전체 rebuild (append 아님). ohlcv 스냅샷이 90개뿐이라 단순·안전.
표현: [A] 데이터 단계 — 거래대금 기준만. 외국인/기관/순유입 표현 금지.
"""

import json, glob, os, sys
from datetime import datetime

KRX_DIR    = "/root/krx-moneyflow"
OHLCV_DIR  = os.path.join(KRX_DIR, "data", "ohlcv")
THEME_PATH = os.path.join(KRX_DIR, "theme_master.json")
SERIES_DIR = os.path.join(KRX_DIR, "data", "series")
OUT_INTERNAL   = os.path.join(SERIES_DIR, "flow_series.json")          # 내부 원본 (판정재료 포함, 웹서빙 X)
OUT_WEB_PUBLIC = os.path.join(KRX_DIR, "output", "flow_series_public.json")  # 공개 slim (% + badge만)

WINDOWS   = [15, 30, 60, 90]
EPS       = 0.3      # netFlow dead zone (%)
NET_TH    = 0.35     # 유입/분배 임계
MIN_STOCK = 3        # 표본 부족 기준
LEADER_SHARE_TH = 0.70  # 대장주 단독 기준
AVG_N     = 3        # 3거래일 평균

# ---------- 유틸 ----------
def direction_with_deadzone(change_rate, eps=EPS):
    if change_rate is None: return 0
    if change_rate >= eps:  return 1
    if change_rate <= -eps: return -1
    return 0

def safe_num(x):
    try:
        v = float(x)
        if v != v:  # NaN
            return 0.0
        return v
    except (TypeError, ValueError):
        return 0.0

def avg_tail(seq, n=AVG_N):
    """리스트 끝 n개 평균 (최근값)"""
    if not seq: return 0.0
    s = seq[-n:] if len(seq) >= n else seq
    return sum(s) / len(s)

def avg_head(seq, n=AVG_N):
    """리스트 앞 n개 평균 (윈도우 시작값)"""
    if not seq: return 0.0
    s = seq[:n] if len(seq) >= n else seq
    return sum(s) / len(s)

def josa(word, with_b, without_b):
    """받침 유무로 조사 선택 (with_b=받침있을때, without_b=받침없을때)"""
    if not word: return with_b
    ch = word[-1]
    if '가' <= ch <= '힣':
        return with_b if (ord(ch) - 0xAC00) % 28 != 0 else without_b
    return with_b

# ---------- 로드 ----------
def load_theme_map():
    """theme_master(list) → {code: theme}"""
    data = json.load(open(THEME_PATH, encoding="utf-8"))
    m = {}
    for row in data:
        code = str(row.get("code", "")).strip()
        theme = row.get("theme")
        if code and theme:
            m[code] = theme
    return m

def load_snapshots():
    """ohlcv/*.json 전부 → {date: [rows]} 날짜 오름차순"""
    files = sorted(glob.glob(os.path.join(OHLCV_DIR, "*.json")))
    snaps = {}
    for f in files:
        date = os.path.splitext(os.path.basename(f))[0]
        if not (len(date) == 8 and date.isdigit()):
            continue
        try:
            rows = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"[warn] load fail {f}: {e}", file=sys.stderr)
            continue
        if isinstance(rows, list):
            snaps[date] = rows
    return snaps

# ---------- 일별 집계 ----------
def aggregate_day(rows, theme_map):
    """하루 스냅샷 → 시장별/테마별 집계"""
    mkt = {"KOSPI": {"tv":0.0,"up":0,"cnt":0}, "KOSDAQ": {"tv":0.0,"up":0,"cnt":0}}
    total_tv = 0.0
    themes = {}  # theme -> {tv, up, cnt, stocks:[{code,name,tv,chg}]}

    for r in rows:
        market = r.get("market")
        tv = safe_num(r.get("tradingValue"))
        chg = safe_num(r.get("changeRate"))
        code = str(r.get("code","")).strip()
        name = r.get("name","")
        if market in mkt:
            mkt[market]["tv"] += tv
            mkt[market]["cnt"] += 1
            if chg > 0: mkt[market]["up"] += 1
        total_tv += tv

        th = theme_map.get(code)
        if th:
            t = themes.setdefault(th, {"tv":0.0,"up":0,"cnt":0,"stocks":[]})
            t["tv"] += tv
            t["cnt"] += 1
            if chg > 0: t["up"] += 1
            t["stocks"].append({"code":code,"name":name,"tv":tv,"chg":chg})

    return mkt, total_tv, themes

def theme_netflow_and_badge(stocks):
    """테마 stocks → (netFlow, coverage, badge, leaderShare, leader)"""
    # 방향 잡힌 거래대금만 분모 (dead zone 제외)  ← coverage 방어
    directional = 0.0
    signed = 0.0
    total = 0.0
    for s in stocks:
        tv = s["tv"]
        if tv <= 0: continue
        total += tv
        d = direction_with_deadzone(s["chg"])
        if d == 0: continue
        directional += tv
        signed += tv * d
    net = (signed / directional) if directional > 0 else 0.0
    cov = (directional / total) if total > 0 else 0.0

    # 대장주
    leader = max(stocks, key=lambda x: x["tv"]) if stocks else None
    leader_share = (leader["tv"]/total) if (leader and total>0) else 0.0

    # 배지 판정 순서: 표본부족 → 대장주단독 → coverage → netFlow
    cnt = len([s for s in stocks if s["tv"]>0])
    if cnt < MIN_STOCK:
        badge = "표본 부족"
    elif leader_share >= LEADER_SHARE_TH:
        badge = "대장주 단독"
    elif cov < 0.5:
        badge = "혼조"
    elif net >= NET_TH:
        badge = "유입 우세"
    elif net <= -NET_TH:
        badge = "분배 우세 후보"
    else:
        badge = "혼조"

    leader_obj = None
    if leader:
        leader_obj = {
            "code": leader["code"], "name": leader["name"],
            "changeRate": round(leader["chg"],2),
            "tradingValueShare": round(leader_share,4)
        }
    return round(net,4), round(cov,4), badge, round(leader_share,4), leader_obj

# ---------- 시계열 빌드 ----------
def build():
    theme_map = load_theme_map()
    snaps = load_snapshots()
    dates = sorted(snaps.keys())
    if not dates:
        print("[fatal] no ohlcv snapshots", file=sys.stderr); sys.exit(1)

    market_series = {"KOSPI": [], "KOSDAQ": []}
    theme_series = {}   # theme -> [ {date, ...} ]
    coverage_last = {"themeCoveredTradingValueShare":0.0, "unassignedTradingValueShare":0.0}

    for date in dates:
        mkt, total_tv, themes = aggregate_day(snaps[date], theme_map)
        # 시장
        for m in ("KOSPI","KOSDAQ"):
            o = mkt[m]
            share = (o["tv"]/total_tv) if total_tv>0 else 0.0
            up_ratio = round(100*o["up"]/o["cnt"],1) if o["cnt"]>0 else 0.0
            market_series[m].append({
                "date": date,
                "tradingValue": round(o["tv"]),
                "share": round(share,4),
                "upRatio": up_ratio,
                "stockCount": o["cnt"]
            })
        # 테마
        covered_tv = sum(t["tv"] for t in themes.values())
        for th, t in themes.items():
            net, cov, badge, lshare, leader = theme_netflow_and_badge(t["stocks"])
            up_ratio = round(100*t["up"]/t["cnt"],1) if t["cnt"]>0 else 0.0
            entry = {
                "date": date,
                "tradingValue": round(t["tv"]),
                "shareOfMarket": round(t["tv"]/total_tv,4) if total_tv>0 else 0.0,
                "shareOfCoveredThemes": round(t["tv"]/covered_tv,4) if covered_tv>0 else 0.0,
                "netFlow": net,
                "netFlowCoverage": cov,
                "upRatio": up_ratio,
                "stockCount": t["cnt"],
                "leader": leader,
                "badge": badge
            }
            theme_series.setdefault(th, []).append(entry)
        # coverage (마지막 날 기준 저장)
        if date == dates[-1]:
            coverage_last = {
                "themeCoveredTradingValueShare": round(covered_tv/total_tv,4) if total_tv>0 else 0.0,
                "unassignedTradingValueShare": round(1-(covered_tv/total_tv),4) if total_tv>0 else 0.0
            }

    # ----- summary: 시장 점유율 이동 (기본 30일 창, 3일평균 비교) -----
    def share_seq(m): return [x["share"] for x in market_series[m]]
    def window_move(seq, w):
        if len(seq) < 2: return avg_tail(seq), avg_tail(seq)
        seg = seq[-w:] if len(seq) >= w else seq
        return avg_head(seg), avg_tail(seg)  # then, now

    kospi_then, kospi_now   = window_move(share_seq("KOSPI"), 30)
    kosdaq_then, kosdaq_now = window_move(share_seq("KOSDAQ"), 30)
    if kospi_now - kospi_then >= 0.02:   mlabel = "코스피 쏠림"
    elif kosdaq_now - kosdaq_then >= 0.02: mlabel = "코스닥 쏠림"
    else: mlabel = "뚜렷한 이동 없음"

    # ----- summary: 테마 점유율 상승/하락 TOP (30일 창, shareOfMarket 3일평균 비교) -----
    rotation = []
    for th, seq in theme_series.items():
        shares = [x["shareOfMarket"] for x in seq]
        seg = shares[-30:] if len(shares) >= 30 else shares
        then = avg_head(seg); now = avg_tail(seg)
        rotation.append({
            "theme": th,
            "shareThen": round(then,4),
            "shareNow": round(now,4),
            "delta": round(now-then,4),
            "badgeNow": seq[-1]["badge"] if seq else "혼조"
        })
    rising = sorted([r for r in rotation if r["delta"]>0], key=lambda x:-x["delta"])[:5]
    falling = sorted([r for r in rotation if r["delta"]<0], key=lambda x:x["delta"])[:5]

    out = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "startDate": dates[0],
        "endDate": dates[-1],
        "days": len(dates),
        "windows": WINDOWS,
        "note": "거래대금 기준 · 주요 테마 바스켓 기준 · 실시간 아님",
        "market": market_series,
        "themes": theme_series,
        "summary": {
            "marketFlow": {
                "window": 30,
                "kospiShareNow": round(kospi_now,4),
                "kospiShareThen": round(kospi_then,4),
                "kosdaqShareNow": round(kosdaq_now,4),
                "kosdaqShareThen": round(kosdaq_then,4),
                "label": mlabel
            },
            "themeRotation": {"rising": rising, "falling": falling}
        },
        "coverage": coverage_last
    }
    return out, dates, market_series, theme_series

# ---------- 공개용 slim 생성 ----------
def window_move_pct(seq, w):
    if not seq: return 0.0, 0.0, 0.0
    seg = seq[-w:] if len(seq) >= w else seq
    then = avg_head(seg); now = avg_tail(seg)
    return round(then*100,2), round(now*100,2), round((now-then)*100,2)

def build_public(out, market_series, theme_series):
    """화면 전용 slim. 내부 판정 재료(netFlow·leaderShare·coverage 원수치·raw tv) 제외."""
    kospi = {x["date"]: x["share"] for x in market_series["KOSPI"]}
    kosdaq = {x["date"]: x["share"] for x in market_series["KOSDAQ"]}
    all_dates = [x["date"] for x in market_series["KOSPI"]]
    market_line = [{"date": d,
        "kospiSharePct": round(kospi.get(d,0)*100,2),
        "kosdaqSharePct": round(kosdaq.get(d,0)*100,2)} for d in all_dates]

    kospi_share = [x["share"] for x in market_series["KOSPI"]]
    kosdaq_share = [x["share"] for x in market_series["KOSDAQ"]]
    market_summary = {}
    for w in WINDOWS:
        kf, kt, kd = window_move_pct(kospi_share, w)
        qf, qt, qd = window_move_pct(kosdaq_share, w)
        if kd >= 2.0:   label = "코스피 쏠림"
        elif qd >= 2.0: label = "코스닥 쏠림"
        else:           label = "뚜렷한 이동 없음"
        market_summary[str(w)] = {
            "kospiFrom": kf, "kospiTo": kt, "kospiDeltaPp": kd,
            "kosdaqFrom": qf, "kosdaqTo": qt, "kosdaqDeltaPp": qd, "label": label}

    theme_summary = {}
    for w in WINDOWS:
        rot = []
        for th, seq in theme_series.items():
            shares = [x["shareOfMarket"] for x in seq]
            f, t, d = window_move_pct(shares, w)
            rot.append({"theme": th, "from": f, "to": t, "deltaPp": d,
                        "badge": seq[-1]["badge"] if seq else "혼조"})
        rising = sorted([r for r in rot if r["deltaPp"]>0], key=lambda x:-x["deltaPp"])[:5]
        falling = sorted([r for r in rot if r["deltaPp"]<0], key=lambda x:x["deltaPp"])[:5]
        theme_summary[str(w)] = {"rising": rising, "falling": falling}

    # ===== STEP1: 시장 핵심 요약 (규칙 기반 자동 문장, LLM 생성 아님) =====
    W30 = market_summary["30"]
    kd = W30["kospiDeltaPp"]
    if kd >= 5.0:      regime_label, tone = "코스피 쏠림", "kospi"
    elif kd <= -5.0:   regime_label, tone = "코스닥 쏠림", "kosdaq"
    else:              regime_label, tone = "시장 비중 혼조", "mixed"
    regime_lines = []
    if tone == "kospi":
        regime_lines = ["최근 30일 기준 거래대금 비중이 코스피 쪽으로 이동했습니다.",
                        "코스닥은 상대적으로 비중이 줄어든 상태입니다."]
    elif tone == "kosdaq":
        regime_lines = ["최근 30일 기준 거래대금 비중이 코스닥 쪽으로 이동했습니다.",
                        "코스피는 상대적으로 비중이 줄어든 상태입니다."]
    else:
        regime_lines = ["최근 30일 기준 거래대금 비중은 큰 변화 없이 유지되고 있습니다."]

    # 오늘의 핵심 변화 (조건문 우선순위: 점유율 상승폭 → 하락폭 → 유입 → 분배 → 혼조+대형)
    latest_theme = {}
    for th, seq in theme_series.items():
        if seq: latest_theme[th] = seq[-1]
    r30 = theme_summary["30"]["rising"]; f30 = theme_summary["30"]["falling"]
    key_changes = []
    if r30:
        top = r30[0]; th = top['theme']
        key_changes.append(f"{th}{josa(th,'은','는')} 최근 30일 거래대금 비중이 상승했습니다({top['from']:.1f}% → {top['to']:.1f}%).")
    if f30:
        bot = f30[0]; th = bot['theme']
        key_changes.append(f"{th}{josa(th,'은','는')} 최근 30일 거래대금 비중이 하락했습니다({bot['from']:.1f}% → {bot['to']:.1f}%).")
    # 유입 우세 테마 묶음
    inflow = [th for th,e in latest_theme.items() if e["badge"]=="유입 우세"]
    if inflow:
        names = "·".join(inflow[:3])
        key_changes.append(f"{names}{josa(inflow[:3][-1],'은','는')} 거래대금 기준 유입 우세로 분류됩니다.")
    # 분배 우세 후보
    outflow = [th for th,e in latest_theme.items() if e["badge"]=="분배 우세 후보"]
    if outflow:
        names = "·".join(outflow[:3])
        key_changes.append(f"{names}{josa(outflow[:3][-1],'은','는')} 하락 거래대금이 우세한 분배 후보 구간입니다.")
    key_changes = key_changes[:3]

    market_summary_block = {
        "regime": {"label": regime_label, "badge": "거래대금 기준", "tone": tone, "lines": regime_lines},
        "keyChanges": key_changes
    }

    # ===== STEP2: 테마 상세 (점유율 90일 시계열 + 윈도우 summary, netFlow 비공개) =====
    def flow_label(deltaPp, badge):
        # 점유율 방향(관심도) + 내부 방향(badge)을 자연스럽게. 모순 표현 회피.
        if deltaPp > 0.3:   share_txt = "거래대금 비중 상승"
        elif deltaPp < -0.3: share_txt = "거래대금 비중 하락"
        else:               share_txt = "거래대금 비중 유지"
        # badge가 표본부족/대장주단독이면 그대로, 아니면 방향 보조
        if badge in ("표본 부족", "대장주 단독"):
            return share_txt + " · " + badge
        if badge == "유입 우세":     inner = "내부 상승 우세"
        elif badge == "분배 우세 후보": inner = "내부 하락 우세"
        else:                        inner = "내부 방향 혼조"
        return share_txt + " · " + inner
    theme_details = {}
    for th, seq in theme_series.items():
        series = [{"date": e["date"], "sharePct": round(e["shareOfMarket"]*100,2),
                   "badge": e["badge"]} for e in seq]
        summ = {}
        shares = [e["shareOfMarket"] for e in seq]
        latest_badge = seq[-1]["badge"] if seq else "혼조"
        for w in WINDOWS:
            f, t, d = window_move_pct(shares, w)
            summ[str(w)] = {"from": f, "to": t, "deltaPp": d,
                            "badge": latest_badge, "label": flow_label(d, latest_badge)}
        theme_details[th] = {"series": series, "summary": summ}

    return {
        "generatedAt": out["generatedAt"],
        "startDate": out["startDate"], "endDate": out["endDate"],
        "windows": WINDOWS, "note": out["note"],
        "marketSummary": market_summary_block,
        "market": {"series": market_line, "summary": market_summary},
        "themes": {"summary": theme_summary},
        "themeDetails": theme_details
    }

def main():
    os.makedirs(SERIES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_WEB_PUBLIC), exist_ok=True)
    out, dates, market_series, theme_series = build()
    # 원본은 내부에만 (웹 서빙 안 함)
    with open(OUT_INTERNAL, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    # 공개 slim만 output/
    pub = build_public(out, market_series, theme_series)
    with open(OUT_WEB_PUBLIC, "w", encoding="utf-8") as f:
        json.dump(pub, f, ensure_ascii=False, separators=(",",":"))
    # 검증 출력
    ks = out["market"]["KOSPI"][-1]["share"] if out["market"]["KOSPI"] else 0
    kq = out["market"]["KOSDAQ"][-1]["share"] if out["market"]["KOSDAQ"] else 0
    internal_sz = os.path.getsize(OUT_INTERNAL)
    public_sz = os.path.getsize(OUT_WEB_PUBLIC)
    print("flow_series OK")
    print(f"dates: {out['startDate']} ~ {out['endDate']} / {out['days']} days")
    print(f"KOSPI latest share: {ks*100:.1f}%")
    print(f"KOSDAQ latest share: {kq*100:.1f}%")
    print(f"theme coverage: {out['coverage']['themeCoveredTradingValueShare']*100:.1f}%")
    print("themes:", len(out["themes"]))
    print("top rising share (30d):", ", ".join(r["theme"] for r in out["summary"]["themeRotation"]["rising"]))
    print("top falling share (30d):", ", ".join(r["theme"] for r in out["summary"]["themeRotation"]["falling"]))
    print(f"internal: {internal_sz} bytes (data/series/, 웹서빙 X)")
    print(f"public:   {public_sz} bytes (output/flow_series_public.json, 웹서빙 O)")
    print(f"public windows: {pub['windows']}")

if __name__ == "__main__":
    main()
