/* F29 한국 머니플로우 렌더 — krx_output.json + flow_series_public.json */
var DATA = null;    // 하루 요약
var FLOW = null;    // 자금흐름 시계열 (public slim)
var curWin = 60;    // 자금흐름 윈도우 (시장 추세 — 긴 기간이 변화 명확)

/* ---------- 포맷 ---------- */
function won(v){
  if(v>=1e12) return (v/1e12).toFixed(2)+"조";
  if(v>=1e8)  return Math.round(v/1e8).toLocaleString()+"억";
  return Math.round(v).toLocaleString();
}
function pct(v){ return (v>0?"+":"")+v.toFixed(2)+"%"; }
function pp(v){ return (v>0?"+":"")+v.toFixed(1)+"%p"; }
function cg(v){ return v>0?"up":(v<0?"down":"flat"); }
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function mk(m){ return m==="KOSDAQ"?"KOSDAQ":"KOSPI"; }
function fmtDate(d){ return (d&&d.length===8)?(d.slice(0,4)+"."+d.slice(4,6)+"."+d.slice(6,8)+" 종가 기준"):"전일 종가 기준"; }
function josa(w, wb, nb){ // wb=받침있을때, nb=받침없을때
  if(!w) return wb;
  var c=w.charCodeAt(w.length-1);
  if(c>=0xAC00 && c<=0xD7A3) return ((c-0xAC00)%28!==0)?wb:nb;
  return wb;
}

/* ---------- 탭 ---------- */
function showPane(name){
  ["summary","stocks","themes","index"].forEach(function(p){
    document.getElementById("pane-"+p).classList.toggle("on",p===name);
    document.getElementById("tab-"+p).classList.toggle("on",p===name);
  });
  window.scrollTo(0,0);
}

