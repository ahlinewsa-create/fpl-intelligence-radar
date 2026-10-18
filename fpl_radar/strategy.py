"""Explainable FPL planning heuristics. Read-only recommendations."""
from collections import defaultdict

ROLES = {'GKP': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}

def fixture_matrix(fixtures, week, horizon=5):
    result = defaultdict(lambda: defaultdict(list))
    for f in fixtures:
        gw = f.get('event')
        if gw is None or not week <= gw < week + horizon:
            continue
        for side in ('h', 'a'):
            team = f.get('team_' + side)
            if team is not None:
                result[str(team)][str(gw)].append(int(f.get('team_' + side + '_difficulty') or 3))
    return {team: dict(games) for team, games in result.items()}

def team_strength(data):
    return sorted([{'team': t.get('name'), 'id': t['id'],
                    'attack_home': t.get('strength_attack_home'),
                    'attack_away': t.get('strength_attack_away'),
                    'defence_home': t.get('strength_defence_home'),
                    'defence_away': t.get('strength_defence_away')}
                   for t in data['teams']],
                  key=lambda t: (t['attack_home'] or 0) + (t['attack_away'] or 0), reverse=True)

def captains(players, count=5):
    return [{'id': p['id'], 'name': p['name'],
             'projected_double_points': round(2 * p['estimated_score'], 2),
             'availability': p['availability']}
            for p in sorted(players, key=lambda x: x['estimated_score'], reverse=True)[:count]]

def starting_eleven(squad):
    if len(squad) != 15 or len({p['id'] for p in squad}) != 15:
        raise ValueError('Expected 15 unique squad members')
    groups = defaultdict(list)
    for p in squad:
        groups[p['position']].append(p)
    if any(len(groups[role]) != size for role, size in ROLES.items()):
        raise ValueError('Invalid 15-player squad roles')
    for members in groups.values():
        members.sort(key=lambda p: p['estimated_score'], reverse=True)
    formations = []
    for d in range(3, 6):
        for m in range(2, 6):
            f = 10 - d - m
            if 1 <= f <= 3:
                lineup = groups['GKP'][:1] + groups['DEF'][:d] + groups['MID'][:m] + groups['FWD'][:f]
                formations.append((sum(p['estimated_score'] for p in lineup), lineup))
    score, xi = max(formations, key=lambda item: item[0])
    starters = {p['id'] for p in xi}
    return {'starting_ids': [p['id'] for p in xi],
            'bench_ids': [p['id'] for p in squad if p['id'] not in starters],
            'projected_points': round(score, 2), 'captain': captains(xi, 1)[0]}

def transfer_ideas(squad, market, bank=0.0, free_transfers=1, limit=5):
    """Indicative one-transfer changes; account selling prices may differ."""
    if free_transfers < 1:
        return []
    owned = {p['id'] for p in squad}
    counts = defaultdict(int)
    for p in squad:
        counts[p['team_id']] += 1
    moves = []
    for old in squad:
        for new in market:
            if new['id'] in owned or new['position'] != old['position']:
                continue
            if new['price'] > old['price'] + bank + 1e-8:
                continue
            if counts[new['team_id']] - (old['team_id'] == new['team_id']) >= 3:
                continue
            gain = new['estimated_score'] - old['estimated_score']
            if gain > 0:
                moves.append({'sell': old['name'], 'buy': new['name'],
                              'sell_id': old['id'], 'buy_id': new['id'],
                              'estimated_gain_next_week': round(gain, 2)})
    return sorted(moves, key=lambda x: x['estimated_gain_next_week'], reverse=True)[:limit]

def suggested_squad(market, budget=100.0):
    """Greedy valid initial squad plus local upgrades; not a global optimum."""
    members = []
    spent = 0.0
    clubs = defaultdict(int)
    for role, required in ROLES.items():
        eligible = sorted((p for p in market if p['position'] == role),
                          key=lambda p: p['price'])
        for p in eligible:
            if sum(x['position'] == role for x in members) == required:
                break
            if p['id'] in {x['id'] for x in members} or clubs[p['team_id']] >= 3:
                continue
            if spent + p['price'] > budget:
                continue
            members.append(p)
            spent += p['price']
            clubs[p['team_id']] += 1
    if len(members) != 15:
        return {'status': 'infeasible', 'reason': 'Insufficient budget or eligible players'}
    for _ in range(3):
        changed = False
        for old in sorted(members, key=lambda x: x['estimated_score']):
            for p in sorted(market, key=lambda x: x['estimated_score'], reverse=True):
                if p['id'] in {x['id'] for x in members} or p['position'] != old['position']:
                    continue
                if spent - old['price'] + p['price'] > budget + 1e-8:
                    continue
                if clubs[p['team_id']] - (p['team_id'] == old['team_id']) >= 3:
                    continue
                if p['estimated_score'] <= old['estimated_score']:
                    continue
                members.remove(old)
                members.append(p)
                spent += p['price'] - old['price']
                clubs[old['team_id']] -= 1
                clubs[p['team_id']] += 1
                changed = True
                break
        if not changed:
            break
    return {'status': 'ok', 'cost': round(spent, 1),
            'players': [{'id': p['id'], 'name': p['name'], 'position': p['position'], 'price': p['price']} for p in members],
            'lineup': starting_eleven(members)}
