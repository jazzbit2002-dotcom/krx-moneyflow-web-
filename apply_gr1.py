#!/usr/bin/env python3
# apply_gr1.py — f29-search.js (가-r1) /tmp dry-run 패치
# 원본 SHA 8f71c0d8..e0b9d4 / 9161B 전제. 라이브 미적용. 앵커 count 게이트.
import hashlib, sys, io

SRC = '/tmp/s6work/f29-search.orig.js'
OUT = '/tmp/s6work/f29-search.patched.js'
BASE_SHA = '8f71c0d804cf1c9194dd30fe17289cdb964f76c5425786076e94ea7a92e0b9d4'

with io.open(SRC, encoding='utf-8') as f:
    src = f.read()

# SHA 게이트
if hashlib.sha256(src.encode('utf-8')).hexdigest() != BASE_SHA:
    print('SHA MISMATCH — abort'); sys.exit(1)

# 마커 중복 방지 (SHA 게이트 선행 후)
if 'GR1' in src:
    print('MARKER GR1 already present — abort'); sys.exit(1)

s = src
anchors = []  # (label, old, new)

# ── 변경1: 헤더 마커 ──────────────────────────────────────────────
anchors.append(('hdr',
  '/* f29-search.js — v1.9.1+D1+S1+S2+S3 (실시간 자동완성 + 정식명 부분일치 회귀 복구 2026-07-13). 의존: f29-metrics.js (F29M.track). S3: optional onStockSelect(stock,queryType) callback, instance-bound. */',
  '/* f29-search.js — v1.9.1+D1+S1+S2+S3+GR1 (indexUrl 격리·인스턴스 결과박스·assetKey·stock.url 우선·시장 queryType·정렬 정상화 2026-07-16 dry-run). 의존: f29-metrics.js (F29M.track). S3: optional onStockSelect(stock,queryType) callback, instance-bound. GR1: options {indexUrl, resultsEl} 후방호환. */'))

# ── 변경1: 전역 IDX/exactMap 제거 → INDEX_CACHE + assetKey 헬퍼 ────
anchors.append(('cache_decl',
  "  const track = (typeof F29M !== 'undefined' && F29M && typeof F29M.track === 'function') ? F29M.track.bind(F29M) : function () {};\n  let IDX = null, exactMap = null;",
  "  const track = (typeof F29M !== 'undefined' && F29M && typeof F29M.track === 'function') ? F29M.track.bind(F29M) : function () {};\n  // GR1: indexUrl별 캐시. key=indexUrl → {promise, idx, exactMap}. 전역 IDX 제거(인스턴스 오염 방지).\n  const INDEX_CACHE = new Map();\n  // GR1: 시장 포함 식별키. 구형 KR 엔트리는 market 폴백 KR.\n  function assetKey(s) { return s.assetKey || ((s.market || 'KR') + ':' + s.c); }\n  function isUS(s) { return (s.market || 'KR') === 'US'; }"))

# ── 변경1: loadIndex → indexUrl 인자 + 캐시 격리 ──────────────────
anchors.append(('loadIndex',
  """  async function loadIndex() {
    if (IDX) return IDX;
    const r = await fetch('/data/search_index.json', { cache: 'no-cache' });
    IDX = await r.json();
    exactMap = new Map();
    for (const s of IDX.stocks) {
      if (!exactMap.has(s.m)) exactMap.set(s.m, []);
      exactMap.get(s.m).push(s);
    }
    return IDX;
  }""",
  """  // GR1: indexUrl별 격리 로드. 같은 URL은 fetch/parse 공유, 다른 URL은 데이터 분리.
  function loadIndex(indexUrl) {
    const url = indexUrl || '/data/search_index.json';
    let ent = INDEX_CACHE.get(url);
    if (ent && ent.promise) return ent.promise;
    ent = {};
    ent.promise = (async () => {
      const r = await fetch(url, { cache: 'no-cache' });
      const idx = await r.json();
      const em = new Map();
      let hasUS = false;
      for (const s of idx.stocks) {
        if (!em.has(s.m)) em.set(s.m, []);
        em.get(s.m).push(s);
        if (isUS(s)) hasUS = true;
      }
      // GR1: 통합 인덱스(US 포함) 여부. legacy US_ALIAS fallback은 이 인덱스에서만 허용.
      ent.idx = idx; ent.exactMap = em; ent.hasUS = hasUS;
      return ent;
    })();
    INDEX_CACHE.set(url, ent);
    return ent.promise;
  }"""))

