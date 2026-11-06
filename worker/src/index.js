const VARIANTS=new Set(['bulk_all','cut_all','budget_all','bulk_vegan','cut_vegan','budget_vegan']);
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ID=/^[a-f0-9]{16}$/;
export const plateKey=ids=>[...ids].sort().join('|');
export function validDate(value) {
  return typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10)===value;
}
export function validateReport(body) {
  if(!body || typeof body!=='object' || Array.isArray(body)) return false;
  const fields=['date','variant','plate_dish_ids','tapped_dish_id','device_id'];
  return Object.keys(body).length===fields.length && fields.every(key=>Object.hasOwn(body,key)) &&
    validDate(body.date) && VARIANTS.has(body.variant) && typeof body.device_id==='string' && UUID.test(body.device_id) &&
    Array.isArray(body.plate_dish_ids) && body.plate_dish_ids.length>=1 && body.plate_dish_ids.length<=3 &&
    body.plate_dish_ids.every(id=>typeof id==='string' && ID.test(id)) &&
    new Set(body.plate_dish_ids).size===body.plate_dish_ids.length &&
    (body.tapped_dish_id==='other' || body.plate_dish_ids.includes(body.tapped_dish_id));
}

export default {
  async fetch(request,env) {
    const origin=request.headers.get('Origin');
    const origins=(env.ALLOWED_ORIGINS || '').split(',').map(s=>s.trim()).filter(Boolean);
    const headers={'Content-Type':'application/json','Cache-Control':'no-store','Vary':'Origin'};
    if(origin && origins.includes(origin)) headers['Access-Control-Allow-Origin']=origin;
    const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers});
    if(origin && !origins.includes(origin)) return json({error:'Origin not allowed'},403);
    if(request.method==='OPTIONS') {
      return new Response(null,{status:204,headers:{...headers,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type'}});
    }
    const url=new URL(request.url);
    const threshold=Number(env.BROKEN_THRESHOLD || 2);
    if(!Number.isInteger(threshold) || threshold<1) return json({error:'Invalid report configuration'},503);
    try {
      if(url.pathname==='/broken' && request.method==='GET') {
        const date=url.searchParams.get('date');
        if(!validDate(date)) return json({error:'Invalid date'},400);
        const {results}=await env.DB.prepare('SELECT plate_key FROM reports WHERE date = ? GROUP BY plate_key HAVING COUNT(DISTINCT device_id) >= ? ORDER BY plate_key').bind(date,threshold).all();
        return json({date,broken:results.map(row=>row.plate_key)});
      }
      if(url.pathname==='/report' && request.method==='POST') {
        if(!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return json({error:'Expected JSON'},415);
        if(Number(request.headers.get('Content-Length'))>4096) return json({error:'Report too large'},413);
        const text=await request.text();
        if(new TextEncoder().encode(text).length>4096) return json({error:'Report too large'},413);
        let body;
        try {body=JSON.parse(text);} catch(_) {return json({error:'Invalid JSON'},400);}
        if(!validateReport(body)) return json({error:'Invalid report'},400);
        const now=new Date();
        const reportDay=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
        const ids=[...body.plate_dish_ids].sort();
        // A single atomic conditional INSERT enforces the limit even for simultaneous requests.
        const result=await env.DB.prepare(`INSERT INTO reports
          (id,date,report_day,variant,plate_key,plate_dish_ids,tapped_dish_id,device_id,created_at)
          SELECT ?,?,?,?,?,?,?,?,? WHERE (SELECT COUNT(*) FROM reports WHERE device_id = ? AND report_day = ?) < 3`)
          .bind(crypto.randomUUID(),body.date,reportDay,body.variant,plateKey(ids),JSON.stringify(ids),body.tapped_dish_id,
                body.device_id.toLowerCase(),now.toISOString(),body.device_id.toLowerCase(),reportDay).run();
        if(result.meta.changes!==1) return json({error:'Daily limit reached'},429);
        return json({ok:true},201);
      }
      return json({error:'Not found'},404);
    } catch(_) {
      return json({error:'Reports temporarily unavailable'},503);
    }
  }
};