/* ============ 자금흐름 (요약 최상단) ============ */
function badgeClass(b){
  if(b==="유입 우세") return "bg-in";
  if(b==="분배 우세 후보") return "bg-out";
  if(b==="대장주 단독") return "bg-lead";
  if(b==="표본 부족") return "bg-few";
  return "bg-mix";
}
function renderFlow(){
  if(!FLOW){ document.getElementById("flowcard").innerHTML='<div class="empty">자금 흐름 데이터를 불러오지 못했습니다.</div>'; return; }
  var series = FLOW.market.series;
  var sm = FLOW.market.summary[String(curWin)];

  // 윈도우 구간만 자름
  var seg = series.slice(-curWin);
  var W=480,H=150,PL=6,PR=30,PT=10,PB=18;
  var n=seg.length;
  // y축 자동 스케일: 두 라인 전체 min/max에 여백 → 변화 확대
  var allVals=[];
  seg.forEach(function(d){ allVals.push(d.kospiSharePct); allVals.push(d.kosdaqSharePct); });
  var vmin=Math.min.apply(null,allVals), vmax=Math.max.apply(null,allVals);
  var pad=Math.max(2,(vmax-vmin)*0.18);
  vmin=Math.max(0, vmin-pad); vmax=Math.min(100, vmax+pad);
  var span=(vmax-vmin)||1;
  function x(i){ return PL + (W-PL-PR)*(n<=1?0:i/(n-1)); }
  function y(v){ return PT + (H-PT-PB)*(1-((v-vmin)/span)); }
  function line(key,color){
    var pts = seg.map(function(d,i){ return x(i).toFixed(1)+","+y(d[key]).toFixed(1); }).join(" ");
    return '<polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="2.2" stroke-linejoin="round"/>';
  }
  // y 가이드: 실제 범위 안에서 3~4개 눈금 (동적)
  function niceStep(range){
    var raw=range/3;
    var mag=Math.pow(10,Math.floor(Math.log(raw)/Math.LN10));
    var norm=raw/mag;
    var step=(norm<1.5?1:(norm<3?2:(norm<7?5:10)))*mag;
    return step;
  }
  var step=niceStep(span);
  var gvals=[]; var g0=Math.ceil(vmin/step)*step;
  for(var gv=g0; gv<=vmax; gv+=step){ gvals.push(Math.round(gv*10)/10); }
  var guides = gvals.map(function(g){
    return '<line x1="'+PL+'" y1="'+y(g).toFixed(1)+'" x2="'+(W-PR)+'" y2="'+y(g).toFixed(1)+'" stroke="#1F2A3D" stroke-width="1" stroke-dasharray="2 3"/>'+
           '<text x="'+(W-PR+3)+'" y="'+(y(g)+3).toFixed(1)+'" fill="#5A6B84" font-size="9">'+g+'%</text>';
  }).join("");
  var svg = '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" style="width:100%;height:135px;display:block;">'+
            guides + line("kospiSharePct","#3DD8B0") + line("kosdaqSharePct","#9D7BEA") + '</svg>';

  var winBtns = FLOW.windows.map(function(w){
    return '<button class="'+(w===curWin?"on":"")+'" onclick="setWin('+w+')">'+w+'일</button>';
  }).join("");

  var kDelta = sm.kospiDeltaPp, qDelta = sm.kosdaqDeltaPp;
  var read;
  if(sm.label==="코스피 쏠림") read = '최근 '+curWin+'일간 거래대금 비중이 <b>코스피(대형주)</b> 쪽으로 이동했습니다.';
  else if(sm.label==="코스닥 쏠림") read = '최근 '+curWin+'일간 거래대금 비중이 <b>코스닥</b> 쪽으로 이동했습니다.';
  else read = '최근 '+curWin+'일간 코스피·코스닥 거래대금 비중에 뚜렷한 이동은 없습니다.';

  document.getElementById("flowcard").innerHTML =
    '<div class="wm">f29.io/kr-moneyflow</div>'+
    '<div class="flow-head"><span class="flow-title">시장 거래대금 비중 추이</span>'+
      '<span class="flow-win">'+winBtns+'</span></div>'+
    '<div class="flow-chart">'+svg+
      '<div class="flow-legend"><span class="lg"><span class="dot" style="background:#3DD8B0"></span>코스피</span>'+
      '<span class="lg"><span class="dot" style="background:#9D7BEA"></span>코스닥</span></div></div>'+
    '<div class="flow-move">'+
      '<div class="flow-col kospi"><div class="mk">KOSPI</div>'+
        '<div class="val">'+sm.kospiFrom.toFixed(1)+'%<span class="arw">→</span>'+sm.kospiTo.toFixed(1)+'%</div>'+
        '<div class="dp '+cg(kDelta)+'">'+pp(kDelta)+'</div></div>'+
      '<div class="flow-col kosdaq"><div class="mk">KOSDAQ</div>'+
        '<div class="val">'+sm.kosdaqFrom.toFixed(1)+'%<span class="arw">→</span>'+sm.kosdaqTo.toFixed(1)+'%</div>'+
        '<div class="dp '+cg(qDelta)+'">'+pp(qDelta)+'</div></div>'+
    '</div>'+
    '<div class="flow-read">'+read+'</div>';
}
function setWin(w){ curWin=w; renderFlow(); renderRotation(); }

