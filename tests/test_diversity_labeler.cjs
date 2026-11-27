const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync, existsSync} = require('node:fs');
const {resolve, dirname} = require('node:path');
const api = require('../label/diversity/label.js');
const data = require('../label/diversity/data.json'), index = api.indexData(data), id = data.pairs[0].id;
const date = new Date('2026-11-27T12:00:00Z');
const make = (decision, flags = {}, time = date) => api.makeRecord(data, index, id, decision, flags, ['main'], 'Test note', time);

test('diversity records encode useful-pair targets separately from suitability', () => {
  const yes = make('worth_both'), no = make('redundant'), unsuitable = make('unsuitable', {a:true});
  assert.equal(yes.worth_offering_both, true); assert.equal(no.worth_offering_both, false);
  assert.equal(unsuitable.worth_offering_both, null); assert.equal(unsuitable.unsuitable_a, true);
  assert.equal(yes.is_human_judgment, true); assert.deepEqual(yes.features, index.get(id).pair.features);
  assert.throws(() => make('worth_both', {a:true})); assert.throws(() => make('unsuitable'));
  assert.throws(() => make('a')); assert.throws(() => api.makeRecord(data,index,id,'worth_both',{},['invented']));
});
test('save, skip, undo, goal filtering and completion retain the correct pair', () => {
  const initial = api.blank(), next = api.applyChoice(initial, make('redundant'));
  assert.notEqual(api.nextPair(data,next).id,id);
  assert.equal(api.nextPair(data,api.undo(next)).id,id);
  const deferred=api.defer(initial,id); assert.notEqual(api.nextPair(data,deferred).id,id);assert.equal(deferred.records.length,0);
  const goal={...initial,goal:'cut'}; assert.equal(api.nextPair(data,goal).goal,'cut');
  const full={...initial,records:data.pairs.map(p=>api.makeRecord(data,index,p.id,'worth_both'))}; assert.equal(api.nextPair(data,full),null);
});
test('review edits a saved decision without duplicating it', () => {
  let state=api.applyChoice(api.blank(),make('worth_both'));state={...state,review:id};
  assert.equal(api.nextPair(data,state).id,id);
  state=api.applyChoice(state,make('redundant'));
  assert.equal(state.records.length,1); assert.equal(state.records[0].worth_offering_both,false);assert.equal(state.review,null);
});
test('compact save restores snapshots/features and stays below browser storage limits', () => {
  const state={...api.blank(),records:data.pairs.map(p=>api.makeRecord(data,index,p.id,'worth_both'))};
  const raw=JSON.stringify(api.compact(state));assert.ok(raw.length<500000);
  assert.deepEqual(api.readState({getItem:()=>raw},data,index),state);
  assert.equal(api.compact(state).records[0].plate_a.items,undefined);
  assert.throws(()=>api.readState({getItem:()=>'{broken'},data,index));
  assert.notEqual(api.storageKey(data),require('../label/v2/label.js').storageKey(data));
});
test('backup validates provenance and dataset, merges newest labels and reconstructs trusted data', () => {
  const state=api.applyChoice(api.blank(),make('worth_both'));
  const newer=api.applyChoice(api.blank(),make('redundant',{},new Date(date.getTime()+1000)));
  const merged=api.mergeBackup(data,index,state,api.backup(data,newer));assert.equal(merged.records.length,1);assert.equal(merged.records[0].decision,'redundant');
  const wrong=api.backup(data,newer);wrong.dataset_id='other';assert.throws(()=>api.mergeBackup(data,index,state,wrong));
  const ai=api.backup(data,newer);ai.records=[{...ai.records[0],is_human_judgment:false}];assert.throws(()=>api.mergeBackup(data,index,state,ai));
  const tampered=api.backup(data,newer);tampered.records=[{...tampered.records[0],features:{fake:1},plate_a:{id:tampered.records[0].plate_a.id,items:[]}}];
  assert.deepEqual(api.mergeBackup(data,index,state,tampered).records[0].features,index.get(id).pair.features);
});
test('page assets resolve and decisions have separate controls',()=>{
  const file=resolve(__dirname,'../label/diversity/index.html'), html=readFileSync(file,'utf8');
  for(const ref of [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(m=>m[1]))assert.ok(existsSync(resolve(dirname(file),ref.split('?')[0])),ref);
  for(const name of ['worth-both','redundant','save-unsuitable','review','goal','export','import'])assert.ok(html.includes(`id="${name}"`));
});
