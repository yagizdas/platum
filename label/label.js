(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api; else {root.Labeler=api;api.start();}
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const KEY='platum-pairwise-judgments-v1',TARGET=150;
  function read(storage){try{const value=JSON.parse(storage.getItem(KEY)||'[]');return Array.isArray(value)?value:[];}catch(_){return [];}}
  function allPlates(data,goal){return data.days.flatMap(day=>(day.goals[goal]||[]).map(plate=>({...plate,menu_date:day.date})));}
  function twoFrom(values,random){if(values.length<2)return [];const first=Math.floor(random()*values.length),offset=1+Math.floor(random()*(values.length-1));return [values[first],values[(first+offset)%values.length]];}
  function selectPair(data,goal,random=Math.random){
    const days=data.days.filter(day=>(day.goals[goal]||[]).length>1);if(!days.length)return [];
    const useTop=random()<.7,day=days[Math.floor(random()*days.length)],pool=useTop?day.goals[goal].slice(0,15):day.goals[goal];
    return twoFrom(pool.map(plate=>({...plate,menu_date:day.date})),random);
  }
  function plateFeatures(plate){const {id,title,dishes,kcal,protein,price,score,menu_date}=plate;return {id,title,dishes:[...dishes],kcal,protein,price,score,menu_date};}
  function judgment(goal,pair,winner,now=new Date()){return {timestamp:now.toISOString(),date:pair[0].menu_date===pair[1].menu_date?pair[0].menu_date:null,goal,plate_a:plateFeatures(pair[0]),plate_b:plateFeatures(pair[1]),winner};}
  function start(){
    const $=id=>document.getElementById(id),goal=$('goal'),pairNode=$('pair'),status=$('status'),count=$('count'),undo=$('undo');let data,pair=[];
    const records=()=>read(localStorage),updateCount=()=>{const total=records().length;count.textContent=String(total);undo.disabled=!total;};
    const metric=(value,label)=>`<div class="metric"><strong>${value}</strong><span>${label}</span></div>`;
    const draw=()=>{pairNode.replaceChildren(...pair.map((plate,index)=>{const button=document.createElement('button');button.type='button';button.className='plate';button.dataset.choice=String(index);button.setAttribute('aria-label',`Choose ${plate.title}`);const dishes=document.createElement('ul');dishes.className='dishes';for(const name of plate.dishes){const item=document.createElement('li');item.textContent=name;dishes.append(item);}button.innerHTML=`<span class="choice-key">${index?'→ RIGHT':'← LEFT'}</span><span class="date">${plate.menu_date}</span><h2></h2>`;button.querySelector('h2').textContent=plate.title;button.append(dishes);const metrics=document.createElement('div');metrics.className='metrics';metrics.innerHTML=metric(`€${plate.price.toFixed(2)}`,'student price')+metric(Math.round(plate.kcal),'kcal')+metric(`${plate.protein.toFixed(1)} g`,'protein');button.append(metrics);return button;}));};
    const next=()=>{pair=selectPair(data,goal.value);draw();};
    const save=winner=>{if(pair.length!==2)return;const values=records();values.push(judgment(goal.value,pair,winner));localStorage.setItem(KEY,JSON.stringify(values));status.textContent=winner==='both_bad'?'Skipped — both marked bad.':'Judgment saved.';updateCount();next();};
    pairNode.addEventListener('click',event=>{const choice=event.target.closest('[data-choice]');if(choice)save(Number(choice.dataset.choice)===0?'a':'b');});$('skip').onclick=()=>save('both_bad');
    undo.onclick=()=>{const values=records();if(!values.length)return;values.pop();localStorage.setItem(KEY,JSON.stringify(values));status.textContent='Last judgment removed.';updateCount();};
    goal.onchange=()=>{status.textContent='';next();};document.addEventListener('keydown',event=>{if(event.target.matches('select,input,textarea'))return;if(event.key==='ArrowLeft'){event.preventDefault();save('a');}else if(event.key==='ArrowRight'){event.preventDefault();save('b');}else if(event.key==='ArrowDown'){event.preventDefault();save('both_bad');}else if(event.key.toLowerCase()==='u')undo.click();});
    $('export').onclick=()=>{const blob=new Blob([JSON.stringify(records(),null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='platum-pairwise-judgments.json';a.click();URL.revokeObjectURL(a.href);};
    fetch('data.json').then(response=>{if(!response.ok)throw Error(response.status);return response.json();}).then(value=>{data=value;updateCount();next();}).catch(()=>status.textContent='Could not load candidate plates.');
  }
  return {KEY,TARGET,read,allPlates,selectPair,plateFeatures,judgment,start};
});