/* ============ 종목 상세 바텀시트 (STEP3: 자금 압력 판독) ============ */
var stockCache={}, stockWin=15, curStock=null;
function stateClassStock(state){
  if(state==="up_concentration") return "bg-in";
  if(state==="down_concentration") return "bg-out";
  if(state==="fade_up") return "bg-mix";
  if(state==="fade_down") return "bg-out";
  if(state==="attention_up") return "bg-lead";
  if(state==="attention_down") return "bg-few";
  return "bg-mix";
}
function openStockSheet(code, name){
  if(!code) return;
  curStock=code; stockWin=15;
  document.getElementById("stockSheet").classList.add("on");
  document.getElementById("stockSheetIn").innerHTML='<div class="loading">불러오는 중...</div>';
  if(stockCache[code]){ renderStockSheet(stockCache[code]); return; }
  fetch("/kr-moneyflow/stocks/"+encodeURIComponent(code)+".json?_="+Date.now())
    .then(function(r){ if(!r.ok) throw new Error("404"); return r.json(); })
    .then(function(d){ stockCache[code]=d; if(curStock===code) renderStockSheet(d); })
    .catch(function(){
      document.getElementById("stockSheetIn").innerHTML=
        '<div class="sheet-hd"><span class="st">'+esc(name||code)+'</span>'+
        '<span class="x" onclick="closeStockSheet()">×</span></div>'+
        '<div class="empty">이 종목은 아직 충분한 데이터가 없습니다.<br>(신규 상장 등)</div>';
    });
}
function closeStockSheet(){ document.getElementById("stockSheet").classList.remove("on"); curStock=null; }
function setStockWin(w){ stockWin=w; if(stockCache[curStock]) renderStockSheet(stockCache[curStock]); }
function renderStockSheet(d){
  var sm=d.summary[String(stockWin)];
  var shareSeries=d.tradingSharePctSeries.slice(-stockWin);
  var priceSeries=d.closeIndexSeries.slice(-stockWin);
  var n=shareSeries.length;
  // 2라인 겹침: 점유율(좌축 느낌)·종가인덱스(우축 느낌) 각각 정규화해서 같은 박스에
  var W=480,H=150,PL=6,PR=6,PT=12,PB=16;
  function normLine(arr, key, color, dash){
    var vals=arr.map(function(x){return x[key];});
    var mn=Math.min.apply(null,vals), mx=Math.max.apply(null,vals);
    var pad=(mx-mn)*0.15||1; mn-=pad; mx+=pad;
    function x(i){ return PL+(W-PL-PR)*(n<=1?0:i/(n-1)); }
    function y(v){ return PT+(H-PT-PB)*(1-((v-mn)/(mx-mn||1))); }
    var pts=arr.map(function(o,i){ return x(i).toFixed(1)+","+y(o[key]).toFixed(1); }).join(" ");
    return '<polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="2.2" stroke-linejoin="round"'+(dash?' stroke-dasharray="4 3"':'')+'/>';
  }
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" style="width:100%;height:135px;display:block;">'+
    normLine(priceSeries,"v","#3DD8B0",false)+   // 종가 인덱스 = teal 실선
    normLine(shareSeries,"v","#D8B45F",true)+     // 거래대금 점유율 = gold 점선
    '</svg>';

  var winBtns=[15,30,60,90].map(function(w){
    return '<button class="'+(w===stockWin?"on":"")+'" onclick="setStockWin('+w+')">'+w+'일</button>';
  }).join("");

  // 판독 해석문 (규칙 기반, 결과만)
  var sc=cg(sm.priceChangePct);
  var read;
  var st=sm.flowState;
  if(st==="up_concentration") read='거래대금이 늘면서 가격도 함께 올랐습니다. 거래가 상승 방향에 실린 구간입니다.';
  else if(st==="down_concentration") read='거래대금이 늘었지만 가격은 내렸습니다. 거래가 하락 방향에 실린 구간으로, 매도 압력이 우세했을 수 있습니다.';
  else if(st==="fade_up") read='거래대금 비중은 줄었지만 가격은 올랐습니다. 관심은 다소 식었으나 가격은 버틴 구간입니다.';
  else if(st==="fade_down") read='거래대금 비중과 가격이 함께 줄었습니다. 관심과 가격이 동반 위축된 구간입니다.';
  else if(st==="attention_up") read='가격 변화는 뚜렷하지 않지만 거래대금 관심이 늘었습니다.';
  else if(st==="attention_down") read='거래대금 관심이 줄어든 구간입니다.';
  else read='최근 '+stockWin+'일간 뚜렷한 방향이 나타나지 않았습니다.';

  document.getElementById("stockSheetIn").innerHTML=
    '<div class="sheet-hd"><span class="st">'+esc(d.name)+'</span>'+
      '<span class="cand-mk" style="margin-left:6px">'+mk(d.market==="KOSDAQ"?"KOSDAQ":"KOSPI")+'</span>'+
      '<span class="x" onclick="closeStockSheet()">×</span></div>'+
    '<div class="sheet-sub">거래대금 점유율 · 가격 흐름 · 최근 '+stockWin+'일</div>'+
    '<div class="sheet-win">'+winBtns+'</div>'+
    svg+
    '<div class="flow-legend" style="margin:6px 0 2px">'+
      '<span class="lg"><span class="dot" style="background:#3DD8B0"></span>가격(지수화)</span>'+
      '<span class="lg"><span class="dot" style="background:#D8B45F"></span>거래대금 점유율</span></div>'+
    '<div class="sheet-share"><span class="big">'+
      '가격 '+(sm.priceChangePct>0?"+":"")+sm.priceChangePct.toFixed(1)+'%</span>'+
      '<span class="dp '+cg(sm.shareDeltaPp)+'">점유율 '+pp(sm.shareDeltaPp)+'</span></div>'+
    '<div><span class="sheet-state '+stateClassStock(st)+'">'+esc(sm.flowLabel)+'</span></div>'+
    '<div class="sheet-read">'+read+'</div>'+
    '<div class="sheet-note">거래대금·가격 기준 참고지표입니다.</div>';
}

