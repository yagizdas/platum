(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.EInspector = api; api.start(); }
})(typeof globalThis === 'undefined' ? this : globalThis, function() {
  'use strict';
  const GOALS = ['bulk', 'cut', 'budget'], PROFILES = ['all', 'vegan', 'vegetarian', 'no_pork', 'no_beef', 'no_pork_beef'];
  const BALANCES = ['quality', 'balanced', 'variety'];
  function displayPlate(p) {
    const t = p.total;
    return {id:p.candidate_id,items:p.items,price:t.price_eur,kcal:t.kcal,protein:t.protein_g,fat_g:t.fat_g,
      carbs_g:t.carbs_g,weight_g:t.weight_g,dish_count:p.items.length,fat_energy_pct:t.kcal?9*t.fat_g/t.kcal*100:0,
      meat_dish_weight_g:p.items.filter(i=>(i.meat_types||[]).some(x=>!['unknown','fish'].includes(x))).reduce((s,i)=>s+i.weight_g,0),
      unknown_diet_weight_g:p.items.filter(i=>(i.meat_types||[]).includes('unknown')).reduce((s,i)=>s+i.weight_g,0),has_estimated_prices:p.has_estimated_prices};
  }
  function selectedPlates(variant, balance) {
    const byId = new Map(variant.candidates.map(p => [p.candidate_id, p]));
    return variant.balances[balance].selections.map(p => ({...byId.get(p.candidate_id), ...p}));
  }
  function validateDay(data) {
    if (!data || !/^\d{4}-\d{2}-\d{2}$/.test(data.date) || !data.settings?.balances || !data.variants) throw Error('Invalid E ranking data.');
    for (const v of Object.values(data.variants)) {
      if (!Array.isArray(v.candidates) || v.candidates.length > 100 || v.candidates.some((p,i)=>p.preference_rank!==i+1)) throw Error('Invalid E candidate pool.');
      const ids = new Set(v.candidates.map(p=>p.candidate_id));
      if (ids.size !== v.candidates.length) throw Error('Duplicate ranked candidates.');
      for (const key of BALANCES) {
        const s = v.balances?.[key]?.selections;
        if (!Array.isArray(s) || s.length !== Math.min(5,v.candidates.length) || new Set(s.map(p=>p.candidate_id)).size !== s.length || s.some(p=>!ids.has(p.candidate_id))) throw Error('Invalid E selections.');
      }
    }
    return data;
  }
  function start() {
    const $ = id=>document.getElementById(id), query = new URLSearchParams(location.search);
    const element = (tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
    let data, index, requestId=0, previousContext='';
    $('goal').value=GOALS.includes(query.get('goal'))?query.get('goal'):'bulk';
    $('profile').value=PROFILES.includes(query.get('profile'))?query.get('profile'):'all';
    $('balance').value=BALANCES.includes(query.get('balance'))?query.get('balance'):'balanced';
    function card(p,pick) {
      const node=BulkPlateCard.render(displayPlate(p),p.candidate_id,()=>{});
      for(const attr of ['role','tabindex','aria-label'])node.removeAttribute(attr);
      node.querySelector('h2').textContent=`Preference #${p.preference_rank}`;
      node.dataset.picked=String(!!pick);
      node.prepend(element('p','pick-label',pick?`E choice ${pick.mmr.pick}`:'Ranked alternative'));
      if(pick)node.append(element('p','selection-note',pick.reason));
      node.append(element('p','candidate-score',`Original preference score ${p.score.total.toFixed(3)}`));
      return node;
    }
    function current() {return data?.variants[$('goal').value+'_'+$('profile').value];}
    function renderAlternative() {
      const v=current();if(!v)return;
      const p=v.candidates.find(p=>p.candidate_id===$('alternative').value);
      const picked=p&&selectedPlates(v,$('balance').value).find(s=>s.candidate_id===p.candidate_id);
      $('alternative-preview').replaceChildren(...(p?[card(p,picked)]:[]));
    }
    function render() {
      if(!data)return;
      const key=$('goal').value+'_'+$('profile').value,v=data.variants[key];
      if(!v)throw Error('This context has not been generated.');
      const balance=$('balance').value,selection=v.balances[balance],plates=selectedPlates(v,balance);
      $('candidates').replaceChildren(...(plates.length?plates.map(p=>card(p,p)):[element('p','empty',selection.message||'No eligible combinations.')]));
      $('candidates').setAttribute('aria-busy','false');$('selected-count').textContent=String(plates.length);
      $('status').textContent=selection.state==='ready'?`${plates.length} MMR picks from ${v.candidates.length} ranked combinations · ${data.settings.balances[balance].label}. ${selection.message||''}`.trim():selection.message;
      const context=data.date+key,old=previousContext===context?$('alternative').value:'';previousContext=context;
      $('alternative').replaceChildren(new Option('Choose a ranked alternative',''),...v.candidates.map(p=>new Option(`#${p.preference_rank} · ${p.title}`,p.candidate_id)));
      $('alternative').value=v.candidates.some(p=>p.candidate_id===old)?old:'';
      $('alternative').disabled=!v.candidates.length;
      $('alternative-count').textContent=`Browse all ${v.candidates.length} ranked combinations`;
      renderAlternative();
      const lambda=data.settings.balances[balance].lambda;
      $('weights').textContent=`λ = ${lambda.toFixed(2)}. At each step, MMR = λ × bounded quality − (1 − λ) × maximum similarity to an earlier pick. No similarity cutoff applies. Quality scale for this pool: ${(plates[0]?.mmr.quality_scale||1).toFixed(3)} preference-score units.`;
      $('steps').replaceChildren(...selection.steps.map(s=>{
        const li=element('li','',`Choice ${s.pick}: original preference rank #${s.preference_rank}`);
        li.append(element('span','',`${s.quality_term.toFixed(3)} quality contribution − ${s.redundancy_penalty.toFixed(3)} repetition penalty = ${s.value.toFixed(3)} MMR.`));
        if(s.closest_selected_rank)li.append(element('span','',`${(s.max_similarity*100).toFixed(1)}% similarity to the closest earlier pick, at preference rank #${s.closest_selected_rank}.`));
        return li;
      }));
      const params=new URLSearchParams({date:data.date,goal:$('goal').value,profile:$('profile').value,balance});
      history.replaceState(null,'','?'+params);
      const menu=new URL('../../menu.html',document.baseURI);menu.search=new URLSearchParams({...Object.fromEntries(params),campus:'arcisstr',method:'e'});
      $('menu-link').href=menu.href;$('menu-link').hidden=false;
      $('d-link').href='../d/?'+new URLSearchParams({date:data.date,goal:$('goal').value,profile:$('profile').value});$('d-link').hidden=false;
    }
    async function load() {
      const id=++requestId;data=null;$('candidates').setAttribute('aria-busy','true');$('status').textContent='Loading MMR choices…';
      try {
        const day=index.days.find(d=>d.date===$('date').value);
        if(!day||!/^\d{4}-\d{2}-\d{2}\.json$/.test(day.file))throw Error('No ranking is available for this date.');
        const response=await fetch(new URL('./data/'+day.file,document.baseURI));
        if(!response.ok)throw Error(`HTTP ${response.status}`);
        const value=validateDay(await response.json());if(id!==requestId)return;data=value;render();
      } catch(error) {
        if(id!==requestId)return;$('candidates').setAttribute('aria-busy','false');
        $('candidates').replaceChildren(element('p','empty',error.message+' Try another date or reload.'));
        $('status').textContent='E selections unavailable.';$('selected-count').textContent='—';
        $('steps').replaceChildren();$('alternative-preview').replaceChildren();$('alternative').disabled=true;$('alternative-count').textContent='Ranked alternatives unavailable';$('weights').textContent='';$('menu-link').hidden=$('d-link').hidden=true;
      }
    }
    $('date').onchange=load;$('alternative').onchange=renderAlternative;
    for(const id of ['goal','profile','balance'])$(id).onchange=()=>{try{render();}catch(error){$('status').textContent=error.message;}};
    fetch(new URL('./data/index.json',document.baseURI),{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json();}).then(value=>{
      if(value.schema_version!==1||!value.days?.length)throw Error('No generated E ranking data.');index=value;
      const today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Berlin'});
      for(const row of value.days)$('date').append(new Option(new Date(row.date+'T12:00:00Z').toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short',timeZone:'Europe/Berlin'}),row.date));
      $('date').value=value.days.some(d=>d.date===query.get('date'))?query.get('date'):value.days.some(d=>d.date===today)?today:value.days[0].date;
      $('date').disabled=false;return load();
    }).catch(error=>{$('status').textContent=error.message;$('candidates').setAttribute('aria-busy','false');$('candidates').replaceChildren(element('p','empty',error.message));});
  }
  return {GOALS,PROFILES,BALANCES,displayPlate,selectedPlates,validateDay,start};
});
