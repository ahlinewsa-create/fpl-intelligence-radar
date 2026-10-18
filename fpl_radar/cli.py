import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .sources import bootstrap, fixtures, public_team, history_csv, statsbomb_competitions
from .analysis import ranked_players, current_event, assess_team


def build_report(data, games, team_id=None):
    event = current_event(data)
    players = ranked_players(data, games, limit=1000)
    top = players[:20]
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'gameweek': event['id'] if event else None,
              'methodology': 'Heuristic using official ep_next, recent form, fixture difficulty and availability; not a guarantee',
              'top_players': top, 'value_picks': sorted(players, key=lambda x: x['value'], reverse=True)[:15],
              'captain_candidates': top[:3], 'sources': ['FPL bootstrap-static', 'FPL fixtures']}
    if team_id and event and int(event['id']) > 1:
        report['team'] = assess_team(public_team(team_id, int(event['id']) - 1)['picks'], players)
        report['team']['note'] = 'Public picks from previous GW; does not reveal unannounced future transfers.'
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
    print(f'Wrote {output} with GW {report["gameweek"]}')

if __name__ == '__main__':
    main()
