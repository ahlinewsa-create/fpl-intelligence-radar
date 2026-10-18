import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .sources import bootstrap, fixtures, public_team, history_csv, statsbomb_competitions
from .analysis import ranked_players, current_event, assess_team
from .strategy import fixture_matrix, team_strength, captains, suggested_squad, starting_eleven, transfer_ideas

def build_report(data, games, team_id=None):
    event = current_event(data)
    players = ranked_players(data, games, limit=len(data['elements']))
    top = players[:20]
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'gameweek': event['id'] if event else None,
        'methodology': 'Uncalibrated heuristic of ep_next, form, fixtures and availability',
        'top_players': top,
        'value_picks': sorted(players, key=lambda p: p['value'], reverse=True)[:15],
        'captain_candidates': captains(players),
        'fixture_difficulty_next_5': fixture_matrix(games, event['id']) if event else {},
        'team_strength': team_strength(data),
        'suggested_squad': suggested_squad(players),
        'sources': ['FPL bootstrap-static', 'FPL fixtures']
    }
    if team_id and event and event['id'] > 1:
        previous = public_team(team_id, event['id'] - 1)
        report['team'] = assess_team(previous['picks'], players)
        by_id = {p['id']: p for p in players}
        squad = [by_id[x['element']] for x in previous['picks']['picks'] if x['element'] in by_id]
        if len(squad) == 15:
            report['team']['starting_eleven'] = starting_eleven(squad)
            report['team']['transfer_ideas'] = transfer_ideas(squad, players)
        report['team']['note'] = 'Previous GW public picks, indicative prices only; no future transfers exposed.'
    return report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='reports/latest.json')
    ap.add_argument('--team-id', type=int, default=None)
    ap.add_argument('--check-sources', action='store_true')
    args = ap.parse_args()
    if args.check_sources:
        results = {}
        for name, fn in [('fpl', bootstrap), ('fixtures', fixtures), ('historical', history_csv), ('statsbomb', statsbomb_competitions)]:
            try:
                result = fn()
                results[name] = {'ok': True, 'records': len(result) if isinstance(result, list) else len(result.get('elements', []))}
            except Exception as ex:
                results[name] = {'ok': False, 'error': f'{type(ex).__name__}: {ex}'}
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if not results['fpl']['ok'] or not results['fixtures']['ok']:
            raise SystemExit(1)
        return
    report = build_report(bootstrap(), fixtures(), args.team_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Wrote {output} for GW {report["gameweek"]}')

if __name__ == '__main__':
    main()