# ── 변경5+1: route → ctx(idx,exactMap) 인자 + 시장별 queryType ──────
# 기존 route(q)는 전역 IDX/exactMap 참조. ctx로 주입하고 US 분기 추가.
anchors.append(('route',
  """  function route(q) {
    const m = norm(q);
    if (!m) return { type: 'fail' };
    if (/^[0-9A-Z]{6}$/.test(m)) {                              // ① 코드 — D-1: 영숫자 6자 계약 (예: 005930, 0126Z0)
      const hit = IDX.stocks.find(s => s.c === m);
      if (hit) return { type: 'kr_code', stock: hit };
      // D-1 부수 규정: 코드 패턴이지만 인덱스 미등재 → 즉시 실패하지 않고 ②~⑦ 계속
      // (영숫자 6자 정식명이 ①에 선점되어 죽는 회귀 방지. 순수 숫자 미등재 코드도 동일 경로로 ⑦ 도달)
    }
    const ex = exactMap.get(m);                                 // ② 정식명 완전
    if (ex) return ex.length === 1 ? { type: 'kr_exact', stock: ex[0] }
                                   : { type: 'kr_exact', list: ex };
    if (IDX.aliases[m]) {                                       // ③ 통칭 완전
      const hit = IDX.stocks.find(s => s.c === IDX.aliases[m]);
      return { type: 'kr_alias', stock: hit };
    }
    const pre = IDX.stocks.filter(s => s.m.startsWith(m));      // ④ 접두
    if (pre.length === 1) return { type: 'kr_partial', stock: pre[0] };
    if (pre.length >= 2)  return { type: 'kr_partial', list: rankCandidates(pre).slice(0, 10) };
    const usKey = q.trim().toUpperCase();                        // ⑤ 미국 — 별칭은 티커로 변환
    if (US_ALIAS.has(usKey)) return { type: 'us', ticker: US_ALIAS.get(usKey) };
    if (CRYPTO[usKey] || CRYPTO[q.trim()])                       // ⑥ 크립토
      return { type: 'crypto', asset: CRYPTO[usKey] || CRYPTO[q.trim()] };
    const con = containsMatch(m);                               // ⑦ 정식명 한글 부분일치 (S2 — US/crypto 뒤)
    if (con.length === 1) return { type: 'kr_partial', stock: con[0] };
    if (con.length >= 2)  return { type: 'kr_partial', list: rankCandidates(con).slice(0, 10) };
    return { type: 'fail' };                                     // ⑧ 실패
  }""",
  """  // GR1: 시장별 queryType. 통합 인덱스에서 US 해결 시 us_* 로 기록(kr_* 오염 방지).
  function qt(base, stock) { return isUS(stock) ? base.replace('kr_', 'us_') : base; }
  // GR1: route는 인스턴스 ctx(idx,exactMap) 주입. 기존 exact/alias/prefix를 시장 공통으로 일반화.
  function route(q, ctx) {
    const IDX = ctx.idx, exactMap = ctx.exactMap;
    const m = norm(q);
    if (!m) return { type: 'fail' };
    if (/^[0-9A-Z]{6}$/.test(m)) {                              // ① 코드 — D-1: 영숫자 6자 계약 (예: 005930, 0126Z0)
      const hit = IDX.stocks.find(s => s.c === m);
      if (hit) return { type: qt('kr_code', hit), stock: hit };
      // D-1 부수 규정: 코드 패턴이지만 인덱스 미등재 → 즉시 실패하지 않고 ②~⑦ 계속
    }
    const ex = exactMap.get(m);                                 // ② 정식명 완전 (시장 공통)
    if (ex) return ex.length === 1 ? { type: qt('kr_exact', ex[0]), stock: ex[0] }
                                   : { type: 'kr_exact', list: ex };
    if (IDX.aliases && IDX.aliases[m]) {                        // ③ 통칭 완전 (시장 공통)
      // GR1: alias 값 = legacy scalar code | asset key scalar | asset key array 모두 수용
      // → stock 객체 배열로 정규화. 0종 계속 / 1종 *_alias / 2종+ 후보.
      const raw = IDX.aliases[m];
      const targets = Array.isArray(raw) ? raw : [raw];
      const hits = [];
      const seenK = new Set();
      for (const tv of targets) {
        const v = String(tv);
        const hit = IDX.stocks.find(s => s.c === v || assetKey(s) === v);
        if (hit && !seenK.has(assetKey(hit))) { seenK.add(assetKey(hit)); hits.push(hit); }
      }
      if (hits.length === 1) return { type: qt('kr_alias', hits[0]), stock: hits[0] };
      if (hits.length >= 2) return { type: 'kr_alias', list: rankCandidates(hits).slice(0, 10) };
      // 0종(dangling 등) → 다음 경로 계속
    }
    const pre = IDX.stocks.filter(s => s.m.startsWith(m));      // ④ 접두 (시장 공통)
    if (pre.length === 1) return { type: qt('kr_partial', pre[0]), stock: pre[0] };
    if (pre.length >= 2)  return { type: 'kr_partial', list: rankCandidates(pre).slice(0, 10) };
    if (CRYPTO[q.trim().toUpperCase()] || CRYPTO[q.trim()])     // ⑥ 크립토 (US_ALIAS 앞 — 무회귀)
      return { type: 'crypto', asset: CRYPTO[q.trim().toUpperCase()] || CRYPTO[q.trim()] };
    const con = containsMatch(m, IDX);                          // ⑦ 정식명 한글 부분일치 (S2)
    if (con.length === 1) return { type: qt('kr_partial', con[0]), stock: con[0] };
    if (con.length >= 2)  return { type: 'kr_partial', list: rankCandidates(con).slice(0, 10) };
    // GR1: legacy fallback — 통합 인덱스(US 포함)에서 미해결일 때만 US_ALIAS→구형 경로.
    // KR 전용 인덱스(weight)는 hasUS=false → US_ALIAS 미적용(weight US 이동 차단).
    if (ctx.hasUS) {
      const usKey = q.trim().toUpperCase();
      if (US_ALIAS.has(usKey)) return { type: 'us_legacy', ticker: US_ALIAS.get(usKey) };
    }
    return { type: 'fail' };                                     // ⑧ 실패
  }"""))

