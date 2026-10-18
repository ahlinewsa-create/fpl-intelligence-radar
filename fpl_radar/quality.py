"""Quality gates for an actionable FPL report, without invented confidence."""
def audit_report(report):
    problems=[]
    desk=report.get('decision_desk') or {}
    team=report.get('team') or {}
    if not desk:
        problems.append('No personalized decision: verify manager data access.')
    if team and (team.get('matched_players') or 0)!=15:
        problems.append('The published 15-player squad was not fully matched.')
    candidates=report.get('multiweek_top') or []
    for row in candidates:
        if not 0 <= float(row.get('minutes_estimate') or 0) <= 90:
            problems.append('Out-of-range minute estimate.')
            break
    if desk:
        lineup=desk.get('starting') or []
        bench=desk.get('bench') or []
        if len(lineup)!=11 or len(bench)!=4:
            problems.append('The selected formation is not 11 starters plus four substitutes.')
        if len(set(lineup+bench))!=15:
            # Names may collide across players; IDs would be more reliable.
            problems.append('Check duplicate or ambiguous names in squad display.')
        if not desk.get('transfers'):
            manager=team.get('manager') or {}
            if manager.get('bank') is None:
                desk['transfer_explanation']='رصيد البنك غير متاح من البيانات المنشورة، فلا يمكن تأكيد القدرة على الشراء.'
            elif not manager.get('selling_prices_available'):
                desk['transfer_explanation']='أسعار البيع الشخصية غير متاحة من واجهة الجولة السابقة؛ لا يمكن تأكيد الانتقالات.'
            else:
                desk['transfer_explanation']='لم يظهر انتقال يحقق شروط الميزانية والمراكز وعدد اللاعبين من النادي وفق تقديراتنا.'
    chips=report.get('chip_strategy') or {}
    if chips and not chips.get('history_verified'):
        problems.append('Chip history was not verified.')
    if chips:
        advice=chips.get('recommendations') or []
        if len({a.get('chip') for a in advice})!=len(advice):
            problems.append('Duplicate chip recommendation.')
    return {'status':'review' if problems else 'ok', 'warnings':problems,
            'prediction_is_calibrated':False,
            'data_freshness':'Previous published gameweek squad; live squad is not authenticated.'}

def benchmark_forecasts(data, forecasts, gameweek):
    """Compare with public FPL ep_next, a baseline rather than actual results."""
    rows=[]
    for player in data.get('elements', []):
        predicted=forecasts.get(player.get('id'),{}).get('weeks',{}).get(gameweek)
        try:
            official=float(player.get('ep_next'))
            if predicted is None:continue
            rows.append({'name':player.get('web_name'), 'ours':float(predicted),
                         'fpl_ep_next':official,'difference':round(float(predicted)-official,2)})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda x:abs(x['difference']),reverse=True)
    return {'n':len(rows),
            'mean_absolute_disagreement':round(sum(abs(r['difference']) for r in rows)/len(rows),3) if rows else None,
            'outliers':rows[:8],
            'note':'Disagreement with FPL estimates does not measure predictive accuracy.'}