/* ============ 시장 핵심 요약 (STEP1: 단기/중기/장기 + 괴리) ============ */
function regimeBadgeCls(label){
  if(label.indexOf("코스피")>=0) return "rb-kospi";
  if(label.indexOf("코스닥")>=0) return "rb-kosdaq";
  return "rb-mixed";
}
function renderKeySummary(){
  if(!FLOW || !FLOW.marketSummary){ document.getElementById("keycard").innerHTML='<div class="empty">요약 데이터를 불러오지 못했습니다.</div>'; return; }
  var ms=FLOW.marketSummary, rg=ms.regime;
  var rbw=ms.regimeByWindow||{};

  // 현재 국면
  var head='<div class="ks-title">현재 로테이션 국면 <span class="regime-badge '+regimeBadgeCls(rg.label)+'">'+esc(rg.label)+'</span></div>';

  // 기간별 로테이션 (단기/중기/장기)
  var periods=[["15","단기"],["30","중기"],["90","장기"]];
  var rows=periods.map(function(p){
    var r=rbw[p[0]]; if(!r) return "";
    return '<div class="ksp-row"><span class="ksp-lbl">'+p[1]+' '+p[0]+'일</span>'+
      '<span class="ksp-badge '+regimeBadgeCls(r.label)+'">'+esc(r.label)+'</span>'+
      '<span class="ksp-dp '+cg(r.deltaPp)+'">'+pp(r.deltaPp)+'</span></div>';
  }).join("");
  var periodBlock='<div class="ks-sub">기간별 로테이션 <span class="ks-hint">· 코스피 비중 기준</span></div><div class="ksp">'+rows+'</div>';

  // 기간 괴리 (핵심)
  var divBlock="";
  if(ms.divergences && ms.divergences.length){
    var dv=ms.divergences.map(function(d,i){
      return '<div class="kc"><span class="n">'+(i+1)+'</span><span class="t">'+esc(d.text)+'</span></div>';
    }).join("");
    divBlock='<div class="ks-sub ks-diverge">기간 괴리 <span class="ks-hint">· 단기와 장기가 다른 테마</span></div>'+dv;
  }

  // 오늘의 핵심 변화
  var kcBlock="";
  if(ms.keyChanges && ms.keyChanges.length){
    var kc=ms.keyChanges.map(function(t,i){
      return '<div class="kc"><span class="n">'+(i+1)+'</span><span class="t">'+esc(t)+'</span></div>';
    }).join("");
    kcBlock='<div class="ks-sub">오늘의 핵심 변화</div>'+kc;
  }

  document.getElementById("keycard").innerHTML = head+periodBlock+divBlock+kcBlock;
}

