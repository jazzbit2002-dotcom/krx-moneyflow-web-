# -*- coding: utf-8 -*-
"""brief_contract_v1_1 regression suite.

Every negative case asserts the *expected* violation message, so removing a
check cannot be masked by an unrelated failure. Exits non-zero on any failure.
"""
import copy

import brief_contract_v1_1 as bc

DISC = bc.DISCLAIMER

CTX = {
    "as_of": "2026-07-17",
    "market_internals": {
        "market_close_snapshot": {"as_of": "2026-07-17",
                                  "freshness": {"state": "fresh"},
                                  "data": {"spy": 743.23, "vix": 18.46}},
        "daily": {"freshness": {"state": "fresh"}, "data": {"uvol": 705000000}}},
    "leaders": [{"ticker": "MSFT", "name": "마이크로소프트", "theme": "빅테크/클라우드"}],
    "exits": [{"ticker": "MRVL", "name": "마벨", "theme": "AI반도체"}],
    "moneyflow_digest": {
        "theme_ranking": {"top": [{"theme": "금융", "score": 89},
                                  {"theme": "헬스혁신", "score": 86}]},
        "horizon_leaders": {"d7": ["필수소비", "금융"], "d30": ["금융"],
                            "d90": ["반도체", "사이버보안"]},
        "value_chains": [{"group": "반도체", "lead": "반도체", "gap": 13,
                          "members": [{"theme": "반도체", "score": 41},
                                      {"theme": "반도체장비", "score": 34}]}],
        "strength_quality": {"theme": "금융"},
        "stock_radar": {
            "dual_axis_winners": [{"ticker": "MSFT", "name": "마이크로소프트"}],
            "dual_axis_laggards": [{"ticker": "MRVL", "name": "마벨"}]}}}


def S(i, t, b, tick=None, th=None):
    return {"id": i, "title": t, "body": b, "tickers": tick or [], "themes": th or []}


ROT = ("짧은 구간에서는 필수소비가 앞선 흐름이었고 긴 구간 기준으로는 반도체가 여전히 위쪽에 자리했습니다. "
       "두 구간의 주도축이 서로 다르다는 점이 오늘의 관찰 대상입니다. "
       "금융도 상위권을 지켰고 사이버보안 역시 긴 구간에서 이름을 올렸습니다. ") * 2
VCR = ("반도체장비는 계열 안에서 뒤쪽에 놓였고 격차가 남아 있습니다. "
       "MSFT는 자기 업종과 시장을 모두 앞선 반면 흐름이 약해진 종목도 함께 있었습니다. "
       "같은 업종 안에서도 방향이 갈렸다는 뜻입니다. ") * 2
CON = "오늘 시장은 한 방향으로 쏠리지 않았고 업종에 따라 선택이 갈린 하루였습니다. " * 5
NXT = "다음 거래일에는 앞선 업종의 흐름이 이어지는지와 뒤처진 쪽이 회복하는지 확인합니다. " * 5


def mk():
    return {
        "schema_version": "us_macro_brief_v1", "as_of": "2026-07-17",
        "headline": "업종별로 갈린 하루의 시장 기록",
        "deck": "시장은 한 방향으로 쏠리지 않았고 업종에 따라 흐름이 나뉘었습니다. 짧은 구간과 긴 구간의 주도축도 서로 달랐습니다.",
        "key_points": ["시장의 선택이 업종별로 갈렸습니다",
                       "짧은 구간과 긴 구간의 주도축이 달랐습니다",
                       "같은 업종 안에서도 종목 차이가 있었습니다"],
        "sections": [S("conclusion", "오늘의 결론", CON),
                     S("rotation", "선택이 옮겨간 곳", ROT, [],
                       ["필수소비", "반도체", "금융", "사이버보안"]),
                     S("value_chain_radar", "산업 안의 강약", VCR, ["MSFT"], ["반도체장비"]),
                     S("next_session", "다음 거래일", NXT)],
        "watchpoints": ["앞선 업종의 흐름이 다음 거래일에도 이어지는지 확인합니다",
                        "두 구간의 주도축 차이가 좁혀지는지 살펴봅니다"],
        "social_summary": "오늘 미국 시장은 한 방향으로 쏠리지 않았습니다. 업종에 따라 흐름이 갈렸고 짧은 구간과 긴 구간의 주도축도 서로 달랐습니다. 같은 업종 안에서도 종목별 차이가 나타났습니다.",
        "email_subject": "업종별로 갈린 하루",
        "email_preview": "시장은 한 방향으로 쏠리지 않았고 업종에 따라 흐름이 나뉘었습니다.",
        "disclaimer": DISC}


