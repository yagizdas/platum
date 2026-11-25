(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;else root.BulkPlateCard=api;
})(typeof globalThis==='undefined'?this:globalThis,function(){
  'use strict';
  const element=(tag,className,text)=>{const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;};
  function render(plate,side,onChoose){
      const card=element('article','plate');card.tabIndex=0;card.dataset.choice=side;card.setAttribute('role','button');card.setAttribute('aria-label',`Choose plate ${side.toUpperCase()}`);
      const top=element('div','plate-top');top.append(element('h2','',`Plate ${side.toUpperCase()}`),element('span','plate-size',`${plate.dish_count} ${plate.dish_count===1?'dish':'dishes'} · ${plate.weight_g.toLocaleString()} g total`));card.append(top);
      const art=element('div','plate-art dish-scene');art.setAttribute('aria-hidden','true');DishIcons.compose(art,plate.items,{fallback:'tray',maxItems:4});card.append(art);
      const list=element('ul','dish-rows');
      for(const item of plate.items){
        const row=element('li'),name=element('span','dish-name',item.name_en||item.name);
        name.title=item.name;
        const portion=element('span','portion',`${item.weight_g.toLocaleString()} g`);portion.append(element('small','',item.unit==='piece'?'1 serving':item.serving));row.append(name,portion);list.append(row);
      }
      card.append(list);const metrics=element('dl','metrics');
      for(const [label,value,unit] of [['Student price',`€${plate.price.toFixed(2)}`,''],['Calories',Math.round(plate.kcal).toLocaleString(),'kcal'],['Protein',plate.protein.toFixed(1),'g'],['Fat',plate.fat_g.toFixed(1),'g'],['Calories from fat',plate.fat_energy_pct.toFixed(1),'%'],['Carbs',plate.carbs_g.toFixed(1),'g']]){
        const metric=element('div','metric'),dd=element('dd','',value);if(unit)dd.append(element('small','',` ${unit}`));metric.append(element('dt','',label),dd);metrics.append(metric);
      }
      card.append(metrics,element('p','meat-weight',`Identified meat dishes: ${plate.meat_dish_weight_g.toLocaleString()} g, including sauces.${plate.unknown_diet_weight_g?` Unclear dietary labels: ${plate.unknown_diet_weight_g.toLocaleString()} g.`:''}${plate.has_estimated_prices?' Includes an estimated price.':''}`));
      card.addEventListener('click',()=>onChoose(side));card.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onChoose(side);}});return card;
    }
  return {render};
});
