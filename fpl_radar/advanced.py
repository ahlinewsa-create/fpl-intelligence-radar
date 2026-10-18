"""Advanced, read-only FPL analytics. Missing data is labeled rather than invented."""
from collections import defaultdict
from datetime import datetime, timezone

def safe_float(x, default=0.0):
    try: return float(x) if x is not None else default
    except (TypeError, ValueError): return default

def player_forecasts(data, fixtures, start_gw, horizon=5):
    """Independent estimates for each future GW; no reuse of ep_next beyond the next."""
    elements = data.get('elements', [])
    games = defaultdict(list)
    for f in fixtures:
        if f.get('event') is not None and start_gw <= f['event'] < start_gw+horizon and not f.get('finished'):
            for side in ('h','a'):
                games[(f.get('team_'+side),f['event'])].append(int(f.get('team_'+side+'_difficulty') or 3))
    forecasts={}
    for p in elements:
        availability=p.get('chance_of_playing_next_round')
        chance=max(0.0,min(1.0,safe_float(availability)/100 if availability is not None else (1.0 if p.get('status')=='a' else (0.0 if p.get('status')=='u' else .5))))
        minutes=safe_float(p.get('minutes'))
        starts=safe_float(p.get('starts'))
        minutes_per_start=min(90.0,max(0.0,(minutes/max(starts,1)) if starts else (minutes/max(1,start_gw-1))))
        minute_factor=min(1.,minutes_per_start/80)
        form=safe_float(p.get('form'))
        ep=safe_float(p.get('ep_next'))
        future_base=.35*form+.65*safe_float(p.get('points_per_game'),form)
        by_gw={}
        for gw in range(start_gw,start_gw+horizon):
            ds=games.get((p.get('team'),gw),[])
            base=(.65*ep+.35*form) if gw==start_gw else future_base
            by_gw[gw]=round(min(20.0,max(0,base*sum(1+(3-d)*.08 for d in ds)*chance*minute_factor)),2)
        forecasts[p['id']]={'weeks':by_gw, 'total':round(sum(by_gw.values()),2),
                             'availability':round(chance,2), 'minutes_estimate':round(minutes_per_start,1),
                             'name':p.get('web_name'), 'xg_season_total':safe_float(p.get('expected_goals')), 'xa_season_total':safe_float(p.get('expected_assists')),
                             'defensive_contributions':safe_float(p.get('defensive_contribution')),
                             'ownership_pct':safe_float(p.get('selected_by_percent'))}
    return forecasts

def injury_watch(data):
    return [{'player':p.get('web_name'), 'status':p.get('status'), 'news':p.get('news') or '',
             'chance_next':p.get('chance_of_playing_next_round')}
            for p in data.get('elements',[]) if p.get('status') not in ('a',None) or p.get('news')]

def price_watch(data, limit=12):
    p=data.get('elements',[])
    rising=sorted(p,key=lambda x:safe_float(x.get('transfers_in_event'))-safe_float(x.get('transfers_out_event')),reverse=True)
    falling=list(reversed(rising))
    def fmt(group):
        return [{'player':x.get('web_name'),'price':safe_float(x.get('now_cost'))/10,
                 'net_transfers':int(safe_float(x.get('transfers_in_event'))-safe_float(x.get('transfers_out_event'))),
                 'price_change_this_round':safe_float(x.get('cost_change_event'))/10} for x in group[:limit]]
    return {'demand_rising':fmt(rising),'demand_falling':fmt(falling),
            'warning':'Transfer demand is not a reliable price-change prediction.'}

def ownership_differentials(data, forecasts, limit=12):
    names={p['id']:p for p in data.get('elements',[])}
    options=[]
    for pid, forecast in forecasts.items():
        p=names[pid]
        ownership=safe_float(p.get('selected_by_percent'))
        if ownership<12 and forecast['total']>0 and forecast['availability']>=.75:
            options.append({'name':p.get('web_name'),'ownership_pct':ownership,
                            'five_week_estimate':forecast['total'],'player_id':pid})
    return sorted(options,key=lambda p:p['five_week_estimate'],reverse=True)[:limit]

def blank_double(fixtures, start_gw, horizon=6):
    team_counts=defaultdict(lambda:defaultdict(int))
    teams=set()
    for f in fixtures:
        a,b=f.get('team_h'),f.get('team_a')
        if a is not None: teams.add(a)
        if b is not None: teams.add(b)
        if f.get('event') is None or not start_gw<=f['event']<start_gw+horizon: continue
        if a is not None:team_counts[f['event']][a]+=1
        if b is not None:team_counts[f['event']][b]+=1
    return [{'gw':gw,'blank_team_ids':sorted(teams-set(team_counts[gw])),
             'double_team_ids':sorted(t for t,n in team_counts[gw].items() if n>1)}
            for gw in range(start_gw,start_gw+horizon)]

def manager_snapshot(entry, picks):
    hist=picks.get('entry_history') or {}
    return {'entry_name':entry.get('name'), 'overall_rank':hist.get('overall_rank'),
            'gameweek_points':hist.get('points'), 'bank':(hist.get('bank')/10 if isinstance(hist.get('bank'),(int,float)) else None),
            'team_value':(hist.get('value')/10 if isinstance(hist.get('value'),(int,float)) else None),
            'event_transfers_cost':hist.get('event_transfers_cost'),
            'selling_prices_available':all(isinstance(p.get('selling_price'),int) for p in picks.get('picks',[]))}

def transfers_with_prices(current_picks, available, forecasts, bank, free_transfers=None, horizon=5, limit=8):
    """Only issue affordable, same-role, club-legal, one-transfer suggestions."""
    if bank is None: return {'status':'missing_bank','ideas':[]}
    ids={p['id'] for p in current_picks}
    counts=defaultdict(int)
    for p in current_picks:counts[p['team_id']]+=1
    ideas=[]
    for old in current_picks:
        selling=old.get('selling_price')
        if selling is None: continue
        for new in available:
            if new['id'] in ids or new['position']!=old['position']:continue
            if new['price']>selling+bank+1e-8:continue
            if counts[new['team_id']]-(old['team_id']==new['team_id'])>=3:continue
            gain=forecasts.get(new['id'],{}).get('total',0)-forecasts.get(old['id'],{}).get('total',0)
            if gain>0: ideas.append({'sell':old['name'],'buy':new['name'],'gain_next_weeks':round(gain,2),
                                    'cash_remaining':round(bank+selling-new['price'],2),
                                    'free_transfers_verified':free_transfers is not None})
    return {'status':'historical_estimates_only','horizon':horizon,'free_transfers':free_transfers,
            'warning':'Verify current squad and free transfers before acting; past GW picks may be stale.',
            'ideas':sorted(ideas,key=lambda x:x['gain_next_weeks'],reverse=True)[:limit]}

def backtest(previous_forecasts, actual_points):
    pairs=[(float(pred),float(actual_points[str(pid)]))
           for pid,pred in previous_forecasts.items() if str(pid) in actual_points]
    if not pairs:return {'sample_size':0,'mae':None}
    return {'sample_size':len(pairs),'mae':round(sum(abs(a-b) for a,b in pairs)/len(pairs),3)}
