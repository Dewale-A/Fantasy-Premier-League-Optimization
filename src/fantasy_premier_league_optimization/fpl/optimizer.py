from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pulp

from fantasy_premier_league_optimization.fpl.scoring import (
    player_cost_millions,
    player_name,
    player_projection_points,
    position_short,
    status_label,
)


@dataclass(frozen=True)
class OptimizedSquad:
    squad: List[Dict[str, Any]]  # length 15
    starting_11: List[Dict[str, Any]]  # length 11
    bench: List[Dict[str, Any]]  # length 4 (GK + 3 outfield ordered)
    captain: Dict[str, Any]
    vice_captain: Dict[str, Any]
    total_cost: float
    total_projected_points: float


ALLOWED_FORMATIONS: Sequence[Tuple[int, int, int]] = (
    (3, 4, 3),
    (3, 5, 2),
    (4, 4, 2),
    (4, 3, 3),
    (5, 3, 2),
    (5, 4, 1),
)


def _normalize_name(s: str) -> str:
    return " ".join(s.strip().lower().split())


def optimize_squad_ilp(
    elements: Iterable[Dict[str, Any]],
    *,
    horizon_gameweeks: int,
    budget: float = 100.0,
    max_from_team: int = 3,
    must_include: Optional[Sequence[str]] = None,
    avoid: Optional[Sequence[str]] = None,
    team_fixture_multiplier: Optional[Dict[int, float]] = None,
    allow_flagged_players: bool = False,
    risk_profile: str = "template",
    differential_weight: float = 0.12,
) -> OptimizedSquad:
    must_include = must_include or []
    avoid = avoid or []
    must_set = {_normalize_name(x) for x in must_include if x and x.strip()}
    avoid_set = {_normalize_name(x) for x in avoid if x and x.strip()}

    players: List[Dict[str, Any]] = []
    for e in elements:
        pos = position_short(int(e.get("element_type", 0) or 0))
        if pos is None:
            continue
        if not allow_flagged_players and status_label(e) != "available":
            continue
        nm = player_name(e)
        if _normalize_name(nm) in avoid_set:
            continue

        team_id = int(e.get("team") or 0)
        mult = (team_fixture_multiplier or {}).get(team_id, 1.0)
        proj = player_projection_points(e, horizon_gameweeks=horizon_gameweeks, fixture_multiplier=mult)
        cost = player_cost_millions(e)
        players.append(
            {
                "id": int(e.get("id")),
                "name": nm,
                "team_id": team_id,
                "element_type": int(e.get("element_type")),
                "position": pos,
                "cost": cost,
                "projected_points": float(proj),
                "total_points": int(e.get("total_points") or 0),
                "form": float(e.get("form") or 0.0),
                "selected_by_percent": float(e.get("selected_by_percent") or 0.0),
                "status": status_label(e),
            }
        )

    if not players:
        raise ValueError("No eligible players available for optimization.")

    # Decision vars
    x: Dict[int, pulp.LpVariable] = {p["id"]: pulp.LpVariable(f"x_{p['id']}", 0, 1, cat="Binary") for p in players}

    model = pulp.LpProblem("fpl_squad_optimization", pulp.LpMaximize)

    risk = (risk_profile or "template").strip().lower()
    if risk not in {"template", "differential"}:
        risk = "template"

    # Objective: maximize projected points (+ optional differential bonus)
    # Differential bonus gently prefers lower ownership but won't dominate points.
    if risk == "differential":
        # low_own ranges ~0..1 ; scale bonus relative to projected points magnitude
        model += pulp.lpSum(
            (p["projected_points"] * (1.0 + float(differential_weight) * (1.0 - (p["selected_by_percent"] / 100.0))))
            * x[p["id"]]
            for p in players
        )
    else:
        model += pulp.lpSum(p["projected_points"] * x[p["id"]] for p in players)

    # Squad size
    model += pulp.lpSum(x[p["id"]] for p in players) == 15

    # Budget
    model += pulp.lpSum(p["cost"] * x[p["id"]] for p in players) <= float(budget)

    # Position constraints: 2 GK, 5 DEF, 5 MID, 3 FWD
    def _pos_sum(pos: str) -> pulp.LpAffineExpression:
        return pulp.lpSum(x[p["id"]] for p in players if p["position"] == pos)

    model += _pos_sum("GK") == 2
    model += _pos_sum("DEF") == 5
    model += _pos_sum("MID") == 5
    model += _pos_sum("FWD") == 3

    # Max players per team
    by_team: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for p in players:
        by_team[p["team_id"]].append(p)
    for team_id, ps in by_team.items():
        model += pulp.lpSum(x[p["id"]] for p in ps) <= int(max_from_team)

    # Must include (best-effort by name match; if multiple share name, include any one)
    if must_set:
        for wanted in must_set:
            candidates = [p for p in players if _normalize_name(p["name"]) == wanted]
            if not candidates:
                raise ValueError(f"Must-include player not found/eligible: '{wanted}'")
            model += pulp.lpSum(x[p["id"]] for p in candidates) >= 1

    # Solve
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus.get(status) != "Optimal":
        raise ValueError(f"Optimization failed: {pulp.LpStatus.get(status)}")

    squad = [p for p in players if pulp.value(x[p["id"]]) >= 0.9]
    if len(squad) != 15:
        raise ValueError(f"Optimization returned {len(squad)} players, expected 15.")

    total_cost = round(sum(p["cost"] for p in squad), 1)
    total_proj = float(sum(p["projected_points"] for p in squad))

    starting_11, bench = pick_starting_11_and_bench(squad)
    captain, vice = pick_captains(starting_11)

    return OptimizedSquad(
        squad=sorted(squad, key=lambda p: (p["position"], -p["projected_points"], p["cost"])),
        starting_11=starting_11,
        bench=bench,
        captain=captain,
        vice_captain=vice,
        total_cost=total_cost,
        total_projected_points=total_proj,
    )


