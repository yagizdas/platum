const {test}=require('node:test');
const assert=require('node:assert/strict');
const {randomUUID}=require('node:crypto');
const {create,plateKey}=require('../report-client.js');
const ids=['aaaaaaaaaaaaaaaa','bbbbbbbbbbbbbbbb'];
const payload={date:'2026-11-06',variant:'bulk_all',plate_dish_ids:ids,tapped_dish_id:ids[0]};
function storage() {
  const values=new Map();return {getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)};
}
test('an unconfigured endpoint makes no request',async()=>{
  const client=create('',{fetcher:()=>assert.fail('No backend request')});
  assert.equal(client.enabled,false);assert.deepEqual(await client.broken(payload.date),[]);
});
test('device UUID persists and reporting hides the plate for this device',async()=>{
  const store=storage(),sent=[];
  const fetcher=async(url,options)=>{sent.push(JSON.parse(options.body));return {ok:true};};
  const first=create('https://reports.example',{storage:store,fetcher});
  await first.report(payload);
  assert(first.isHidden(payload.date,plateKey(ids)));
  const second=create('https://reports.example',{storage:store,fetcher});
  assert(second.isHidden(payload.date,plateKey(ids)));
  await second.report({...payload,variant:'cut_all'});
  assert.equal(sent[0].device_id,sent[1].device_id);
  assert.deepEqual(Object.keys(sent[0]).sort(),['date','variant','plate_dish_ids','tapped_dish_id','device_id'].sort());
});
test('blocked localStorage still supports a stable in-memory device UUID',async()=>{
  const sent=[];
  const store={getItem(){throw Error('Blocked');},setItem(){throw Error('Blocked');}};
  const client=create('https://reports.example',{storage:store,crypto:{randomUUID},fetcher:async(url,o)=>{sent.push(JSON.parse(o.body));return {ok:true};}});
  await client.report(payload);await client.report(payload);
  assert.equal(sent[0].device_id,sent[1].device_id);assert(client.isHidden(payload.date,plateKey(ids)));
});
test('broken keys have a canonical dish order and fail open on every fetch error',async()=>{
  assert.equal(plateKey(ids),plateKey([...ids].reverse()));
  for(const fetcher of [async()=>{throw Error('Offline');},async()=>({ok:false}),async()=>({ok:true,json:async()=>({broken:'wrong'})})]) {
    assert.deepEqual(await create('https://reports.example',{fetcher}).broken(payload.date),[]);
  }
  const client=create('https://reports.example',{fetcher:async()=>({ok:true,json:async()=>({broken:[plateKey(ids)]})})});
  assert.deepEqual(await client.broken(payload.date),[plateKey(ids)]);
});
test('an unsuccessful submission never hides a plate or pretends to accept it',async()=>{
  const client=create('https://reports.example',{storage:storage(),fetcher:async()=>({ok:false,status:429})});
  await assert.rejects(client.report(payload),/limit/);assert.equal(client.isHidden(payload.date,plateKey(ids)),false);
});
