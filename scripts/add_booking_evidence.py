"""Export calibration residuals for exploratory booking probabilities, without reselection."""
import json
from datetime import date
from pathlib import Path
from air_alerts.data import load_regions, daily_profiles, working_load
from air_alerts.models import PlannerModel
from air_alerts.pipeline import PROTOCOL, planner_eval, clean
root=Path(__file__).resolve().parents[1]
path=root/'dashboard/src/data.json'
data=json.loads(path.read_text())
selection=json.loads((root/'reports/selection.json').read_text())
regions,_=load_regions()
rows=[]
for region,alerts in regions.items():
 days,profile=daily_profiles(alerts,max(a.start for a in regions['Kyiv City']))
 for sh,eh in PROTOCOL['planner_shifts']:
  shift=f'{sh}-{eh}'
  loads=working_load(profile,sh,eh)
  name=selection['regions'][region]['shifts'][shift]['selected']
  model=PlannerModel(name).fit(days,loads,date.fromisoformat(PROTOCOL['planner_fit_end']))
  samples=planner_eval(model,days,loads,date.fromisoformat(PROTOCOL['planner_calibration_start']),date.fromisoformat(PROTOCOL['planner_calibration_end_exclusive']),(eh-sh)*60)
  rows.extend({**r,'region':region,'shift':shift,'residual':r['actual']-r['point']} for r in samples)
data['queries']['booking_calibration']={'rows':clean(rows),'source':{**data['queries']['weekly_forecasts']['source'],'description':'Frozen selected models; rolling weekly calibration 2026-05-11 through 2026-09-27. Each horizon has 20 weekly observations. Empirical residual frequency is exploratory, not a calibrated future safety probability.'}}
data['buildStatus']='complete'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Exported',len(rows),'calibration residuals without changing selected models or holdout results.')
