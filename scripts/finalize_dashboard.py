"""Bind the reviewed raw preview and mark the dashboard ready for packaging."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'dashboard/src/data.json'
data=json.loads(path.read_text())
data['queries']['source_preview']={'rows':data['sourcePreview'],'source':data['queries']['replay']['source']}
data['buildStatus']='complete'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
