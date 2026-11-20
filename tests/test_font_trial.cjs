const {test}=require('node:test');
const assert=require('node:assert/strict');
const {choices,nextChoice}=require('../font-trial.js');

test('font trial contains every requested choice in order',()=>{
  assert.deepEqual(choices.map(choice=>choice.id),[
    'jakarta','dm-sans','bricolage-dm','fraunces-figtree','instrument','current',
  ]);
});

test('font trial cycles and wraps',()=>{
  assert.equal(nextChoice('jakarta').id,'dm-sans');
  assert.equal(nextChoice('current').id,'jakarta');
  assert.equal(nextChoice('not-saved').id,'jakarta');
});