/* ============ 테마 상세 바텀시트 (STEP2) ============ */
var sheetTheme=null, sheetWin=15;
function openThemeSheet(theme){
  if(!FLOW || !FLOW.themeDetails || !FLOW.themeDetails[theme]){ return; }
  sheetTheme=theme; sheetWin=15;
  document.getElementById("themeSheet").classList.add("on");
  renderThemeSheet();
}
function closeSheet(){ document.getElementById("themeSheet").classList.remove("on"); sheetTheme=null; }
function setSheetWin(w){ sheetWin=w; renderThemeSheet(); }
function stateClass(badge){
  if(badge==="유입 우세") return "bg-in";
  if(badge==="분배 우세 후보") return "bg-out";
  if(badge==="대장주 단독") return "bg-lead";
  if(badge==="표본 부족") return "bg-few";
  return "bg-mix";
}
function renderThemeSheet(){
  var det=FLOW.themeDetails[sheetTheme];
  var sm=det.summary[String(sheetWin)];
  var series=det.series.slice(-sheetWin);
  // 점유율 라인
  var W=480,H=130,PL=6,PR=32,PT=10,PB=16, n=series.length;
  var vals=series.map(function(d){return d.sharePct;});
  var mn=Math.min.apply(null,vals), mx=Math.max.apply(null,vals);
  var pad=(mx-mn)*0.15||1; mn-=pad; mx+=pad;
  function x(i){ return PL+(W-PL-PR)*(n<=1?0:i/(n-1)); }
  function y(v){ return PT+(H-PT-PB)*(1-((v-mn)/(mx-mn||1))); }
  var pts=series.map(function(d,i){ return x(i).toFixed(1)+","+y(d.sharePct).toFixed(1); }).join(" ");
  var yLabels=[mx,(mx+mn)/2,mn].map(function(v){
    return '<text x="'+(W-PR+3)+'" y="'+(y(v)+3)+'" fill="#5A6B84" font-size="9">'+v.toFixed(1)+'%</text>';
  }).join("");
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" style="width:100%;height:118px;display:block;">'+
    '<polyline points="'+pts+'" fill="none" stroke="#D8B45F" stroke-width="2.2" stroke-linejoin="round"/>'+yLabels+'</svg>';

  var winBtns=FLOW.windows.map(function(w){
    return '<button class="'+(w===sheetWin?"on":"")+'" onclick="setSheetWin('+w+')">'+w+'일</button>';
  }).join("");

  // 해석문 (규칙 기반, label 활용)
  var dpCls=cg(sm.deltaPp);
  var read;
  var shareUp = sm.deltaPp>0.3, shareDown = sm.deltaPp<-0.3;
  var josaIga = josa(sheetTheme,"이","가");
  if(shareDown) read='전체 시장 거래대금에서 '+esc(sheetTheme)+josaIga+' 차지하는 비중이 줄었습니다. 시장 관심이 상대적으로 이 테마에서 빠져나간 구간입니다.';
  else if(shareUp) read='전체 시장 거래대금에서 '+esc(sheetTheme)+josaIga+' 차지하는 비중이 늘었습니다. 시장 관심이 상대적으로 이 테마로 모인 구간입니다.';
  else read='전체 시장 거래대금에서 '+esc(sheetTheme)+'의 비중은 큰 변화 없이 유지되고 있습니다.';

  document.getElementById("themeSheetIn").innerHTML=
    '<div class="sheet-hd"><span class="st">'+esc(sheetTheme)+' 자금 흐름</span>'+
      '<span class="x" onclick="closeSheet()">×</span></div>'+
    '<div class="sheet-sub">거래대금 점유율 · 최근 '+sheetWin+'일</div>'+
    '<div class="sheet-win">'+winBtns+'</div>'+
    svg+
    '<div class="sheet-share"><span class="big">'+sm.from.toFixed(1)+'%<span class="arw"> → </span>'+sm.to.toFixed(1)+'%</span>'+
      '<span class="dp '+dpCls+'">'+pp(sm.deltaPp)+'</span></div>'+
    '<div><span class="sheet-state '+stateClass(sm.badge)+'">'+esc(sm.label)+'</span></div>'+
    '<div class="sheet-read">'+read+'</div>'+
    '<div class="sheet-note">거래대금 기준 참고지표입니다.</div>';
}

