/* F29 돈의 무게 — weight.js */
var WEIGHT=null;

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
  fetch("/weight/stocks/"+encodeURIComponent(code)+".json?_="+Date.now())
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
/* ============ 랭킹 렌더 ============ */
function fmtPct(v){ return (v>0?"+":"")+v.toFixed(1)+"%"; }
var activeTab="buy";

function renderSummary(){
  var c=WEIGHT.counts||{};
  var buy=c.up_concentration||0, sell=c.down_concentration||0;
  var fadeUp=c.fade_up||0, fadeDown=c.fade_down||0;
  var tot=buy+sell||1;
  var buyW=Math.round(buy/tot*100), sellW=100-buyW;
  var read = buy>sell ? '오늘은 <b>상승 방향</b>에 거래대금이 실린 종목이 더 많은 편입니다.'
           : sell>buy ? '오늘은 <b>하락 방향</b>에 거래대금이 실린 종목이 더 많은 편입니다.'
           : '오늘은 상승·하락 압력이 비슷한 편입니다.';
  document.getElementById("summaryCard").innerHTML=
    '<div class="pd-def">거래대금이 늘어난 종목 중 가격도 오른 쪽은 <b style="color:var(--up)">매수 압력</b>, 가격이 내린 쪽은 <b style="color:var(--down)">매도 압력</b>으로 나눠 봅니다.</div>'+
    '<div class="pbal-head"><span class="b buy">매수 압력 '+buy+'</span><span class="b sell">매도 압력 '+sell+'</span></div>'+
    '<div class="pbal-bar"><span class="buy" style="width:'+buyW+'%"></span><span class="sell" style="width:'+sellW+'%"></span></div>'+
    '<div class="pbal-read">'+read+'</div>'+
    '<div class="pd-sub-title">보조 신호</div>'+
    '<div class="pd-sub"><span>관심도 약화 <b>'+fadeDown+'</b></span><span>얇은 상승 <b>'+fadeUp+'</b></span></div>';

  // 기본 탭 = 많은 쪽
  activeTab = buy>=sell ? "buy" : "sell";
  renderTabs(buy, sell);
  renderActiveList();
}

function renderTabs(buy, sell){
  document.getElementById("pressureTabs").innerHTML=
    '<button class="'+(activeTab==="buy"?"active buy":"")+'" onclick="switchTab(\'buy\')">매수 압력 '+buy+'</button>'+
    '<button class="'+(activeTab==="sell"?"active sell":"")+'" onclick="switchTab(\'sell\')">매도 압력 '+sell+'</button>';
}
function switchTab(t){
  activeTab=t;
  var c=WEIGHT.counts||{};
  renderTabs(c.up_concentration||0, c.down_concentration||0);
  renderActiveList();
}
function renderActiveList(){
  document.getElementById("rankSub").textContent = activeTab==="buy"
    ? "최근 15일 거래대금이 상승에 실린 종목"
    : "최근 15일 거래대금이 하락에 실린 종목";
  renderRank("rankCard", activeTab==="buy"?WEIGHT.buyPressure:WEIGHT.sellPressure, activeTab);
}

function renderRank(cardId, list, kind){
  if(!list || !list.length){ document.getElementById(cardId).innerHTML='<div class="empty">해당 종목이 없습니다.</div>'; return; }
  var maxAbs=Math.max.apply(null, list.map(function(o){return Math.abs(o.changeRate);}))||1;
  var color = kind==="buy" ? "#3DDC84" : "#F0997B";
  var rows=list.map(function(o,i){
    var w=Math.max(6, Math.abs(o.changeRate)/maxAbs*100);
    var warn = (kind==="buy" && o.changeRate>=30) ? '<span class="warn">단기 급등</span>' : '';
    return '<div class="prow" onclick="openStockSheet(\''+o.code+'\',\''+esc(o.name)+'\')">'+
      '<span class="rk">'+(i+1)+'</span>'+
      '<span class="nm">'+esc(o.name)+'<span class="mkbadge">'+mk(o.market)+'</span></span>'+warn+
      '<span class="bar-wrap"><span class="bar-fill" style="width:'+w.toFixed(0)+'%;background:'+color+'"></span></span>'+
      '<span class="cg '+cg(o.changeRate)+'">'+fmtPct(o.changeRate)+'</span></div>';
  }).join("");
  var note = kind==="buy"
    ? '최근 15일간 거래대금 점유율이 높아지고 가격도 함께 오른 종목입니다. 등락률은 15일 기준이며, 급등 종목은 변동성에 유의하세요.'
    : '최근 15일간 거래대금 점유율은 높아졌지만 가격은 하락한 종목입니다. 거래가 하락 방향에 실린 구간으로, 거래대금이 많다고 좋은 신호가 아닙니다. 등락률은 15일 기준입니다.';
  document.getElementById(cardId).innerHTML=rows+'<div class="card-note">'+note+'</div>';
}

function bootWeight(){
  fetch("/weight/weight_output.json?_="+Date.now())
    .then(function(r){ return r.json(); })
    .then(function(d){
      WEIGHT=d;
      if(d.date) document.getElementById("updated").textContent=fmtDate(d.date);
      renderSummary();
    })
    .catch(function(){
      document.getElementById("summaryCard").innerHTML='<div class="empty">데이터를 불러오지 못했습니다.</div>';
    });
}
document.addEventListener("DOMContentLoaded", bootWeight);
