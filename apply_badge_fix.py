#!/usr/bin/env python3
# apply_badge_fix.py — f29-search.js 시장 배지 보정 (서버 적용본)
# 결함1: .f29-mkt CSS 부재 → 배지가 평문으로 붙어 "한국삼성전자"로 보임.
# 결함2: 단일 시장 인덱스(weight=KR만)에서도 배지 렌더 → 구분 대상 없는 노이즈.
# 수정: (1) 라우터가 스타일 1회 주입(공유 컴포넌트, 페이지별 CSS 요구 안 함)
#       (2) ctx.hasUS(통합 인덱스)일 때만 배지 렌더
# 색: 기존 토큰 teal #3DD8B0 / gold #f0c674 사용. 신규 색 토큰 생성 금지.
import hashlib, sys, io

SRC = '/var/www/f29/assets/f29-search.js'
OUT = '/root/moneyflow/f29-search.badge.js'
BASE_SHA = 'a30997bca698daac52bd982bb7e0fa40d921acf077b2a6d755c85c0f818c99d8'

with io.open(SRC, encoding='utf-8') as f:
    src = f.read()

if hashlib.sha256(src.encode('utf-8')).hexdigest() != BASE_SHA:
    print('SHA MISMATCH — abort (기대 %s)' % BASE_SHA[:12]); sys.exit(1)
if 'GR1-BADGE' in src:
    print('MARKER GR1-BADGE already present — abort'); sys.exit(1)

s = src
anchors = []

# 앵커1: badge() 시그니처 + hasUS 게이트 + CSS 주입 헬퍼 추가
anchors.append(('badge_fn',
"""  // GR1: 시장 배지 — 시각 보조. 선택 로직에 미사용.
  function badge(s) { return isUS(s) ? '<span class="f29-mkt f29-mkt-us">미국</span>' : '<span class="f29-mkt f29-mkt-kr">한국</span>'; }""",
"""  // GR1-BADGE: 배지 스타일 1회 주입(공유 컴포넌트 — 페이지별 CSS 추가 요구 안 함).
  var _mktCss = false;
  function ensureMktCss() {
    if (_mktCss || typeof document === 'undefined' || !document.head) return;
    _mktCss = true;
    var st = document.createElement('style');
    st.textContent = '.f29-mkt{display:inline-block;font-size:.72em;line-height:1.35;padding:1px 5px;'
      + 'margin-right:6px;border-radius:4px;vertical-align:middle;font-weight:600;letter-spacing:.02em}'
      + '.f29-mkt-kr{background:rgba(61,216,176,.14);color:#3DD8B0}'
      + '.f29-mkt-us{background:rgba(240,198,116,.16);color:#f0c674}';
    document.head.appendChild(st);
  }
  // GR1-BADGE: 시장 배지 — 시각 보조. 선택 로직에 미사용.
  // 통합 인덱스(ctx.hasUS)에서만 렌더. 단일 시장 인덱스(weight=KR만)에서는 구분 대상이 없어 생략.
  function badge(s, opts) {
    var ctx = opts && opts.__ctx;
    if (!ctx || !ctx.hasUS) return '';
    return isUS(s) ? '<span class="f29-mkt f29-mkt-us">미국</span>'
                   : '<span class="f29-mkt f29-mkt-kr">한국</span>';
  }"""))

# 앵커2: renderCandidates 호출부 — badge(s, opts) + ensureMktCss()
anchors.append(('render_call',
"""  function renderCandidates(list, qtype, opts) {
    const box = resultBox(opts);
    if (!box) return;
    box.innerHTML = list.map(s =>
      `<button class="f29-cand" data-key="${esc(assetKey(s))}">${badge(s)}${esc(s.n)}</button>`).join('');""",
"""  function renderCandidates(list, qtype, opts) {
    const box = resultBox(opts);
    if (!box) return;
    ensureMktCss();
    box.innerHTML = list.map(s =>
      `<button class="f29-cand" data-key="${esc(assetKey(s))}">${badge(s, opts)}${esc(s.n)}</button>`).join('');"""))

for label, old, new in anchors:
    cnt = s.count(old)
    if cnt != 1:
        print('ANCHOR FAIL [%s] count=%d — abort' % (label, cnt)); sys.exit(2)
    s = s.replace(old, new)

# 사후 가드: badge(s) 단일인자 호출 잔존 금지
if 'badge(s)}' in s:
    print('RESIDUE: badge(s) 단일인자 호출 잔존 — abort'); sys.exit(3)

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(s)

print('OK anchors=%d' % len(anchors))
print('out_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('out_bytes=%d' % len(s.encode('utf-8')))
print('live_untouched_sha=%s' % hashlib.sha256(src.encode('utf-8')).hexdigest())