/* ============ 테마 로테이션 (요약) ============ */
function renderRotation(){
  if(!FLOW){ document.getElementById("rotcard").innerHTML='<div class="empty">데이터 없음</div>'; return; }
  var ts = FLOW.themes.summary[String(curWin)];
  function bars(arr, kind){
    if(!arr.length) return '<div class="empty" style="padding:10px 0">해당 없음</div>';
    var maxAbs = Math.max.apply(null, arr.map(function(r){return Math.abs(r.deltaPp);}))||1;
    return arr.map(function(r){
      var w = Math.max(4, Math.abs(r.deltaPp)/maxAbs*100);
      var col = kind==="up"?"var(--up)":"var(--down)";
      return '<div class="rotb">'+
        '<div class="rotb-top"><span class="rotb-nm clickable" onclick="openThemeSheet(\''+esc(r.theme)+'\')">'+esc(r.theme)+'</span>'+
        '<span class="rotb-dp '+(kind==="up"?"up":"down")+'">'+pp(r.deltaPp)+'</span></div>'+
        '<div class="rotb-bar"><i style="width:'+w+'%;background:'+col+'"></i></div>'+
        '<div class="rotb-sub">'+r.from.toFixed(1)+'% → '+r.to.toFixed(1)+'%</div>'+
        '</div>';
    }).join("");
  }
  document.getElementById("rotcard").innerHTML =
    '<div class="rot-wrap">'+
      '<div class="rot-col"><div class="rot-h up">자금 유입 (점유율↑)</div>'+bars(ts.rising,"up")+'</div>'+
      '<div class="rot-col"><div class="rot-h down">자금 유출 (점유율↓)</div>'+bars(ts.falling,"down")+'</div>'+
    '</div>';
}

/* ============ 시장 국면 ============ */
function renderRegime(){
  var ms=DATA.marketSummary;
  function ln(o,cls){
    var up=o.upRatio;
    var tone = up>=55?"자금이 넓게 퍼진 편":(up>=45?"방향이 갈린 혼조":"오른 종목이 적은 편");
    return '<div class="regime-line"><div class="regime-mk '+cls+'">'+o.market+'</div>'+
      '<div class="regime-body">거래대금 <b>'+won(o.totalValue)+'</b> · 상승 <b>'+up.toFixed(1)+'%</b> ('+o.count+'종목) · '+tone+
      '<div class="regime-bar"><i style="width:'+Math.max(2,Math.min(100,up))+'%"></i></div></div></div>';
  }
  document.getElementById("regimecard").innerHTML = ln(ms.KOSPI,"kospi")+ln(ms.KOSDAQ,"kosdaq");
}

