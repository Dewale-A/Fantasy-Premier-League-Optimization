from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from fantasy_premier_league_optimization.fpl.api import bootstrap_static, team_mapping
from fantasy_premier_league_optimization.fpl.scoring import (
    player_cost_millions,
    player_name,
    position_short,
    status_label,
)


class FPLPlayerWatchlistInput(BaseModel):
    top_n: int = Field(25, description="How many players to include in the watchlist (approx).")
    min_minutes: int = Field(180, description="Minimum minutes to consider (filters out tiny samples).")
    allow_flagged_players: bool = Field(False, description="If false, excludes players with injury/suspension flags.")
    team_multipliers_json: str | None = Field(
        None,
        description="Optional JSON (from fpl_fixture_outlook) containing {team_multipliers: {team_id: multiplier}}.",
    )
    force_refresh: bool = Field(False, description="Force refresh instead of reading cached API payload.")


class FPLPlayerWatchlistTool(BaseTool):
    name: str = "fpl_player_watchlist"
    description: str = (
        "Build a structured FPL player watchlist using official API stats (points, form, ICT proxies, minutes, price, ownership). "
        "Returns a markdown table plus a JSON block that can be used by the optimizer."
    )
    args_schema: Type[BaseModel] = FPLPlayerWatchlistInput

    @staticmethod
    def _to_markdown_table(df: pd.DataFrame, columns: List[str]) -> str:
        """
        Render a simple GitHub-flavored markdown table without requiring optional deps (e.g. tabulate).
        """
        cols = [c for c in columns if c in df.columns]
        if not cols:
            return ""
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        lines = [header, sep]
        for _, row in df[cols].iterrows():
            vals: List[str] = []
            for c in cols:
                v = row[c]
                if isinstance(v, float):
                    vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines) + "\n"

    def _run(
        self,
        top_n: int = 25,
        min_minutes: int = 180,
        allow_flagged_players: bool = False,
        team_multipliers_json: str | None = None,
        force_refresh: bool = False,
    ) -> str:
        boot = bootstrap_static(force_refresh=force_refresh)
        teams = team_mapping(boot)
        elements = boot.get("elements", [])

        multipliers: Dict[int, float] = {}
        if team_multipliers_json:
            try:
                raw = json.loads(team_multipliers_json)
                multipliers_raw = raw.get("team_multipliers", raw)
                multipliers = {int(k): float(v) for k, v in multipliers_raw.items()}
            except Exception:
                multipliers = {}

        rows: List[Dict[str, Any]] = []
        for e in elements:
            pos = position_short(int(e.get("element_type") or 0))
            if pos is None:
                continue
            minutes = int(e.get("minutes") or 0)
            if minutes < int(min_minutes):
                continue
            if not allow_flagged_players and status_label(e) != "available":
                continue
            team = teams.get(int(e.get("team") or 0), {}).get("name", "")
            team_id = int(e.get("team") or 0)
            rows.append(
                {
                    "Name": player_name(e),
                    "Team": team,
                    "Team_ID": team_id,
                    "Position": pos,
                    "Price": player_cost_millions(e),
                    "Total_Points": int(e.get("total_points") or 0),
                    "Form": float(e.get("form") or 0.0),
                    "Points_per_game": float(e.get("points_per_game") or 0.0),
                    "ep_next": float(e.get("ep_next") or 0.0),
                    "Minutes": minutes,
                    "Injury_or_flag_status": status_label(e),
                    "Ownership_%": float(e.get("selected_by_percent") or 0.0),
                    # Official “underlying-ish” proxies
                    "ICT_Index": float(e.get("ict_index") or 0.0),
                    "Threat": float(e.get("threat") or 0.0),
                    "Creativity": float(e.get("creativity") or 0.0),
                    "Influence": float(e.get("influence") or 0.0),
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            return "No players found after filtering. Try lowering min_minutes."

        # crude value score: ep_next + form + ppg, adjusted by price
        df["ValueScore"] = (df["ep_next"] + 0.8 * df["Form"] + 0.6 * df["Points_per_game"]) / df["Price"].clip(
            lower=4.0
        )
        df = df.sort_values(["ValueScore", "ep_next", "Total_Points"], ascending=False).head(int(top_n))

        if multipliers:
            def _outlook(team_id_val: Any) -> str:
                m = multipliers.get(int(team_id_val), 1.0)
                if m >= 1.07:
                    return "good"
                if m <= 0.95:
                    return "bad"
                return "mixed"

            df["Fixture_Outlook"] = df["Team_ID"].apply(_outlook)
        else:
            df["Fixture_Outlook"] = "unknown"

        md = self._to_markdown_table(
            df,
            [
                "Name",
                "Team",
                "Position",
                "Price",
                "Total_Points",
                "Form",
                "ep_next",
                "Minutes",
                "Injury_or_flag_status",
                "Ownership_%",
                "ICT_Index",
                "Fixture_Outlook",
            ],
        )

        payload = df.drop(columns=["Team_ID"], errors="ignore").to_dict(orient="records")
        return md + "\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"


