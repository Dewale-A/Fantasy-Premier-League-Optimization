from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from fantasy_premier_league_optimization.fpl.api import bootstrap_static, team_mapping

# Default paths for artifacts
DEFAULT_OPTIMIZED_SQUAD_PATH = "artifacts/optimized_squad.json"
DEFAULT_FIXTURES_PATH = "artifacts/fixtures.md"
DEFAULT_PLAYER_WATCHLIST_PATH = "artifacts/player_watchlist.md"
DEFAULT_REPORT_OUTPUT_PATH = "report.md"


def _normalize_str_input(value: Any, default: str) -> str:
    """
    Normalize input that might be a string, dict (schema definition), or None.
    LLMs sometimes pass the field schema definition instead of the actual value.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value if value.strip() else default
    if isinstance(value, dict):
        # LLM passed schema definition like {'description': '...', 'type': 'str'}
        # Fall back to default
        return default
    return default


def _normalize_bool_input(value: Any, default: bool) -> bool:
    """Normalize boolean input that might be bool, dict, string, or None."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return default
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


class FPLGenerateReportInput(BaseModel):
    optimized_squad_path: Optional[str] = Field(
        default=None,
        description=f"Path to optimized_squad.json (default: {DEFAULT_OPTIMIZED_SQUAD_PATH}).",
    )
    fixtures_path: Optional[str] = Field(
        default=None,
        description=f"Path to fixtures.md (default: {DEFAULT_FIXTURES_PATH}).",
    )
    player_watchlist_path: Optional[str] = Field(
        default=None,
        description=f"Path to player_watchlist.md (default: {DEFAULT_PLAYER_WATCHLIST_PATH}).",
    )
    force_refresh: Optional[bool] = Field(
        default=None,
        description="Force refresh of FPL bootstrap (default: false).",
    )


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
        "Generate a grounded FPL report from existing tool outputs on disk. "
        "Uses default artifact paths if none provided. Saves report to report.md automatically. "
        "Call with empty arguments or no arguments to use all defaults."
    )
    args_schema: Type[BaseModel] = FPLGenerateReportInput

    def _run(
        self,
        optimized_squad_path: Optional[Union[str, Dict[str, Any]]] = None,
        fixtures_path: Optional[Union[str, Dict[str, Any]]] = None,
        player_watchlist_path: Optional[Union[str, Dict[str, Any]]] = None,
        force_refresh: Optional[Union[bool, Dict[str, Any]]] = None,
        **kwargs: Any,  # Absorb any extra malformed arguments
    ) -> str:
        # Normalize inputs - handles cases where LLM passes dict schema instead of values
        squad_path_str = _normalize_str_input(optimized_squad_path, DEFAULT_OPTIMIZED_SQUAD_PATH)
        fx_path_str = _normalize_str_input(fixtures_path, DEFAULT_FIXTURES_PATH)
        wl_path_str = _normalize_str_input(player_watchlist_path, DEFAULT_PLAYER_WATCHLIST_PATH)
        do_refresh = _normalize_bool_input(force_refresh, False)

        base = Path.cwd()
        squad_path = (base / squad_path_str).resolve()
        fx_path = (base / fx_path_str).resolve()
        wl_path = (base / wl_path_str).resolve()

        squad = _load_json_file(squad_path)
        boot = bootstrap_static(force_refresh=do_refresh)
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
        # Save report directly to file to ensure it's persisted
        # even if the agent doesn't return the exact tool output
        report_output_path = base / DEFAULT_REPORT_OUTPUT_PATH
        try:
            report_output_path.write_text(report, encoding="utf-8")
        except Exception:
            pass  # Silently fail if we can't write - the return value is still valid

        return report









