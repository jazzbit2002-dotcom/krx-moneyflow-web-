'use strict';
const fs = require('fs');

let fetchLog = [];
const IDX_KR  = JSON.parse(fs.readFileSync('/tmp/s6work/real_kr.json','utf8'));   // weight용 (scalar aliases)
const IDX_ALL = JSON.parse(fs.readFileSync('/tmp/s6work/real_all.json','utf8'));  // portal용 (배열 aliases)

global.fetch = async (url) => {
  fetchLog.push(url);
  return { json: async () => (url.indexOf('all') >= 0 ? IDX_ALL : IDX_KR) };
};

let navLog = [];
function makeLocation(){ const o={}; let h=''; Object.defineProperty(o,'href',{get:()=>h,set:v=>{h=v;navLog.push(v);}}); return o; }
global.location = makeLocation();

function makeEl(){
  const L={};
  return {
    innerHTML:'', hidden:true, value:'', _cands:[], _lastHTML:null,
    addEventListener(e,f){ (L[e]=L[e]||[]).push(f); },
    _fire(e,a){ (L[e]||[]).forEach(f=>f(a||{})); },
    querySelectorAll(){
      // innerHTML 변경 시에만 버튼 재생성(같은 렌더 내 querySelectorAll은 동일 객체 반환 → 핸들러 유지)
      if(this._lastHTML!==this.innerHTML){
        const keys=[...this.innerHTML.matchAll(/data-key="([^"]*)"/g)].map(x=>x[1]);
        this._cands=keys.map(k=>{ const bl={}; return {_k:k,addEventListener(e,f){(bl[e]=bl[e]||[]).push(f);},click(){(bl.click||[]).forEach(f=>f());}}; });
        this._lastHTML=this.innerHTML;
      }
      return this._cands;
    }
  };
}

const boxPortal=makeEl(), boxWeight=makeEl(), inputPortal=makeEl(), inputWeight=makeEl();
const legacyBox=makeEl();
global.document={ getElementById(id){ return id==='f29-search-results'?legacyBox:null; } };
global.window={};

require('/tmp/s6work/f29-search.patched.js');
const F29Search=global.window.F29Search;

let PASS=0,FAIL=0; const fails=[];
function chk(n,c){ if(c)PASS++; else {FAIL++;fails.push(n);} console.log((c?'PASS':'FAIL')+' '+n); }
function rn(){ navLog=[]; }
function clickCand(box, key){
  const cands = box.querySelectorAll('.f29-cand');  // 캐시된 버튼(핸들러 유지)
  const t = cands.find(c=>c._k===key);
  if(t) t.click();
  return !!t;
}

