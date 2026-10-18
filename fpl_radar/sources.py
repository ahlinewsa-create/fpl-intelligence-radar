"""Public-source integrations; failures are explicit, not silently substituted."""
import csv
import io
import json
from urllib.request import Request, urlopen

FPL = 'https://fantasy.premierleague.com/api'
HISTORY = 'https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data'
STATSBOMB = 'https://raw.githubusercontent.com/hudl/open-data/master/data'


def get_json(url, timeout=20):
    req = Request(url, headers={'User-Agent': 'FPL-Intelligence-Radar/0.1 (personal analytics)', 'Accept': 'application/json'})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def bootstrap():
    payload = get_json(f'{FPL}/bootstrap-static/')
    for key in ('elements', 'teams', 'events', 'element_types'):
        if not isinstance(payload.get(key), list):
            raise ValueError(f'FPL response lacks expected field {key}')
    return payload


def fixtures():
    data = get_json(f'{FPL}/fixtures/')
    if not isinstance(data, list):
        raise ValueError('Invalid fixture payload')
    return data


def public_team(team_id, event):
    """Read public entry and picks; access may be limited by FPL privacy/API rules."""
    if not 1 <= int(team_id) <= 100_000_000 or not 1 <= int(event) <= 60:
        raise ValueError('Invalid team ID or gameweek')
    entry = get_json(f'{FPL}/entry/{int(team_id)}/')
    picks = get_json(f'{FPL}/entry/{int(team_id)}/event/{int(event)}/picks/')
    if not isinstance(picks.get('picks'), list):
        raise ValueError('Invalid picks payload')
    return {'entry': entry, 'picks': picks}


def history_csv(season='2024-25'):
    if not season.replace('-', '').isdigit() or len(season) != 7:
        raise ValueError('Bad season')
    req = Request(f'{HISTORY}/{season}/cleaned_players.csv', headers={'User-Agent': 'FPL-Intelligence-Radar/0.1'})
    with urlopen(req, timeout=20) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode('utf-8-sig'))))


def statsbomb_competitions():
    return get_json(f'{STATSBOMB}/competitions.json')
