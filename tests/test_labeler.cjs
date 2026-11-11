const {test}=require('node:test');
const assert=require('node:assert/strict');
const {KEY,read,sample,snapshot}=require('../label/label.js');
const plates=Array.from({length:12},(_,i)=>({id:String(i),title:`Plate ${i}`,dishes:[`Dish ${i}`],kcal:500+i,protein:20+i,price:3+i/10,score:12-i}));
test('ranking screens contain four or five candidates with roughly 70% top-scored',()=>{
  for(const key of ['a','b','c','d']){const chosen=sample(plates,key);assert.ok(chosen.length===4||chosen.length===5);const top=Math.round(chosen.length*.7);assert.deepEqual(chosen.slice(0,top),plates.slice(0,top));assert.ok(chosen.slice(top).every(p=>Number(p.id)>=top));}
});
test('sampling is stable for a date and goal',()=>assert.deepEqual(sample(plates,'2026-11-11|bulk'),sample(plates,'2026-11-11|bulk')));
test('snapshot is self-contained',()=>{const result=snapshot('2026-11-11','cut',plates.slice(0,4),new Date('2026-11-11T12:00:00Z'));assert.equal(result.timestamp,'2026-11-11T12:00:00.000Z');assert.deepEqual(result.ranking,['0','1','2','3']);assert.deepEqual(result.plates[0].dishes,['Dish 0']);assert.equal(result.plates[0].score,undefined);});
test('malformed storage is safely ignored',()=>assert.deepEqual(read({getItem:key=>{assert.equal(key,KEY);return '{';}}),[]));
