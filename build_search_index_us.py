#!/usr/bin/env python3
# build_search_index_us.py — F29 US 검색 인덱스 빌더 (Phase 0)
# 입력: positions_output.json (.positions[]) + us-slug-map.json + us_alias_override.json
# 출력: search_index_us.json (40종, 포털 통합 병합 입력)
# 계약(Sky 2026-07-16 §5):
#   - 검색 토큰 = raw ticker + slug + name_ko + 승인 alias override(5종)만.
#   - 승인 목록 밖 한글 통칭 자동 생성 0.
#   - KR build_search_index.py 무수정. 이 파일은 신규·독립.
#   - 실패 시 기존 출력 보존(atomic rename), 검증 실패는 raise.

import json, os, re, sys, unicodedata

BASE       = '/root/moneyflow'
SRC        = os.path.join(BASE, 'positions_output.json')
SLUG_MAP   = '/var/www/f29-stock-us/us-slug-map.json'
ALIAS_OVR  = os.path.join(BASE, 'us_alias_override.json')
OUT        = '/var/www/f29-portal/data/search_index_us.json'
MARKET     = 'US'


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def norm(s):
    """검색 정규화: NFKC → 대문자화 → 공백/특수문자 제거. KR 검색기와 동일 원칙."""
    if s is None:
        return ''
    s = unicodedata.normalize('NFKC', str(s))
    s = s.upper()
    s = re.sub(r'[\s\-_.·]', '', s)
    return s


def slugify(ticker):
    return str(ticker).replace('.', '-').upper()


def write_atomic(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def build():
    data = load_json(SRC)
    positions = data.get('positions', [])
    updated = data.get('updated', '')
    slug_map = load_json(SLUG_MAP) if os.path.exists(SLUG_MAP) else {}
    alias_ovr = load_json(ALIAS_OVR) if os.path.exists(ALIAS_OVR) else {}

    entries = []
    seen_ticker, seen_slug, seen_url, seen_asset = set(), set(), set(), set()
    # 후속 백로그 보고용
    ascii_or_same, no_ko_alias = [], []

    for r in positions:
        t = r.get('ticker')
        if not t:
            raise SystemExit(f'HARD_FAIL: 빈 ticker 레코드: {r}')
        slug = slugify(t)
        name = r.get('name_ko') or t
        url = f'/stock/us/{slug}/'
        asset = f'{MARKET}:{t}'

        # 중복 게이트
        if t in seen_ticker:   raise SystemExit(f'HARD_FAIL: ticker 중복 {t}')
        if slug in seen_slug:  raise SystemExit(f'HARD_FAIL: slug 중복 {slug}')
        if url in seen_url:    raise SystemExit(f'HARD_FAIL: URL 중복 {url}')
        if asset in seen_asset:raise SystemExit(f'HARD_FAIL: asset key 중복 {asset}')
        seen_ticker.add(t); seen_slug.add(slug); seen_url.add(url); seen_asset.add(asset)

        # 검색 토큰(정규화): ticker + slug + name_ko + 승인 alias만
        raw_aliases = [t, slug, name] + list(alias_ovr.get(t, []))
        norm_aliases, seen_na = [], set()
        for a in raw_aliases:
            na = norm(a)
            if na and na not in seen_na:
                seen_na.add(na)
                norm_aliases.append(na)

        entries.append({
            'c': t,                 # 원티커
            'n': name,              # 대표 표시명(name_ko)
            'm': norm(name),        # 정규화 대표명
            'market': MARKET,
            'slug': slug,
            'url': url,
            'aliases': norm_aliases,
        })

        # 백로그 보고(Phase 0 비차단)
        if name == t or all(ord(ch) < 128 for ch in name):
            ascii_or_same.append(t)
        has_ko = any(re.search(r'[\uac00-\ud7a3]', a) for a in raw_aliases)
        if not has_ko:
            no_ko_alias.append(t)

    # 유니버스 정합
    if len(entries) != len(positions):
        raise SystemExit(f'HARD_FAIL: 인덱스 {len(entries)} ≠ 유니버스 {len(positions)}')

    out = {
        'market': MARKET,
        'generated_from': updated,
        'count': len(entries),
        'stocks': entries,
    }
    write_atomic(OUT, out)
    print(f'[us-index] count={len(entries)} ticker={len(seen_ticker)} '
          f'slug={len(seen_slug)} url={len(seen_url)} asset={len(seen_asset)} → {OUT}')
    print(f'[us-index] alias_override 적용 = {sorted(k for k in alias_ovr if not k.startswith("_"))}')
    print(f'[백로그] name_ko=ticker 또는 ASCII-only ({len(ascii_or_same)}종): {ascii_or_same}')
    print(f'[백로그] 한글 검색 별칭 없음 ({len(no_ko_alias)}종): {no_ko_alias}')
    print('[백로그] ↑ Phase 0 비차단 — 후속 alias 확장 근거')


if __name__ == '__main__':
    build()