(async () => {
  let wSel=null;
  await F29Search.init(inputWeight, { indexUrl:'/data/search_index.json', resultsEl:boxWeight, onStockSelect:(s,q)=>{wSel={code:s.c,qt:q};} });
  await F29Search.init(inputPortal, { indexUrl:'/data/search_index_all.json', resultsEl:boxPortal });

  chk('fetch 2 distinct', fetchLog.length===2 && new Set(fetchLog).size===2);

  // ── §5 핵심 스모크 (portal = all.json) ──
  // KR alias·exact·code
  rn(); inputPortal.value='삼전'; inputPortal._fire('keydown',{key:'Enter'});
  chk('삼전 → /stock/005930/', navLog[0]==='/stock/005930/?ref=search');
  rn(); inputPortal.value='삼성전자'; inputPortal._fire('keydown',{key:'Enter'});
  chk('삼성전자 → /stock/005930/', navLog[0]==='/stock/005930/?ref=search');
  rn(); inputPortal.value='005930'; inputPortal._fire('keydown',{key:'Enter'});
  chk('005930 → /stock/005930/', navLog[0]==='/stock/005930/?ref=search');

  // US alias·exact — 전부 stock.url(/stock/us/{SLUG}/), NVDA도 동일 경로(분기 불일치 금지)
  rn(); inputPortal.value='엔비디아'; inputPortal._fire('keydown',{key:'Enter'});
  chk('엔비디아 → /stock/us/NVDA/', navLog[0]==='/stock/us/NVDA/?ref=search');
  rn(); inputPortal.value='NVDA'; inputPortal._fire('keydown',{key:'Enter'});
  chk('NVDA → /stock/us/NVDA/ (구형경로 아님!)', navLog[0]==='/stock/us/NVDA/?ref=search');
  rn(); inputPortal.value='NVIDIA'; inputPortal._fire('keydown',{key:'Enter'});
  chk('NVIDIA → /stock/us/NVDA/', navLog[0]==='/stock/us/NVDA/?ref=search');
  rn(); inputPortal.value='알파벳'; inputPortal._fire('keydown',{key:'Enter'});
  chk('알파벳 → /stock/us/GOOGL/', navLog[0]==='/stock/us/GOOGL/?ref=search');

  // 충돌 alias '구글' → KR:005930 + US:GOOGL 후보 2종(자동이동 0)
  rn(); boxPortal.innerHTML=''; inputPortal.value='구글'; inputPortal._fire('keydown',{key:'Enter'});
  const html = boxPortal.innerHTML;
  chk('구글(충돌) → 자동이동 0', navLog.length===0);
  chk('구글(충돌) → 후보 2종 렌더', (html.match(/f29-cand/g)||[]).length===2);
  chk('구글(충돌) → KR+US 배지 공존', html.indexOf('f29-mkt-kr')>=0 && html.indexOf('f29-mkt-us')>=0);
  // 충돌 후보 클릭: US:GOOGL 선택 → stock.url
  rn(); clickCand(boxPortal,'US:GOOGL');
  chk('충돌 후보 US:GOOGL 클릭 → /stock/us/GOOGL/', navLog[0]==='/stock/us/GOOGL/?ref=search');
  rn(); boxPortal.innerHTML=''; inputPortal.value='구글'; inputPortal._fire('keydown',{key:'Enter'});
  clickCand(boxPortal,'KR:005930');
  chk('충돌 후보 KR:005930 클릭 → /stock/005930/', navLog[0]==='/stock/005930/?ref=search');

  // US partial 후보 클릭 → stock.url (엔비 접두 2건: 엔비디아·엔비스타)
  rn(); boxPortal.innerHTML=''; inputPortal.value='엔비'; inputPortal._fire('keydown',{key:'Enter'});
  chk('엔비(partial 2건) → 자동이동 0(후보)', navLog.length===0);
  chk('엔비 → 후보 2건 렌더', (boxPortal.innerHTML.match(/f29-cand/g)||[]).length===2);
  rn(); clickCand(boxPortal,'US:NVDA');
  chk('US partial 클릭 → stock.url /stock/us/NVDA/', navLog[0]==='/stock/us/NVDA/?ref=search');

  // legacy-only US alias (통합 인덱스 없음, US_ALIAS엔 있음) → /moneyflow/#
  rn(); inputPortal.value='애플'; inputPortal._fire('keydown',{key:'Enter'});
  chk('애플(legacy only) → /moneyflow/#stock-AAPL', navLog[0]==='/moneyflow/#stock-AAPL');

  // crypto·fail 무회귀
  rn(); inputPortal.value='비트코인'; inputPortal._fire('keydown',{key:'Enter'});
  chk('비트코인 → /index.html?asset=btc', navLog[0]==='/index.html?asset=btc');
  rn(); boxPortal.innerHTML=''; inputPortal.value='없는거xyz'; inputPortal._fire('keydown',{key:'Enter'});
  chk('없는종목 → 이동0 + fail카드', navLog.length===0 && boxPortal.innerHTML.indexOf('f29-fail')>=0);

  // ── weight (KR-only, scalar aliases) ──
  rn(); wSel=null; inputWeight.value='삼전'; inputWeight._fire('keydown',{key:'Enter'});
  chk('weight 삼전(scalar alias) → onStockSelect(005930), 이동0', wSel&&wSel.code==='005930'&&navLog.length===0);
  rn(); wSel=null; inputWeight.value='삼성전자'; inputWeight._fire('keydown',{key:'Enter'});
  chk('weight 삼성전자 → onStockSelect, 이동0', wSel&&wSel.code==='005930'&&navLog.length===0);
  rn(); boxWeight.innerHTML=''; wSel=null; inputWeight.value='엔비디아'; inputWeight._fire('keydown',{key:'Enter'});
  chk('weight 엔비디아 → US 후보0(fail), 이동0', navLog.length===0 && !wSel && boxWeight.innerHTML.indexOf('f29-fail')>=0);
  rn(); boxWeight.innerHTML=''; wSel=null; inputWeight.value='NVDA'; inputWeight._fire('keydown',{key:'Enter'});
  chk('weight NVDA → 이동0(legacy 차단)', navLog.length===0);

  // ── 교차 렌더 0 ──
  boxPortal.innerHTML=''; boxWeight.innerHTML='WEIGHT_KEEP';
  inputPortal.value='삼'; inputPortal._fire('input'); await new Promise(r=>setTimeout(r,150));
  chk('교차0: portal suggest → weight 박스 무변경', boxWeight.innerHTML==='WEIGHT_KEEP');

  // ── suggest US 배지(portal) / weight 배지 0 ──
  boxPortal.innerHTML=''; inputPortal.value='엔'; inputPortal._fire('input'); await new Promise(r=>setTimeout(r,150));
  chk('portal suggest 미국 배지 존재', boxPortal.innerHTML.indexOf('f29-mkt-us')>=0);
  boxWeight.innerHTML=''; inputWeight.value='삼'; inputWeight._fire('input'); await new Promise(r=>setTimeout(r,150));
  chk('weight suggest 미국 배지 0', boxWeight.innerHTML.indexOf('f29-mkt-us')<0);

  // ── callback throw → 이동 0 ──
  rn();
  const bT=makeEl(), iT=makeEl();
  await F29Search.init(iT,{indexUrl:'/data/search_index_all.json',resultsEl:bT,onStockSelect:()=>{throw new Error('boom');}});
  try{ iT.value='삼성전자'; iT._fire('keydown',{key:'Enter'}); }catch(e){}
  chk('callback throw → 이동0', navLog.length===0);

  // ── dedupe: 알파벳 접두 suggest에 GOOGL 1건 ──
  boxPortal.innerHTML=''; inputPortal.value='알'; inputPortal._fire('input'); await new Promise(r=>setTimeout(r,150));
  chk('dedupe: 알파벳 후보 GOOGL 1건', (boxPortal.innerHTML.match(/US:GOOGL/g)||[]).length<=1);

  // ── legacy 박스 미사용 ──
  chk('legacyBox 미사용', legacyBox.innerHTML==='');

  console.log('\n=== RESULT PASS='+PASS+' FAIL='+FAIL+' ===');
  if(FAIL){ console.log('FAILED:', fails.join(' | ')); process.exit(1); }
})().catch(e=>{ console.error('HARNESS ERROR', e); process.exit(2); });