P = 0
F = 0


def run(name, brief, expect="FAIL", must_contain=None,
        status="baseline_only", asof="2026-07-17", ctx=CTX):
    global P, F
    r = bc.validate_brief(brief, ctx, status, asof)
    tag = "PASS" if r.ok else "FAIL"
    ok = (tag == expect)
    detail = ""
    if ok and expect == "FAIL" and must_contain:
        if not any(must_contain in v for v in r.violations):
            ok = False
            detail = "expected violation missing: %s" % must_contain
    if not ok and not detail:
        detail = (r.violations[:1] or [""])[0][:58]
    if ok:
        P += 1
    else:
        F += 1
    print("%s %-36s %-4s digest=%-16s art=%4d %s"
          % ("O" if ok else "X", name, tag, r.digest_usage, r.article_chars, detail))
    return r


print("=== 정상 ===")
run("T01 정상 fixture", mk(), expect="PASS")

print("\n=== digest 실사용 ===")
b = mk(); b["sections"][1]["body"] = CON; b["sections"][1]["themes"] = []
run("T02 rotation d7/d90 누락", b, must_contain="short-term (d7) and")
b = mk(); b["sections"][2]["body"] = CON; b["sections"][2]["tickers"] = []
b["sections"][2]["themes"] = []
run("T03 vcr 산업근거 누락", b, must_contain="industry-chain theme")
b = mk()
b["sections"] = [b["sections"][0], b["sections"][3],
                 S("breadth", "체력", CON), S("commodities", "원자재", CON)]
run("T04 digest 필수섹션 누락", b, must_contain="required section(s) missing")

print("\n=== ticker 양방향 (L1-1) ===")
b = mk(); b["sections"][2]["tickers"] = []
run("T05 body 언급 ticker 배열 누락", b, must_contain="tickers array omits it")
b = mk(); b["sections"][0]["tickers"] = ["MSFT"]
run("T06 배열에만 있고 body 없음", b, must_contain="declared but not mentioned in body")
b = mk(); b["sections"][2]["body"] = VCR.replace("MSFT", "마이크로소프트")
run("T07 한글명 + 올바른 ticker", b, expect="PASS")
b = mk(); b["sections"][2]["body"] = VCR.replace("MSFT", "마이크로소프트")
b["sections"][2]["tickers"] = []
run("T08 한글명 + ticker 누락", b, must_contain="tickers array omits it")

print("\n=== themes 양방향 (L1-2) ===")
b = mk(); b["sections"][0]["themes"] = ["금융"]
run("T09 허용 theme이나 body 미언급", b, must_contain="declared but not discussed")
b = mk(); b["sections"][1]["themes"] = ["필수소비"]
run("T10 body theme 배열 누락", b, must_contain="themes array omits it")

print("\n=== 파생 폐포 (L1-3) ===")
b = mk(); b["headline"] = "금리가 42bp 내린 하루입니다"
run("T11 파생 신규 수치", b, must_contain="introduces number(s)")
b = mk(); b["social_summary"] = b["social_summary"] + " 마벨은 흐름이 약했습니다."
run("T12 파생 신규 종목", b, must_contain="introduces stock(s)")

print("\n=== 구조 ===")
b = mk(); b["key_points"] = b["key_points"][:2]
run("T13 key_points 2개", b, must_contain="exactly 3 items")
b = mk(); b["key_points"] = b["key_points"] + ["넷째 항목입니다 충분히 길게 씁니다"]
run("T14 key_points 4개", b, must_contain="exactly 3 items")
b = mk(); del b["sections"][2]["themes"]
run("T15 section themes 키 누락", b, must_contain="keys must be exactly")
b = mk(); del b["disclaimer"]
run("T16 disclaimer 누락", b, must_contain="missing top-level key")
b = mk(); b["disclaimer"] = "이 브리핑은 시장 상태를 정리한 정보입니다."
run("T17 disclaimer 변조", b, must_contain="disclaimer must match")
b = mk(); b["extra"] = 1
run("T18 추가 키", b, must_contain="unexpected top-level key")
b = mk(); b["schema_version"] = "v2"
run("T19 schema_version 불일치", b, must_contain="schema_version must equal")
b = mk(); b["as_of"] = "2026-07-16"
run("T20 as_of 불일치", b, must_contain="!= expected")
b = mk(); b["sections"].append(S("size_style", "대형", CON))
run("T21 baseline에 비교섹션", b, must_contain="must not include comparison")
b = mk(); b["sections"][0]["body"] = "짧음"
run("T22 body 길이 미달", b, must_contain="out of range 60-900")
b = mk(); b["social_summary"] = "짧다"
run("T23 social 길이 미달", b, must_contain="out of range 80-240")

