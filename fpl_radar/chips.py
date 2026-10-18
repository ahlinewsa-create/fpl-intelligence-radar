"""Conservative 2026/27 chip recommendations. One chip per GW, two distinct halves."""
CHIPS = ('wildcard', 'freehit', 'bboost', '3xc')

def recommend_chips(week, fixtures, players, squad, used_chips=(), history_verified=False):
    """Advice only. Check upcoming schedule and published chip history; never auto-activate."""
    if week is None:
        return {'decision': 'بيانات الجولة غير متاحة', 'recommendations': []}
    end = 19 if week <= 19 else 38
    remaining = end - week + 1
    used = set()
    previous_freehit_gw19 = False
    for item in used_chips:
        name = item.get('name') if isinstance(item, dict) else item
        event = item.get('event') if isinstance(item, dict) else None
        if name == 'freehit' and event == 19:
            previous_freehit_gw19 = True
        if name in CHIPS and (event is None or (event <= 19) == (week <= 19)):
            used.add(name)
    pool = {p['id']: p for p in players}
    by_week = {}
    for f in fixtures:
        event = f.get('event')
        if event is None or not week <= event <= min(end, week + 5):
            continue
        for side in ('h', 'a'):
            by_week.setdefault(event, {}).setdefault(f.get('team_' + side), 0)
            by_week[event][f.get('team_' + side)] += 1
    selected = [pool[p['element']] for p in squad.get('picks', []) if p.get('element') in pool] if isinstance(squad, dict) else []
    safe = len(selected) == 15
    recommendations = []
    for gw in range(week, min(end, week + 5) + 1):
        counts = by_week.get(gw, {})
        double_teams = {team for team, count in counts.items() if count > 1}
        if safe:
            fixtures_available = sum(1 for p in selected if counts.get(p['team_id'], 0))
            double_count = sum(1 for p in selected if p['team_id'] in double_teams)
            weak = sum(1 for p in selected if p['availability'] < .75 or p['estimated_score'] < 2.2)
            from .strategy import starting_eleven
            try:
                bench_ids = set(starting_eleven(selected)['bench_ids'])
                bench_estimate = sum(p['estimated_score'] for p in selected if p['id'] in bench_ids)
            except (ValueError, KeyError):
                bench_estimate = 0
            captain = max(selected, key=lambda p: p['estimated_score'])
            captain_estimate = captain['estimated_score']
        else:
            fixtures_available = double_count = weak = 0
            bench_estimate = captain_estimate = 0
        signals = {
            'wildcard': (False, f'وجود {weak} نقاط ضعف وحده لا يثبت جدوى الوايلد كارد؛ يلزم تقييم مكسبها مقابل الانتظار'),
            'freehit': (fixtures_available <= 8 and safe, f'{fixtures_available} لاعبين من فريقك لديهم مباريات في الجولة'),
            'bboost': (safe and bench_estimate >= 12 and fixtures_available >= 14, f'تقدير نقاط الدكة {bench_estimate:.1f}'),
            '3xc': (safe and captain_estimate >= 8 and (captain['team_id'] in double_teams or captain_estimate >= 11),
                    f'تقدير نقاط الكابتن الأساسية {captain_estimate:.1f}')
        }
        if remaining <= 4 and gw >= end - 3:
            for chip in CHIPS:
                if chip == 'freehit' and gw == 20 and previous_freehit_gw19:
                    continue
                if chip in used:
                    continue
                active, reason = signals[chip]
                if active:
                    recommendations.append({'gameweek': gw, 'chip': chip, 'confidence': 'متوسط', 'reason': reason})
                elif gw == end:
                    recommendations.append({'gameweek': gw, 'chip': chip, 'confidence': 'منخفض',
                                            'reason': 'آخر فرصة لهذه الخاصية في نصف الموسم؛ تقييمها ضعيف بالبيانات الحالية'})
        else:
            for chip, (active, reason) in signals.items():
                if chip == 'freehit' and gw == 20 and previous_freehit_gw19:
                    continue
                if active and chip not in used:
                    recommendations.append({'gameweek': gw, 'chip': chip, 'confidence': 'متوسط', 'reason': reason})
    # Never recommend two chips in the same round; prioritize strength and shorter horizon.
    priorities = {'freehit': 0, 'wildcard': 1, 'bboost': 2, '3xc': 3}
    recommendations.sort(key=lambda x: (x['gameweek'], x['confidence'] == 'منخفض', priorities[x['chip']]))
    picks, taken = [], set()
    for item in recommendations:
        if item['gameweek'] not in taken:
            picks.append(item)
            taken.add(item['gameweek'])
    unique = {}
    for item in sorted(picks, key=lambda p: (p['confidence'] != 'متوسط', p['gameweek'])):
        unique.setdefault(item['chip'], item)
    selected_advice = sorted(unique.values(), key=lambda p:p['gameweek']) if history_verified else []
    return {
        'half': 'الأول' if week <= 19 else 'الثاني',
        'chip_deadline_gameweek': end, 'weeks_remaining': remaining,
        'used_chips': sorted(used),
        'history_verified': history_verified,
        'decision': 'لا يُنصح بالوايلد كارد دون مقارنة خطتي التفعيل والانتظار؛ إشارات الخواص الأخرى مبدئية. تحقق من قواعد الموسم والمهل الرسمية.',
        'recommendations': selected_advice,
        'unused_count': len(CHIPS) - len(used),
        'urgency_note': ('تبقى %d خواص غير مستخدمة في النصف الحالي؛ لا يمكن استخدام أكثر من خاصية واحدة في الجولة.' % (len(CHIPS) - len(used))) if remaining <= 4 else '',
        'no_action': not bool(selected_advice),
        'rule': 'خاصية واحدة فقط لكل جولة'
    }
