const {test}=require('node:test');
const assert=require('node:assert/strict');
const {get,file}=require('../campus-config.js');
test('campus menu URLs resolve beneath the current deployment subpath',()=>{
 for(const base of ['https://example.org/platum/menu.html','https://example.org/platum/staging/menu.html']) {
  const prefix=base.slice(0,base.lastIndexOf('/'));
  assert.equal(new URL(file('garching','data/week.json'),base).href,prefix+'/data/campuses/garching/week.json');
  assert.equal(new URL(file('arcisstr','data/days/2026-11-23.json'),base).href,prefix+'/data/days/2026-11-23.json');
 }
});
test('only registered campuses and date JSON paths can be selected',()=>{
 assert.equal(get('unknown').id,'arcisstr');assert.equal(get('__proto__').id,'arcisstr');
 assert.match(get('garching').official,/422/);assert.match(get('arcisstr').official,/421/);
 assert.throws(()=>file('garching','../.env'));
 assert.throws(()=>file('garching','data/proposals/2026-11-23.json'));
});
