(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api; else { root.Labeler=api; api.start(); }
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const KEY='platum-preference-rankings-v1';
  function read(storage){try{const value=JSON.parse(storage.getItem(KEY)||'[]');return Array.isArray(value)?value:[];}catch(_){return [];}}
  // A stable seed keeps a screen intact across visits, while each day/goal gets a different sample.
  function hash(text){let h=2166136261;for(const char of text){h^=char.charCodeAt(0);h=Math.imul(h,16777619);}return h>>>0;}
  function sample(plates,key){
    if(plates.length<=5) return plates.slice();
    const count=4+(hash(key)%2), topCount=Math.round(count*.7), top=plates.slice(0,topCount), rest=plates.slice(topCount);
    let seed=hash(key+'-random');
    for(let i=rest.length-1;i>0;i--){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const j=seed%(i+1);[rest[i],rest[j]]=[rest[j],rest[i]];}
    return top.concat(rest.slice(0,count-topCount));
  }
  function snapshot(date,goal,plates,now=new Date()){
    return {timestamp:now.toISOString(),menu_date:date,goal,ranking:plates.map(p=>p.id),plates:plates.map(({id,title,dishes,kcal,protein,price})=>({id,title,dishes,kcal,protein,price}))};
  }
  function start(){
    const $=id=>document.getElementById(id), date=$('date'),goal=$('goal'),list=$('plates'),status=$('status');let data,current=[];
    const render=()=>{const day=data.days.find(d=>d.date===date.value);current=sample(day.goals[goal.value],date.value+'|'+goal.value);const saved=read(localStorage).findLast?.(r=>r.menu_date===date.value&&r.goal===goal.value);if(saved){const rank=new Map(saved.ranking.map((id,i)=>[id,i]));current.sort((a,b)=>(rank.get(a.id)??99)-(rank.get(b.id)??99));}draw();};
    const draw=()=>{list.replaceChildren(...current.map((plate,index)=>{const li=document.createElement('li');li.className='plate';li.draggable=true;li.dataset.id=plate.id;li.innerHTML=`<div><h2>${plate.title}</h2><p>${plate.dishes.join(' · ')}</p><p class="metrics">${Math.round(plate.kcal)} kcal · ${plate.protein.toFixed(1)} g protein · €${plate.price.toFixed(2)}</p></div><div class="moves"><button aria-label="Move ${plate.title} up" data-move="-1">↑</button><button aria-label="Move ${plate.title} down" data-move="1">↓</button></div>`;return li;}));};
    list.addEventListener('click',e=>{const move=Number(e.target.dataset.move);if(!move)return;const li=e.target.closest('li'),from=current.findIndex(p=>p.id===li.dataset.id),to=Math.max(0,Math.min(current.length-1,from+move));current.splice(to,0,current.splice(from,1)[0]);draw();});
    let dragged=null;list.addEventListener('dragstart',e=>{dragged=e.target.closest('li');dragged.classList.add('dragging');});list.addEventListener('dragend',()=>{dragged?.classList.remove('dragging');dragged=null;});list.addEventListener('dragover',e=>{e.preventDefault();const target=e.target.closest('li');if(!dragged||!target||target===dragged)return;const from=current.findIndex(p=>p.id===dragged.dataset.id),to=current.findIndex(p=>p.id===target.dataset.id);current.splice(to,0,current.splice(from,1)[0]);draw();dragged=list.children[to];dragged.classList.add('dragging');});
    let touchId=null;list.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;touchId=e.target.closest('li')?.dataset.id;});list.addEventListener('pointermove',e=>{if(!touchId)return;const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('li');if(!target||target.dataset.id===touchId)return;const from=current.findIndex(p=>p.id===touchId),to=current.findIndex(p=>p.id===target.dataset.id);current.splice(to,0,current.splice(from,1)[0]);draw();});list.addEventListener('pointerup',()=>touchId=null);
    $('save').onclick=()=>{const records=read(localStorage);records.push(snapshot(date.value,goal.value,current));localStorage.setItem(KEY,JSON.stringify(records));status.textContent='Ranking saved on this device.';};
    $('export').onclick=()=>{const blob=new Blob([JSON.stringify(read(localStorage),null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='platum-rankings.json';a.click();URL.revokeObjectURL(a.href);};
    fetch('data.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json();}).then(value=>{data=value;for(const day of data.days){const option=document.createElement('option');option.value=option.textContent=day.date;date.append(option);}date.value=data.days.at(-1).date;date.onchange=goal.onchange=render;render();}).catch(()=>status.textContent='Could not load candidate plates.');
  }
  return {KEY,read,sample,snapshot,start};
});
