const {test}=require('node:test');
const assert=require('node:assert/strict');
const {existsSync,readFileSync}=require('node:fs');
const {resolve,dirname}=require('node:path');
const {KEY,read,forGoal,resetGoal,undoGoal,proteinCaloriesPercent,allPlates,selectPair,judgment,validData,dataUrl}=require('../label/label.js');
const {assetUrl}=require('../dish-icons.js');
const plate=(id,score)=>({id,title:`Plate ${id}`,dishes:[`Dish ${id}`],kcal:500,protein:30,price:4,score});
const data={days:[{date:'2026-11-10',goals:{bulk:Array.from({length:20},(_,i)=>plate(`a${i}`,20-i))}},{date:'2026-11-11',goals:{bulk:Array.from({length:20},(_,i)=>plate(`b${i}`,20-i))}}]};
test('top sampling uses two distinct plates from a single day top 15',()=>{const pair=selectPair(data,'bulk',()=>0);assert.equal(pair.length,2);assert.equal(pair[0].menu_date,pair[1].menu_date);assert.notEqual(pair[0].id,pair[1].id);assert.ok(pair.every(value=>Number(value.id.slice(1))<15));});
test('random sampling draws from a full day and samples across available days',()=>{const values=[.9,.99,0,.99];let i=0;const pair=selectPair(data,'bulk',()=>values[i++]??0);assert.equal(pair[0].id,'b0');assert.equal(pair[1].id,'b19');assert.equal(pair[0].menu_date,pair[1].menu_date);});
test('all plates include their menu date',()=>assert.equal(allPlates(data,'bulk')[20].menu_date,'2026-11-11'));
test('judgment is self-contained for later fitting',()=>{const pair=[{...plate('a',2),menu_date:'2026-11-10'},{...plate('b',1),menu_date:'2026-11-11'}],value=judgment('bulk',pair,'a',new Date('2026-11-11T12:00:00Z'));assert.equal(value.timestamp,'2026-11-11T12:00:00.000Z');assert.equal(value.date,null);assert.equal(value.plate_a.id,'a');assert.equal(value.plate_b.score,1);assert.equal(value.winner,'a');});
test('malformed storage is safely ignored',()=>assert.deepEqual(read({getItem:key=>{assert.equal(key,KEY);return '{';}}),[]));
test('protein calorie percentage uses four kcal per gram and handles missing energy',()=>{
  assert.equal(proteinCaloriesPercent({protein:45,kcal:600}),30);
  assert.equal(proteinCaloriesPercent({protein:32,kcal:480}),27);
  assert.equal(proteinCaloriesPercent({protein:0,kcal:600}),0);
  assert.equal(proteinCaloriesPercent({protein:45,kcal:0}),null);
  assert.equal(proteinCaloriesPercent({protein:45}),null);
});
test('existing mixed judgments export separately by goal',()=>{
  const values=[{goal:'bulk',winner:'a'},{goal:'cut',winner:'b'},{goal:'bulk',winner:'both_bad'},{goal:'budget',winner:'a'}];
  assert.deepEqual(forGoal(values,'cut'),[values[1]]);
  assert.deepEqual(forGoal(values,'bulk'),[values[0],values[2]]);
  assert.deepEqual(forGoal(values,'missing'),[]);
});
test('reset removes only the selected goal and leaves the original data untouched',()=>{
  const values=[{goal:'bulk'},{goal:'cut'},{goal:'budget'},{goal:'cut'}];
  assert.deepEqual(resetGoal(values,'cut'),[values[0],values[2]]);
  assert.equal(values.length,4);
  assert.deepEqual(resetGoal(values,'missing'),values);
});
test('undo removes the last judgment for the selected goal only',()=>{
  const values=[{goal:'cut',winner:'a'},{goal:'bulk'},{goal:'cut',winner:'b'},{goal:'budget'}];
  assert.deepEqual(undoGoal(values,'cut'),[values[0],values[1],values[3]]);
  assert.deepEqual(undoGoal(values,'missing'),values);
  assert.deepEqual(undoGoal([],'cut'),[]);
});
test('label data and icon assets resolve beneath the deployed staging base path',()=>{
  assert.equal(dataUrl('https://yagizdas.github.io/platum/staging/label/'),'https://yagizdas.github.io/platum/staging/label/data.json');
  assert.equal(assetUrl('tray','https://yagizdas.github.io/platum/staging/dish-icons.js'),'https://yagizdas.github.io/platum/staging/icons/ui/tray.webp');
  const html=readFileSync(resolve(__dirname,'../label/index.html'),'utf8');
  for(const reference of [...html.matchAll(/(?:href|src)="([^"#]+)"/g)].map(match=>match[1])) {
    assert.ok(existsSync(resolve(dirname(resolve(__dirname,'../label/index.html')),reference.split('?')[0])),`${reference} must exist in the deployed tree`);
  }
  const published=JSON.parse(readFileSync(resolve(__dirname,'../label/data.json'),'utf8'));
  assert.ok(validData(published));
  assert.ok(published.days.flatMap(day=>day.goals.bulk).every(value=>value.items.length));
});
