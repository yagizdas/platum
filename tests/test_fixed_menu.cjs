const {test}=require('node:test'),assert=require('node:assert/strict'),{readFileSync}=require('node:fs');
const menu=readFileSync(require('node:path').resolve(__dirname,'../menu.html'),'utf8');
test('public menu exposes no experiment methods, balance control, or legacy query override',()=>{
 assert.doesNotMatch(menu,/data-bulk-method|id="bulk-experiment"|id="mmr-balance"|requestedMethod|bulkMethod|mmrBalance|comparisonSite/);
 assert.doesNotMatch(menu,/label\/[cdeg]\/\?/);
 assert.match(menu,/plate\.items\.slice\(0,4\)/);
 assert.match(menu,/payload\.filtered_variants/);
});
