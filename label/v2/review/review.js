(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else{root.BulkReview=api;api.start();}
})(typeof globalThis==='undefined'?this:globalThis,function(){
  'use strict';
  const EXPERIMENT='bulk-exhaustive-v2-ai-review',BASE='bulk-exhaustive-v2';
  const choices=new Set(['a','b','both_bad']);
  const key=row=>`${row.date}:${row.pair_id}`;
  const label=winner=>winner==='both_bad'?'Both bad':`Plate ${winner.toUpperCase()}`;
  const storageKey=data=>`plato-bulk-v2-ai-review:${data.review_id}`;
  const blank=()=>({position:0,filter:'all',reviews:{},notes:{}});
  const filters=new Set(['all','pending','changed','agreed']);
  function validateSource(data){
    if(data?.schema_version!==1||data.experiment!==EXPERIMENT||!data.review_id||!data.dataset_id||!Array.isArray(data.records)||!data.records.length)throw Error('The AI review data is invalid.');
    const seen=new Set();
    data.records.forEach((row,i)=>{
      if(row.dataset_id!==data.dataset_id||row.case_index!==i+1||row.is_human_judgment!==false||!choices.has(row.winner)||!row.rationale||seen.has(key(row)))throw Error('An AI comparison has invalid provenance.');
      seen.add(key(row));
      for(const side of ['a','b']){
        const p=row['plate_'+side];
        if(!p?.id||!Array.isArray(p.items)||!p.items.length||p.items.length>4||!['kcal','protein','price','fat_g','fat_energy_pct','carbs_g','weight_g','dish_count','meat_dish_weight_g'].every(name=>Number.isFinite(p[name])))throw Error('An AI comparison has missing plate data.');
      }
      if(row.plate_a.id===row.plate_b.id)throw Error('A comparison repeats the same plate.');
    });return data;
  }
  function normalizeState(data,value){
    if(!value||typeof value.reviews!=='object'||!value.reviews||Array.isArray(value.reviews))throw Error('Saved review progress is invalid.');
    const known=new Set(data.records.map(key)),reviews={},notes={};
    for(const [id,entry] of Object.entries(value.reviews)){
      if(!known.has(id)||!entry||!choices.has(entry.winner)||!Number.isFinite(Date.parse(entry.reviewed_at)))throw Error('A saved review is invalid.');
      reviews[id]={winner:entry.winner,reviewed_at:entry.reviewed_at};
    }
    for(const [id,note] of Object.entries(value.notes||{})){
      if(!known.has(id)||typeof note!=='string'||note.length>2000)throw Error('A saved note is invalid.');
      notes[id]=note;
    }
    return {position:Number.isInteger(value.position)&&value.position>=0&&value.position<data.records.length?value.position:0,filter:filters.has(value.filter)?value.filter:'all',reviews,notes};
  }
  function readState(storage,data){const raw=storage.getItem(storageKey(data));return raw?normalizeState(data,JSON.parse(raw)):blank();}
  function setChoice(data,state,winner,note='',now=new Date()){
    if(!choices.has(winner))throw Error('Invalid choice.');
    const id=key(data.records[state.position]);
    return {...state,reviews:{...state.reviews,[id]:{winner,reviewed_at:now.toISOString()}},notes:{...state.notes,[id]:String(note).slice(0,2000)}};
  }
  function unreview(data,state){const reviews={...state.reviews};delete reviews[key(data.records[state.position])];return {...state,reviews};}
  function visibleIndices(data,state){
    return data.records.flatMap((row,i)=>{
      const review=state.reviews[key(row)],matches=state.filter==='all'||state.filter==='pending'&&!review||state.filter==='changed'&&review&&review.winner!==row.winner||state.filter==='agreed'&&review&&review.winner===row.winner;
      return matches?[i]:[];
    });
  }
  function counts(data,state){
    const reviewed=data.records.filter(row=>state.reviews[key(row)]),changed=reviewed.filter(row=>state.reviews[key(row)].winner!==row.winner);
    return {reviewed:reviewed.length,changed:changed.length,agreed:reviewed.length-changed.length,pending:data.records.length-reviewed.length};
  }
  function reviewedRecord(row,review,note){
    const result=structuredClone(row),winner=review.winner;
    delete result.rationale;
    return {...result,timestamp:review.reviewed_at,winner,preference:winner==='both_bad'?null:winner,
      acceptable_a:winner==='both_bad'?false:winner==='a'?true:null,
      acceptable_b:winner==='both_bad'?false:winner==='b'?true:null,
      annotation_source:'human_review_of_ai',is_human_judgment:true,annotator:'human_reviewer',
      user_note:note||'',ai_original:{winner:row.winner,rationale:row.rationale,timestamp:row.timestamp,annotator:row.annotator},
      review:{status:winner===row.winner?'confirmed':'corrected',reviewed_at:review.reviewed_at}};
  }
  function exportReviews(data,state,{audit=false}={}){
    const records=data.records.flatMap(row=>{
      const review=state.reviews[key(row)];
      if(review)return [reviewedRecord(row,review,state.notes[key(row)])];
      return audit?[{...structuredClone(row),review:{status:'unreviewed'},user_note:state.notes[key(row)]||''}]:[];
    });
    return {schema_version:2,experiment:BASE,review_experiment:EXPERIMENT,review_id:data.review_id,dataset_id:data.dataset_id,campus:'arcisstr',goal:'bulk',exported_at:new Date().toISOString(),annotation_source:audit?'mixed_ai_and_human_review':'human_review_of_ai',is_human_judgment:audit?null:true,review_summary:counts(data,state),resume_case:state.position+1,records};
  }
  function mergeBackup(data,state,value){
    if(value?.schema_version!==2||value.experiment!==BASE||value.review_experiment!==EXPERIMENT||value.review_id!==data.review_id||value.dataset_id!==data.dataset_id||!Array.isArray(value.records))throw Error('Choose an exported review file from these 150 cases.');
    const original=new Map(data.records.map(row=>[key(row),row])),reviews={...state.reviews},notes={...state.notes};
    for(const row of value.records){
      const id=key(row),source=original.get(id);
      if(!source||row.plate_a?.id!==source.plate_a.id||row.plate_b?.id!==source.plate_b.id)throw Error('A backup comparison does not match the original plates.');
      if(row.is_human_judgment===false&&row.review?.status==='unreviewed')continue;
      if(row.is_human_judgment!==true||row.annotation_source!=='human_review_of_ai'||!choices.has(row.winner)||row.ai_original?.winner!==source.winner||!Number.isFinite(Date.parse(row.timestamp))||typeof row.user_note!=='string'||row.user_note.length>2000)throw Error('A backup review has invalid provenance.');
      if(!reviews[id]||Date.parse(row.timestamp)>Date.parse(reviews[id].reviewed_at)){reviews[id]={winner:row.winner,reviewed_at:row.timestamp};notes[id]=row.user_note;}
    }
    return normalizeState(data,{...state,reviews,notes});
  }
  function start(){
    const $=id=>document.getElementById(id);let data,state=blank(),ready=false,noteTimer=null;
    const element=(tag,className,text)=>{const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;};
    const notice=message=>{$('notice').textContent=message;$('notice').hidden=!message;};
    const status=message=>{$('status').textContent=message;};
    const current=()=>data.records[state.position];
    const updateUrl=()=>{const url=new URL(location.href);url.searchParams.set('case',state.position+1);history.replaceState(null,'',url);};
    const persist=next=>{try{localStorage.setItem(storageKey(data),JSON.stringify(next));state=next;notice('');return true;}catch{notice('This browser could not save the review. Your previous choices are kept. Export them before trying another browser.');return false;}};
    function controls(){
      const tally=counts(data,state),row=current(),review=state.reviews[key(row)],visible=visibleIndices(data,state);
      $('review-count').textContent=`${tally.reviewed} / ${data.records.length}`;$('summary-counts').textContent=`${tally.agreed} agreed · ${tally.changed} changed · ${tally.pending} still to review. Reviews stay in this browser.`;
      $('case-number').value=state.position+1;$('case-number').max=data.records.length;$('case-total').textContent=`of ${data.records.length}`;$('filter').value=state.filter;
      $('previous').disabled=!visible.some(i=>i<state.position);$('next').disabled=!visible.some(i=>i>state.position);
      $('unreview').disabled=!review;$('export').disabled=!tally.reviewed;
      $('your-choice').textContent=review?`Your choice: ${label(review.winner)} · ${review.winner===row.winner?'Agreed':'Changed'}`:'Your review: pending';
      for(const [id,winner] of [['choose-a','a'],['choose-b','b'],['both-bad','both_bad']])$(id).setAttribute('aria-pressed',String(review?.winner===winner));
      document.querySelectorAll('.plate').forEach(card=>card.dataset.humanChoice=String(review?.winner===card.dataset.choice));
      $('agree-next').textContent=tally.pending?'Agree & next':'Keep AI choice';
      $('browse-summary').textContent=`Browse cases · ${visible.length} ${state.filter==='all'?'total':$('filter').selectedOptions[0].textContent.toLowerCase()}`;
      const grid=visible.map(i=>{const source=data.records[i],choice=state.reviews[key(source)],button=element('button','',String(i+1));button.type='button';button.dataset.case=String(i+1);button.dataset.reviewed=String(!!choice);button.setAttribute('aria-current',String(i===state.position));button.setAttribute('aria-label',`Case ${i+1}: ${choice?'reviewed, your choice':'AI suggests'} ${label(choice?.winner||source.winner)}`);button.append(element('span','',choice?.winner==='both_bad'||!choice&&source.winner==='both_bad'?'Neither':(choice?.winner||source.winner).toUpperCase()));button.onclick=()=>go(i);return button;});
      $('case-grid').replaceChildren(...(grid.length?grid:[element('p','empty-filter','No cases match this view yet. Choose All cases to browse everything.')]));
    }
    function draw(){
      const row=current(),review=state.reviews[key(row)];
      const cards=['a','b'].map(side=>{
        const card=BulkPlateCard.render(row['plate_'+side],side,choose);
        const marker=element('p','choice-marker',row.winner===side?'AI pick':row.winner==='both_bad'?'AI rejected both':'Alternative');
        if(review?.winner===side)marker.append(element('strong','',' · Your choice'));
        card.prepend(marker);return card;
      });
      $('pair').replaceChildren(...cards);$('pair').setAttribute('aria-busy','false');$('ai-choice').textContent=`AI originally chose: ${label(row.winner)}`;$('reason').textContent=row.rationale;
      const date=new Date(row.date+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'Europe/Berlin'});
      $('scope').textContent=`Arcisstraße · ${date} · estimated nutrition and scoop weights`;
      const flags=row.data_quality_flags||[];$('quality-notes').hidden=!flags.length;$('quality-notes').open=false;$('quality-list').replaceChildren(...flags.map(flag=>element('li','',`${flag.dish_name}: ${flag.issue}`)));
      $('note').value=state.notes[key(row)]||'';controls();
    }
    function saveNote(){
      clearTimeout(noteTimer);noteTimer=null;if(!ready)return true;
      const id=key(current()),note=$('note').value.slice(0,2000);
      if(note===(state.notes[id]||''))return true;
      const next={...state,notes:{...state.notes,[id]:note},reviews:{...state.reviews}};
      if(next.reviews[id])next.reviews[id]={...next.reviews[id],reviewed_at:new Date().toISOString()};
      if(!persist(next))return false;status('Note saved.');return true;
    }
    function go(position,resetFilter=false){
      if(!ready||position<0||position>=data.records.length||!saveNote())return;
      if(persist({...state,position,filter:resetFilter?'all':state.filter})){draw();updateUrl();window.scrollTo({top:0,behavior:'instant'});}
    }
    function choose(winner){
      if(!ready)return false;clearTimeout(noteTimer);noteTimer=null;
      if(!persist(setChoice(data,state,winner,$('note').value)))return false;
      draw();status(`Saved your choice: ${label(winner)}. You can switch it again or move to the next case.`);return true;
    }
    function navigate(direction){const visible=visibleIndices(data,state),target=direction>0?visible.find(i=>i>state.position):visible.findLast(i=>i<state.position);if(target!==undefined)go(target);}
    $('choose-a').onclick=()=>choose('a');$('choose-b').onclick=()=>choose('b');$('both-bad').onclick=()=>choose('both_bad');
    $('agree-next').onclick=()=>{
      if(!ready||!choose(current().winner))return;
      const pending=data.records.flatMap((row,i)=>!state.reviews[key(row)]?[i]:[]),target=pending.find(i=>i>state.position)??pending[0];
      if(target!==undefined)go(target);
      status(pending.length?'Agreed and saved. Here is the next unreviewed case.':'All 150 cases reviewed. Export reviews to keep your decisions.');
    };
    $('previous').onclick=()=>navigate(-1);$('next').onclick=()=>navigate(1);
    $('case-number').onchange=()=>{const value=Number($('case-number').value);if(Number.isInteger(value)&&value>=1&&value<=data.records.length)go(value-1,!visibleIndices(data,state).includes(value-1));else $('case-number').value=state.position+1;};
    $('filter').onchange=()=>{if(!saveNote())return;const next={...state,filter:$('filter').value},visible=visibleIndices(data,next);if(visible.length&&!visible.includes(next.position))next.position=visible[0];if(persist(next)){draw();updateUrl();}};
    $('note').oninput=()=>{clearTimeout(noteTimer);noteTimer=setTimeout(saveNote,250);};$('note').onchange=saveNote;
    $('unreview').onclick=()=>{if(saveNote()&&persist(unreview(data,state))){draw();status('Marked unreviewed. The original AI suggestion is kept.');}};
    const download=audit=>{if(!saveNote())return;const value=exportReviews(data,state,{audit}),url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=`plato-bulk-v2-${audit?'full-audit':'human-reviews'}-${data.review_id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status(audit?'Full audit exported with AI and human provenance.':'Your reviewed decisions exported. Unreviewed AI picks are excluded.');};
    $('export').onclick=()=>download(false);$('export-audit').onclick=()=>download(true);$('restore').onclick=()=>$('restore-file').click();
    $('restore-file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>30*1024*1024)throw Error('This backup is too large.');const next=mergeBackup(data,state,JSON.parse(await file.text()));if(persist(next)){ready=true;enable();draw();status('Reviews restored. Duplicate cases were merged using the latest review.');}}catch(error){notice(error.message);}finally{event.target.value='';}};
    function enable(){for(const id of ['choose-a','choose-b','both-bad','agree-next','note','case-number','filter','restore','export-audit'])$(id).disabled=false;}
    document.addEventListener('keydown',event=>{
      if(!ready||event.repeat||event.ctrlKey||event.altKey||event.metaKey||event.target.matches('input,select,textarea,summary'))return;
      if(event.key==='ArrowLeft'){event.preventDefault();choose('a');}else if(event.key==='ArrowRight'){event.preventDefault();choose('b');}else if(event.key==='ArrowDown'){event.preventDefault();choose('both_bad');}else if(event.key==='Enter'&&!event.target.closest('button,a,[role="button"]')){event.preventDefault();$('agree-next').click();}
    });
    window.addEventListener('storage',event=>{if(data&&event.key===storageKey(data)){try{state=readState(localStorage,data);ready=true;enable();draw();status('Reviews updated from your other tab.');}catch(error){notice(error.message);}}});
    fetch(new URL('./data.json',document.baseURI),{cache:'no-cache'}).then(response=>{if(!response.ok)throw Error(`Could not load AI picks (HTTP ${response.status}).`);return response.json();}).then(value=>{
      data=validateSource(value);$('restore').disabled=false;
      try{state=readState(localStorage,data);}catch{notice('Saved reviews could not be read. Restore an exported review file to protect your existing choices.');return;}
      const requested=Number(new URL(location.href).searchParams.get('case'));if(Number.isInteger(requested)&&requested>=1&&requested<=data.records.length)state.position=requested-1;
      ready=true;enable();draw();status('A smaller plate is not automatically a good Bulk lunch. Choose Both bad when neither fits.');
    }).catch(error=>{$('pair').setAttribute('aria-busy','false');$('pair').replaceChildren(element('p','empty',error.message+' Reload to try again.'));notice(error.message);});
  }
  return {EXPERIMENT,BASE,key,label,storageKey,blank,validateSource,normalizeState,readState,setChoice,unreview,visibleIndices,counts,reviewedRecord,exportReviews,mergeBackup,start};
});