# ── 변경1: containsMatch → IDX 인자 ───────────────────────────────
anchors.append(('containsMatch',
  """  function containsMatch(m) {
    if (!m || m.length < 2 || !/[가-힣]/.test(m)) return [];
    return IDX.stocks.filter(s => s.m.includes(m) && !s.m.startsWith(m));
  }""",
  """  function containsMatch(m, IDX) {
    if (!m || m.length < 2 || !/[가-힣]/.test(m)) return [];
    return IDX.stocks.filter(s => s.m.includes(m) && !s.m.startsWith(m));
  }"""))

# ── 변경6: rankCandidates 정렬 정상화(반대칭·결정성, KR Full 우선 보존) ──
anchors.append(('rankCandidates',
  """  function rankCandidates(arr) {
    return arr.slice().sort((a, b) =>
      (a.t === b.t) ? a.n.localeCompare(b.n, 'ko') : (a.t === 'f' ? -1 : 1));
  }""",
  """  // GR1: 시장·tier 수치화로 comparator 반대칭·결정성 보장. KR Full 우선 보존.
  // 순위: KR Full(0) < KR Lite(1) < US(2) < 그 외(3), 동순위는 이름(ko).
  function tierRank(s) {
    if (isUS(s)) return 2;
    if (s.t === 'f') return 0;
    if (s.t === 'l') return 1;
    return (s.market ? 3 : 1); // KR인데 t 미상 → Lite 취급(기존 KR 계약 보존)
  }
  function rankCandidates(arr) {
    return arr.slice().sort((a, b) => {
      const ra = tierRank(a), rb = tierRank(b);
      if (ra !== rb) return ra - rb;
      return a.n.localeCompare(b.n, 'ko');
    });
  }"""))

