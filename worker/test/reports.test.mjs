import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {spawn,spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {plateKey,validateReport} from '../src/index.js';

const state=mkdtempSync(join(tmpdir(),'mensa-reports-'));
const wrangler=join(process.cwd(),'node_modules/wrangler/bin/wrangler.js');
const endpoint='http://127.0.0.1:8799';
const env={...process.env,WRANGLER_SEND_METRICS:'false',CI:'true'};
let server,logs='';
const body=(device_id=randomUUID(),extra={})=>({date:'2026-11-06',variant:'bulk_all',
  plate_dish_ids:['aaaaaaaaaaaaaaaa','bbbbbbbbbbbbbbbb'],tapped_dish_id:'aaaaaaaaaaaaaaaa',device_id,...extra});
const post=data=>fetch(endpoint+'/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});

before(async()=>{
  const result=spawnSync(process.execPath,[wrangler,'d1','migrations','apply','DB','--local','--persist-to',state],{env,encoding:'utf8'});
  assert.equal(result.status,0,result.stderr+result.stdout);
  server=spawn(process.execPath,[wrangler,'dev','--ip','127.0.0.1','--port','8799','--persist-to',state],{env,stdio:['ignore','pipe','pipe']});
  server.stdout.on('data',chunk=>{logs+=chunk;});server.stderr.on('data',chunk=>{logs+=chunk;});
  for(let i=0;i<300;i++) {
    try {if((await fetch(endpoint+'/broken?date=2026-11-06')).ok) return;} catch(_) {}
    if(server.exitCode!==null) break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.fail('wrangler dev did not become ready: '+logs);
}, {timeout:45000});
after(async()=>{
  if(server && server.exitCode===null) {
    const exited=new Promise(resolve=>server.once('exit',resolve));server.kill('SIGTERM');await exited;
  }
  rmSync(state,{recursive:true,force:true});
});

test('two distinct devices break a plate; repeat reports and variant changes do not add votes',async()=>{
  const report=body();
  assert.equal((await post(report)).status,201);
  assert.equal((await post({...report,variant:'cut_all'})).status,201);
  assert.deepEqual((await (await fetch(endpoint+'/broken?date='+report.date)).json()).broken,[]);
  assert.equal((await post({...report,device_id:randomUUID(),variant:'budget_all'})).status,201);
  assert.deepEqual((await (await fetch(endpoint+'/broken?date='+report.date)).json()).broken,[plateKey(report.plate_dish_ids)]);
  assert.deepEqual((await (await fetch(endpoint+'/broken?date=2026-11-09')).json()).broken,[]);
});
test('max three submissions per device per Berlin day across menu dates, including simultaneous requests',async()=>{
  const device=randomUUID();
  const responses=await Promise.all(Array.from({length:10},(_,i)=>post(body(device,{date:i%2?'2026-11-09':'2026-11-10'}))));
  assert.equal(responses.filter(r=>r.status===201).length,3);
  assert.equal(responses.filter(r=>r.status===429).length,7);
});
test('raw reports retain date, variant, dish IDs, tapped dish and random device ID',async()=>{
  const report=body(randomUUID(),{tapped_dish_id:'other'});
  assert.equal((await post(report)).status,201);
  const result=spawnSync(process.execPath,[wrangler,'d1','execute','DB','--local','--persist-to',state,'--json',
    '--command',`SELECT * FROM reports WHERE device_id = '${report.device_id}'`],{env,encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const row=JSON.parse(result.stdout)[0].results[0];
  for(const key of ['date','variant','tapped_dish_id','device_id']) assert.equal(row[key],report[key]);
  assert.deepEqual(JSON.parse(row.plate_dish_ids),report.plate_dish_ids);
  assert(row.report_day && row.created_at);
});
test('invalid payloads and origins are rejected and browser preflight works',async()=>{
  assert.equal((await post(body(randomUUID(),{tapped_dish_id:'ffffffffffffffff'}))).status,400);
  assert.equal((await post(body(randomUUID(),{date:'2026-02-30'}))).status,400);
  assert.equal((await fetch(endpoint+'/broken?date=bad')).status,400);
  assert.equal((await fetch(endpoint+'/broken?date=2026-11-06',{headers:{Origin:'https://untrusted.example'}})).status,403);
  const response=await fetch(endpoint+'/report',{method:'OPTIONS',headers:{Origin:'http://127.0.0.1:8000','Access-Control-Request-Method':'POST'}});
  assert.equal(response.status,204);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'http://127.0.0.1:8000');
});
test('strict validation rejects duplicate dishes, extra fields and invalid UUIDs',()=>{
  assert(validateReport(body()));
  assert(!validateReport(body(randomUUID(),{plate_dish_ids:['aaaaaaaaaaaaaaaa','aaaaaaaaaaaaaaaa']})));
  assert(!validateReport({...body(),personal_data:'no'}));
  assert(!validateReport(body('not-a-uuid')));
});
