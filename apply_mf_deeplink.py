#!/usr/bin/env python3
# apply_mf_deeplink.py — /moneyflow 종목 카드에서 티커·종목명 클릭 시 US 판정 페이지 이동
# 대상: /root/moneyflow/index.html (pm2 moneyflow, 포트 3001)
# 계약: SLUG = ticker 대문자 + '.'→'-' (build_us_stock_pages.py 동일 규칙)
#       ticker 없으면 링크 생략(방어). 배지·메타는 링크 밖 유지.
#       ?ref=moneyflow 로 GA4 유입 경로 구분.
import hashlib, io, os, sys, shutil, datetime

P = '/root/moneyflow/index.html'

raw = io.open(P, encoding='utf-8').read()
before_sha = hashlib.sha256(raw.encode('utf-8')).hexdigest()

if 'MF-DEEPLINK' in raw:
    print('ALREADY APPLIED (MF-DEEPLINK) — abort'); sys.exit(1)

s = raw
anchors = []

# 앵커1: 헬퍼 추가 (normalCard 직전 = specialCard 정의 앞 공통 위치)
anchors.append(('helper',
"""  function specialCard(p,acc,msg){""",
"""  // MF-DEEPLINK: 티커/종목명 → US 판정 페이지. SLUG 규칙 = build_us_stock_pages.py와 동일.
  function usHref(t){
    if(!t) return "";
    return "/stock/us/"+String(t).toUpperCase().replace(/\\./g,"-")+"/?ref=moneyflow";
  }
  function cardHead(p){
    var inner='<span class="tk">'+esc(p.ticker)+'</span><span class="nm">'+esc(p.name_ko)+'</span>';
    var h=usHref(p.ticker);
    return h ? '<a class="mflink" href="'+h+'">'+inner+'</a>' : inner;
  }
  function specialCard(p,acc,msg){"""))

# 앵커2: normalCard 헤드 교체
anchors.append(('normal',
"""      '<div class="top"><span class="tk">'+esc(p.ticker)+'</span><span class="nm">'+esc(p.name_ko)+'</span>'+
      '<span class="badge '+(BADGE[ax]||"bg-neu")+'">'+esc(ax)+'</span></div>'+""",
"""      '<div class="top">'+cardHead(p)+
      '<span class="badge '+(BADGE[ax]||"bg-neu")+'">'+esc(ax)+'</span></div>'+"""))

# 앵커3: specialCard 헤드 교체
anchors.append(('special',
"""      '<div class="top"><span class="tk">'+esc(p.ticker)+'</span><span class="nm">'+esc(p.name_ko)+'</span>'+
      '<span class="badge bg-neu">관찰 시작</span></div>'+""",
"""      '<div class="top">'+cardHead(p)+
      '<span class="badge bg-neu">관찰 시작</span></div>'+"""))

# 앵커4: 링크 스타일 (</style> 앞)
anchors.append(('css',
"""</style>""",
"""/* MF-DEEPLINK */
.mflink{display:inline-flex;align-items:baseline;gap:6px;text-decoration:none;color:inherit;border-radius:4px}
.mflink:hover .nm,.mflink:focus-visible .nm{text-decoration:underline}
.mflink:focus-visible{outline:2px solid #3DDC84;outline-offset:2px}
.mflink .nm::after{content:"\\203A";margin-left:4px;opacity:.55;font-size:.9em}
</style>"""))

for label, old, new in anchors:
    cnt = s.count(old)
    if cnt != 1:
        print('ANCHOR FAIL [%s] count=%d — abort' % (label, cnt)); sys.exit(2)
    s = s.replace(old, new)

# 사후 가드
if s.count('cardHead(p)') != 2:
    print('GUARD FAIL: cardHead 호출 %d회 (expected 2)' % s.count('cardHead(p)')); sys.exit(3)
if 'function usHref' not in s or 'function cardHead' not in s:
    print('GUARD FAIL: 헬퍼 누락'); sys.exit(4)

# 백업
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
bdir = '/root/f29-backups/mf-deeplink-' + ts
os.makedirs(bdir, exist_ok=True)
shutil.copy2(P, os.path.join(bdir, 'index.html'))

mode = os.stat(P).st_mode & 0o777
tmp = P + '.tmp'
with io.open(tmp, 'w', encoding='utf-8') as f:
    f.write(s)
os.replace(tmp, P)
os.chmod(P, mode)

print('OK anchors=%d' % len(anchors))
print('backup=%s' % bdir)
print('before_sha=%s' % before_sha)
print('after_sha=%s' % hashlib.sha256(s.encode('utf-8')).hexdigest())
print('after_bytes=%d' % len(s.encode('utf-8')))
print('mode=%o' % mode)
