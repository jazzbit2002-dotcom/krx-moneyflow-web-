#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F29 v7.1 structured review renderer.

Reads evidence/<run_id>/{evidence.json, validation.json, response.json,
response.raw.txt, briefing_context_raw.json} and produces:

  evidence/<run_id>/review.html
  review/runs/<run_id>.html      (portable copy)
  review/index.html
  review/latest.html             (only fully-passing runs)

Derived artifact only. Canonical files are never modified.
No external CSS/JS/CDN. Every model string is HTML-escaped.
"""

import hashlib
import html
import json
import os
import sys

BASE = "/root/moneyflow/briefing_delivery"
EVIDIR = os.path.join(BASE, "evidence")
REVDIR = os.path.join(BASE, "review")

CSS = """
:root{--bg:#0A0E17;--card:#131A28;--line:#1F2A3D;--txt:#E8EDF7;--txt2:#8B9AB5;
--txt3:#5A6B84;--teal:#3DD8B0;--gold:#D8B45F;--red:#F0997B}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--txt);line-height:1.6;
font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:20px}
h1{font-size:18px;color:var(--teal);margin-bottom:4px}
.sub{font-size:12px;color:var(--txt3);margin-bottom:16px}
.card{background:var(--card);border-radius:10px;padding:14px 16px;margin-bottom:14px}
.card h2{font-size:12px;color:var(--txt3);text-transform:uppercase;letter-spacing:.08em;
padding-bottom:8px;border-bottom:.5px solid var(--line);margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
td{padding:5px 0;border-bottom:.5px solid var(--line);vertical-align:top}
td:first-child{color:var(--txt2);width:38%}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:11px;word-break:break-all}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;
border:1px solid currentColor;margin-right:6px}
.ok{color:var(--teal)}.warn{color:var(--gold)}.bad{color:var(--red)}
.v{font-size:12.5px;padding:5px 0;border-bottom:.5px solid var(--line);color:var(--red)}
.v:last-child{border-bottom:none}
.hl{font-size:20px;font-weight:600;line-height:1.4;margin-bottom:6px}
.deck{font-size:14px;color:var(--txt2);margin-bottom:12px}
.kp{font-size:13.5px;padding:4px 0 4px 14px;position:relative}
.kp:before{content:"-";position:absolute;left:2px;color:var(--teal)}
.sec{border-top:.5px solid var(--line);padding-top:10px;margin-top:12px}
.sec .st{font-size:14px;font-weight:600;color:var(--teal);margin-bottom:4px}
.sec .sb{font-size:13.5px;white-space:pre-wrap;line-height:1.8}
.tag{font-size:11px;color:var(--txt3);margin-top:6px}
.wp{font-size:13px;padding:4px 0 4px 14px;position:relative;color:var(--txt2)}
.wp:before{content:"?";position:absolute;left:2px;color:var(--gold)}
.disc{font-size:11.5px;color:var(--txt3);margin-top:14px;padding-top:10px;
border-top:.5px solid var(--line)}
.chan{background:#0E1420;border-radius:8px;padding:12px;font-size:13.5px;
white-space:pre-wrap}
.note{font-size:11px;color:var(--txt3);margin-top:14px;line-height:1.7}
details{margin-top:6px}summary{cursor:pointer;color:var(--txt2);font-size:12px}
pre{white-space:pre-wrap;word-break:break-all;font-family:ui-monospace,Menlo,monospace;
font-size:10.5px;color:var(--txt2);margin-top:8px}
.idx td{font-size:12.5px}
"""

DIGEST_CLASS = {"PASS": "ok", "REQUIRED": "warn", "SKIPPED_MISSING": "warn",
                "SKIPPED_STALE": "warn", "FAIL": "bad", "NOT_RUN": "warn"}


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def gate_rows(ev, val, rd=None):
    """Validation summary rows: (label, value, css class)."""
    parsed = val is not None and "JSON parse failed" not in " ".join(
        val.get("violations") or [])
    schema = (val or {}).get("schema_validation", "NOT_RUN")
    contract_ok = bool((val or {}).get("ok"))
    viol = (val or {}).get("violations") or []
    return [
        ("strict JSON parse", "PASS" if parsed else "FAIL", "ok" if parsed else "bad"),
        ("JSON Schema", schema, "ok" if schema == "DRAFT202012" else "bad"),
        ("contract", "PASS" if contract_ok else "FAIL (%d)" % len(viol),
         "ok" if contract_ok else "bad"),
        ("comparison_status", ev.get("comparison_status"),
         "ok" if ev.get("comparison_status") in ("baseline_only", "ready") else "bad"),
        ("as_of", "%s (prev %s)" % (ev.get("current_as_of"),
                                    ev.get("previous_as_of") or "-"), "ok"),
        ("article length", "%s자" % (val or {}).get("article_chars"),
         "ok" if contract_ok else "warn"),
        ("digest_usage", (val or {}).get("digest_usage", "NOT_RUN"),
         DIGEST_CLASS.get((val or {}).get("digest_usage", "NOT_RUN"), "warn")),
        ("field_scan", "위반 %d개 필드" % len((val or {}).get("field_scan") or {}),
         "ok" if not (val or {}).get("field_scan") else "bad"),
        ("brief_sha256", (val or {}).get("brief_sha256") or "-", "ok"),
        ("eligible_for_latest", "true" if eligible(ev, val, rd) else "false",
         "ok" if eligible(ev, val, rd) else "bad"),
    ]


def integrity(rd, ev):
    """Canonical-artifact integrity gates (restored r3.1 contract).

    Returns (ok, [(label, value, css_class), ...]).
    """
    rows = []
    bpath = os.path.join(rd, "brief.json")
    exists = os.path.isfile(bpath)
    rows.append(("brief.json 존재", "O" if exists else "X", "ok" if exists else "bad"))

    st_ok = ev.get("status") == "brief_saved"
    rows.append(("status", ev.get("status"), "ok" if st_ok else "bad"))
    mode_ok = ev.get("contract_mode") == "v7"
    rows.append(("contract_mode", ev.get("contract_mode"), "ok" if mode_ok else "bad"))
    c_ok = ev.get("contract_ok") is True
    rows.append(("contract_ok", ev.get("contract_ok"), "ok" if c_ok else "bad"))

    rec = ev.get("brief_sha256")
    rows.append(("evidence.brief_sha256", (rec or "-")[:24], "ok" if rec else "bad"))

    sha_ok = False
    actual = None
    if exists:
        with open(bpath, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        sha_ok = bool(rec) and actual == rec
    rows.append(("brief.json 실측 SHA", (actual or "-")[:24],
                 "ok" if sha_ok else "bad"))

    same_ok = False
    detail = "비교 불가"
    if exists:
        raw = _read_text(os.path.join(rd, "response.txt")) or \
            _read_text(os.path.join(rd, "response.raw.txt"))
        brief = _read_json(bpath)
        if raw is not None and brief is not None:
            try:
                import brief_contract_v1_1 as _bc
                parsed = _bc.parse_response(raw)
                same_ok = (parsed == brief)
                detail = "일치" if same_ok else "불일치(변조 의심)"
            except Exception as exc:
                detail = "원시 파싱 실패: %s" % type(exc).__name__
    rows.append(("원시 응답 <-> brief.json", detail, "ok" if same_ok else "bad"))

    ok = all(x[2] == "ok" for x in rows)
    return ok, rows


def eligible(ev, val, rd=None):
    """latest.html candidacy: contract gates + canonical-artifact integrity."""
    if not val or not val.get("ok"):
        return False
    if val.get("schema_validation") != "DRAFT202012":
        return False
    if ev.get("stop_reason") != "end_turn":
        return False
    if ev.get("close_snapshot_state") != "fresh":
        return False
    if ev.get("daily_state") != "fresh":
        return False
    if ev.get("comparison_status") not in ("baseline_only", "ready"):
        return False
    if rd is not None:
        ok, _ = integrity(rd, ev)
        if not ok:
            return False
    return True


def render_page(brief):
    if not brief:
        return '<div class="card"><h2>Page preview</h2>' \
               '<div class="warn">response.json 없음 — 검증 실패 run</div></div>'
    kp = "".join('<div class="kp">%s</div>' % esc(x) for x in (brief.get("key_points") or []))
    secs = ""
    for s in (brief.get("sections") or []):
        tags = []
        if s.get("tickers"):
            tags.append("종목 " + ", ".join(esc(t) for t in s["tickers"]))
        if s.get("themes"):
            tags.append("테마 " + ", ".join(esc(t) for t in s["themes"]))
        secs += ('<div class="sec"><div class="st">%s <span class="mono">[%s]</span></div>'
                 '<div class="sb">%s</div><div class="tag">%s</div></div>'
                 % (esc(s.get("title")), esc(s.get("id")), esc(s.get("body")),
                    esc(" · ".join(tags))))
    wp = "".join('<div class="wp">%s</div>' % esc(x) for x in (brief.get("watchpoints") or []))
    return ('<div class="card"><h2>Page preview</h2>'
            '<div class="hl">%s</div><div class="deck">%s</div>%s%s'
            '<div style="margin-top:14px">%s</div>'
            '<div class="disc">%s</div></div>'
            % (esc(brief.get("headline")), esc(brief.get("deck")), kp, secs, wp,
               esc(brief.get("disclaimer"))))


def render_channels(brief):
    if not brief:
        return ""
    return ('<div class="card"><h2>SNS preview</h2><div class="chan">%s</div>'
            '<div class="tag">%d자</div></div>'
            '<div class="card"><h2>Email preview</h2>'
            '<table><tr><td>subject</td><td>%s</td></tr>'
            '<tr><td>preview</td><td>%s</td></tr></table></div>'
            % (esc(brief.get("social_summary")),
               len(brief.get("social_summary") or ""),
               esc(brief.get("email_subject")), esc(brief.get("email_preview"))))


def render_review(run_id, ev, val, brief, raw_text, rd=None):
    rows = "".join('<tr><td>%s</td><td><span class="badge %s">%s</span></td></tr>'
                   % (esc(k), c, esc(v)) for k, v, c in gate_rows(ev, val, rd))
    integ = ""
    if rd is not None:
        iok, irows = integrity(rd, ev)
        integ = ('<div class="card"><h2>정본 무결성 %s</h2><table>%s</table></div>'
                 % ("PASS" if iok else "FAIL",
                    "".join('<tr><td>%s</td><td><span class="badge %s">%s</span></td></tr>'
                            % (esc(k), c, esc(v)) for k, v, c in irows)))
    viol = (val or {}).get("violations") or []
    vhtml = "".join('<div class="v">%s</div>' % esc(v) for v in viol) or \
        '<div class="chk ok">위반 0건</div>'
    fs = (val or {}).get("field_scan") or {}
    fshtml = "".join('<tr><td>%s</td><td class="bad">%s</td></tr>'
                     % (esc(k), esc(", ".join(v))) for k, v in sorted(fs.items()))
    meta = [("model", ev.get("model")), ("stop_reason", ev.get("stop_reason")),
            ("input_tokens", ev.get("input_tokens")),
            ("output_tokens", ev.get("output_tokens")),
            ("cost_usd", ev.get("cost_usd")),
            ("close_snapshot", ev.get("close_snapshot_state")),
            ("daily", ev.get("daily_state")),
            ("snapshot_sha256", ev.get("snapshot_sha256")),
            ("prompt_sha256", ev.get("prompt_sha256")),
            ("output_sha256", ev.get("output_sha256"))]
    mhtml = "".join('<tr><td>%s</td><td class="mono">%s</td></tr>' % (esc(k), esc(v))
                    for k, v in meta)
    rawblock = ""
    if brief:
        rawblock = ('<details><summary>Raw JSON 펼치기</summary><pre>%s</pre></details>'
                    % esc(json.dumps(brief, ensure_ascii=False, indent=1)))
    elif raw_text:
        rawblock = ('<details open><summary>모델 원문 (파싱 실패)</summary><pre>%s</pre>'
                    '</details>' % esc(raw_text[:4000]))
    return """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>검수 %s</title><style>%s</style></head><body><div class="wrap">
