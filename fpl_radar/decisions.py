"""Actionable but cautious FPL decision desk; uses only published data."""
from .strategy import starting_eleven

def decision_desk(squad, market, forecasts, bank, event, deadline=None):
    if len(squad) != 15:
        return {'action':'راجع بيانات فريقك','reason':'لم تُسترجع تشكيلة كاملة','transfers':[]}
    by_id={p['id']:p for p in squad}
    lineup=starting_eleven(squad)
    starting=[by_id[i] for i in lineup['starting_ids']]
    bench=[by_id[i] for i in lineup['bench_ids']]
    captain=sorted(starting,key=lambda p:forecasts.get(p['id'],{}).get('weeks',{}).get(event,0),reverse=True)
    owned=set(by_id)
    clubs={}
    for p in squad:clubs[p['team_id']]=clubs.get(p['team_id'],0)+1
    moves=[]
    watchlist=[]
    flagged=[]
    if bank is not None:
        for old in squad:
            selling=old.get('selling_price')
            price_verified=selling is not None
            if selling is None:
                selling=old.get('price')  # Indicative only: current price is not selling price.
            if selling is None:continue
            for new in market:
                if new['id'] in owned or new['position']!=old['position']:continue
                status=new.get('fpl_status')
                probability=new.get('chance_of_playing_next_round')
                if status not in (None,'a') or (probability is not None and float(probability)<75) or new.get('availability',0)<.75:continue
                affordable=new['price']<=selling+bank+.00001
                if not affordable:continue
                if clubs.get(new['team_id'],0)-(old['team_id']==new['team_id'])>=3:continue
                oldf=forecasts.get(old['id'],{}).get('weeks',{})
                newf=forecasts.get(new['id'],{}).get('weeks',{})
                week_gain=newf.get(event,0)-oldf.get(event,0)
                old_total=sum(oldf.get(g,0) for g in range(event,event+5))
                new_total=sum(newf.get(g,0) for g in range(event,event+5))
                total_gain=new_total-old_total
                # Extremely low five-week baseline is a data-quality warning, not a reliable giant gain.
                if old_total < 5 and old.get('fpl_status','a') == 'a' and old.get('availability',1)>=.75:
                    flagged.append({'sell':old['name'],'buy':new['name'],'old_5gw':round(old_total,2), 'new_5gw':round(new_total,2),'reason':'توقع اللاعب المباع منخفض جداً ويحتاج مراجعة المباريات والدقائق'})
                    continue
                if total_gain>2 and week_gain>-.5:
                    target=moves if price_verified else watchlist
                    target.append({'sell':old['name'],'buy':new['name'],'cost':new['price'],
                                  'sell_price':selling,'bank_after':round(bank+selling-new['price'],1),
                                  'gain_5gw':round(total_gain,2),'gain_next':round(week_gain,2),
                                  'old_5gw':round(old_total,2),'new_5gw':round(new_total,2),
                                  'price_verified':price_verified})
    # Highly uncertain recovery estimates must not masquerade as validated gains.
    moves.sort(key=lambda x:x['gain_5gw'],reverse=True)
    watchlist.sort(key=lambda x:x['gain_5gw'],reverse=True)
    for item in moves+watchlist:
        item['estimate_warning']='تقديرات خمس جولات تتأثر بافتراضات تعافي المصابين؛ ليست مكسباً مضموناً.'
    # No implied hit or confirmation of actual free-transfer count; this is a published-GW plan.
    recommended= moves[0] if moves and moves[0]['gain_5gw']>=5 else None
    if recommended:
        action='انتقال يستحق المراجعة'
        reason='أفضل انتقال متاح مالياً وفق بيانات الجولة المنشورة، بشرط تأكيد الانتقالات المجانية والأسعار الحالية'
    else:
        action='الاحتفاظ بالانتقال مؤقتاً'
        reason='لا يوجد مكسب واضح يستحق انتقالاً وفق نموذج التقديرات الحالي، أو أسعار البيع غير متاحة'
    captain_scores=[{'name':p['name'],'points':round(forecasts.get(p['id'],{}).get('weeks',{}).get(event,0),2)} for p in captain[:3]]
    return {'action':action,'reason':reason,'captain_comparison':captain_scores,'confidence':'منخفضة — نموذج غير معاير',
            'captain':captain[0]['name'] if captain else None,
            'vice_captain':captain[1]['name'] if len(captain)>1 else None,
            'starting': [p['name'] for p in starting],
            'bench':[p['name'] for p in bench],
            'bench_estimate':round(sum(forecasts.get(p['id'],{}).get('weeks',{}).get(event,0) for p in bench),2),
            'transfers':moves[:3],'watchlist':watchlist[:3],'forecast_anomalies':flagged[:3],'best_transfer':recommended,'deadline':deadline,
            'data_note':'تشكيلة الجولة السابقة؛ ليست تأكيداً لتشكيلتك الحالية. لا تنفذ انتقالات تلقائياً.'}
