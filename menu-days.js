(function(root,factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.MenuDays=api;
})(typeof globalThis!=='undefined'?globalThis:this,function() {
  'use strict';
  const validDate=text=>typeof text==='string' && /^\d{4}-\d{2}-\d{2}$/.test(text);
  const berlinDate=(now=new Date())=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
  function defaultMenuDay(index,now=new Date()) {
    const today=berlinDate(now);
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now);
    const number=type=>Number(parts.find(p=>p.type===type).value);
    const cutoff=(index.lunch_cutoff || '14:30').split(':').map(Number);
    const late=number('hour')*60+number('minute')>=cutoff[0]*60+cutoff[1];
    const days=[...index.days].sort((a,b)=>a.date.localeCompare(b.date));
    return days.find(row=>row.state==='open' && (row.date>today || (!late && row.date===today)));
  }
  function validWeek(index,now=new Date(),requestedDate=null) {
    if(!index || index.schema_version!==2 || !Array.isArray(index.days) || !index.days.length ||
       !validDate(index.week_start) || !validDate(index.valid_through) || index.week_start>index.valid_through) return false;
    const seen=new Set();
    if(!index.days.every(row=>row && validDate(row.date) && !seen.has(row.date) && seen.add(row.date) &&
       row.date>=index.week_start && row.date<=index.valid_through &&
       ['open','closed','unavailable'].includes(row.state) && row.file==='data/days/'+row.date+'.json')) return false;
    // Publication age says nothing about validity of individual future menu dates.
    return index.valid_through>=berlinDate(now) || validDate(requestedDate);
  }
  return {berlinDate,defaultMenuDay,validWeek};
});
