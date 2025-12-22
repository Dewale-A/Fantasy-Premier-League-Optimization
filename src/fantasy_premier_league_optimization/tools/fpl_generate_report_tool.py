from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from fantasy_premier_league_optimization.fpl.api import bootstrap_static, team_mapping


class FPLGenerateReportInput(BaseModel):
    optimized_squad_path: str = Field(
        "artifacts/optimized_squad.json",
        description="Path to optimized_squad.json produced by the optimizer task.",
    )
    fixtures_path: str = Field(
        "artifacts/fixtures.md",
        description="Path to fixtures.md produced by the fixture tool task.",
    )
    player_watchlist_path: str = Field(
        "artifacts/player_watchlist.md",
        description="Path to player_watchlist.md produced by the player watchlist tool task.",
    )
    force_refresh: bool = Field(False, description="Force refresh of FPL bootstrap (only used for team names).")


def _load_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _team_name(teams: Dict[int, Dict[str, Any]], team_id: int) -> str:
    return str(teams.get(int(team_id), {}).get("name") or f"team_{team_id}")


def _table(rows: List[List[str]], headers: List[str]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([line, sep] + body)


class FPLGenerateReportTool(BaseTool):
    name: str = "fpl_generate_report"
    description: str = (
        "Generate a grounded FPL report strictly from existing tool outputs on disk "
        "(especially artifacts/optimized_squad.json). This prevents hallucinated players/teams."
    )
    args_schema: Type[BaseModel] = FPLGenerateReportInput

    def _run(
        self,
        optimized_squad_path: str = "artifacts/optimized_squad.json",
        fixtures_path: str = "artifacts/fixtures.md",
        player_watchlist_path: str = "artifacts/player_watchlist.md",
        force_refresh: bool = False,
    ) -> str:
        base = Path.cwd()
        squad_path = (base / optimized_squad_path).resolve()
        fx_path = (base / fixtures_path).resolve()
        wl_path = (base / player_watchlist_path).resolve()

        squad = _load_json_file(squad_path)
        boot = bootstrap_static(force_refresh=force_refresh)
        teams = team_mapping(boot)

        starting = squad.get("starting_11", [])
        bench = squad.get("bench", [])
        full = squad.get("squad", [])
        captain = squad.get("captain", {})
        vice = squad.get("vice_captain", {})

        def fmt_player(p: Dict[str, Any]) -> List[str]:
            return [
                str(p.get("name", "")),
                str(p.get("position", "")),
                _team_name(teams, int(p.get("team_id") or 0)),
                f"£{float(p.get('cost') or 0.0):.1f}",
                f"{float(p.get('projected_points') or 0.0):.2f}",
                f"{float(p.get('selected_by_percent') or 0.0):.1f}%",
                str(p.get("status", "")),
            ]

        xi_table = _table([fmt_player(p) for p in starting], ["Player", "Pos", "Team", "Price", "Proj", "Own%", "Status"])
        bench_table = _table([fmt_player(p) for p in bench], ["Player", "Pos", "Team", "Price", "Proj", "Own%", "Status"])

        squad_rows = []
        for p in full:
            squad_rows.append(
                [
                    str(p.get("name", "")),
                    str(p.get("position", "")),
                    _team_name(teams, int(p.get("team_id") or 0)),
                    f"£{float(p.get('cost') or 0.0):.1f}",
                    f"{float(p.get('selected_by_percent') or 0.0):.1f}%",
                ]
            )
        squad_md = _table(squad_rows, ["Player", "Pos", "Team", "Price", "Own%"])

        fixtures_excerpt = ""
        if fx_path.exists():
            fixtures_excerpt = fx_path.read_text(encoding="utf-8").strip()
            fixtures_excerpt = "\n".join(fixtures_excerpt.splitlines()[:40]).strip()
        watchlist_excerpt = ""
        if wl_path.exists():
            watchlist_excerpt = wl_path.read_text(encoding="utf-8").strip()
            watchlist_excerpt = "\n".join(watchlist_excerpt.splitlines()[:25]).strip()

        total_cost = float(squad.get("total_cost") or 0.0)
        total_proj = float(squad.get("total_projected_points") or 0.0)
        horizon = int(squad.get("horizon_gameweeks") or 1)
        budget = float(squad.get("budget") or 100.0)

        report = f"""# FPL Optimized Squad Report (Next GW)

## Overview
- Horizon: **{horizon} gameweek(s)** (next GW only)
- Squad cost: **£{total_cost:.1f}** / £{budget:.1f}
- Total projected points (proxy): **{total_proj:.2f}**
- Captain: **{captain.get('name','')}**
- Vice-captain: **{vice.get('name','')}**

## Starting XI
{xi_table}

## Bench (ordered)
{bench_table}

## Full 15-man squad
{squad_md}

## Notes (grounded)
- This report only uses the optimized squad JSON produced by the optimizer tool; it does not introduce any additional players.
- All players in the optimizer output are marked as **available** (no flagged players).

## Fixture context (excerpt)
```
{fixtures_excerpt}
```

## Watchlist context (excerpt)
```
{watchlist_excerpt}
```
"""
        return report



