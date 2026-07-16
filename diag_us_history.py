#!/usr/bin/env python3
# diag_us_history.py — positions_history.json 40종 전수 스키마·날짜정합 진단 (읽기 전용)
# 출력만. 파일 미변경. build_us_stock_pages.py ② 어댑터 설계 입력.
import json

HIST = '/root/moneyflow/positions_history.json'
POS  = '/root/moneyflow/positions_output.json'

hist = json.load(open(HIST, encoding='utf-8'))
pos  = json.load(open(POS, encoding='utf-8'))
updated = pos.get('updated', '')
pm = {r['ticker']: r for r in pos['positions'] if 'ticker' in r}

print(f'updated(positions_output) = {updated!r}')
print(f'history tickers = {len(hist)} / positions tickers = {len(pm)}')

# 1) ticker 매칭: history에 있으나 positions에 없음 / 반대
h_only = set(hist) - set(pm)
p_only = set(pm) - set(hist)
print(f'history-only ticker = {sorted(h_only)}')
print(f'positions-only ticker = {sorted(p_only)}')

VALID_LC = {'신규부상','강화','주도','관심도성숙','관찰시작','둔화관찰','이탈관찰','이탈','중립'}

date_rel = {'equal':0, 'past':0, 'future':0}  # 마지막 날짜 vs updated
issues = {'not_list':[], 'empty':[], 'no_final':[], 'bad_label':[], 'not_sorted':[], 'len_lt2':[]}
last_date_samples = []

for t, arr in hist.items():
    if not isinstance(arr, list):
        issues['not_list'].append(t); continue
    if not arr:
        issues['empty'].append(t); continue
    # final 키·라벨 유효
    finals = [e.get('final') for e in arr]
    if any('final' not in e for e in arr):
        issues['no_final'].append(t)
    bad = [f for f in finals if f not in VALID_LC]
    if bad:
        issues['bad_label'].append((t, sorted(set(bad))))
    # 날짜 오름차순
    dates = [e.get('date','') for e in arr]
    if dates != sorted(dates):
        issues['not_sorted'].append(t)
    if len(arr) < 2:
        issues['len_lt2'].append(t)
    # 마지막 날짜 vs updated
    last = dates[-1] if dates else ''
    if last == updated:      date_rel['equal'] += 1
    elif last < updated:     date_rel['past'] += 1
    else:                    date_rel['future'] += 1
    if len(last_date_samples) < 5:
        last_date_samples.append((t, last, finals[-1], pm.get(t,{}).get('lifecycle')))

print('\n--- 날짜 관계 (history 마지막 date vs updated) ---')
print(f'equal={date_rel["equal"]} past={date_rel["past"]} future={date_rel["future"]}')
print('  (future>0 이면 HARD_FAIL 대상 — 스펙 §2)')

print('\n--- 스키마 이슈 (전부 [] 여야 정상) ---')
for k, v in issues.items():
    print(f'{k}: {v if v else "OK"}')

print('\n--- 샘플 5종: (ticker, history마지막date, history마지막final, output.lifecycle) ---')
for s in last_date_samples:
    match = 'MATCH' if s[2] == s[3] else 'DIFF'
    print(f'  {s}  [{match}]')

# 2) final 마지막값 vs output.lifecycle 불일치 전수 (날짜 past일 때 정상일 수 있음)
mism = [(t, hist[t][-1].get('final'), pm[t].get('lifecycle'))
        for t in hist if t in pm and isinstance(hist[t], list) and hist[t]
        and hist[t][-1].get('final') != pm[t].get('lifecycle')]
print(f'\n--- history 마지막 final ≠ output.lifecycle : {len(mism)}종 ---')
for m in mism[:12]:
    print(f'  {m}')
