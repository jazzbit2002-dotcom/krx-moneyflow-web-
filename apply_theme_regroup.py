#!/usr/bin/env python3
# apply_theme_regroup.py — posradar_master.json theme_group 재편 (서버 적용본)
# 사유: 40종에 테마 34개 → 30종이 단독 테마 → P05-4 테마 동조 카드가 대부분 빈 껍데기.
#       상위 개념으로 병합해 동료 있는 종목 10 → 36으로 확대. 데이터 신규 수집 0.
# 원칙: 3종 이상 그룹 목표 / 기존 라벨 최대 승계 / 억지 묶기 금지(단독 4종 유지)
#       risk_group·benchmark 등 다른 필드 무변경.
# 게이트: 40종 전건의 현재 theme_group이 기대값과 일치해야 진행(구조 게이트).
#         이미 적용됐으면 중단(멱등).
import json, io, os, sys, hashlib, shutil, datetime

P = '/root/moneyflow/posradar_master.json'

# ticker -> (기대 현재값, 신규값)
MAP = {
    'NVDA':  ('AI\ubc18\ub3c4\uccb4', 'AI\ubc18\ub3c4\uccb4'),
    'AMD':   ('AI\ubc18\ub3c4\uccb4', 'AI\ubc18\ub3c4\uccb4'),
    'AVGO':  ('AI\ubc18\ub3c4\uccb4', 'AI\ubc18\ub3c4\uccb4'),
    'MRVL':  ('AI\ubc18\ub3c4\uccb4', 'AI\ubc18\ub3c4\uccb4'),

    'INTC':  ('\ubc18\ub3c4\uccb4', '\ubc18\ub3c4\uccb4 \uc81c\uc870\u00b7\uc7a5\ube44'),
    'AMAT':  ('\ubc18\ub3c4\uccb4\uc7a5\ube44', '\ubc18\ub3c4\uccb4 \uc81c\uc870\u00b7\uc7a5\ube44'),
    'LRCX':  ('\ubc18\ub3c4\uccb4\uc7a5\ube44', '\ubc18\ub3c4\uccb4 \uc81c\uc870\u00b7\uc7a5\ube44'),
    'TSM':   ('\ud30c\uc6b4\ub4dc\ub9ac', '\ubc18\ub3c4\uccb4 \uc81c\uc870\u00b7\uc7a5\ube44'),

    'MU':    ('\uba54\ubaa8\ub9ac/HBM', '\uba54\ubaa8\ub9ac\u00b7\uc2a4\ud1a0\ub9ac\uc9c0'),
    'WDC':   ('\uc2a4\ud1a0\ub9ac\uc9c0/AI\uc800\uc7a5', '\uba54\ubaa8\ub9ac\u00b7\uc2a4\ud1a0\ub9ac\uc9c0'),
    'SNDK':  ('\uba54\ubaa8\ub9ac/\ub0ae\ub4dc', '\uba54\ubaa8\ub9ac\u00b7\uc2a4\ud1a0\ub9ac\uc9c0'),

    'LITE':  ('\uad11\ud1b5\uc2e0/AI', '\uad11\ud1b5\uc2e0'),
    'COHR':  ('\uad11\ud1b5\uc2e0/AI', '\uad11\ud1b5\uc2e0'),
    'GLW':   ('\uad11\ud1b5\uc2e0/\uc18c\uc7ac', '\uad11\ud1b5\uc2e0'),

    'MSFT':  ('\ube45\ud14c\ud06c/\ud074\ub77c\uc6b0\ub4dc', '\ube45\ud14c\ud06c \ud50c\ub7ab\ud3fc'),
    'GOOGL': ('\ube45\ud14c\ud06c/\uac80\uc0c9', '\ube45\ud14c\ud06c \ud50c\ub7ab\ud3fc'),
    'META':  ('\ube45\ud14c\ud06c/\uad11\uace0', '\ube45\ud14c\ud06c \ud50c\ub7ab\ud3fc'),
    'AMZN':  ('\ube45\ud14c\ud06c/\ucee4\uba38\uc2a4\u00b7\ud074\ub77c\uc6b0\ub4dc', '\ube45\ud14c\ud06c \ud50c\ub7ab\ud3fc'),

    'ORCL':  ('\uc5d4\ud130\ud504\ub77c\uc774\uc988SW', '\uc5d4\ud130\ud504\ub77c\uc774\uc988 SW'),
    'IBM':   ('\uc5d4\ud130\ud504\ub77c\uc774\uc988IT', '\uc5d4\ud130\ud504\ub77c\uc774\uc988 SW'),
    'OKTA':  ('\ubcf4\uc548SW', '\uc5d4\ud130\ud504\ub77c\uc774\uc988 SW'),

    'PLTR':  ('AI\uc18c\ud504\ud2b8/\ubc29\uc0b0', 'AI \uc18c\ud504\ud2b8\u00b7\uc778\ud504\ub77c'),
    'CRWV':  ('AI\uc778\ud504\ub77c/\ud074\ub77c\uc6b0\ub4dc', 'AI \uc18c\ud504\ud2b8\u00b7\uc778\ud504\ub77c'),

    'IONQ':  ('\uc591\uc790\ucef4\ud4e8\ud305', '\uc591\uc790\ucef4\ud4e8\ud305'),
    'RGTI':  ('\uc591\uc790\ucef4\ud4e8\ud305', '\uc591\uc790\ucef4\ud4e8\ud305'),

    'SPCX':  ('\uc6b0\uc8fc/\uc704\uc131/AI', '\uc6b0\uc8fc\u00b7\uc704\uc131'),
    'RKLB':  ('\uc6b0\uc8fc/\ubc1c\uc0ac\uccb4', '\uc6b0\uc8fc\u00b7\uc704\uc131'),
    'ASTS':  ('\uc704\uc131\ud1b5\uc2e0', '\uc6b0\uc8fc\u00b7\uc704\uc131'),
    'RDW':   ('\uc6b0\uc8fc/\ubd80\ud488', '\uc6b0\uc8fc\u00b7\uc704\uc131'),
    'PL':    ('\uc704\uc131/\ub370\uc774\ud130', '\uc6b0\uc8fc\u00b7\uc704\uc131'),

    'BE':    ('\uc218\uc18c/\uc5f0\ub8cc\uc804\uc9c0', '\uc804\ub825\u00b7\uc5d0\ub108\uc9c0'),
    'FLNC':  ('ESS/\uc5d0\ub108\uc9c0\uc800\uc7a5', '\uc804\ub825\u00b7\uc5d0\ub108\uc9c0'),
    'SMR':   ('SMR/\uc6d0\uc790\ub825', '\uc804\ub825\u00b7\uc5d0\ub108\uc9c0'),
    'POWL':  ('\uc804\ub825\uc7a5\ube44', '\uc804\ub825\u00b7\uc5d0\ub108\uc9c0'),

    'UNH':   ('\ud5ec\uc2a4\ucf00\uc5b4\ubcf4\ud5d8', '\ud5ec\uc2a4\ucf00\uc5b4'),
    'HNGE':  ('\ub514\uc9c0\ud138\ud5ec\uc2a4', '\ud5ec\uc2a4\ucf00\uc5b4'),

    # 단독 유지 (억지 묶기 금지)
    'ARM':   ('\ubc18\ub3c4\uccb4IP', '\ubc18\ub3c4\uccb4IP'),
    'TSLA':  ('EV/\uc790\uc728\uc8fc\ud589', 'EV/\uc790\uc728\uc8fc\ud589'),
    'CRCL':  ('\uc2a4\ud14c\uc774\ube14\ucf54\uc778/\ud540\ud14c\ud06c', '\uc2a4\ud14c\uc774\ube14\ucf54\uc778/\ud540\ud14c\ud06c'),
    'CAT':   ('\uc911\uc7a5\ube44/\uc778\ud504\ub77c', '\uc911\uc7a5\ube44/\uc778\ud504\ub77c'),
}

