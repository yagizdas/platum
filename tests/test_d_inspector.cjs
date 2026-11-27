const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync, existsSync} = require('node:fs');
const {resolve, dirname} = require('node:path');
const api = require('../label/d/d.js');

test('D decisions explain which earlier pick caused a skip', () => {
  assert.equal(api.decisionText({decision:'selected'}), 'Selected');
  assert.match(api.decisionText({decision:'skipped', similarity:{total:.8}, closest_selected_rank:3}), /80.0%.*#3/);
});
test('D validates an actual ordered selection walk', () => {
  const v = {pool_count:3, walk:[{preference_rank:1, decision:'selected'}, {preference_rank:2, decision:'skipped'}, {preference_rank:3, decision:'selected'}], plates:[{preference_rank:1}, {preference_rank:3}]};
  const data = {date:'2026-11-27', settings:{}, variants:{bulk_all:v}};
  assert.equal(api.validateDay(data), data);
  assert.throws(() => api.validateDay({...data, variants:{bulk_all:{...v, plates:[{preference_rank:2}, {preference_rank:3}]}}}));
});
test('D page assets and menu switch are available', () => {
  const file = resolve(__dirname, '../label/d/index.html'), html = readFileSync(file, 'utf8');
  for (const ref of [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(m => m[1])) assert.ok(existsSync(resolve(dirname(file), ref.split('?')[0])), ref);
  assert.deepEqual(api.GOALS, ['bulk','cut','budget']);
  assert.ok(api.PROFILES.includes('vegan'));
  const menu = readFileSync(resolve(__dirname,'../menu.html'),'utf8');
  assert.match(menu, /data-bulk-method="d"/);
  assert.match(menu, /combination_d/);
  assert.match(menu, /usingBulkB\(\) \|\| usingC\(\) \|\| usingD\(\)/);
});