def pick_starting_11_and_bench(squad: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_pos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in squad:
        by_pos[p["position"]].append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda p: p["projected_points"], reverse=True)

    if len(by_pos["GK"]) != 2:
        raise ValueError("Squad must have exactly 2 GKs for starting XI selection.")

    best_score = -1e18
    best_xi: List[Dict[str, Any]] = []
    for d, m, f in ALLOWED_FORMATIONS:
        if len(by_pos["DEF"]) < d or len(by_pos["MID"]) < m or len(by_pos["FWD"]) < f:
            continue
        xi = []
        xi.extend(by_pos["GK"][:1])
        xi.extend(by_pos["DEF"][:d])
        xi.extend(by_pos["MID"][:m])
        xi.extend(by_pos["FWD"][:f])
        score = sum(p["projected_points"] for p in xi)
        if score > best_score:
            best_score = score
            best_xi = xi

    if len(best_xi) != 11:
        raise ValueError("Failed to construct a valid starting XI from squad.")

    starting_ids = {p["id"] for p in best_xi}
    bench_gk = [p for p in by_pos["GK"] if p["id"] not in starting_ids]
    bench_outfield = [p for p in squad if p["position"] != "GK" and p["id"] not in starting_ids]
    bench_outfield.sort(key=lambda p: p["projected_points"], reverse=True)

    bench = []
    bench.extend(bench_gk[:1])
    bench.extend(bench_outfield[:3])
    if len(bench) != 4:
        raise ValueError("Failed to construct bench.")

    return best_xi, bench


def pick_captains(starting_11: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ordered = sorted(starting_11, key=lambda p: p["projected_points"], reverse=True)
    if len(ordered) < 2:
        raise ValueError("Starting XI must have at least 2 players to pick captain/vice.")
    return ordered[0], ordered[1]


def validate_squad(squad: Sequence[Dict[str, Any]], *, budget: float = 100.0, max_from_team: int = 3) -> None:
    if len(squad) != 15:
        raise ValueError("Squad must be 15 players.")
    cost = sum(p["cost"] for p in squad)
    if cost > budget + 1e-9:
        raise ValueError("Squad exceeds budget.")
    pos_counts = Counter(p["position"] for p in squad)
    if pos_counts["GK"] != 2 or pos_counts["DEF"] != 5 or pos_counts["MID"] != 5 or pos_counts["FWD"] != 3:
        raise ValueError(f"Invalid position counts: {dict(pos_counts)}")
    team_counts = Counter(p["team_id"] for p in squad)
    if any(v > max_from_team for v in team_counts.values()):
        raise ValueError("Exceeded max_from_team constraint.")

