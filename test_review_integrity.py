# -*- coding: utf-8 -*-
"""정본 무결성 통합 테스트 (r3.1 계약 복원, v1.1 파일명 기준).

brief.json 누락 / 실측 SHA 불일치 / 원시 응답 객체 불일치 / status·mode·contract_ok
불일치 상황에서 latest 자격이 차단되는지 확인한다.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brief_contract_v1_1 as bc
import build_review_v2_1 as br

# 계약 fixture 재사용
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "test_contract.py"), encoding="utf-8").read()
exec(_src.split("P = 0")[0])  # noqa: S102 - CTX, mk, S 로드

P = 0
F = 0


def check(name, got, want):
    global P, F
    ok = (got == want)
    if ok:
        P += 1
    else:
        F += 1
    print("%s %-44s got=%-5s want=%s" % ("O" if ok else "X", name, got, want))


def make_run(root, rid, tamper=None):
    """정상 run 하나를 만든 뒤 tamper 로 변형한다."""
    rd = os.path.join(root, "evidence", rid)
    os.makedirs(rd, exist_ok=True)
    brief = mk()
    raw = json.dumps(brief, ensure_ascii=False)
    val = bc.validate_brief(brief, CTX, "baseline_only", "2026-07-17")
    assert val.ok, val.violations

    bpath = os.path.join(rd, "brief.json")
    with open(bpath, "w", encoding="utf-8") as fh:
        json.dump(brief, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    with open(bpath, "rb") as fh:
        file_sha = hashlib.sha256(fh.read()).hexdigest()

    open(os.path.join(rd, "response.txt"), "w", encoding="utf-8").write(raw)
    ev = {"run_id": rid, "model": "claude-opus-4-8", "stop_reason": "end_turn",
          "current_as_of": "2026-07-17", "previous_as_of": None,
          "comparison_status": "baseline_only",
          "close_snapshot_state": "fresh", "daily_state": "fresh",
          "contract_mode": "v7", "contract_ok": True,
          "brief_sha256": file_sha, "status": "brief_saved",
          "input_tokens": 15000, "output_tokens": 2100, "cost_usd": 0.13}
    if tamper:
        tamper(rd, ev, brief)
    json.dump(ev, open(os.path.join(rd, "evidence.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(val.to_dict(), open(os.path.join(rd, "validation.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=2)
    return rd, ev, val


root = tempfile.mkdtemp(prefix="f29_integ_")
try:
    # I1 정상 run -> 적격
    rd, ev, val = make_run(root, "20260721T010000Z-good")
    check("I1 정상 run latest 적격", br.eligible(ev, val.to_dict(), rd), True)

    # I2 brief.json 없음
    def t_missing(rd, ev, brief):
        os.remove(os.path.join(rd, "brief.json"))
    rd, ev, val = make_run(root, "20260721T020000Z-missing", t_missing)
    check("I2 brief.json 없음 -> 부적격", br.eligible(ev, val.to_dict(), rd), False)

    # I3 실측 SHA 불일치 (파일 변조)
    def t_sha(rd, ev, brief):
        b = dict(brief)
        b["headline"] = "변조된 제목입니다 검수용"
        with open(os.path.join(rd, "brief.json"), "w", encoding="utf-8") as fh:
            json.dump(b, fh, ensure_ascii=False, indent=2)
    rd, ev, val = make_run(root, "20260721T030000Z-shabad", t_sha)
    check("I3 파일 SHA 불일치 -> 부적격", br.eligible(ev, val.to_dict(), rd), False)

    # I4 원시 응답 객체 불일치 (SHA는 맞게 재기록)
    def t_obj(rd, ev, brief):
        b = dict(brief)
        b["headline"] = "다른 제목으로 교체했습니다"
        p = os.path.join(rd, "brief.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(b, fh, ensure_ascii=False, indent=2)
        with open(p, "rb") as fh:
            ev["brief_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    rd, ev, val = make_run(root, "20260721T040000Z-objdiff", t_obj)
    check("I4 원시<->정본 객체 불일치 -> 부적격",
          br.eligible(ev, val.to_dict(), rd), False)

    # I5 status != brief_saved
    def t_status(rd, ev, brief):
        ev["status"] = "draft_saved"
    rd, ev, val = make_run(root, "20260721T050000Z-status", t_status)
    check("I5 status 불일치 -> 부적격", br.eligible(ev, val.to_dict(), rd), False)

    # I6 contract_mode / contract_ok 불일치
    def t_mode(rd, ev, brief):
        ev["contract_mode"] = "v6"
        ev["contract_ok"] = None
    rd, ev, val = make_run(root, "20260721T060000Z-mode", t_mode)
    check("I6 contract_mode 불일치 -> 부적격",
          br.eligible(ev, val.to_dict(), rd), False)

    # I7 변조 run 이 latest 를 차지하지 못함
    br.BASE = root
    br.EVIDIR = os.path.join(root, "evidence")
    br.REVDIR = os.path.join(root, "review")
    rc = br.main()
    latest = os.path.join(root, "review", "latest.html")
    html = open(latest, encoding="utf-8").read() if os.path.isfile(latest) else ""
    bad_ids = ("20260721T020000Z-missing", "20260721T030000Z-shabad",
               "20260721T040000Z-objdiff", "20260721T050000Z-status",
               "20260721T060000Z-mode")
    only_good = ("20260721T010000Z-good" in html) and \
        all(x not in html for x in bad_ids)
    check("I7 변조 run latest 배제 / 정상 run 유지", only_good, True)
    check("I7b 실패 run 화면도 생성",
          os.path.isfile(os.path.join(root, "review", "runs",
                                      "20260721T030000Z-shabad.html")), True)
finally:
    shutil.rmtree(root, ignore_errors=True)

print("\n==== 정본 무결성 %d passed / %d failed ====" % (P, F))
raise SystemExit(1 if F else 0)