# ── 변경4: selectStock → stock.url 우선 ───────────────────────────
anchors.append(('selectStock',
  """    if (opts && typeof opts.onStockSelect === 'function') {
      opts.onStockSelect(stock, qtype);   // callback present -> no location.href fallback (even on throw)
      return;
    }
    location.href = `/stock/${stock.c}/?ref=search`;""",
  """    if (opts && typeof opts.onStockSelect === 'function') {
      opts.onStockSelect(stock, qtype);   // callback present -> no location.href fallback (even on throw)
      return;
    }
    // GR1: stock.url 우선(US=/stock/us/{SLUG}/). 없으면 구형 KR 경로. ref=search는 기존 query 보존.
    if (stock.url) { location.href = withRef(stock.url); return; }
    location.href = `/stock/${stock.c}/?ref=search`;"""))

# ── 변경4: withRef 헬퍼 추가 (selectStock 앞) ─────────────────────
anchors.append(('withRef',
  """  function selectStock(stock, qtype, opts) {""",
  """  // GR1: 기존 query 유무 안전 처리(중복 ?? 금지, 기존 query 훼손 금지).
  function withRef(u) {
    if (/[?&]ref=search(&|$)/.test(u)) return u;
    return u + (u.indexOf('?') >= 0 ? '&' : '?') + 'ref=search';
  }
  function selectStock(stock, qtype, opts) {"""))

# ── 변경5: submit → ctx 주입 + us_* 분기 + us_legacy fallback ──────
anchors.append(('submit',
  """  function go(res, qtype, opts) {
    track('search_submit', { query_type: qtype });
    if (res.stock) selectStock(res.stock, qtype, opts);
  }

  function submit(q, opts) {
    const res = route(q);
    switch (res.type) {
      case 'kr_code': case 'kr_exact': case 'kr_alias': case 'kr_partial':
        if (res.stock) return go(res, res.type, opts);
        track('search_submit', { query_type: res.type });
        return renderCandidates(res.list, res.type, opts);            // 자동 이동 금지
      case 'us':
        track('search_submit', { query_type: 'us' });
        return location.href = `/moneyflow/#stock-${res.ticker}`; // [ADAPT] 앵커 규격, 배너는 착지 측
      case 'crypto':
        track('search_submit', { query_type: 'crypto' });
        return location.href = `/index.html?asset=${res.asset}`;
      default:
        track('search_submit', { query_type: 'fail' });
        track('search_no_result', { q: q.trim().slice(0, 20) });
        return renderFail();
    }
  }""",
  """  function go(res, qtype, opts) {
    track('search_submit', { query_type: qtype });
    if (res.stock) selectStock(res.stock, qtype, opts);
  }

  function submit(q, opts) {
    const res = route(q, opts.__ctx);
    switch (res.type) {
      // GR1: KR·US exact/alias/partial 공통 처리(stock.url 우선은 selectStock에서)
      case 'kr_code': case 'kr_exact': case 'kr_alias': case 'kr_partial':
      case 'us_code': case 'us_exact': case 'us_alias': case 'us_partial':
        if (res.stock) return go(res, res.type, opts);
        track('search_submit', { query_type: res.type });
        return renderCandidates(res.list, res.type, opts);            // 자동 이동 금지
      case 'us_legacy':
        // GR1: 통합 인덱스 미해결 시에만 구형 경로(legacy fallback)
        track('search_submit', { query_type: 'us_legacy' });
        return location.href = `/moneyflow/#stock-${res.ticker}`; // [ADAPT] 앵커 규격, 배너는 착지 측
      case 'crypto':
        track('search_submit', { query_type: 'crypto' });
        return location.href = `/index.html?asset=${res.asset}`;
      default:
        track('search_submit', { query_type: 'fail' });
        track('search_no_result', { q: q.trim().slice(0, 20) });
        return renderFail();
    }
  }"""))

