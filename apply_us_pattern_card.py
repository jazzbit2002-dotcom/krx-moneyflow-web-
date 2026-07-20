#!/usr/bin/env python3
# apply_us_pattern_card.py — US 종목 페이지 '차트 형태' 카드 추가 (서버 적용본, 완전판)
#
# 데이터 원천: /root/f29-pattern-lab/history/pattern_judgments/{YYYY-MM-DD}.jsonl
#   스키마: {ticker, date, data_last_date, bars, engine_version,
#            top1:{pattern_id, pattern_title, score}, top2, top3, ...}
#
# 원칙:
#   - 유사도 재계산 금지. Pattern Lab top1.score 그대로 표시 (SSOT 이원화 방지).
#   - 보유 종목만 렌더. 미보유 → 카드 생략. 빈 카드 금지(§7 계약).
#   - 시점 갭 정면 표기: pattern cron 07:30/07:40 UTC > US 빌더 07:00 UTC → 전일 판정 참조.
#     data_last_date != updated 이면 형태 기준일 명시(보정·추정 금지).
#   - 컴플라이언스: 상승·하락 확률 표현 금지, '적중/신뢰도' 어근 금지,
#     Pattern Lab 문구 승계("학습용 형태 닮음 점수, 확률 아님").
#   - match.html에 쿼리 파라미터 처리 없음 → 링크는 /lab/match.html 까지만.
import hashlib, io, os, sys, shutil, datetime

P = '/root/moneyflow/build_us_stock_pages.py'
BASE_SHA = 'bc4f67589f5754e67944b03a85673011b1ee43c1d24157868523bbe618cb5047'

raw = io.open(P, encoding='utf-8').read()
before = hashlib.sha256(raw.encode('utf-8')).hexdigest()
if before != BASE_SHA:
    print('SHA MISMATCH — abort (현재 %s)' % before[:12]); sys.exit(1)
if 'US-P05-PATTERN' in raw:
    print('ALREADY APPLIED (US-P05-PATTERN) — abort'); sys.exit(1)

s = raw
anchors = []

anchors.append(('fn',
"""def card_history(rec, hist, updated):""",
'''def load_pattern_judgments():
    """US-P05-PATTERN: Pattern Lab 판정 최신 가용분 로드 -> {TICKER: row}.
    빌더(07:00 UTC)가 pattern cron(07:30/07:40)보다 먼저 돌아 당일 파일이 없을 수 있다.
    가장 최근 존재 파일을 쓰고, 화면에 그 기준일을 명시한다(보정/추정 금지)."""
    import glob
    d = '/root/f29-pattern-lab/history/pattern_judgments'
    try:
        files = sorted(glob.glob(os.path.join(d, '*.jsonl')))
    except Exception:
        return {}
    if not files:
        return {}
    out = {}
    try:
        with open(files[-1], encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                t = r.get('ticker')
                if t and isinstance(r.get('top1'), dict):
                    out[t] = r
    except Exception:
        return {}
    return out


def card_pattern(rec, pj, updated):
    """차트 형태 (US-P05-PATTERN). Pattern Lab top1 표시, 미보유 -> None(카드 생략)."""
    r = (pj or {}).get(rec.get('ticker'))
    if not r:
        return None
    t1 = r.get('top1') or {}
    title = t1.get('pattern_title')
    score = t1.get('score')
    if not title or score is None:
        return None
    base = r.get('data_last_date') or r.get('date') or ''
    bars = r.get('bars', 60)
    note = ''
    if base and updated and base != updated:
        note = (f'<p class="hint">형태 비교 기준일 {esc(base)} — 이 페이지 기준일'
                f'({esc(updated)})과 다릅니다.</p>')
    return (f'<section class="card"><h2>차트 형태</h2>'
            f'<p class="pat"><span class="patname">{esc(title)}</span>'
            f'<span class="patscore">닮음 {esc(score)}<span class="patmax">/100</span></span></p>'
            f'<p class="hint">최근 {esc(bars)}거래일 종가 흐름을 학습용 형태와 비교한 닮음 '
            f'점수입니다. 상승·하락 확률이 아니며 방향을 전망하지 않습니다.</p>'
            f'{note}'
            f'<p class="patlink"><a href="/lab/match.html">차트분석 연구소에서 직접 비교 &rsaquo;</a></p>'
            f'</section>')


def card_history(rec, hist, updated):'''))