<h1>미국장 매크로 데일리 초안 검수 (v7.1)</h1>
<div class="sub">run_id %s &nbsp;|&nbsp; 내부 검수용 파생 문서. 게시물 아님.</div>
<div class="card"><h2>Validation summary</h2><table>%s</table></div>
<div class="card"><h2>위반 목록</h2>%s%s</div>
%s
%s%s
<div class="card"><h2>실행 정보</h2><table>%s</table></div>
<div class="card"><h2>Raw JSON</h2>%s</div>
<div class="note">response.json 과 evidence.json 이 정본이며 이 HTML 은 파생 산출물입니다.
언제든 재생성 가능하며 정본을 수정하지 않습니다.</div>
</div></body></html>""" % (
        esc(run_id), CSS, esc(run_id), rows, vhtml,
        ("<table>%s</table>" % fshtml) if fshtml else "", integ,
        render_page(brief), render_channels(brief), mhtml, rawblock)


def render_index(runs):
    rows = "".join(
        '<tr><td><a href="runs/%s.html">%s</a></td><td>%s</td><td>%s</td>'
        '<td class="%s">%s</td><td class="%s">%s</td><td>%s</td></tr>'
        % (esc(r["run_id"]), esc(r["run_id"][:15]),
           esc(r["ev"].get("current_as_of")), esc(r["ev"].get("comparison_status")),
           "ok" if (r["val"] or {}).get("ok") else "bad",
           "PASS" if (r["val"] or {}).get("ok") else "FAIL",
           DIGEST_CLASS.get((r["val"] or {}).get("digest_usage", "NOT_RUN"), "warn"),
           esc((r["val"] or {}).get("digest_usage", "-")),
           "적격" if r["eligible"] else "부적격")
        for r in runs)
    return """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>초안 검수 목록</title><style>%s</style></head><body><div class="wrap">
