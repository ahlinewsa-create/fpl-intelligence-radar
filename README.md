# FPL Intelligence Radar ⚽

Independent read-only Fantasy Premier League analytics. No dependency on cults-radar.

## Data and limitations

- Current: public FPL bootstrap-static and fixtures endpoints (subject to API availability).
- History: vaastav/Fantasy-Premier-League; weekly updates stopped after 2024-25.
- Advanced match events: hudl/open-data (StatsBomb), selected open matches only.
- amosbastian/fpl: optional legacy wrapper, not needed for initial launch.

## Run

Python 3.10+, standard library only:

```bash
python -m unittest discover -s tests -v
python -m fpl_radar.cli --check-sources
python -m fpl_radar.cli
python -m fpl_radar.cli --team-id 123456
```

Report: `reports/latest.json`. Ranking is a **heuristic** based on FPL `ep_next`, form, fixture difficulty, and availability; not a validated prediction model nor a legal 15-player lineup optimizer. Personal team analysis uses previous gameweek publicly available picks, not private pending transfers.

## GitHub Actions

Workflow runs daily at 07:20 UTC (10:20 Saudi Arabia time) and supports manual `workflow_dispatch`. Set an optional repository Actions **variable** `FPL_TEAM_ID` to your numeric FPL manager ID for personal reporting. The workflow uploads a `fpl-report` artifact, no write permission or credentials necessary. Public endpoints may rate-limit or fail; inspect source health and workflow logs.

This independent project does not change cults-radar.
