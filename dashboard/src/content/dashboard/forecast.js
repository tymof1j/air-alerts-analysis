const fmt=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Kyiv',hour:'numeric',month:'numeric',day:'numeric',year:'numeric',hourCycle:'h23'});
export function quantile(values,q){if(!values.length)return null;const a=[...values].sort((x,y)=>x-y),i=(a.length-1)*q,l=Math.floor(i);return a[l]+(a[Math.ceil(i)]-a[l])*(i-l);}
export function predict(model,start,elapsed,phase='all'){
 const c=Object.fromEntries(fmt.formatToParts(new Date(start*1000)).map(x=>[x.type,x.value]));let a=model.durations;
 if(model.name==='seasonal'){const b=a.filter(r=>r.year===Number(c.year)-1&&r.month===Number(c.month));if(b.length>=20)a=b;}
 if(model.name.startsWith('daynight')||phase!=='all'){const n=phase==='all'?(Number(c.hour)>=22||Number(c.hour)<6):phase==='night';const b=a.filter(r=>(r.hour>=22||r.hour<6)===n);if(b.length>=20)a=b;}
 const r=a.filter(v=>v.duration>elapsed).map(v=>v.duration-elapsed),p=h=>r.length?r.filter(v=>v<=h).length/r.length:null;
 return {median:quantile(r,.5),lower:quantile(r,.1),upper:quantile(r,.9),support:r.length,probabilities:[15,30,60,120].map(p),curve:Array.from({length:49},(_,i)=>({minute:i*5,endShare:i? p(i*5):0}))};
}
export const minutes=n=>n==null?'—':n>=60?`${Math.floor(Math.round(n)/60)} год ${Math.round(n)%60} хв`:`${Math.round(n)} хв`;
export const budget=(length,upper,existing,reserve)=>Math.max(0,length-upper-existing-reserve);
export const localTime=t=>new Intl.DateTimeFormat('uk-UA',{timeZone:'Europe/Kyiv',hour:'2-digit',minute:'2-digit'}).format(new Date(t*1000));
export function csv(rows){const f=Object.keys(rows[0]??{}),q=v=>'"'+String(v??'').replaceAll('"','""')+'"';const text='\uFEFF'+[f.map(q).join(','),...rows.map(r=>f.map(k=>q(r[k])).join(','))].join('\n');const u=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=u;a.download='shelter-scenario.csv';a.click();URL.revokeObjectURL(u);}

export function localDate(t){const c=Object.fromEntries(fmt.formatToParts(new Date(t*1000)).map(x=>[x.type,x.value]));return `${c.year}-${c.month.padStart(2,'0')}-${c.day.padStart(2,'0')}`;}

export function capacityFrequency(samples,point,capacity,length){
 const successes=samples.filter(r=>Math.max(0,Math.min(length,point+r.residual))<=capacity).length;
 const total=samples.length,p=total?successes/total:null,z=1.96;
 const center=total?(p+z*z/(2*total))/(1+z*z/total):null;
 const margin=total?z*Math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total):null;
 return {successes,total,probability:p,lower:total?Math.max(0,center-margin):null,upper:total?Math.min(1,center+margin):null};
}
