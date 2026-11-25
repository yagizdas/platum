const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync,existsSync}=require('node:fs');
const {resolve,dirname}=require('node:path');
const api=require('../label/v2/review/review.js');
const original=require('../label/v2/label.js');
const data=JSON.parse(readFileSync(resolve(__dirname,'../label/v2/review/data.json'),'utf8'));
const dataset=JSON.parse(readFileSync(resolve(__dirname,'../label/v2/data.json'),'utf8'));
const first=new Date('2026-11-25T18:00:00Z'),later=new Date('2026-11-25T19:00:00Z');

test('all 150 published AI comparisons match the frozen labeling data and keep their reasons',()=>{
 assert.equal(api.validateSource(data),data);assert.equal(data.records.length,150);
 const index=original.indexData(dataset);
 const counts={a:0,b:0,both_bad:0};
 data.records.forEach((row,i)=>{const value=index.get(original.refKey(dataset.queue[i]));assert.equal(row.case_index,i+1);assert.deepEqual(row.plate_a,value.a);assert.deepEqual(row.plate_b,value.b);assert.ok(row.rationale.length>30);assert.equal(row.is_human_judgment,false);counts[row.winner]++;});
 assert.deepEqual(counts,{a:54,b:53,both_bad:43});
});
test('unreviewed AI suggestions never become human training rows',()=>{
 const state=api.blank(),human=api.exportReviews(data,state),audit=api.exportReviews(data,state,{audit:true});
 assert.equal(human.records.length,0);assert.equal(audit.records.length,150);
 assert.ok(audit.records.every(r=>r.is_human_judgment===false&&r.review.status==='unreviewed'));
 assert.equal(api.mergeBackup(data,state,audit).reviews.constructor,Object);
 assert.deepEqual(api.counts(data,api.mergeBackup(data,state,audit)),{reviewed:0,changed:0,agreed:0,pending:150});
});
test('confirming AI and switching left/right/both-bad preserve both original choice and human provenance',()=>{
 const ai=structuredClone(data.records[0]);let state=api.blank();
 for(const winner of ['a','b','both_bad']){
  state=api.setChoice(data,state,winner,'A smaller portion would help.',first);
  const out=api.exportReviews(data,state),row=out.records[0];
  assert.equal(out.records.length,1);assert.equal(row.winner,winner);assert.equal(row.is_human_judgment,true);
  assert.equal(row.acceptable_a,winner==='both_bad'?false:winner==='a'?true:null);
  assert.equal(row.acceptable_b,winner==='both_bad'?false:winner==='b'?true:null);
  assert.equal(row.ai_original.winner,ai.winner);assert.equal(row.ai_original.rationale,ai.rationale);
  assert.equal(row.user_note,'A smaller portion would help.');assert.equal(row.rationale,undefined);
  assert.deepEqual(row.plate_a,ai.plate_a);assert.deepEqual(data.records[0],ai);
 }
 state=api.setChoice(data,state,ai.winner,'Agree.',later);
 assert.deepEqual(api.counts(data,state),{reviewed:1,changed:0,agreed:1,pending:149});
 assert.equal(api.exportReviews(data,state).records[0].review.status,'confirmed');
});
test('filters and marking a case unreviewed follow explicit human reviews only',()=>{
 let state=api.setChoice(data,api.blank(),data.records[0].winner,'',first);
 state={...state,position:1};state=api.setChoice(data,state,data.records[1].winner==='a'?'b':'a','',first);
 assert.deepEqual(api.visibleIndices(data,{...state,filter:'agreed'}),[0]);
 assert.deepEqual(api.visibleIndices(data,{...state,filter:'changed'}),[1]);
 assert.equal(api.visibleIndices(data,{...state,filter:'pending'}).length,148);
 state=api.unreview(data,state);assert.equal(api.exportReviews(data,state).records.length,1);
 assert.equal(state.reviews[api.key(data.records[1])],undefined);
});
test('review storage is independent, resumes position and rejects corrupt or cross-dataset entries',()=>{
 const state={...api.setChoice(data,api.blank(),'a','',first),position:42,filter:'changed'};
 assert.notEqual(api.storageKey(data),original.storageKey(dataset));
 const storage={getItem:k=>{assert.equal(k,api.storageKey(data));return JSON.stringify(state);}};
 assert.deepEqual(api.readState(storage,data),state);
 assert.throws(()=>api.readState({getItem:()=>'{bad'},data));
 assert.throws(()=>api.normalizeState(data,{...state,reviews:{unknown:{winner:'a',reviewed_at:first.toISOString()}}}));
});
test('review backups merge by latest timestamp and never count unreviewed AI as reviewed',()=>{
 const old=api.setChoice(data,api.blank(),'a','Old',first),fresh=api.setChoice(data,api.blank(),'b','New',later);
 const merged=api.mergeBackup(data,old,api.exportReviews(data,fresh,{audit:true}));
 assert.equal(api.counts(data,merged).reviewed,1);assert.equal(merged.reviews[api.key(data.records[0])].winner,'b');
 assert.equal(merged.notes[api.key(data.records[0])],'New');
 assert.equal(api.mergeBackup(data,merged,api.exportReviews(data,old)).notes[api.key(data.records[0])],'New');
 assert.throws(()=>api.mergeBackup(data,old,{...api.exportReviews(data,fresh),review_id:'other'}));
 const bad=api.exportReviews(data,fresh);bad.records[0].is_human_judgment=false;
 assert.throws(()=>api.mergeBackup(data,old,bad));
});
test('the full audit retains mixed sources while reviewed-only exports contain confirmed or corrected rows',()=>{
 const state=api.setChoice(data,api.blank(),'a','My choice',first),audit=api.exportReviews(data,state,{audit:true});
 assert.equal(audit.records.length,150);assert.equal(audit.records.filter(r=>r.is_human_judgment).length,1);
 assert.equal(audit.records[1].rationale,data.records[1].rationale);
 assert.equal(audit.is_human_judgment,null);assert.equal(api.exportReviews(data,state).is_human_judgment,true);
});
test('nested review assets and the entry link resolve in the deployed tree',()=>{
 const path=resolve(__dirname,'../label/v2/review/index.html'),html=readFileSync(path,'utf8');
 for(const ref of [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(m=>m[1]))assert.ok(existsSync(resolve(dirname(path),ref.split('?')[0])),ref);
 assert.match(readFileSync(resolve(__dirname,'../label/v2/index.html'),'utf8'),/href="\.\/review\/"/);
 assert.match(html,/noindex,nofollow/);
});
test('AI review files cannot be mistaken for direct human-labeler backups',()=>{
 const sourceIndex=original.indexData(dataset),state=api.setChoice(data,api.blank(),'a','',first);
 assert.throws(()=>original.mergeBackup(dataset,sourceIndex,original.blank(),api.exportReviews(data,state)),/AI review page/);
 assert.throws(()=>original.mergeBackup(dataset,sourceIndex,original.blank(),{schema_version:2,experiment:api.BASE,dataset_id:data.dataset_id,records:[data.records[0]]}),/AI review page/);
});
