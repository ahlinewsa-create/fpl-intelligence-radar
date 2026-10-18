"""Persist pre-deadline forecasts and evaluate them only after final FPL results."""
import json
from datetime import datetime, timezone
from pathlib import Path
from .sources import get_json, FPL

def snapshot(report, directory='data/forecast_history'):
    event=report.get('gameweek')
    if not isinstance(event,int):
        return {'status':'no_gameweek'}
    root=Path(directory)
    root.mkdir(parents=True,exist_ok=True)
    destination=root/f'gw_{event:02d}.json'
    if destination.exists():
        return {'status':'already_saved','path':str(destination)}
    raw=report.get('player_forecasts_for_archive') or {}
    if not raw:
        return {'status':'no_projections'}
    payload={'gw':event,'recorded_at':datetime.now(timezone.utc).isoformat(),
             'predictions':{str(pid):round(float(value),3) for pid,value in raw.items()}}
    destination.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'saved','path':str(destination),'count':len(raw)}

def evaluate(data, directory='data/forecast_history'):
    root=Path(directory)
    completed={int(e['id']) for e in data.get('events',[]) if e.get('finished')}
    results=[]
    for path in sorted(root.glob('gw_*.json')):
        try:
            record=json.loads(path.read_text(encoding='utf-8'))
            gw=int(record['gw'])
            if gw not in completed: continue
            live=get_json(f'{FPL}/event/{gw}/live/')
            actual={str(x['id']):x['stats'].get('total_points') for x in live.get('elements',[])}
            pairs=[(float(pred),float(actual[pid])) for pid,pred in record['predictions'].items()
                   if pid in actual and actual[pid] is not None]
            if not pairs:continue
            mae=sum(abs(a-b) for a,b in pairs)/len(pairs)
            bias=sum(a-b for a,b in pairs)/len(pairs)
            results.append({'gw':gw,'players':len(pairs),'mae':round(mae,3),
                            'bias':round(bias,3),'sample':'Pre-deadline archived predictions only'})
        except (OSError,KeyError,ValueError,TypeError) as exc:
            results.append({'status':'evaluation_error','file':path.name,'error':type(exc).__name__})
    return {'rounds':results,'evaluated_rounds':sum('mae' in r for r in results)}
