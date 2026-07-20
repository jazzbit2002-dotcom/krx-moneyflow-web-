#!/usr/bin/env python3
# apply_merge_tier.py — merge_search_indexes.patched.py에 KR tier(t) 보존 추가 (서버 적용본)
# 사유: all.json KR 원소에 t 누락 → 라우터 tierRank가 KR=3, US=2로 판정 → 후보에서 US가 KR 위로.
#       Sky 변경계약 6번 "KR Full 우선 보존" 위반. 원본 KR 인덱스 190종 전건 t='f' 실측 확인.
import hashlib, sys, io

SRC = '/root/moneyflow/merge_search_indexes.patched.py'
OUT = '/root/moneyflow/merge_search_indexes.patched.py'   # 제자리 갱신(스테이징 파일)
BASE_SHA = 'a107aa30f2b5881b29d0fbeefef1ac833723cc822deb6d87c348311850bc54dc'

with io.open(SRC, encoding='utf-8') as f:
    src = f.read()

if hashlib.sha256(src.encode('utf-8')).hexdigest() != BASE_SHA:
    print('SHA MISMATCH — abort (기대 %s)' % BASE_SHA[:12]); sys.exit(1)
if 'GR1-TIER' in src:
    print('MARKER GR1-TIER already present — abort'); sys.exit(1)

OLD = """        out.append({
            'c': code,
            'n': name,
            'm': e.get('m') or norm(name),
            'market': e.get('market') or 'KR',
            'slug': e.get('slug') or code,
            'url': url,
            'aliases': al,
        })"""

NEW = """        _ent = {
            'c': code,
            'n': name,
            'm': e.get('m') or norm(name),
            'market': e.get('market') or 'KR',
            'slug': e.get('slug') or code,
            'url': url,
            'aliases': al,
        }
        # GR1-TIER: KR tier(t) 보존. 라우터 tierRank의 KR Full(0) < KR Lite(1) < US(2) 계약 유지.
        # 값 없으면 키 생략(None 주입 금지 — 없는 필드 추정 금지 원칙).
        if e.get('t'):
            _ent['t'] = e.get('t')
        out.append(_ent)"""

cnt = src.count(OLD)
if cnt != 1:
    print('ANCHOR FAIL count=%d — abort' % cnt); sys.exit(2)

s = src.replace(OLD, NEW)

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(s)

print('OK anchor=1')
print('out_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('out_bytes=%d' % len(s.encode('utf-8')))