anchors.append(('sig',
"""def page_html(rec, all_recs, hist, updated):""",
"""def page_html(rec, all_recs, hist, updated, pj=None):"""))

anchors.append(('assemble',
"""        c4 = card_theme_sync(rec, all_recs)
        c5 = card_bench(rec)
        c6 = card_meta(rec, updated)
        parts = [p for p in (c1, c2, c3, ch, c4, c5, c6) if p]""",
"""        c4 = card_theme_sync(rec, all_recs)
        cp = card_pattern(rec, pj, updated)   # US-P05-PATTERN: 미보유 시 None -> 생략
        c5 = card_bench(rec)
        c6 = card_meta(rec, updated)
        parts = [p for p in (c1, c2, c3, ch, c4, cp, c5, c6) if p]"""))

anchors.append(('call',
"""    built, indexed = [], []
    for r in positions:
        t = r.get('ticker')
        if not t: continue
        slug = slugify(t)
        html_out = page_html(r, positions, hist_map.get(t), updated)""",
"""    built, indexed = [], []
    pj = load_pattern_judgments()   # US-P05-PATTERN: 루프 밖 1회 로드
    print('[us-build] pattern_judgments=%d' % len(pj))
    for r in positions:
        t = r.get('ticker')
        if not t: continue
        slug = slugify(t)
        html_out = page_html(r, positions, hist_map.get(t), updated, pj)"""))

anchors.append(('css',
""".topchange{color:var(--sub);font-size:.86rem;margin:-6px 0 18px;white-space:normal;word-break:keep-all}
'''""",
""".topchange{color:var(--sub);font-size:.86rem;margin:-6px 0 18px;white-space:normal;word-break:keep-all}
.pat{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:2px 0 10px}
.patname{font-size:1.15rem;font-weight:700;color:var(--tx)}
.patscore{font-size:1.05rem;font-weight:700;color:var(--gold);white-space:nowrap}
.patmax{font-size:.8rem;font-weight:400;color:var(--sub);margin-left:1px}
.patlink{margin-top:10px}
.patlink a{color:var(--teal);text-decoration:none;font-size:.9rem}
.patlink a:hover{text-decoration:underline}
'''"""))

for label, old, new in anchors:
    cnt = s.count(old)
    if cnt != 1:
        print('ANCHOR FAIL [%s] count=%d — abort' % (label, cnt)); sys.exit(2)
    s = s.replace(old, new)

for need in ('def load_pattern_judgments', 'def card_pattern', 'US-P05-PATTERN',
             'updated, pj)', '.patscore{'):
    if need not in s:
        print('GUARD FAIL: %r 누락' % need); sys.exit(3)
_c = s.count('cp = card_pattern(rec, pj, updated)')
if _c != 1:
    print('GUARD FAIL: card_pattern 호출부 %d회 (expected 1)' % _c); sys.exit(4)
if s.count('c4, cp, c5, c6') != 1:
    print('GUARD FAIL: parts 조립에 cp 미포함'); sys.exit(5)

ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
bdir = '/root/f29-backups/us-pattern-' + ts
os.makedirs(bdir, exist_ok=True)
shutil.copy2(P, os.path.join(bdir, 'build_us_stock_pages.py'))

mode = os.stat(P).st_mode & 0o777
tmp = P + '.tmp'
io.open(tmp, 'w', encoding='utf-8').write(s)
os.replace(tmp, P)
os.chmod(P, mode)

print('OK anchors=%d' % len(anchors))
print('backup=%s' % bdir)
print('before_sha=%s' % before)
print('after_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('after_bytes=%d' % len(s.encode('utf-8')))
