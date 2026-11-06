(function(root,factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.PlateReports=api;
})(typeof globalThis!=='undefined'?globalThis:this,function() {
  'use strict';
  const plateKey=ids=>[...new Set(ids)].sort().join('|');
  function create(endpoint,{fetcher=globalThis.fetch,storage,crypto=globalThis.crypto}={}) {
    endpoint=(endpoint || '').replace(/\/$/,'');
    let device,hidden={};
    try {storage=storage || globalThis.localStorage;hidden=JSON.parse(storage.getItem('mensa-hidden-plates') || '{}') || {};} catch(_) {}
    if(typeof hidden!=='object' || Array.isArray(hidden)) hidden={};
    function deviceId() {
      if(device) return device;
      try {device=storage.getItem('mensa-device-id');} catch(_) {}
      if(typeof device!=='string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(device)) {
        device=crypto.randomUUID();
        try {storage.setItem('mensa-device-id',device);} catch(_) {}
      }
      return device;
    }
    function hide(date,key) {
      hidden[date]=[...new Set([...(Array.isArray(hidden[date])?hidden[date]:[]),key])];
      try {storage.setItem('mensa-hidden-plates',JSON.stringify(hidden));} catch(_) {}
    }
    function isHidden(date,key) {return Array.isArray(hidden[date]) && hidden[date].includes(key);}
    async function broken(date) {
      if(!endpoint) return [];
      try {
        const response=await fetcher(endpoint+'/broken?date='+encodeURIComponent(date),{signal:AbortSignal.timeout(2500),cache:'no-store'});
        if(!response.ok) return [];
        const payload=await response.json();
        return Array.isArray(payload.broken)?payload.broken.filter(key=>typeof key==='string'):[];
      } catch(_) {return [];}
    }
    async function report(payload) {
      const response=await fetcher(endpoint+'/report',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...payload,device_id:deviceId()}),signal:AbortSignal.timeout(6000)});
      if(!response.ok) throw new Error(response.status===429?'Today’s report limit is reached.':'Couldn’t send. Please try again.');
      hide(payload.date,plateKey(payload.plate_dish_ids));
    }
    return {enabled:!!endpoint,broken,report,isHidden};
  }
  return {plateKey,create};
});
