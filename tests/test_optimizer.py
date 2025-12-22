from fantasy_premier_league_optimization.fpl.optimizer import validate_squad


def test_validate_squad_happy_path():
    # Minimal fake squad that satisfies counts + budget + team cap
    squad = []
    # 2 GK
    squad += [{"id": 1, "position": "GK", "cost": 4.0, "team_id": 1}]
    squad += [{"id": 2, "position": "GK", "cost": 4.0, "team_id": 2}]
    # 5 DEF
    for i in range(3, 8):
        squad.append({"id": i, "position": "DEF", "cost": 4.5, "team_id": (i % 5) + 1})
    # 5 MID
    for i in range(8, 13):
        squad.append({"id": i, "position": "MID", "cost": 6.0, "team_id": (i % 5) + 1})
    # 3 FWD
    for i in range(13, 16):
        squad.append({"id": i, "position": "FWD", "cost": 7.0, "team_id": (i % 5) + 1})

    validate_squad(squad, budget=100.0, max_from_team=3)


def test_validate_squad_rejects_too_many_from_team():
    squad = []
    squad += [{"id": 1, "position": "GK", "cost": 4.0, "team_id": 1}]
    squad += [{"id": 2, "position": "GK", "cost": 4.0, "team_id": 1}]
    # Force >3 from team 1
    for i in range(3, 16):
        pos = "DEF" if i <= 7 else "MID" if i <= 12 else "FWD"
        squad.append({"id": i, "position": pos, "cost": 4.0, "team_id": 1})

    try:
        validate_squad(squad, budget=100.0, max_from_team=3)
        assert False, "expected ValueError"
    except ValueError:
        assert True


