from __future__ import annotations

import json
from typing import Any, Dict, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from fantasy_premier_league_optimization.fpl.api import bootstrap_static, fixtures, team_mapping
from fantasy_premier_league_optimization.fpl.fixtures import compute_fixture_outlook, fixture_outlook_markdown


class FPLFixtureOutlookInput(BaseModel):
    horizon_gameweeks: int = Field(5, description="How many upcoming gameweeks to analyze.")
    from_event: int | None = Field(None, description="Start from this event/gameweek (defaults to current-ish).")
    force_refresh: bool = Field(False, description="Force refresh instead of reading cached API payload.")


class FPLFixtureOutlookTool(BaseTool):
    name: str = "fpl_fixture_outlook"
    description: str = (
        "Fetch official FPL fixtures and compute a team fixture outlook table over the next N gameweeks. "
        "Returns markdown plus a JSON blob (with per-team multipliers) to be reused by later tasks."
    )
    args_schema: Type[BaseModel] = FPLFixtureOutlookInput

    def _run(self, horizon_gameweeks: int = 5, from_event: int | None = None, force_refresh: bool = False) -> str:
        boot = bootstrap_static(force_refresh=force_refresh)
        fx = fixtures(force_refresh=force_refresh)
        teams = team_mapping(boot)

        # If from_event isn't provided, infer from bootstrap "events" (current or next GW)
        if from_event is None:
            events = boot.get("events", [])
            current = next((e for e in events if e.get("is_current")), None)
            if current and current.get("id"):
                from_event = int(current["id"])
            else:
                nxt = next((e for e in events if e.get("is_next")), None)
                from_event = int(nxt["id"]) if nxt and nxt.get("id") else None

        rows, multipliers = compute_fixture_outlook(
            teams=teams,
            fixtures_payload=fx,
            from_event=from_event,
            horizon_events=int(horizon_gameweeks),
        )
        md = fixture_outlook_markdown(rows)
        payload: Dict[str, Any] = {
            "from_event": from_event,
            "horizon_gameweeks": int(horizon_gameweeks),
            "team_multipliers": multipliers,
        }
        return md + "\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"


