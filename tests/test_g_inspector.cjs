const {test}=require('node:test'),assert=require('node:assert/strict');
const {readFileSync,existsSync}=require('node:fs'),{resolve,dirname}=require('node:path');
const api=require('../label/e/e.js');
test('G audit reuses the MMR inspector and links to G and F with Cut/Budget scope',()=>{
 const file=resolve(__dirname,'../label/g/index.html'),html=readFileSync(file,'utf8');
 for(const ref of [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(m=>m[1]))assert.ok(existsSync(resolve(dirname(file),ref.split('?')[0])),ref);
 assert.match(html,/data-experiment="g"/);assert.match(html,/method=g/);assert.match(html,/method=f/);
 assert.match(html,/<option value="cut">/);assert.match(html,/<option value="budget">/);assert.doesNotMatch(html,/<option value="bulk">/);
 const menu=readFileSync(resolve(__dirname,'../menu.html'),'utf8');assert.match(menu,/data-bulk-method="g"/);assert.match(menu,/usingG\(\)/);assert.match(menu,/label\/g\/\?/);
});
test('G reconstructs exactly the selected F candidates in MMR order',()=>{
 const candidates=[1,2,3].map(i=>({candidate_id:`g00${i}`,preference_rank:i,score:{total:1-i/10},items:[],total:{}}));
 const v={candidates,balances:{balanced:{selections:[{candidate_id:'g001'},{candidate_id:'g003'},{candidate_id:'g002'}]}}};
 assert.deepEqual(api.selectedPlates(v,'balanced').map(p=>p.preference_rank),[1,3,2]);
});
