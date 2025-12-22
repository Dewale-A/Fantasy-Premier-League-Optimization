from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class FixtureOutlookRow:
    team: str
    fixture_difficulty_score: float
    number_of_good_fixtures: int
    number_of_bad_fixtures: int
    special_notes: str


def _fixture_team_difficulty(fx: Dict[str, Any], team_id: int) -> Optional[int]:
    """
    FPL fixtures endpoint provides difficulty 1..5 from each team's perspective.
    """
    if fx.get("team_h") == team_id:
        return fx.get("team_h_difficulty")
    if fx.get("team_a") == team_id:
        return fx.get("team_a_difficulty")
    return None


def upcoming_fixtures_for_team(
    fixtures_payload: Iterable[Dict[str, Any]],
    team_id: int,
    *,
    from_event: Optional[int],
    horizon_events: int,
) -> List[Dict[str, Any]]:
    res: List[Dict[str, Any]] = []
    for fx in fixtures_payload:
        ev = fx.get("event")
        if ev is None:
            continue
        if from_event is not None and ev < from_event:
            continue
        if from_event is not None and ev >= from_event + horizon_events:
            continue
        if fx.get("team_h") == team_id or fx.get("team_a") == team_id:
            res.append(fx)
    res.sort(key=lambda x: (x.get("event") or 9999, x.get("kickoff_time") or ""))
    return res


def compute_fixture_outlook(
    *,
    teams: Dict[int, Dict[str, Any]],
    fixtures_payload: Iterable[Dict[str, Any]],
    from_event: Optional[int],
    horizon_events: int,
    good_threshold: int = 2,
    bad_threshold: int = 4,
) -> Tuple[List[FixtureOutlookRow], Dict[int, float]]:
    """
    Returns:
      - rows for reporting
      - per-team outlook multiplier in [~0.85..1.15] (lower difficulty => higher multiplier)
    """
    rows: List[FixtureOutlookRow] = []
    multipliers: Dict[int, float] = {}

    for team_id, team in teams.items():
        upcoming = upcoming_fixtures_for_team(
            fixtures_payload, team_id, from_event=from_event, horizon_events=horizon_events
        )
        diffs: List[int] = []
        good = 0
        bad = 0
        notes: List[str] = []

        if len(upcoming) == 0:
            rows.append(
                FixtureOutlookRow(
                    team=team.get("name", str(team_id)),
                    fixture_difficulty_score=99.0,
                    number_of_good_fixtures=0,
                    number_of_bad_fixtures=0,
                    special_notes="No upcoming fixtures found in horizon",
                )
            )
            multipliers[team_id] = 1.0
            continue

        events = [fx.get("event") for fx in upcoming if fx.get("event") is not None]
        # naive DGW/BGW detection within horizon (duplicate/missing events)
        if len(set(events)) < len(events):
            notes.append("Potential DGW in horizon")

        for fx in upcoming:
            d = _fixture_team_difficulty(fx, team_id)
            if d is None:
                continue
            diffs.append(int(d))
            if d <= good_threshold:
                good += 1
            if d >= bad_threshold:
                bad += 1

        avg = sum(diffs) / max(1, len(diffs))
        # map avg difficulty 1..5 to multiplier ~1.15..0.85
        mult = 1.15 - ((avg - 1.0) * (0.30 / 4.0))
        multipliers[team_id] = float(max(0.80, min(1.20, mult)))

        rows.append(
            FixtureOutlookRow(
                team=team.get("name", str(team_id)),
                fixture_difficulty_score=float(round(avg, 2)),
                number_of_good_fixtures=good,
                number_of_bad_fixtures=bad,
                special_notes=", ".join(notes) if notes else "",
            )
        )

    rows.sort(key=lambda r: r.fixture_difficulty_score)
    return rows, multipliers


def fixture_outlook_markdown(rows: List[FixtureOutlookRow]) -> str:
    header = (
        "| Team | Fixture_Difficulty_Score | Number_of_good_fixtures | Number_of_bad_fixtures | Special_notes |\n"
        "|---|---:|---:|---:|---|\n"
    )
    lines = []
    for r in rows:
        notes = r.special_notes.replace("\n", " ").strip()
        lines.append(
            f"| {r.team} | {r.fixture_difficulty_score:.2f} | {r.number_of_good_fixtures} | {r.number_of_bad_fixtures} | {notes} |"
        )
    return header + "\n".join(lines) + "\n"


