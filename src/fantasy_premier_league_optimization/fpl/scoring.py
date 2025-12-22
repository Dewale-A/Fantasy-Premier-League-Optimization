from __future__ import annotations

from typing import Any, Dict, Optional


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def player_projection_points(
    element: Dict[str, Any],
    *,
    horizon_gameweeks: int,
    fixture_multiplier: float = 1.0,
) -> float:
    """
    Simple proxy for projected points:
      - Prefer official expected points next GW (`ep_next`) if present
      - Blend with `form` and `points_per_game`
      - Apply a team fixture multiplier (easier fixtures => slightly higher)
      - Scale by horizon_gameweeks (roughly)
    """
    ep_next = _to_float(element.get("ep_next"), 0.0)
    ppg = _to_float(element.get("points_per_game"), 0.0)
    form = _to_float(element.get("form"), 0.0)

    # Reliability proxy: minutes share (downweight low-minute players)
    minutes = _to_float(element.get("minutes"), 0.0)
    availability = 0.65 + min(0.35, minutes / 1800.0)  # after ~20 matches, near full weight

    base_one_gw = max(ep_next, 0.55 * ppg + 0.45 * form)
    return float(base_one_gw * horizon_gameweeks * fixture_multiplier * availability)


def player_cost_millions(element: Dict[str, Any]) -> float:
    # `now_cost` is in tenths of a million (e.g., 75 == £7.5m)
    return _to_float(element.get("now_cost"), 0.0) / 10.0


def player_name(element: Dict[str, Any]) -> str:
    first = str(element.get("first_name", "")).strip()
    second = str(element.get("second_name", "")).strip()
    name = f"{first} {second}".strip()
    return name or str(element.get("web_name", "")).strip()


def is_available(element: Dict[str, Any]) -> bool:
    # `status`: a = available, d = doubtful, i = injured, s = suspended, u = unavailable
    status = str(element.get("status", "a")).lower()
    return status == "a"


def status_label(element: Dict[str, Any]) -> str:
    status = str(element.get("status", "")).lower()
    if status == "a":
        return "available"
    if status == "d":
        return "doubtful"
    if status == "i":
        return "injured"
    if status == "s":
        return "suspended"
    if status == "u":
        return "unavailable"
    return status or "unknown"


def position_short(element_type_id: int) -> Optional[str]:
    return {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}.get(int(element_type_id))


