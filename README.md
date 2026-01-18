# Fantasy Premier League Optimization

A **CrewAI**-powered pipeline that automates FPL player selection using official API data and integer-programming optimization.

## Features

- **4-agent crew**: Fixture Analyst → Player Scout → Optimization Engineer → Report Writer
- **Official FPL API**: Pulls live data from `bootstrap-static` and `fixtures` endpoints
- **ILP optimizer**: Builds a valid 15-man squad under FPL constraints (budget, positions, max 3 per club)
- **Differential mode**: Prefers low-ownership players for higher upside
- **No flagged players**: Automatically excludes injured/suspended players

## Installation

```bash
pip install uv
cd fantasy_premier_league_optimization
crewai install
```

Add your `OPENAI_API_KEY` to `.env`:

```
OPENAI_API_KEY=sk-...
```

## Usage

```bash
crewai run
```

Optional arguments (via `uv run`):

```bash
uv run fantasy_premier_league_optimization <horizon> <budget> <must_include> <avoid> <risk_profile>
# Example: optimize for next GW, £100m budget, differential mode
uv run fantasy_premier_league_optimization 1 100.0 "" "" differential
```

## Outputs

| File | Description |
|------|-------------|
| `artifacts/fixtures.md` | Team fixture difficulty table |
| `artifacts/player_watchlist.md` | Top players ranked by value score |
| `artifacts/optimized_squad.json` | Optimized 15-man squad with XI, bench, captain |
| `report.md` | Human-readable strategy report |

## Project Structure

```
src/fantasy_premier_league_optimization/
├── config/
│   ├── agents.yaml      # Agent definitions
│   └── tasks.yaml       # Task definitions
├── crew.py              # CrewAI crew setup
├── main.py              # Entry point
├── fpl/
│   ├── api.py           # FPL API client
│   ├── fixtures.py      # Fixture difficulty logic
│   ├── optimizer.py     # ILP squad optimizer
│   └── scoring.py       # Player projection helpers
└── tools/
    ├── fpl_fixture_outlook_tool.py
    ├── fpl_player_watchlist_tool.py
    ├── fpl_optimize_squad_tool.py
    └── fpl_generate_report_tool.py
```

## Customization

- **Horizon**: Set `horizon_gameweeks` to optimize for 1–8 upcoming GWs
- **Risk profile**: `"differential"` (low ownership bonus) or `"template"` (ignore ownership)
- **Must-include/avoid**: Force or exclude specific players by name

## License

MIT