print("\n=== 표현 계약 ===")
b = mk(); b["headline"] = "진입 시점을 알려드립니다 오늘도"
run("T24 금칙어(진입)", b, must_contain="금칙어:진입")
b = mk(); b["deck"] = b["deck"] + " 돈이 몰렸습니다."
run("T25 자금은유", b, must_contain="자금은유")
b = mk(); b["deck"] = b["deck"] + " 밸류체인 관점입니다."
run("T26 업계용어", b, must_contain="업계용어")
b = mk(); b["email_preview"] = "lifecycle 판정이 바뀌었습니다 오늘 기준으로"
run("T27 내부명칭 노출", b, must_contain="내부명칭")

print("\n=== comparison_status strict ===")
run("T31 status 누락", mk(), must_contain="comparison_status must be exactly", status=None)
run("T32 status 임의값", mk(), must_contain="comparison_status must be exactly", status="unknown")
run("T33 status ready (섹션 4개)", mk(), must_contain="requires 6-8 sections", status="ready")

print("\n=== 스키마 런타임 검증 ===")
r = bc.validate_brief(mk(), CTX, "baseline_only", "2026-07-17")
ok = (r.schema_validation == "DRAFT202012")
P += 1 if ok else 0
F += 0 if ok else 1
print("%s %-36s schema_validation=%s" % ("O" if ok else "X",
      "T34 schema 실행경로 사용", r.schema_validation))
b = mk(); b["headline"] = "짧다"
r = bc.validate_brief(b, CTX, "baseline_only", "2026-07-17")
ok = any(v.startswith("schema:") for v in r.violations)
P += 1 if ok else 0
F += 0 if ok else 1
print("%s %-36s %s" % ("O" if ok else "X", "T35 schema가 길이 위반 검출",
      [v for v in r.violations if v.startswith("schema:")][:1]))
b = mk(); b["sections"][0]["id"] = "bogus_id"
r = bc.validate_brief(b, CTX, "baseline_only", "2026-07-17")
ok = any("bogus_id" in v and v.startswith("schema:") for v in r.violations)
P += 1 if ok else 0
F += 0 if ok else 1
print("%s %-36s %s" % ("O" if ok else "X", "T36 schema가 section id enum 검출",
      "enum violation detected" if ok else "MISS"))

print("\n=== 파싱 (L1-4) ===")
CASES = [("순수 JSON", '{"a":1}', True), ("코드펜스", '```json\n{"a":1}\n```', False),
         ("앞 설명", '설명입니다\n{"a":1}', False), ("뒤 문자열", '{"a":1}\n끝', False),
         ("깨진 JSON", '{"a":', False), ("빈 응답", '   ', False)]
for nm, raw, should_ok in CASES:
    try:
        bc.parse_response(raw)
        got, msg = True, "parsed"
    except Exception as exc:
        got, msg = False, type(exc).__name__
    ok = (got == should_ok)
    P += 1 if ok else 0
    F += 0 if ok else 1
    print("%s %-36s %s" % ("O" if ok else "X", "P-" + nm, msg))

print("\n=== digest 결측/stale ===")
c2 = copy.deepcopy(CTX); c2["moneyflow_digest"] = {}
b = mk()
for sec in b["sections"]:
    sec["themes"] = []; sec["tickers"] = []
b["sections"][1]["body"] = CON
b["sections"][2]["body"] = CON
run("T28 digest 없음 -> SKIPPED_MISSING", b, expect="PASS", ctx=c2)
c3 = copy.deepcopy(CTX); c3["moneyflow_digest"]["freshness"] = {"state": "stale"}
b = mk()
for sec in b["sections"]:
    sec["themes"] = []; sec["tickers"] = []
b["sections"][1]["body"] = CON
b["sections"][2]["body"] = CON
run("T29 digest 자체 stale -> SKIPPED", b, expect="PASS", ctx=c3)
c4 = copy.deepcopy(CTX)
c4["market_internals"]["market_close_snapshot"]["freshness"] = {"state": "stale"}
r = bc.validate_brief(mk(), c4, "baseline_only", "2026-07-17")
ok = (r.digest_usage in ("PASS", "REQUIRED"))
P += 1 if ok else 0
F += 0 if ok else 1
print("%s %-36s digest=%s  (close stale은 digest 판정과 무관)"
      % ("O" if ok else "X", "T30 close stale != digest stale", r.digest_usage))

print("\n==== %d passed / %d failed ====" % (P, F))
raise SystemExit(1 if F else 0)
