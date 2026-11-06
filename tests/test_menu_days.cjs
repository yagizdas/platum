const {test}=require('node:test');
const assert=require('node:assert/strict');
const {defaultMenuDay,validWeek}=require('../menu-days.js');
function index() {
  const dates=['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06','2026-11-09','2026-11-10','2026-11-11','2026-11-12','2026-11-13'];
  return {schema_version:2,generated_on:'2026-11-03',week_start:dates[0],valid_through:dates.at(-1),lunch_cutoff:'14:30',days:dates.map(date=>({date,state:'open',file:'data/days/'+date+'.json'}))};
}
for(const [label,now,date] of [
  ['Friday at eleven opens today','2026-11-06T10:00:00Z','2026-11-06'],
  ['Friday at fifteen opens Monday','2026-11-06T14:00:00Z','2026-11-09'],
  ['Saturday opens Monday','2026-11-07T10:00:00Z','2026-11-09'],
  ['cutoff is Berlin time','2026-11-06T13:30:00Z','2026-11-09']]) {
  test(label,()=>assert.equal(defaultMenuDay(index(),new Date(now)).date,date));
}
test('old generation date leaves a still-valid menu usable',()=>{
  const data=index(),now=new Date('2026-11-06T10:00:00Z');
  assert(validWeek(data,now));assert.equal(defaultMenuDay(data,now).date,'2026-11-06');
});
test('no default ever selects a past day, even in an expired index',()=>{
  const data=index(),now=new Date('2026-11-16T10:00:00Z');
  assert.equal(defaultMenuDay(data,now),undefined);assert.equal(validWeek(data,now),false);
  assert.equal(validWeek(data,now,'2026-11-02'),true);
  assert.equal(validWeek(data,now,'2026-10-30'),true); // explicit history can be outside the current strip
});
test('a future week is allowed and dates are sorted before choosing',()=>{
  const data=index();data.days=data.days.filter(d=>d.date>='2026-11-09').reverse();data.week_start='2026-11-09';
  assert(validWeek(data,new Date('2026-11-07T10:00:00Z')));
  assert.equal(defaultMenuDay(data,new Date('2026-11-07T10:00:00Z')).date,'2026-11-09');
});
test('closed days are skipped and an exhausted week has no fallback meal',()=>{
  const data=index();data.days.find(d=>d.date==='2026-11-06').state='closed';
  assert.equal(defaultMenuDay(data,new Date('2026-11-06T10:00:00Z')).date,'2026-11-09');
  assert.equal(defaultMenuDay(data,new Date('2026-11-13T14:00:00Z')),undefined);
});