# ── 변경2: 결과 박스 인스턴스 귀속 — renderCandidates ─────────────
anchors.append(('renderCandidates',
  """  function renderCandidates(list, qtype, opts) {
    const box = document.getElementById('f29-search-results');
    box.innerHTML = list.map(s =>
      `<button class="f29-cand" data-code="${s.c}">${esc(s.n)}</button>`).join('');
    box.hidden = false;
    const btns = box.querySelectorAll('.f29-cand');
    Array.prototype.forEach.call(btns, (b, i) => {
      const s = list[i];   // full stock object via closure (name from object, no extra button attr)
      b.addEventListener('click', () => selectStock(s, qtype, opts));
    });
  }""",
  """  // GR1: 인스턴스 결과 박스(opts.resultsEl 우선, 없으면 기존 #f29-search-results).
  function resultBox(opts) {
    return (opts && opts.resultsEl) || document.getElementById('f29-search-results');
  }
  // GR1: 시장 배지 — 시각 보조. 선택 로직에 미사용.
  function badge(s) { return isUS(s) ? '<span class="f29-mkt f29-mkt-us">미국</span>' : '<span class="f29-mkt f29-mkt-kr">한국</span>'; }
  function renderCandidates(list, qtype, opts) {
    const box = resultBox(opts);
    if (!box) return;
    box.innerHTML = list.map(s =>
      `<button class="f29-cand" data-key="${esc(assetKey(s))}">${badge(s)}${esc(s.n)}</button>`).join('');
    box.hidden = false;
    const btns = box.querySelectorAll('.f29-cand');
    Array.prototype.forEach.call(btns, (b, i) => {
      const s = list[i];   // full stock object via closure (assetKey dedupe upstream)
      b.addEventListener('click', () => selectStock(s, qtype, opts));
    });
  }"""))

# ── 변경2: renderFail 인스턴스 박스 ───────────────────────────────
anchors.append(('renderFail',
  """  function renderFail() {
    const box = document.getElementById('f29-search-results');
    box.innerHTML = `<div class="f29-fail">현재 F29 데이터에서 이 종목을 찾지 못했습니다.<br>
      종목명 또는 6자리 코드를 다시 확인해주세요. 통칭보다 정식 종목명이 정확합니다.</div>`;
    box.hidden = false;
  }""",
  """  function renderFail(opts) {
    const box = resultBox(opts);
    if (!box) return;
    box.innerHTML = `<div class="f29-fail">현재 F29 데이터에서 이 종목을 찾지 못했습니다.<br>
      종목명 또는 6자리 코드를 다시 확인해주세요. 통칭보다 정식 종목명이 정확합니다.</div>`;
    box.hidden = false;
  }"""))

# renderFail() 호출부(submit default)도 opts 전달
anchors.append(('renderFail_call',
  """        track('search_no_result', { q: q.trim().slice(0, 20) });
        return renderFail();""",
  """        track('search_no_result', { q: q.trim().slice(0, 20) });
        return renderFail(opts);"""))