/* ============ 거래대금 막대 ============ */
function tvBars(arr, n){
  arr = arr.slice(0,n);
  var maxTv = Math.max.apply(null, arr.map(function(o){return o.tradingValue;}))||1;
  return arr.map(function(o,i){
    var w = Math.max(3, o.tradingValue/maxTv*100);
    return '<div class="bar"><div class="bar-top">'+
      '<span class="bar-rk">'+(i+1)+'</span>'+
      '<span class="bar-nm clickable" onclick="openStockSheet(\''+o.code+'\',\''+esc(o.name)+'\')">'+esc(o.name)+'<span class="mk">'+mk(o.market)+'</span></span>'+
      '<span class="bar-cg '+cg(o.changeRate)+'">'+pct(o.changeRate)+'</span></div>'+
      '<div class="bar-track"><i style="width:'+w+'%"></i></div>'+
      '<div class="bar-val">'+won(o.tradingValue)+'</div></div>';
  }).join("");
}
function renderTV5(){ document.getElementById("tv5card").innerHTML = tvBars(DATA.tradingValueTop||[],5); }
function renderTV(mode){
  var key = mode==="up"?"tradingValueUp":(mode==="down"?"tradingValueDown":"tradingValueTop");
  document.getElementById("tvcard").innerHTML = tvBars(DATA[key]||[],10) || '<div class="empty">데이터 없음</div>';
}
function showTV(mode){
  ["top","up","down"].forEach(function(m){ document.getElementById("tv-"+m).classList.toggle("on",m===mode); });
  renderTV(mode);
}

/* ============ 후보 (리더/급등) ============ */
function candCard(o,kind){
  var c=cg(o.changeRate), tags="";
  if(kind==="leader"){
    if(o.tvConsecutive>=2) tags+='<span class="cand-tag tag-consec">연속 '+o.tvConsecutive+'일</span> ';
    if(o.tvSurge>=2) tags+='<span class="cand-tag tag-surge">거래대금 '+o.tvSurge.toFixed(1)+'배</span>';
  } else {
    tags+='<span class="cand-tag tag-surge">거래대금 '+o.tvSurge.toFixed(1)+'배</span> ';
    tags+='<span class="cand-tag tag-oneday">연속 '+o.tvConsecutive+'일</span>';
  }
  return '<div class="cand"><div class="cand-top"><span class="cand-name clickable" onclick="openStockSheet(\''+o.code+'\',\''+esc(o.name)+'\')">'+esc(o.name)+'</span>'+
    '<span class="cand-mk">'+mk(o.market)+'</span>'+
    '<span class="cand-chg '+c+'">'+pct(o.changeRate)+'</span></div>'+
    '<div class="cand-stats">'+
      '<span class="s">20일 <b>'+(o.ret20>0?"+":"")+o.ret20.toFixed(1)+'%</b></span>'+
      '<span class="s">5일 <b>'+(o.ret5>0?"+":"")+o.ret5.toFixed(1)+'%</b></span>'+
      '<span class="s">거래대금 <b>'+won(o.tradingValue)+'</b></span> '+tags+
    '</div></div>';
}
function renderLeaders(n,elId){
  var arr=(DATA.leaderCandidates||[]).slice(0,n);
  document.getElementById(elId).innerHTML = arr.length ? arr.map(function(o){return candCard(o,"leader");}).join("")
    : '<div class="empty">오늘은 연속 유입 조건을 채운 리더 후보가 없습니다.</div>';
}
function renderSpikes(){
  var arr=DATA.spikeCandidates||[];
  document.getElementById("spikecard").innerHTML = arr.length ? arr.slice(0,10).map(function(o){return candCard(o,"spike");}).join("")
    : '<div class="empty">오늘은 단기 관심 집중 후보가 없습니다.<br>거래대금이 하루만 튄 종목이 없다는 뜻입니다.</div>';
}

