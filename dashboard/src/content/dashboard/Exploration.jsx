import React,{useState} from 'react';
import {DataComponent,EvidenceChart,Section} from '../../data-app-public.jsx';
import {minutes} from './forecast.js';
const weekdays=['Пн','Вт','Ср','Чт','Пт','Сб','Нд'];
const hourOrder=Array.from({length:24},(_,i)=>`${String(i).padStart(2,'0')}:00`);
export function Exploration({region,snapshot,names}){
 const [period,setPeriod]=useState('365'),[panel,setPanel]=useState('hourly'),[metric,setMetric]=useState('startsPerDay');
 const all=snapshot.queries.exploration?.rows??[];
 const selected=all.filter(r=>r.region===region&&r.period===period);
 const kind=k=>selected.filter(r=>r.kind===k),summary=kind('summary')[0];
 const valueLabel=metric==='startsPerDay'?'Стартів на календарний день':'Середня тривалість · хв';
 const chart=(id,title,rows,type='bar',y=metric,height=260)=> <EvidenceChart id={id} queryId="exploration" title={title} variant="card" sourceRows={rows} rows={rows} height={height} spec={{type,x:'label',xLabel:rows[0]?.kind==='histogram'?'Тривалість · хв':rows[0]?.kind==='hour'?'Година початку':undefined,y,rowHeight:type==='horizontalBar'?24:undefined,showValues:type==='horizontalBar',stackable:false,valueDecimals:y==='startsPerDay'?2:1,yLabel:y==='count'?'Кількість тривог':y==='mean'?'Хвилини':valueLabel,colors:{[y]:'var(--chart-1)'}}}/>;
 const regional=all.filter(r=>r.period===period&&r.kind==='summary'&&r.mean!=null).map(r=>({...r,label:(names[r.region]??r.region).replace(' область','').replace('Івано-Франківська','Ів.-Франківська')})).sort((a,b)=>b.mean-a.mean);
 const peak=kind('hour').reduce((best,r)=>!best||r.count>best.count?r:best,null);
 if(!summary)return <p>Готуються дані початкового аналізу.</p>;
 return <>
  <div className="aa-intro aa-planner-purpose"><div><h2>Початковий аналіз і пошук закономірностей</h2><p>Де й коли починаються тривоги, як змінюється їхня тривалість та які дні були найбільш завантаженими. Оберіть область угорі й період нижче. Це опис минулих спостережень, а не прогноз і не доказ причини загроз.</p></div></div>
  <div className="aa-controls"><label className="aa-field"><span>Період аналізу · повні дні</span><select aria-label="Період аналізу" value={period} onChange={e=>setPeriod(e.target.value)}><option value="30">Останні 30 днів</option><option value="90">Останні 90 днів</option><option value="365">Останні 365 днів</option><option value="all">Від 1 січня 2023 року</option></select></label>{panel==='calendar'&&<label className="aa-field"><span>Показник графіків</span><select aria-label="Показник закономірностей" value={metric} onChange={e=>setMetric(e.target.value)}><option value="startsPerDay">Частота стартів · на день</option><option value="mean">Середня тривалість · хв</option></select></label>}</div>
  <div className="aa-explore-stats" data-reviewed-rows><div><span>Завершених тривог</span><strong>{summary.count.toLocaleString('uk-UA')}</strong></div><div><span>Середня тривалість</span><strong>{minutes(summary.mean)}</strong></div><div><span>Медіанна тривалість</span><strong>{minutes(summary.median)}</strong></div><div><span>Період</span><strong>{summary.begin} → 2026-10-11</strong></div></div>
  <nav className="aa-explore-nav" aria-label="Види початкового аналізу">{[['hourly','За годинами'],['calendar','Тиждень, місяць і сезон'],['duration','Тривалість і області']].map(([id,label])=><button className="aa-button" key={id} aria-pressed={panel===id} onClick={()=>setPanel(id)}>{label}</button>)}</nav>
  <p className="aa-footnote">Час — Europe/Kyiv. День: 06:00–22:00, ніч: 22:00–06:00; групуємо за початком тривоги, а не типом зброї. Частота нормована на число календарних днів відповідної групи. У тривалості враховані лише завершені записи; незавершені та записи з імітованим кінцем виключені. Повнота роботи джерела історично не підтверджена; відсутність запису не доводить відсутність тривоги. Для часткових місяців і сезонів вказаний період має значення.</p>
  {panel==='hourly'&&<>
   <p className="aa-muted">Найбільше стартів у вибірці: {peak.label}:00–{String(peak.hour+1).padStart(2,'0')}:00 ({peak.count} записів). Середнє може зростати через окремі дуже довгі тривоги, тому порівнюйте його з медіаною.</p>
   <div className="aa-explore-grid">{chart('eda-hour-count','Кількість стартів за годиною початку',kind('hour'),'bar','count')}{chart('eda-hour-duration','Середня тривалість за годиною початку',kind('hour'),'line','mean')}</div>
   <div className="aa-explore-grid">{chart('eda-hour-hist','Розподіл тривалості тривог',kind('histogram'),'bar','count')}
    <DataComponent id="eda-top-days" queryId="exploration" title="10 найбільш завантажених днів" kind="table" variant="card" sourceRows={kind('top')} displayRows={kind('top')}><div className="aa-table-scroll"><table><thead><tr><th>Дата</th><th>Стартів</th><th>Час під тривогою</th></tr></thead><tbody>{kind('top').map(r=><tr key={r.date}><th>{r.date}</th><td>{r.count}</td><td>{minutes(r.minutes)}</td></tr>)}</tbody></table></div><p className="aa-footnote">Рейтинг за сумарним часом під тривогою в межах місцевого дня. Інтервали об’єднані: перекриття не рахується двічі. Тривога, що почалася раніше й перейшла через північ, може дати зайнятий день без нових стартів.</p></DataComponent>
   </div>
  </>}
  {panel==='calendar'&&<>
   <EvidenceChart id="eda-hour-week-heat" queryId="exploration" title="Щільність стартів · день тижня × година" variant="card" sourceRows={kind('heat')} rows={kind('heat')} height={570} spec={{type:'heatmap',x:'weekday',y:'startsPerDay',series:'hour',categoryOrder:weekdays,seriesOrder:hourOrder,rowHeight:20,reverseRows:true,valueDecimals:2,showValues:false,missingValues:'gap',colorScaleStartAtZero:true,baseColor:'var(--chart-4)',xLabel:'День тижня',yLabel:'Година початку',tooltipFields:[{field:'count',label:'Стартів у вибірці'},{field:'exposureDays',label:'Календарних днів'}]}}/>
   <p className="aa-footnote">Колір показує середню кількість стартів у цю годину на один відповідний день тижня. Нуль — немає записаних стартів; пропуск — немає календарної експозиції.</p>
   <div className="aa-explore-grid">{chart('eda-weekday','За днем тижня',kind('weekday'))}{chart('eda-month','За календарним місяцем',kind('month'),'line')}{chart('eda-season','За сезоном',kind('season'))}{chart('eda-daynight','Початок удень і вночі',kind('phase'))}</div>
  </>}
  {panel==='duration'&&<>
   <Section id="eda-regional" title="Порівняння регіонів">{chart('eda-region-duration','Середня тривалість тривоги за регіоном',regional,'horizontalBar','mean',600)}<p className="aa-footnote">Однаковий календарний період для всіх регіонів. Київ — офіційне міське джерело, області — волонтерський архів; відмінності можуть частково пояснюватися різною повнотою й деталізацією джерел. Обласні дані не є статистикою конкретного міста.</p></Section>
   <div className="aa-explore-grid">{chart('eda-duration-hist','Розподіл тривалості в обраному регіоні',kind('histogram'),'bar','count')}{chart('eda-duration-start','Тривалість за годиною початку в обраному регіоні',kind('hour'),'line','mean')}</div>
  </>}
 </>;
}
