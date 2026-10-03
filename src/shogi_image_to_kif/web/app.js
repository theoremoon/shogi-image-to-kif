'use strict';
const $ = id => document.getElementById(id);
const glyphs = {P:'歩',L:'香',N:'桂',S:'銀',G:'金',B:'角',R:'飛',K:'玉','+P':'と','+L':'杏','+N':'圭','+S':'全','+B':'馬','+R':'龍'};
const handOrder = ['R','B','G','S','N','L','P'];
const limits = {R:2,B:2,G:4,S:4,N:4,L:4,P:18};
let sourceImage = null, imageData = null, bounds = null, clicks = [], picking = false;
let draft = null, chosenPiece = 'P', chosenSide = 'b', result = null, history = [], changed = new Set(), busy = false;
let sampleRows = [];
function status(text, error=false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
async function api(path, data) {
  if (window.shogiBackend) return window.shogiBackend.request(path, data);
  const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || '処理に失敗しました');
  return value;
}
function bind(id, type, callback) { $(id).addEventListener(type, async event => {try {await callback(event);} catch(error) {status(error.message, true);}}); }
function invalidate() {
  result = null; $('output-area').hidden = true;
  updateExport();
}
function updateExport() {
  const ready = Boolean(draft);
  $('export').disabled = !ready || busy;
}
function setBusy(value) {
  busy = value; $('recognize').disabled = value;
  $('recognize').textContent = value ? 'Reading…' : 'Read →';
  ['orientation','select-bounds','auto-bounds','reset-image','sample-list','image-file','draft-file','import-sfen','blank-board'].forEach(id => $(id).disabled = value);
  updateExport();
}
function snapshot() {
  history.push({board:[...draft.board],review_squares:[...(draft.review_squares || [])],changed:[...changed]});
  if (history.length > 100) history.shift();
  $('undo').disabled = false;
}
function drawSource() {
  if (!sourceImage) return;
  const canvas = $('source-canvas'), context = canvas.getContext('2d');
  const factor = Math.min(1, 1000/sourceImage.naturalWidth, 1000/sourceImage.naturalHeight);
  canvas.width = Math.round(sourceImage.naturalWidth * factor);
  canvas.height = Math.round(sourceImage.naturalHeight * factor);
  context.drawImage(sourceImage,0,0,canvas.width,canvas.height);
  if (bounds) {
    const [left,top,right,bottom] = bounds.map(v=>v*factor);
    context.strokeStyle='#2f9866'; context.lineWidth=3;
    context.strokeRect(left,top,right-left,bottom-top);
  }
  clicks.forEach(([x,y]) => {context.fillStyle='#2f9866';context.beginPath();context.arc(x*factor,y*factor,5,0,Math.PI*2);context.fill();});
}
async function loadBlob(blob, name='貼り付けた画像') {
  if (busy) return;
  if (blob.size > 16*1024*1024) throw new Error('画像ファイルは16MB以下にしてください');
  if (!blob.type.startsWith('image/')) throw new Error('画像ファイルを選んでください');
  const data = await new Promise((resolve,reject) => {const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('画像を開けませんでした'));reader.readAsDataURL(blob);});
  const image = await new Promise((resolve,reject) => {const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('対応する画像ファイルを選んでください'));img.src=data;});
  if (image.naturalWidth*image.naturalHeight > 24000000) throw new Error('画像は2400万画素以下にしてください');
  sourceImage=image; imageData=data; bounds=null; clicks=[]; picking=false; $('sample-credit').replaceChildren();
  $('dropzone').hidden=true; $('image-area').hidden=false; $('reset-image').hidden=false;
  $('image-name').textContent=`${name} · ${image.naturalWidth} × ${image.naturalHeight}`;
  $('bounds-status').textContent='Auto';
  draft=null; history=[]; changed.clear(); invalidate();
  $('review-area').hidden=true; $('review-placeholder').hidden=false;
  $('review-count').hidden=true;
  drawSource(); status('');
}
function palette() {
  $('palette').replaceChildren();
  for (const [piece,label] of [...Object.entries(glyphs),[null,'×']]) {
    const button=document.createElement('button');button.textContent=label;
    button.classList.toggle('selected',chosenPiece===piece);
    button.setAttribute('aria-pressed',String(chosenPiece===piece));
    button.setAttribute('aria-label',piece ? `${chosenSide==='b'?'先手':'後手'}の${label}を置く` : 'マスの駒を消す');
    button.onclick=()=>{chosenPiece=piece;palette();};$('palette').append(button);
  }
}
function renderBoard() {
  $('board').replaceChildren();
  const review = new Set(draft.review_squares || []);
  draft.board.forEach((piece,index) => {
    const button = document.createElement('button'), span=document.createElement('span');
    const row=Math.floor(index/9),col=index%9;
    const base = piece && piece !== '?' ? piece.toUpperCase() : null;
    span.textContent = piece === '?' ? '？' : (glyphs[base] || '');
    if (piece && piece !== '?' && piece.slice(-1)===piece.slice(-1).toLowerCase()) span.classList.add('white');
    if (piece?.startsWith('+')) span.classList.add('promoted');
    button.className = 'square'; button.dataset.index=String(index);
    button.classList.toggle('uncertain',review.has(index) || piece === '?');
    button.classList.toggle('changed',changed.has(index));
    const owner = !piece || piece==='?' ? '' : (piece.slice(-1)===piece.slice(-1).toUpperCase() ? '先手の' : '後手の');
    button.setAttribute('aria-label',`${9-col}${row+1} ${owner}${piece==='?'?'不明':glyphs[base]||'空'}${review.has(index)?'、要確認':''}`);
    button.title = `${9-col}${row+1}: ${owner}${piece==='?'?'不明':glyphs[base]||'空'}`;
    button.onfocus = () => {
      const cell = draft.cells?.[index];
      const alternatives = cell?.alternatives?.map(a=>`${glyphs[a.piece.toUpperCase()]}（${a.piece.slice(-1)===a.piece.slice(-1).toUpperCase()?'先手':'後手'}）`).join(' / ');
      $('cell-detail').textContent = `${9-col}${row+1}: ${alternatives ? alternatives : '駒を選んでマスをクリック'}`;
    };
    button.onclick=()=>{
      snapshot();draft.board[index]=chosenPiece ? (chosenSide==='b'?chosenPiece:chosenPiece.toLowerCase()) : null;
      draft.review_squares=(draft.review_squares||[]).filter(i=>i!==index);changed.add(index);
      invalidate();renderBoard();$('board').children[index].focus();
    };
    button.append(span);$('board').append(button);
  });
  const count=draft.review_squares?.length || 0;
  $('review-count').hidden = !count; $('review-count').textContent = `${count} 要確認`;
}
function renderHands() {
  for (const side of ['b','w']) {
    $(`hands-${side}`).replaceChildren();
    handOrder.forEach(piece=>{
      const label=document.createElement('label'), input=document.createElement('input');
      label.textContent=glyphs[piece]; input.type='number';input.min='0';input.max=String(limits[piece]);input.step='1';
      input.value=String(draft.pending_hands?.[side]?.[piece] ?? draft.hands?.[side]?.[piece] ?? 0);input.dataset.piece=piece;
      input.setAttribute('aria-label',`${side==='b'?'先手':'後手'}の${glyphs[piece]}の枚数`);
      input.oninput=()=>{draft.hands ||= {b:null,w:null}; draft.hands[side]={}; draft.default_hands=(draft.default_hands||[]).filter(s=>s!==side); invalidate();};
      label.append(input);$(`hands-${side}`).append(label);
    });
    const hint=document.createElement('p'); hint.className='hint hand-status'; hint.textContent=draft.hands?.[side] == null ? '手入力' : 'OCR';
    const parent=$(`hands-${side}`).parentElement; parent.querySelector('.hand-status')?.remove(); parent.insertBefore(hint,$(`hands-${side}`));
  }
}
function showDraft(value) {
  if (!Array.isArray(value.board) || value.board.length!==81) throw new Error('81マスの盤面データが必要です');
  for (const p of value.board) if(p!==null && p!=='?' && !(typeof p==='string' && glyphs[p.toUpperCase()])) throw new Error('盤面に不正な駒があります');
  draft=value;history=[];changed.clear();$('undo').disabled=true;invalidate();
  $('review-placeholder').hidden=true;$('review-area').hidden=false;
  $('turn').value=draft.turn || 'b';renderBoard();renderHands();palette();
  $('ocr-text').textContent=(draft.ocr_texts || []).join('\n\n') || '—';
  if (draft.board_bounds) {bounds=draft.board_bounds;drawSource();}
}
function currentDraft() {
  const value=structuredClone(draft); value.turn=$('turn').value || 'b'; value.default_turn=!draft.turn || Boolean(draft.default_turn);
  value.hands={b:{},w:{}}; value.pending_hands={b:{},w:{}}; value.default_hands=[];
  for (const side of ['b','w']) {
    const hand={};
    $(`hands-${side}`).querySelectorAll('input').forEach(input=>{
      const n=Number(input.value);
      if (!input.value.trim() || !Number.isInteger(n) || n<0 || n>limits[input.dataset.piece]) throw new Error('持ち駒の枚数を確認してください');
      if(n) hand[input.dataset.piece]=n;
    }); value.pending_hands[side]=hand; value.hands[side]=hand; if((draft.hands?.[side]==null || draft.default_hands?.includes(side)) && !Object.keys(hand).length) value.default_hands.push(side);
  }
  value.reviewed=false;
  return value;
}
function download(text, name, mime='text/plain;charset=utf-8') {
  const url=URL.createObjectURL(new Blob([text],{type:mime})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function showOutput() { $('output-text').value=result[$('output-format').value]; }
bind('image-file','change',async e=>{if(e.target.files[0]) await loadBlob(e.target.files[0],e.target.files[0].name);});
bind('reset-image','click',()=>{$('image-file').value='';$('image-file').click();});
$('dropzone').addEventListener('dragover',e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
$('dropzone').addEventListener('dragleave',()=>{$('dropzone').classList.remove('dragover');});
bind('dropzone','drop',async e=>{e.preventDefault();$('dropzone').classList.remove('dragover');if(e.dataTransfer.files[0])await loadBlob(e.dataTransfer.files[0],e.dataTransfer.files[0].name);});
document.addEventListener('paste',async e=>{const file=[...(e.clipboardData?.items||[])].find(item=>item.type.startsWith('image/'))?.getAsFile();if(file){e.preventDefault();try{await loadBlob(file);}catch(error){status(error.message,true);}}});
bind('select-bounds','click',()=>{picking=true;clicks=[];bounds=null;drawSource();$('bounds-status').textContent='左上 → 右下をクリック';});
bind('auto-bounds','click',()=>{picking=false;clicks=[];bounds=null;drawSource();$('bounds-status').textContent='Auto';});
bind('source-canvas','click',e=>{
  if(!picking)return;const rect=e.target.getBoundingClientRect();
  clicks.push([Math.round((e.clientX-rect.left)/rect.width*sourceImage.naturalWidth),Math.round((e.clientY-rect.top)/rect.height*sourceImage.naturalHeight)]);
  if(clicks.length===2){const [[x1,y1],[x2,y2]]=clicks;bounds=[Math.min(x1,x2),Math.min(y1,y2),Math.max(x1,x2),Math.max(y1,y2)];clicks=[];picking=false;$('bounds-status').textContent='Selected';}drawSource();
});
bind('recognize','click',async()=>{
  if(!imageData)return;if(picking)throw new Error('盤の右下もクリックしてください');
  setBusy(true);status('Reading…');
  try {const value=await api('/api/recognize',{image:imageData,bounds,orientation:$('orientation').value});showDraft(value);status('');}
  finally {setBusy(false);}
});
for(const side of ['b','w'])bind(`side-${side}`,'click',()=>{chosenSide=side;for(const other of ['b','w']){$(`side-${other}`).classList.toggle('selected',other===side);$(`side-${other}`).setAttribute('aria-pressed',String(other===side));}palette();});
bind('undo','click',()=>{const previous=history.pop();if(!previous)return;draft.board=previous.board;draft.review_squares=previous.review_squares;changed=new Set(previous.changed);invalidate();renderBoard();$('undo').disabled=history.length===0;});
bind('turn','change',()=>{draft.turn=$('turn').value || null; draft.default_turn=false; invalidate();});
bind('export','click',async()=>{
  $('export').disabled=true;
  try {result=await api('/api/export',{draft:currentDraft(),preview:true});$('output-area').hidden=false;showOutput();$('output-warnings').textContent=result.warnings.join(' / ');$('output-area').scrollIntoView({behavior:'smooth',block:'start'});status('');}
  finally {updateExport();}
});
bind('output-format','change',showOutput);
bind('copy-output','click',async()=>{try{await navigator.clipboard.writeText($('output-text').value);status('Copied');}catch{$('output-text').focus();$('output-text').select();status('テキストを選択しました。コピーしてください。');}});
bind('download-output','click',()=>{const format=$('output-format').value;download($('output-text').value+($('output-text').value.endsWith('\n')?'':'\n'),`position.${format==='sfen'?'sfen':format}`);});
bind('save-draft','click',()=>download(JSON.stringify(currentDraft(),null,2),'position-draft.json','application/json'));
bind('draft-file','change',async e=>{const file=e.target.files[0];if(!file)return;if(file.size>1024*1024)throw new Error('JSONは1MB以下にしてください');showDraft(JSON.parse(await file.text()));status('');});
bind('import-sfen','click',async()=>{showDraft(await api('/api/import-sfen',{sfen:$('sfen-input').value}));status('');});
bind('blank-board','click',()=>{showDraft({board:Array(81).fill(null),hands:{b:null,w:null},turn:null,cells:[],review_squares:[],move_number:1});status('');});
bind('sample-list','change',async e=>{
  const row=sampleRows.find(s=>s.id===e.target.value);if(!row)return;
  const response=await fetch(window.shogiBackend ? window.shogiBackend.sampleUrl(row) : `/api/sample/${encodeURIComponent(row.id)}`);if(!response.ok)throw new Error('サンプルを開けませんでした');
  await loadBlob(await response.blob(),row.title.replace('File:',''));
  $('sample-credit').replaceChildren();const a=document.createElement('a');a.href=row.source_url;a.target='_blank';a.rel='noreferrer';a.textContent=`Source · ${row.license}`;$('sample-credit').append(a);
});
(async()=>{try{sampleRows=window.shogiBackend ? await window.shogiBackend.samples() : await (await fetch('/api/samples')).json();for(const row of sampleRows){const option=document.createElement('option');option.value=row.id;option.textContent=`${row.title.replace('File:','')} (${row.kind})`;$('sample-list').append(option);}}catch{status('サンプル一覧を開けませんでした。画像ファイルを選択して利用できます。');}})();

document.addEventListener('runtime-status',event=>status(event.detail));
