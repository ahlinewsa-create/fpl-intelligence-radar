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

## Arabic weekly email

The workflow creates a mobile-friendly RTL Arabic HTML report and attempts sending it after a successful Wednesday run (07:20 UTC). Configure the following **Actions repository secrets** under Settings → Secrets and variables → Actions:

- `GMAIL_USER`: Gmail sender account
- `GMAIL_PASS`: Gmail app password (not your normal login password)
- `TO_EMAIL`: recipient email address

The email step skips with a workflow warning if any of these values are missing; email delivery is **not enabled** until they exist and a live run succeeds. Secrets belong to this repository; secrets in `cults-radar` are not automatically shared. No credentials are committed to files. The workflow will still upload JSON reports without email. The existing weekly schedule remains `20 7 * * 3`.

Run email unit tests with `python -m unittest discover -s tests -v`. Email delivery needs a separate live test.

## Advanced analytics (development preview)

The weekly JSON and RTL email now include per-GW five-week scoring heuristics, fixture blanks/doubles, injuries/news, ownership differentials, player xG/xA season totals, price-demand signals, and bank/buy suggestions where historically published pick selling prices exist. Their estimates are **not calibrated models**; all proposed moves must be confirmed inside the official game.

Personal team details come from the last published gameweek and may not reflect transfers made since. If private/past team data is unavailable, the workflow attempts a general report and labels personal data unavailable.

Module `fpl_radar.advanced.backtest` can score saved predictions against actual points, but persistent history and automated reconciliation are not yet configured. Rival league comparison, guaranteed notification before each dynamic deadline, calibrated minute/points probabilities, authenticated real-time squads, and true mathematically optimal multiweek transfer/chip scheduling remain future work—not claimed as operational.

The schedule remains **Wednesday 07:20 UTC**; do not treat it as a deadline reminder because FPL deadlines move.
