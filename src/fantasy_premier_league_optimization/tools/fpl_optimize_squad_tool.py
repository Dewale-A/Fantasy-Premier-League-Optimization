from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from fantasy_premier_league_optimization.fpl.api import bootstrap_static, team_mapping
from fantasy_premier_league_optimization.fpl.optimizer import optimize_squad_ilp, validate_squad


class FPLOptimizeSquadInput(BaseModel):
    horizon_gameweeks: int = Field(5, description="How many upcoming gameweeks to optimize for.")
    budget: float = Field(100.0, description="Total budget in £m (e.g., 100.0).")
    max_from_team: int = Field(3, description="Maximum number of players from any one club.")
    must_include: List[str] = Field(default_factory=list, description='Player names to force-include, e.g., ["Erling Haaland"].')
    avoid: List[str] = Field(default_factory=list, description='Player names to avoid, e.g., ["Player X"].')
    risk_profile: str = Field("template", description='Either "template" or "differential".')
    allow_flagged_players: bool = Field(False, description="If false, excludes players with injury/suspension flags.")
    team_multipliers_json: str | None = Field(
        None,
        description="JSON string that contains {team_multipliers: {team_id: multiplier}} from fixture outlook tool.",
    )
    force_refresh: bool = Field(False, description="Force refresh instead of reading cached API payload.")


def _extract_team_multipliers(team_multipliers_json: Optional[str]) -> Dict[int, float]:
    if not team_multipliers_json:
        return {}
    try:
        raw = json.loads(team_multipliers_json)
        multipliers = raw.get("team_multipliers", raw)
        return {int(k): float(v) for k, v in multipliers.items()}
    except Exception:
        # Sometimes an agent pastes fenced JSON; try to extract JSON object.
        m = re.search(r"\{[\s\S]*\}", team_multipliers_json)
        if not m:
            return {}
        try:
            raw = json.loads(m.group(0))
            multipliers = raw.get("team_multipliers", raw)
            return {int(k): float(v) for k, v in multipliers.items()}
        except Exception:
            return {}


class FPLOptimizeSquadTool(BaseTool):
    name: str = "fpl_optimize_squad"
    description: str = (
        "Solve an optimized 15-man FPL squad under official constraints (2 GK, 5 DEF, 5 MID, 3 FWD; "
        "£budget; max 3 per team). Returns JSON with squad, starting XI, bench, captain/vice, totals."
    )
    args_schema: Type[BaseModel] = FPLOptimizeSquadInput

    def _run(
        self,
        horizon_gameweeks: int = 5,
        budget: float = 100.0,
        max_from_team: int = 3,
        must_include: Optional[Sequence[str]] = None,
        avoid: Optional[Sequence[str]] = None,
        risk_profile: str = "template",
        allow_flagged_players: bool = False,
        team_multipliers_json: Optional[str] = None,
        force_refresh: bool = False,
    ) -> str:
        boot = bootstrap_static(force_refresh=force_refresh)
        teams = team_mapping(boot)
        multipliers = _extract_team_multipliers(team_multipliers_json)

        result = optimize_squad_ilp(
            boot.get("elements", []),
            horizon_gameweeks=int(horizon_gameweeks),
            budget=float(budget),
            max_from_team=int(max_from_team),
            must_include=list(must_include or []),
            avoid=list(avoid or []),
            team_fixture_multiplier=multipliers,
            allow_flagged_players=bool(allow_flagged_players),
            risk_profile=str(risk_profile),
        )
        validate_squad(result.squad, budget=float(budget), max_from_team=int(max_from_team))

        def _enrich(p: Dict[str, Any]) -> Dict[str, Any]:
            t = teams.get(int(p.get("team_id") or 0), {})
            return {**p, "team_name": t.get("name", ""), "team_short_name": t.get("short_name", "")}

        payload: Dict[str, Any] = {
            "horizon_gameweeks": int(horizon_gameweeks),
            "budget": float(budget),
            "max_from_team": int(max_from_team),
            "total_cost": result.total_cost,
            "total_projected_points": result.total_projected_points,
            "captain": _enrich(result.captain),
            "vice_captain": _enrich(result.vice_captain),
            "starting_11": [_enrich(p) for p in result.starting_11],
            "bench": [_enrich(p) for p in result.bench],
            "squad": [_enrich(p) for p in result.squad],
        }
        return json.dumps(payload, indent=2)