# ── 변경2+3: suggest 인스턴스 박스 + ctx + assetKey dedupe ─────────
anchors.append(('suggest',
  """  function suggest(q, opts) {
    const box = document.getElementById('f29-search-results');
    if (!box || !IDX) return;
    const m = norm(q);
    if (!m) { box.innerHTML = ''; box.hidden = true; return; }
    const seen = new Set(), pre = [], con = [];
    for (const s of IDX.stocks) {                               // ① 정식명 접두
      if (s.m.startsWith(m) && !seen.has(s.c)) { seen.add(s.c); pre.push(s); }
    }
    for (const a in IDX.aliases) {                               // 통칭 접두 → 종목 (완전 아닌 접두 허용 — S1 기존)
      if (!a.startsWith(m)) continue;
      const code = IDX.aliases[a];
      if (seen.has(code)) continue;
      const hit = IDX.stocks.find(s => s.c === code);
      if (hit) { seen.add(code); pre.push(hit); }
    }
    for (const s of containsMatch(m)) {                          // ② 정식명 한글 부분일치 (S2)
      if (!seen.has(s.c)) { seen.add(s.c); con.push(s); }
    }
    const out = rankCandidates(pre).concat(rankCandidates(con)); // 접두 우선 → 부분일치
    if (!out.length) { box.innerHTML = ''; box.hidden = true; return; }
    renderCandidates(out.slice(0, 10), 'kr_partial', opts);
  }""",
  """  function suggest(q, opts) {
    const box = resultBox(opts);
    const ctx = opts.__ctx;
    if (!box || !ctx) return;
    const IDX = ctx.idx;
    const m = norm(q);
    if (!m) { box.innerHTML = ''; box.hidden = true; return; }
    // GR1: assetKey dedupe(raw c 단독 금지 — 시장 충돌 방지)
    const seen = new Set(), pre = [], con = [];
    for (const s of IDX.stocks) {                               // ① 정식명 접두
      const k = assetKey(s);
      if (s.m.startsWith(m) && !seen.has(k)) { seen.add(k); pre.push(s); }
    }
    if (IDX.aliases) for (const a in IDX.aliases) {              // 통칭 접두 → 종목 (S1 기존)
      if (!a.startsWith(m)) continue;
      const raw = IDX.aliases[a];
      const targets = Array.isArray(raw) ? raw : [raw];
      for (const tv of targets) {
        const v = String(tv);
        const hit = IDX.stocks.find(s => s.c === v || assetKey(s) === v);
        if (hit && !seen.has(assetKey(hit))) { seen.add(assetKey(hit)); pre.push(hit); }
      }
    }
    for (const s of containsMatch(m, IDX)) {                     // ② 정식명 한글 부분일치 (S2)
      const k = assetKey(s);
      if (!seen.has(k)) { seen.add(k); con.push(s); }
    }
    const out = rankCandidates(pre).concat(rankCandidates(con)); // 접두 우선 → 부분일치
    if (!out.length) { box.innerHTML = ''; box.hidden = true; return; }
    renderCandidates(out.slice(0, 10), 'kr_partial', opts);
  }"""))

# ── 변경1+2: init → indexUrl 로드 + ctx 바인딩 + resultsEl ─────────
anchors.append(('init',
  """  window.F29Search = {
    async init(inputEl, options) {
      const opts = options || {};
      await loadIndex();
      inputEl.addEventListener('focus', () => track('search_focus', {}), { once: true });""",
  """  window.F29Search = {
    async init(inputEl, options) {
      const opts = options || {};
      // GR1: 인스턴스별 indexUrl 로드 → ctx 바인딩(전역 상태 없음)
      opts.__ctx = await loadIndex(opts.indexUrl);
      inputEl.addEventListener('focus', () => track('search_focus', {}), { once: true });"""))

# 적용 (앵커 count 게이트)
for label, old, new in anchors:
    cnt = s.count(old)
    if cnt != 1:
        print('ANCHOR FAIL [%s] count=%d (expected 1) — abort' % (label, cnt))
        sys.exit(2)
    s = s.replace(old, new)

# 잔존 전역 참조 가드: 치환 후 함수 밖 전역 IDX/exactMap 참조가 없어야
# (route/suggest 내부는 지역 IDX로 재선언됨. loadIndex 구식 시그니처 잔존 금지)
forbidden = [
  "if (IDX) return IDX;",           # 구 loadIndex
  "const res = route(q);",          # ctx 없는 호출
  "for (const s of containsMatch(m))",  # IDX 인자 없는 호출 (구형)
]
for fb in forbidden:
    if fb in s:
        print('FORBIDDEN residue present: %r — abort' % fb)
        sys.exit(3)

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(s)

print('OK anchors=%d' % len(anchors))
print('out_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('out_bytes=%d' % len(s.encode('utf-8')))
print('live_untouched_src_sha=%s' % hashlib.sha256(src.encode('utf-8')).hexdigest())