<h1>미국장 매크로 데일리 검수 목록 (v7.1)</h1>
<div class="sub">총 %d건 &nbsp;|&nbsp; 내부 검수용. 게시물 아님.</div>
<div class="card"><table class="idx">
<tr><td>run_id</td><td>기준일</td><td>상태</td><td>검증</td><td>digest</td><td>latest</td></tr>
%s</table></div>
<div class="note">최근 적격 검수본은 latest.html 입니다. 검증 실패 run 도 목록에 남지만
latest 를 덮어쓰지 않습니다.</div>
</div></body></html>""" % (CSS, len(runs), rows)


def main():
    if not os.path.isdir(EVIDIR):
        print("no evidence dir:", EVIDIR)
        return 1
    os.makedirs(os.path.join(REVDIR, "runs"), exist_ok=True)

    runs = []
    for rid in sorted(os.listdir(EVIDIR)):
        rd = os.path.join(EVIDIR, rid)
        ev = _read_json(os.path.join(rd, "evidence.json"))
        if ev is None:
            continue
        val = _read_json(os.path.join(rd, "validation.json"))
        brief = _read_json(os.path.join(rd, "brief.json"))
        raw = _read_text(os.path.join(rd, "response.raw.txt")) or \
            _read_text(os.path.join(rd, "response.txt"))
        elig = eligible(ev, val, rd)
        h = render_review(rid, ev, val, brief, raw, rd)
        for path in (os.path.join(rd, "review.html"),
                     os.path.join(REVDIR, "runs", rid + ".html")):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(h)
            os.replace(tmp, path)
        runs.append({"run_id": rid, "ev": ev, "val": val, "html": h, "eligible": elig})
        print("review -> %s | contract=%s | digest=%s | latest자격=%s"
              % (rid, "PASS" if (val or {}).get("ok") else "FAIL",
                 (val or {}).get("digest_usage", "-"), "O" if elig else "X"))

    if not runs:
        print("no runs found")
        return 0

    runs.sort(key=lambda r: r["run_id"], reverse=True)
    tmp = os.path.join(REVDIR, "index.html.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(render_index(runs))
    os.replace(tmp, os.path.join(REVDIR, "index.html"))
    print("index.html   ->", os.path.join(REVDIR, "index.html"))

    elig = [r for r in runs if r["eligible"]]
    if elig:
        tmp = os.path.join(REVDIR, "latest.html.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(elig[0]["html"])
        os.replace(tmp, os.path.join(REVDIR, "latest.html"))
        print("latest.html  -> run %s" % elig[0]["run_id"])
    else:
        print("latest.html  -> 갱신 안 함 (적격 run 없음, 기존 latest 유지)")
    print("REVIEW BUILD: DONE (%d runs, %d eligible)" % (len(runs), len(elig)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