/* ============ 테마 (테마 탭) ============ */
function renderThemes(){
  // flow_series 최신 배지를 테마명으로 매핑 (30일 요약의 rising/falling에서 badge 추출)
  var badgeMap={};
  if(FLOW){
    ["rising","falling"].forEach(function(k){
      (FLOW.themes.summary["30"][k]||[]).forEach(function(r){ badgeMap[r.theme]=r.badge; });
    });
  }
  var html=(DATA.themes||[]).map(function(t){
    var badge = badgeMap[t.theme] || null;
    var chips=(t.stocks||[]).slice(0,3).map(function(s){
      return '<span class="th-chip"><b>'+esc(s.name)+'</b> <span class="'+cg(s.changeRate)+'">'+pct(s.changeRate)+'</span></span>';
    }).join("");
    var badgeHtml = badge ? '<span class="th-badge '+badgeClass(badge)+'">'+badge+'</span>' : '';
    return '<div class="th"><div class="th-top"><span class="th-name clickable" onclick="openThemeSheet(\''+esc(t.theme)+'\')">'+esc(t.theme)+'</span>'+badgeHtml+
      '<span class="th-tv">'+won(t.tradingValue)+'</span></div>'+
      '<div class="th-meta">상승 '+t.upRatio.toFixed(0)+'% · '+t.count+'종목 · '+
      '<span class="th-lead">대장 '+esc(t.leader)+' <span class="'+cg(t.leaderChange)+'">'+pct(t.leaderChange)+'</span></span></div>'+
      '<div class="th-stocks">'+chips+'</div></div>';
  }).join("");
  document.getElementById("themecard").innerHTML = html;
}

/* ============ 지수 기여 (지수 탭) ============ */
function renderContrib(){
  var top=DATA.contributionTop||[], bot=DATA.contributionBottom||[];
  var allAbs = top.concat(bot).map(function(o){return Math.abs(o.contribution);});
  var maxAbs = Math.max.apply(null, allAbs)||1;
  function col(arr,pos){
    return arr.map(function(o){
      var w=Math.max(3,Math.abs(o.contribution)/maxAbs*100);
      var sign=o.contribution>0?"+":"";
      var col=pos?"var(--up)":"var(--down)";
      return '<div class="cb"><div class="cb-top"><span class="cb-nm clickable" onclick="openStockSheet(\''+o.code+'\',\''+esc(o.name)+'\')">'+esc(o.name)+'</span>'+
        '<span class="cb-p '+(pos?"up":"down")+'">'+sign+Math.round(o.contribution).toLocaleString()+'</span></div>'+
        '<div class="cb-track"><i style="width:'+w+'%;background:'+col+'"></i></div></div>';
    }).join("");
  }
  document.getElementById("contribcard").innerHTML =
    '<div class="contrib-wrap">'+
      '<div class="contrib-col"><div class="contrib-h up">지수를 밀어올린</div>'+col(top,true)+'</div>'+
      '<div class="contrib-col"><div class="contrib-h down">지수를 끌어내린</div>'+col(bot,false)+'</div>'+
    '</div>';
}

/* ============ 이미지 저장 ============ */
function saveCard(){
  var el=document.querySelector(".pane.on");
  if(typeof html2canvas!=="function") return;
  html2canvas(el,{backgroundColor:"#0A0E17",scale:2}).then(function(cv){
    var a=document.createElement("a"); a.download="f29-kr-moneyflow-"+(DATA?DATA.date:"")+".png"; a.href=cv.toDataURL(); a.click();
  });
}

/* ============ 부트 ============ */
function boot(){
  if(DATA){
    document.getElementById("updated").textContent=fmtDate(DATA.date);
    renderRegime(); renderTV5(); renderLeaders(3,"leader3card");
    renderLeaders(10,"leadercard"); renderSpikes(); showTV("top");
    renderThemes(); renderContrib();
  }
  if(FLOW){ renderKeySummary(); renderFlow(); renderRotation(); }
}
function load(url){ return fetch(url+"?_="+Date.now()).then(function(r){ if(!r.ok) throw new Error(url+" "+r.status); return r.json(); }); }
function start(){
  Promise.all([
    load("/kr-moneyflow/krx_output.json").then(function(d){DATA=d;}).catch(function(e){console.error(e);}),
    load("/kr-moneyflow/flow_series_public.json").then(function(d){FLOW=d;}).catch(function(e){console.error(e);})
  ]).then(function(){
    if(!DATA && !FLOW){
      document.querySelectorAll(".loading").forEach(function(el){ el.textContent="데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."; });
      return;
    }
    boot();
  });
}
if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",start);}else{start();}
