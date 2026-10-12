"""Descriptive patterns from closed canonical episodes; no forecasting or fitting."""
import json
from collections import Counter,defaultdict
from datetime import datetime,date,timedelta,time
from pathlib import Path
from statistics import mean,median
from air_alerts.data import load_regions,daily_profiles,KYIV
root=Path(__file__).resolve().parents[1]
path=root/'dashboard/src/data.json'
data=json.loads(path.read_text())
regions,_=load_regions()
end=date(2026,10,12)
cutoff=datetime.combine(end,time(),KYIV).timestamp()
periods={'30':end-timedelta(days=30),'90':end-timedelta(days=90),'365':end-timedelta(days=365),'all':date(2023,1,1)}
wd=['Пн','Вт','Ср','Чт','Пт','Сб','Нд']
seasons=['Зима','Весна','Літо','Осінь']
rows=[]
def stats(a):
 return {'count':len(a),'mean':mean(a) if a else None,'median':median(a) if a else None}
for region,alerts in regions.items():
 complete=[a for a in alerts if a.end is not None and a.end<=cutoff and a.start>=datetime(2023,1,1,tzinfo=KYIV).timestamp()]
 days,profile=daily_profiles(complete,cutoff)
 daily={d:float(p.sum()) for d,p in zip(days,profile) if d<end}
 for period,begin in periods.items():
  calendar=[begin+timedelta(days=i) for i in range((end-begin).days)]
  events=[a for a in complete if begin<=a.local.date()<end]
  common={'region':region,'period':period,'begin':begin.isoformat(),'endExclusive':end.isoformat()}
  def add(kind,**r):rows.append({**common,'kind':kind,**r})
  n=len(calendar)
  durations=[a.duration for a in events]
  add('summary',**stats(durations),calendarDays=n,startsPerDay=len(events)/n,occupiedMinutes=sum(daily.get(d,0) for d in calendar))
  groups=defaultdict(list)
  for a in events:
   local=a.local
   for kind,key in [('hour',local.hour),('weekday',local.weekday()),('month',local.strftime('%Y-%m')),('season',(local.month%12)//3),('phase','Ніч' if local.hour>=22 or local.hour<6 else 'День'),('heat',(local.weekday(),local.hour)),('day',local.date())]:groups[(kind,key)].append(a.duration)
  for h in range(24):add('hour',label=f'{h:02d}',hour=h,startsPerDay=len(groups['hour',h])/n,**stats(groups['hour',h]))
  for w in range(7):
   exposure=sum(d.weekday()==w for d in calendar)
   add('weekday',label=wd[w],exposureDays=exposure,startsPerDay=len(groups['weekday',w])/exposure if exposure else None,**stats(groups['weekday',w]))
   for h in range(24):add('heat',weekday=wd[w],hour=f'{h:02d}:00',startsPerDay=len(groups['heat',(w,h)])/exposure if exposure else None,count=len(groups['heat',(w,h)]),exposureDays=exposure)
  monthExposure=Counter(d.strftime('%Y-%m') for d in calendar)
  for label,exposure in sorted(monthExposure.items()):add('month',label=label,startsPerDay=len(groups['month',label])/exposure,exposureDays=exposure,**stats(groups['month',label]))
  for season,label in enumerate(seasons):
   exposure=sum((d.month%12)//3==season for d in calendar)
   add('season',label=label,startsPerDay=len(groups['season',season])/exposure if exposure else None,exposureDays=exposure,**stats(groups['season',season]))
  for phase in ['День','Ніч']:add('phase',label=phase,startsPerDay=len(groups['phase',phase])/n,**stats(groups['phase',phase]))
  bins=[(0,15),(15,30),(30,60),(60,120),(120,240),(240,360),(360,float('inf'))]
  for lo,hi in bins:
   count=sum(lo<=v<hi for v in durations)
   add('histogram',label=f'{lo}–{hi}' if hi!=float('inf') else '≥360',count=count,share=count/len(durations) if durations else None)
  busiest=sorted(calendar,key=lambda d:daily.get(d,0),reverse=True)[:10]
  for d in busiest:add('top',date=d.isoformat(),count=len(groups['day',d]),minutes=daily.get(d,0))
source={**data['queries']['weekly_forecasts']['source'],'description':'Descriptive aggregates of closed canonical episodes, local Europe/Kyiv. Common end-exclusive 2026-10-12. Starts counted by local start time. Calendar-day exposure is an archive assumption, not verified feed uptime. Daily occupied minutes use union of intervals.'}
source['files']=source['files']+['scripts/add_exploration.py']
data['queries']['exploration']={'rows':rows,'source':source}
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Exported',len(rows),'descriptive aggregate rows; models and holdout unchanged.')