raw = io.open(P, encoding='utf-8').read()
before_sha = hashlib.sha256(raw.encode('utf-8')).hexdigest()
d = json.loads(raw)
S = d['stocks']

if len(S) != 40:
    print('GATE FAIL: stocks=%d (expected 40)' % len(S)); sys.exit(1)

meta = d.get('_meta', {})
if meta.get('theme_revision'):
    print('ALREADY APPLIED: _meta.theme_revision=%s — abort' % meta['theme_revision']); sys.exit(1)

# 구조 게이트: 40종 전건 현재값 일치 확인
bad = []
for x in S:
    t = x.get('ticker')
    if t not in MAP:
        bad.append('%s: MAP 미등재' % t); continue
    cur = x.get('theme_group')
    exp = MAP[t][0]
    if cur != exp:
        bad.append('%s: 현재=%r 기대=%r' % (t, cur, exp))
if bad:
    print('GATE FAIL — theme_group 불일치 %d건:' % len(bad))
    for b in bad[:10]: print('  ', b)
    sys.exit(2)

# 백업
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
bdir = '/root/f29-backups/theme-regroup-' + ts
os.makedirs(bdir, exist_ok=True)
shutil.copy2(P, os.path.join(bdir, 'posradar_master.json'))

# 적용
for x in S:
    x['theme_group'] = MAP[x['ticker']][1]

d['_meta']['theme_revision'] = {
    'date': ts,
    'from': '34 themes (30 singletons)',
    'to': '15 themes (4 singletons: ARM, TSLA, CRCL, CAT)',
    'reason': 'theme sync card coverage — no new data collection',
    'prev_sha256': before_sha,
}

tmp = P + '.tmp'
with io.open(tmp, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write('\n')
os.replace(tmp, P)
os.chmod(P, 0o644)

after = io.open(P, encoding='utf-8').read()
from collections import Counter
c = Counter(x['theme_group'] for x in json.loads(after)['stocks'])
print('OK backup=%s' % bdir)
print('before_sha=%s' % before_sha)
print('after_sha=%s' % hashlib.sha256(after.encode('utf-8')).hexdigest())
print('themes=%d (singletons=%d)' % (len(c), sum(1 for v in c.values() if v == 1)))
for k, v in c.most_common():
    print('  %2d %s' % (v, k))
