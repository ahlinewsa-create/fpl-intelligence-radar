"""Transparent ranking heuristics, not guaranteed point predictions."""
from collections import defaultdict


def current_event(data):
    events = data['events']
    next_event = next((e for e in events if e.get('is_next')), None)
    if next_event:
        return next_event
    return next((e for e in events if not e.get('finished')), None)


def ranked_players(data, fixtures_data, limit=20):
    event = current_event(data)
    if not event:
        return []
    gw = event['id']
    difficulties = defaultdict(list)
    for fixture in fixtures_data:
        if fixture.get('event') == gw and not fixture.get('finished'):
            home, away = fixture.get('team_h'), fixture.get('team_a')
            if home is not None:
                difficulties[home].append(int(fixture.get('team_h_difficulty') or 3))
            if away is not None:
                difficulties[away].append(int(fixture.get('team_a_difficulty') or 3))
    teams = {team['id']: team['short_name'] for team in data['teams']}
    positions = {p['id']: p['singular_name_short'] for p in data['element_types']}
    result = []
    for p in data['elements']:
        try:
            price = int(p['now_cost']) / 10
            form = float(p.get('form') or 0)
            ep = float(p.get('ep_next') or 0)
            minutes = int(p.get('minutes') or 0)
            chance = p.get('chance_of_playing_next_round')
            availability = float(chance) / 100 if chance is not None else (1.0 if p.get('status') == 'a' else 0.5)
            fixture_difficulty = difficulties.get(p['team'], [])
            fixture_factor = 1 + sum((3 - diff) * 0.04 for diff in fixture_difficulty)
            projection = max(0, (0.8 * ep + 0.2 * form) * fixture_factor * availability)
            result.append({'id': p['id'], 'name': p['web_name'], 'team': teams.get(p['team'], '?'),
                           'position': positions.get(p['element_type'], '?'), 'price': price,
                           'form': form, 'ep_next': ep, 'estimated_score': round(projection, 2),
                           'value': round(projection / max(price, 0.1), 3), 'minutes': minutes,
                           'status': p.get('status'), 'availability': availability})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    return sorted(result, key=lambda x: x['estimated_score'], reverse=True)[:limit]


def assess_team(picks, candidates):
    by_id = {p['id']: p for p in candidates}
    selected = [by_id[p['element']] for p in picks['picks'] if p['element'] in by_id]
    return {'matched_players': len(selected), 'captain_candidates': sorted(selected, key=lambda x: x['estimated_score'], reverse=True)[:3],
            'weakest_candidates': sorted(selected, key=lambda x: x['estimated_score'])[:3]}
