#!/usr/bin/env python3
# apply_merge_r1.py — merge_search_indexes.py 방식②-r1 패치 (/tmp dry-run)
# 원본 SHA 8aa83d3e.. / 4475B 전제. top-level aliases 다중대상 맵 생성.
import hashlib, sys, io

SRC = '/tmp/s6work/merge_search_indexes.py'
OUT = '/tmp/s6work/merge_search_indexes.patched.py'
BASE_SHA = '8aa83d3e9a814cf76ab03ef184e35d112172bc1302f3baa8936fed02ee139032'

with io.open(SRC, encoding='utf-8') as f:
    src = f.read()

if hashlib.sha256(src.encode('utf-8')).hexdigest() != BASE_SHA:
    print('SHA MISMATCH — abort'); sys.exit(1)
if 'build_top_aliases' in src:
    print('MARKER already present — abort'); sys.exit(1)

s = src
anchors = []

# ── 앵커1: build_top_aliases 함수 추가 (write_atomic 앞) ──
anchors.append(('fn',
"""def write_atomic(path, obj):""",
"""def build_top_aliases(kr_raw, kr_entries_list, us_entries_list):
    \"\"\"방식②-r1: 병합본 top-level aliases = norm(alias) → sorted(asset key 배열).
    KR scalar(alias→code)를 [KR:code]로, US 내장 aliases[]를 US:{ticker}에 누적.
    충돌(다른 asset 동일 alias)은 보존(overwrite/HARD_FAIL 금지). dangling asset은 HARD_FAIL.
    \"\"\"
    # 유효 asset key 집합(dangling 검출용)
    valid = set()
    for e in kr_entries_list:
        valid.add(f'{e["market"]}:{e["c"]}')
    for e in us_entries_list:
        valid.add(f'{e.get("market","US")}:{e["c"]}')

    amap = {}  # norm_alias -> set(asset keys)

    def add(alias, asset):
        k = norm(alias)
        if not k:
            return
        if asset not in valid:
            raise SystemExit(f'HARD_FAIL: dangling alias target {asset} (alias={alias})')
        amap.setdefault(k, set()).add(asset)

    # KR top-level aliases (기존 scalar alias→code). dict만 수용.
    kr_al = kr_raw.get('aliases') if isinstance(kr_raw, dict) else None
    if isinstance(kr_al, dict):
        for alias, val in kr_al.items():
            # 값이 scalar code, 또는 이미 asset key, 또는 배열 — 모두 수용
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                v = str(v)
                asset = v if ':' in v else f'KR:{v}'
                add(alias, asset)

    # US 내장 aliases[] → US:{ticker} 승격
    for e in us_entries_list:
        asset = f'{e.get("market","US")}:{e["c"]}'
        for a in (e.get('aliases') or []):
            add(a, asset)

    # set → 결정적 정렬 배열
    return {k: sorted(v) for k, v in amap.items()}


def write_atomic(path, obj):"""))

# ── 앵커2: merge() 안에서 build_top_aliases 호출 + out에 aliases 주입 ──
anchors.append(('call',
"""    kr_n = sum(1 for e in merged if e['market'] == 'KR')
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
    return 0""",
"""    kr_n = sum(1 for e in merged if e['market'] == 'KR')
    us_n = sum(1 for e in merged if e['market'] == 'US')
    # 방식②-r1: top-level aliases 다중대상 맵(비어도 {} 출력, 키 생략 금지)
    top_aliases = build_top_aliases(kr_raw, kr, us)
    _dt = __import__('datetime')
    out = {
        'generated': _dt.datetime.now(_dt.timezone.utc).isoformat(),
        'source': {'kr': KR_IN, 'us': US_IN},
        'counts': {'KR': kr_n, 'US': us_n, 'total': len(merged)},
        'stocks': merged,
        'aliases': top_aliases,
    }
    write_atomic(OUT, out)
    _collide = sum(1 for v in top_aliases.values() if len(v) >= 2)
    print(f'[merge] KR={kr_n} US={us_n} total={len(merged)} '
          f'asset_unique={len(seen_asset)} url_unique={len(seen_url)} '
          f'aliases={len(top_aliases)} collisions={_collide} → {OUT}')
    return 0"""))

for label, old, new in anchors:
    cnt = s.count(old)
    if cnt != 1:
        print('ANCHOR FAIL [%s] count=%d — abort' % (label, cnt)); sys.exit(2)
    s = s.replace(old, new)

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(s)
print('OK anchors=%d' % len(anchors))
print('out_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('out_bytes=%d' % len(s.encode('utf-8')))
print('live_untouched_sha=%s' % hashlib.sha256(src.encode('utf-8')).hexdigest())
