#!/usr/bin/env python3
# merge_search_indexes.py — F29 포털 통합 검색 인덱스 병합 (Phase 0)
# 입력: search_index.json (KR, 기존·무변경) + search_index_us.json (US 신규)
# 출력: search_index_all.json (포털 검색 전용)
# 계약(Sky 2026-07-16 §6):
#   - 두 입력 read-only. 출력 temp→atomic rename.
#   - 입력 누락·JSON 오류·스키마 오류 → 기존 정상 all.json 보존(비파괴 종료).
#   - asset key·URL·slug 충돌 HARD_FAIL. 단 시장 다르면 slug/표시명 동일 무방(asset key로 구분).
#   - 병합 실패가 KR·US 원천 빌드를 차단하지 않음(독립 후속 단계 — cron에서 || true 등).
#   - KR 기존 필드 하위호환 유지.

import json, os, sys, unicodedata, re

BASE   = '/var/www/f29-portal/data'
KR_IN  = os.path.join(BASE, 'search_index.json')
US_IN  = os.path.join(BASE, 'search_index_us.json')
OUT    = os.path.join(BASE, 'search_index_all.json')


def norm(s):
    if s is None: return ''
    s = unicodedata.normalize('NFKC', str(s)).upper()
    return re.sub(r'[\s\-_.·]', '', s)


def load_or_none(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'[merge] 입력 로드 실패 {p}: {e}', file=sys.stderr)
        return None


def kr_entries(kr_raw):
    """KR search_index.json → 통합 스키마로 어댑트. 원본 무변경(읽기만)."""
    # KR 인덱스 구조는 배포 계약(196~201종). stocks 배열 또는 최상위 배열 방어.
    if isinstance(kr_raw, dict):
        arr = kr_raw.get('stocks') or kr_raw.get('index') or []
    elif isinstance(kr_raw, list):
        arr = kr_raw
    else:
        arr = []
    out = []
    for e in arr:
        if not isinstance(e, dict):
            continue
        code = e.get('c') or e.get('code') or ''
        name = e.get('n') or e.get('name') or ''
        if not code:
            continue
        # KR URL: 기존 엔트리는 url 없을 수 있음 → 코드 기반 생성(하위호환)
        url = e.get('url') or f'/stock/{code}/'
        al = e.get('aliases')
        if not isinstance(al, list):
            al = []
        out.append({
            'c': code,
            'n': name,
            'm': e.get('m') or norm(name),
            'market': e.get('market') or 'KR',
            'slug': e.get('slug') or code,
            'url': url,
            'aliases': al,
        })
    return out


def us_entries(us_raw):
    arr = us_raw.get('stocks', []) if isinstance(us_raw, dict) else []
    return [e for e in arr if isinstance(e, dict) and e.get('c')]


def write_atomic(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def merge():
    kr_raw = load_or_none(KR_IN)
    us_raw = load_or_none(US_IN)
    if kr_raw is None or us_raw is None:
        print('[merge] 입력 누락/오류 — 기존 all.json 보존, 종료(비차단)', file=sys.stderr)
        return 0  # 비파괴: 기존 통합본 유지, KR/US 빌드 차단 안 함

    kr = kr_entries(kr_raw)
    us = us_entries(us_raw)
    merged = kr + us

    # 충돌 게이트: asset key(market:code)·URL·slug
    seen_asset, seen_url = {}, {}
    for e in merged:
        asset = f'{e["market"]}:{e["c"]}'
        if asset in seen_asset:
            raise SystemExit(f'HARD_FAIL: asset key 충돌 {asset}')
        seen_asset[asset] = e
        # URL은 시장 무관 전역 유일해야(같은 URL 두 종목 금지)
        if e['url'] in seen_url:
            raise SystemExit(f'HARD_FAIL: URL 충돌 {e["url"]} ({seen_url[e["url"]]} vs {asset})')
        seen_url[e['url']] = asset
        # slug는 시장 다르면 동일 허용 — asset key로 이미 구분되므로 slug 단독 충돌 검사 안 함

    kr_n = sum(1 for e in merged if e['market'] == 'KR')
    us_n = sum(1 for e in merged if e['market'] == 'US')
    _dt = __import__('datetime')
    out = {
        'generated': _dt.datetime.now(_dt.timezone.utc).isoformat(),
        'source': {'kr': KR_IN, 'us': US_IN},
        'counts': {'KR': kr_n, 'US': us_n, 'total': len(merged)},
        'stocks': merged,
    }
    write_atomic(OUT, out)
    print(f'[merge] KR={kr_n} US={us_n} total={len(merged)} '
          f'asset_unique={len(seen_asset)} url_unique={len(seen_url)} → {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(merge())
