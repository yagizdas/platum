(function(root,factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.FontTrial=api;
})(typeof globalThis!=='undefined'?globalThis:this,function() {
  'use strict';
  // Flip this one flag (or remove this script tag) when the font trial ends.
  const ENABLED=true;
  const STORAGE_KEY='mensa-plate-font-trial';
  const choices=[
    {id:'jakarta',label:'Plus Jakarta Sans'},
    {id:'dm-sans',label:'DM Sans'},
    {id:'bricolage-dm',label:'Bricolage + DM Sans'},
    {id:'fraunces-figtree',label:'Fraunces + Figtree'},
    {id:'instrument',label:'Instrument Serif + Sans'},
    {id:'current',label:'Current font'},
  ];
  function nextChoice(current) {
    const index=choices.findIndex(choice=>choice.id===current);
    return choices[(index+1+choices.length)%choices.length];
  }
  function init(doc=document,storage=localStorage) {
    if(!ENABLED) return;
    let current;
    try {current=storage.getItem(STORAGE_KEY);} catch(_) {}
    if(!choices.some(choice=>choice.id===current)) current=choices[0].id;
    const button=doc.createElement('button');
    button.type='button';button.className='font-trial';
    const sample=doc.createElement('span');sample.className='font-trial-sample';sample.textContent='Aa';sample.setAttribute('aria-hidden','true');
    const name=doc.createElement('span');name.className='font-trial-name';
    button.append(sample,name);doc.body.append(button);
    function apply(id) {
      current=id;doc.documentElement.dataset.fontTrial=id;
      const choice=choices.find(item=>item.id===id);
      name.textContent=choice.label;button.title='Try next font';button.setAttribute('aria-label','Current font: '+choice.label+'. Try next font.');
      try {storage.setItem(STORAGE_KEY,id);} catch(_) {}
    }
    button.addEventListener('click',()=>apply(nextChoice(current).id));
    apply(current);
    return button;
  }
  return {ENABLED,STORAGE_KEY,choices,nextChoice,init};
});
