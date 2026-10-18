import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .sources import bootstrap, fixtures, public_team, history_csv, statsbomb_competitions, chip_history
from .analysis import ranked_players, current_event, assess_team
from .chips import recommend_chips
from .decisions import decision_desk
from .quality import audit_report, benchmark_forecasts
from .history import snapshot
from .advanced import player_forecasts, injury_watch, price_watch, ownership_differentials, blank_double, manager_snapshot, transfers_with_prices
from .strategy import fixture_matrix, team_strength, captains, suggested_squad, starting_eleven, transfer_ideas

def build_report(data, games, team_id=None):
    event = current_event(data)
    players = ranked_players(data, games, limit=len(data['elements']))
    raw_by_id = {p['id']:p for p in data['elements']}
    for player in players:
        raw = raw_by_id[player['id']]
        player['fpl_status'] = raw.get('status')
        player['chance_of_playing_next_round'] = raw.get('chance_of_playing_next_round')
    healthy = [p for p in players if p.get('fpl_status') == 'a' and p.get('availability',0)>=.75]
    top = healthy[:20]
    forecasts = player_forecasts(data, games, event['id']) if event else {}
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'build_sha': os.environ.get('GITHUB_SHA','unknown')[:12],
        'gameweek': event['id'] if event else None,
        'methodology': 'Uncalibrated heuristic of ep_next, form, fixtures and availability; do not treat projections as verified',
        'top_players': top,
        'value_picks': sorted(healthy, key=lambda p: p['value'], reverse=True)[:15],
        'captain_candidates': captains(healthy),
        'fixture_difficulty_next_5': fixture_matrix(games, event['id']) if event else {},
        'team_strength': team_strength(data),
        'suggested_squad': suggested_squad(players),
        'multiweek_top': sorted([{'id':pid, **value} for pid,value in forecasts.items()], key=lambda x:x['total'], reverse=True)[:25],
        'injury_watch': injury_watch(data),
        'price_watch': price_watch(data),
        'differentials': [x for x in ownership_differentials(data, forecasts,limit=100) if raw_by_id[x['player_id']].get('status') == 'a' and forecasts[x['player_id']]['availability'] >= .75][:12],
        'blank_double': blank_double(games, event['id']) if event else [],
        'sources': ['FPL bootstrap-static', 'FPL fixtures']
    }
    if team_id and event and event['id'] > 1:
        try:
            chips_used = chip_history(team_id)
            verified = True
        except (OSError, ValueError, KeyError) as exc:
            chips_used, verified = [], False
            report['chip_history_warning'] = type(exc).__name__
        previous = public_team(team_id, event['id'] - 1)
        report['team'] = assess_team(previous['picks'], players)
        report['team']['manager'] = manager_snapshot(previous['entry'], previous['picks'])
        by_id = {p['id']: p for p in players}
        squad = [by_id[x['element']] for x in previous['picks']['picks'] if x['element'] in by_id]
        report['chip_strategy'] = recommend_chips(event['id'], games, players, previous['picks'],
                                                   used_chips=chips_used, history_verified=verified)
        if len(squad) == 15:
            prices = {p['element']:p.get('selling_price') for p in previous['picks']['picks']}
            for player in squad:
                if isinstance(prices.get(player['id']), int):
                    player['selling_price'] = prices[player['id']] / 10
            bank = report['team']['manager']['bank']
            report['team']['multiweek_transfers'] = transfers_with_prices(squad, players, forecasts, bank)
            report['team']['starting_eleven'] = starting_eleven(squad)
            report['decision_desk'] = decision_desk(squad, players, forecasts, bank, event['id'], event.get('deadline_time'))
            report['team']['transfer_ideas'] = []  # Replaced: legacy suggestions ignored selling prices and free transfer constraints.
        report['team']['note'] = 'Previous GW public picks and historical bank; may be stale, verify before transfer.'
    report['forecast_benchmark'] = benchmark_forecasts(data, forecasts, event['id']) if event else {}
    report['player_forecasts_for_archive'] = {str(pid):row['weeks'][event['id']] for pid,row in forecasts.items()} if event else {}
    report['quality'] = audit_report(report)
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
    data, games = bootstrap(), fixtures()
    try:
        report = build_report(data, games, args.team_id)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if not args.team_id:
            raise
        print(f'Warning: personalized data unavailable ({type(exc).__name__}); generating general report')
        report = build_report(data, games)
        report['personal_data_warning'] = type(exc).__name__
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Forecast archive:', snapshot(report))
    print(f'Wrote {output} for GW {report["gameweek"]}')

if __name__ == '__main__':
    main()
