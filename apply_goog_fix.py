#!/usr/bin/env python3
# apply_goog_fix.py — f29-search.js US_ALIAS에서 GOOG→GOOGL 제거 (서버 적용본)
# 사유: GOOG(Class C)와 GOOGL(Class A)은 같은 회사의 서로 다른 상장 주식.
#       정확한 티커 GOOG 입력을 GOOGL 판정 페이지로 보내면 종목 오표시.
#       US:GOOG 데이터·독립 페이지가 생길 때만 정식 지원한다.
#       GOOGL / 구글 / 알파벳 경로는 유지(통합 인덱스가 /stock/us/GOOGL/로 해결).
# 결과: GOOG 입력 → 통합 인덱스 miss → US_ALIAS miss → 검색 결과 없음(실패 카드).
#       "검색 결과 없음이 잘못된 종목 판정보다 낫다" (Sky 2026-07-20)
import hashlib, sys, io

SRC = '/var/www/f29/assets/f29-search.js'
OUT = '/root/moneyflow/f29-search.goog.js'
BASE_SHA = '5f1bf020c041ad69b444f7d67db29dfb61e20a02c2b898b1bba2c3b0d2af44a4'

with io.open(SRC, encoding='utf-8') as f:
    src = f.read()

if hashlib.sha256(src.encode('utf-8')).hexdigest() != BASE_SHA:
    print('SHA MISMATCH — abort (기대 %s)' % BASE_SHA[:12]); sys.exit(1)
if 'GR1-GOOG' in src:
    print('MARKER GR1-GOOG already present — abort'); sys.exit(1)

OLD = "    ['GOOGL','GOOGL'],['GOOG','GOOGL'],['\uad6c\uae00','GOOGL'],['AMZN','AMZN'],['\uc544\ub9c8\uc874','AMZN'],"
NEW = "    ['GOOGL','GOOGL'],['\uad6c\uae00','GOOGL'],['AMZN','AMZN'],['\uc544\ub9c8\uc874','AMZN'],  // GR1-GOOG: GOOG\u2192GOOGL \uc81c\uac70(\ubcc4\uac1c \uc0c1\uc7a5 \uc885\ubaa9)"

cnt = src.count(OLD)
if cnt != 1:
    print('ANCHOR FAIL count=%d — abort' % cnt); sys.exit(2)

s = src.replace(OLD, NEW)

# 사후 가드
if "['GOOG','GOOGL']" in s:
    print('RESIDUE: GOOG mapping still present — abort'); sys.exit(3)
if "['GOOGL','GOOGL']" not in s:
    print('REGRESSION: GOOGL self-mapping lost — abort'); sys.exit(4)

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write(s)

print('OK anchor=1')
print('out_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('out_bytes=%d' % len(s.encode('utf-8')))
print('live_untouched_sha=%s' % hashlib.sha256(src.encode('utf-8')).hexdigest())
