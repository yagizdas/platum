(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api;
  else {root.BulkLabelerV2=api;api.start();}
})(typeof globalThis==='undefined'?this:globalThis,function(){
  'use strict';
  const VERSION=2,EXPERIMENT='bulk-exhaustive-v2';
  const refKey=ref=>`${ref.date}:${ref.pair_id}`;
  const storageKey=data=>`plato-bulk-labeler-v2:${data.dataset_id}`;
  const blank=()=>({records:[],deferred:[],resume:null});
  const dataUrl=base=>new URL('./data.json',base).href;
  function indexData(data){
    if(data?.schema_version!==VERSION||data.experiment!==EXPERIMENT||!data.dataset_id||!Array.isArray(data.days)||!Array.isArray(data.queue)||!data.queue.length) throw Error('This labeling dataset is invalid.');
    const index=new Map();
    for(const day of data.days){
      const plates=new Map(day.plates.map(p=>[p.id,p]));
      for(const pair of day.pairs){
        const a=plates.get(pair.a),b=plates.get(pair.b),ref={date:day.date,pair_id:pair.id};
        if(!a||!b||a.id===b.id) throw Error('A comparison has missing plates.');
        index.set(refKey(ref),{ref,pair,a,b});
      }
    }
    const keys=data.queue.map(refKey);
    if(new Set(keys).size!==keys.length||keys.some(key=>!index.has(key))) throw Error('The comparison queue is invalid.');
    return index;
  }
  function makeRecord(data,index,ref,winner,now=new Date()){
    if(!['a','b','both_bad'].includes(winner)) throw Error('Invalid choice.');
    const value=index.get(refKey(ref));if(!value) throw Error('Unknown comparison.');
    return {schema_version:VERSION,experiment:EXPERIMENT,dataset_id:data.dataset_id,
      timestamp:now.toISOString(),date:ref.date,pair_id:ref.pair_id,campus:'arcisstr',goal:'bulk',strategy:value.pair.strategy,
      winner,preference:winner==='both_bad'?null:winner,
      acceptable_a:winner==='both_bad'?false:winner==='a'?true:null,
      acceptable_b:winner==='both_bad'?false:winner==='b'?true:null,
      plate_a:structuredClone(value.a),plate_b:structuredClone(value.b)};
  }
  function restoreRecords(data,index,records){
    if(!Array.isArray(records)) throw Error('The backup has no choices.');
    const found=new Map();
    for(const row of records){
      const ref={date:row.date,pair_id:row.pair_id},value=index.get(refKey(ref));
      if(row.dataset_id!==data.dataset_id||row.experiment!==EXPERIMENT||!value||row.plate_a?.id!==value.a.id||row.plate_b?.id!==value.b.id||!Number.isFinite(Date.parse(row.timestamp))) throw Error('This backup does not match these Bulk v2 comparisons.');
      found.set(refKey(ref),makeRecord(data,index,ref,row.winner,new Date(row.timestamp)));
    }
    return [...found.values()];
  }
  function readState(storage,data,index){
    const raw=storage.getItem(storageKey(data));if(!raw)return blank();
    const value=JSON.parse(raw),records=restoreRecords(data,index,value.records);
    return {records,deferred:Array.isArray(value.deferred)?[...new Set(value.deferred.filter(key=>index.has(key)))]:[],resume:index.has(value.resume)?value.resume:null};
  }
  function storageState(state){
    // Keep browser storage small; the frozen dataset restores full snapshots for export.
    return {...state,records:state.records.map(row=>({...row,plate_a:{id:row.plate_a.id},plate_b:{id:row.plate_b.id}}))};
  }
  function nextRef(data,state){
    const done=new Set(state.records.map(refKey)),pending=data.queue.filter(ref=>!done.has(refKey(ref)));
    if(!pending.length)return null;
    const resumed=pending.find(ref=>refKey(ref)===state.resume);if(resumed)return resumed;
    const deferred=new Set(state.deferred),fresh=pending.find(ref=>!deferred.has(refKey(ref)));if(fresh)return fresh;
    return state.deferred.map(key=>pending.find(ref=>refKey(ref)===key)).find(Boolean)||pending[0];
  }
  function applyChoice(state,record){
    const key=refKey(record);
    return {records:[...state.records.filter(row=>refKey(row)!==key),record],deferred:state.deferred.filter(value=>value!==key),resume:null};
  }
  function undo(state){
    if(!state.records.length)return state;
    const last=state.records.at(-1),key=refKey(last);
    return {records:state.records.slice(0,-1),deferred:state.deferred.filter(value=>value!==key),resume:key};
  }
  function defer(state,ref){const key=refKey(ref);return {...state,deferred:[...state.deferred.filter(value=>value!==key),key],resume:null};}
  function backup(data,state){return {schema_version:VERSION,experiment:EXPERIMENT,dataset_id:data.dataset_id,campus:'arcisstr',goal:'bulk',exported_at:new Date().toISOString(),records:state.records};}
  function mergeBackup(data,index,state,value){
    if(value?.review_experiment||(Array.isArray(value?.records)&&value.records.some(row=>row.is_human_judgment===false||row.annotation_source==='ai_proxy'))) throw Error('Restore AI review files on the AI review page to keep their provenance separate.');
    if(value?.schema_version!==VERSION||value.experiment!==EXPERIMENT||value.dataset_id!==data.dataset_id) throw Error('Choose a backup from this Bulk v2 dataset.');
    const imported=restoreRecords(data,index,value.records),merged=new Map(state.records.map(row=>[refKey(row),row]));
    for(const row of imported){const key=refKey(row),old=merged.get(key);if(!old||row.timestamp>old.timestamp)merged.set(key,row);}
    return {...state,records:[...merged.values()].sort((a,b)=>a.timestamp.localeCompare(b.timestamp)),resume:null};
  }
  function start(){
    const $=id=>document.getElementById(id);let data,index,state=blank(),ref=null,busy=false;
    const notice=message=>{$('notice').hidden=!message;$('notice').textContent=message;};
    const persist=next=>{try{localStorage.setItem(storageKey(data),JSON.stringify(storageState(next)));state=next;notice('');return true;}catch{notice('This browser could not save your choice. Nothing was advanced. Free some browser storage or try again; export a backup of your saved choices first.');return false;}};
    const updateCount=()=>{
      $('count').textContent=state.records.length.toLocaleString();
      $('remaining').textContent=`${state.records.length.toLocaleString()} of ${data.queue.length.toLocaleString()} comparisons labeled. You can stop and resume at any time.`;
      $('undo').disabled=!state.records.length;$('export').disabled=!state.records.length;
    };
    const element=(tag,className,text)=>{const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;};
    const drawPlate=(plate,side)=>BulkPlateCard.render(plate,side,save);
    function draw(){
      ref=nextRef(data,state);updateCount();$('pair').setAttribute('aria-busy','false');
      for(const id of ['choose-a','choose-b','both-bad','pass'])$(id).disabled=!ref;
      if(!ref){const box=element('div','empty');box.append(element('h2','','All comparisons labeled.'),element('p','','Thanks. Export a backup to keep your choices ready for training. You can use Undo to revisit your last choice.'));$('pair').replaceChildren(box);$('scope').textContent='Arcisstraße · Bulk v2';return;}
      const pair=index.get(refKey(ref));$('pair').replaceChildren(drawPlate(pair.a,'a'),drawPlate(pair.b,'b'));
      const date=new Date(ref.date+'T12:00:00Z').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short',year:'numeric',timeZone:'Europe/Berlin'});
      $('scope').textContent=`Arcisstraße · ${date} · estimated nutrition`;
    }
    function save(winner){
      if(!ref||busy)return;busy=true;
      const next=applyChoice(state,makeRecord(data,index,ref,winner));
      if(persist(next)){draw();$('status').textContent=winner==='both_bad'?'Saved: both plates rejected.':`Saved: plate ${winner.toUpperCase()} preferred.`;window.scrollTo({top:0,behavior:'instant'});}
      busy=false;
    }
    $('choose-a').onclick=()=>save('a');$('choose-b').onclick=()=>save('b');$('both-bad').onclick=()=>save('both_bad');
    $('undo').onclick=()=>{if(persist(undo(state))){draw();$('status').textContent='Last choice removed. Here is that comparison again.';window.scrollTo({top:0,behavior:'instant'});}};
    $('pass').onclick=()=>{if(ref&&persist(defer(state,ref))){draw();$('status').textContent='Skipped for now. This comparison will return after the others.';window.scrollTo({top:0,behavior:'instant'});}};
    $('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(backup(data,state),null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=`plato-bulk-v2-${data.dataset_id}-judgments.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('status').textContent='Backup downloaded. It includes your preferences and both-bad choices.';};
    $('import').onclick=()=>$('import-file').click();
    $('import-file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>30*1024*1024)throw Error('This backup is too large.');const value=JSON.parse(await file.text()),next=mergeBackup(data,index,state,value);if(persist(next)){draw();$('status').textContent=`Backup restored. ${state.records.length} choices saved; duplicate comparisons merged.`;}}catch(error){notice(error.message);}finally{event.target.value='';}};
    document.addEventListener('keydown',event=>{
      if(event.repeat||event.altKey||event.ctrlKey||event.metaKey||event.target.matches('input,select,textarea,summary')||!data)return;
      if(event.key==='ArrowLeft'){event.preventDefault();save('a');}else if(event.key==='ArrowRight'){event.preventDefault();save('b');}else if(event.key==='ArrowDown'){event.preventDefault();save('both_bad');}else if(event.key.toLowerCase()==='u'&&!$('undo').disabled){event.preventDefault();$('undo').click();}
    });
    window.addEventListener('storage',event=>{if(data&&event.key===storageKey(data)){try{state=readState(localStorage,data,index);draw();$('status').textContent='Progress updated from your other tab.';}catch(error){notice(error.message);}}});
    fetch(dataUrl(document.baseURI),{cache:'no-cache'}).then(response=>{if(!response.ok)throw Error(`Could not load comparisons (HTTP ${response.status}).`);return response.json();}).then(value=>{
      index=indexData(value);data=value;
      try{state=readState(localStorage,data,index);}catch{notice('Saved progress could not be read. Labeling is paused to protect existing choices. Restore an exported backup to continue.');$('import').disabled=false;return;}
      $('import').disabled=false;draw();
    }).catch(error=>{$('pair').setAttribute('aria-busy','false');$('pair').replaceChildren(element('p','empty',error.message+' Reload to try again.'));$('scope').textContent='Comparisons unavailable';});
  }
  return {VERSION,EXPERIMENT,refKey,storageKey,blank,dataUrl,indexData,makeRecord,restoreRecords,readState,storageState,nextRef,applyChoice,undo,defer,backup,mergeBackup,start};
});
