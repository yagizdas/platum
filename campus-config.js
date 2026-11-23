(function(root,factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.Campuses=api;
})(typeof globalThis!=='undefined'?globalThis:this,function() {
  const campuses={
    arcisstr:{id:'arcisstr',label:'Arcisstraße',name:'Mensa Arcisstraße',data:'data',official:'https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/speiseplan/speiseplan_421_-de.html'},
    garching:{id:'garching',label:'Garching',name:'Mensa Garching',data:'data/campuses/garching',official:'https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/speiseplan/speiseplan_422_-de.html'}
  };
  function get(id) {return Object.hasOwn(campuses,id)?campuses[id]:campuses.arcisstr;}
  function file(id,path) {
    if(!/^data\/(?:today\.json|week\.json|days\/\d{4}-\d{2}-\d{2}\.json)$/.test(path)) throw Error('Invalid menu file');
    return './'+get(id).data+path.slice(4);
  }
  return {get,file};
});
