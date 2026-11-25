const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync,existsSync}=require('node:fs');
const {resolve,dirname}=require('node:path');
const api=require('../label/v2/label.js');
const data=JSON.parse(readFileSync(resolve(__dirname,'../label/v2/data.json'),'utf8'));
const index=api.indexData(data);
const now=new Date('2026-11-25T12:00:00Z');

test('v2 published data resolves every pair and nested asset',()=>{
 assert.equal(index.size,data.queue.length);
 assert.equal(api.dataUrl('https://eatplato.de/staging/label/v2/'),'https://eatplato.de/staging/label/v2/data.json');
 const path=resolve(__dirname,'../label/v2/index.html'),html=readFileSync(path,'utf8');
 for(const ref of [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(m=>m[1]))assert.ok(existsSync(resolve(dirname(path),ref.split('?')[0])),ref);
 assert.match(html,/noindex,nofollow/);
 assert.match(html,/Both bad/);
});
test('v2 choices retain complete features and separate preference from acceptability',()=>{
 const ref=data.queue[0],a=api.makeRecord(data,index,ref,'a',now),bad=api.makeRecord(data,index,ref,'both_bad',now);
 assert.equal(a.acceptable_a,true);assert.equal(a.acceptable_b,null);assert.equal(a.preference,'a');
 assert.equal(bad.acceptable_a,false);assert.equal(bad.acceptable_b,false);assert.equal(bad.preference,null);
 assert.equal(bad.winner,'both_bad');assert.equal(bad.dataset_id,data.dataset_id);
 assert.ok('fat_energy_pct' in bad.plate_a);assert.ok('meat_dish_weight_g' in bad.plate_a);
 assert.notEqual(a.plate_a,index.get(api.refKey(ref)).a);
 assert.ok(a.plate_a.items.every(i=>'fat_g' in i&&'weight_g' in i&&'count' in i));
});
test('v2 resumes the next unlabeled comparison and undo restores the exact last pair',()=>{
 let state=api.blank(),ref=api.nextRef(data,state);
 state=api.applyChoice(state,api.makeRecord(data,index,ref,'a',now));
 assert.notEqual(api.refKey(api.nextRef(data,state)),api.refKey(ref));
 const restored=api.undo(state);assert.equal(restored.records.length,0);
 assert.equal(api.refKey(api.nextRef(data,restored)),api.refKey(ref));
 assert.equal(api.nextRef(data,{records:data.queue,deferred:[]}),null);
});
test('skip postpones a comparison without inventing a judgment',()=>{
 const state=api.blank(),ref=api.nextRef(data,state),next=api.defer(state,ref);
 assert.equal(next.records.length,0);assert.notEqual(api.refKey(api.nextRef(data,next)),api.refKey(ref));
 const small={queue:data.queue.slice(0,2)};
 let s=api.defer(api.defer(api.blank(),small.queue[0]),small.queue[1]);
 assert.equal(api.refKey(api.nextRef(small,s)),api.refKey(small.queue[0]));
 s=api.defer(s,small.queue[0]);assert.equal(api.refKey(api.nextRef(small,s)),api.refKey(small.queue[1]));
});
test('v2 storage is separate, round-trips choices, and fails visibly on corrupt records',()=>{
 let state=api.applyChoice(api.blank(),api.makeRecord(data,index,data.queue[0],'both_bad',now));
 const key=api.storageKey(data);assert.notEqual(key,require('../label/label.js').KEY);
 const compact=api.storageState(state);assert.equal(compact.records[0].plate_a.items,undefined);
 const storage={getItem:k=>{assert.equal(k,key);return JSON.stringify(compact);}};
 assert.deepEqual(api.readState(storage,data,index),state);
 assert.throws(()=>api.readState({getItem:()=>'{bad'},data,index));
});
test('v2 backup merges without duplicate labels and rejects a different dataset',()=>{
 const ref=data.queue[0],older=api.makeRecord(data,index,ref,'a',now),newer=api.makeRecord(data,index,ref,'both_bad',new Date(now.getTime()+1000));
 const state=api.applyChoice(api.blank(),older),other=api.applyChoice(api.blank(),newer);
 const merged=api.mergeBackup(data,index,state,api.backup(data,other));
 assert.equal(merged.records.length,1);assert.equal(merged.records[0].winner,'both_bad');
 assert.throws(()=>api.mergeBackup(data,index,state,{...api.backup(data,other),dataset_id:'another'}));
 const tampered=api.backup(data,other);tampered.records=[{...newer,plate_a:{id:'wrong'}}];
 assert.throws(()=>api.mergeBackup(data,index,state,tampered));
});
