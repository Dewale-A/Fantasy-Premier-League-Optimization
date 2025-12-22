#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from fantasy_premier_league_optimization.crew import FantasyPremierLeagueOptimization

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """
    Run the crew.
    """
    inputs = {
        # Optimization horizon (number of upcoming gameweeks to consider)
        "horizon_gameweeks": int(sys.argv[1]) if len(sys.argv) > 1 else 5,
        # Official FPL initial budget is 100.0 (i.e., £100.0m)
        "budget": float(sys.argv[2]) if len(sys.argv) > 2 else 100.0,
        # Optional comma-separated players to force-include or avoid (match by "First Last")
        "must_include": sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else [],
        "avoid": sys.argv[4].split(",") if len(sys.argv) > 4 and sys.argv[4] else [],
        "current_year": str(datetime.now().year),
    }

    try:
        FantasyPremierLeagueOptimization().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "horizon_gameweeks": 5,
        "budget": 100.0,
        "must_include": [],
        "avoid": [],
        "current_year": str(datetime.now().year),
    }
    try:
        FantasyPremierLeagueOptimization().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        FantasyPremierLeagueOptimization().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "horizon_gameweeks": 5,
        "budget": 100.0,
        "must_include": [],
        "avoid": [],
        "current_year": str(datetime.now().year),
    }

    try:
        FantasyPremierLeagueOptimization().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        result = FantasyPremierLeagueOptimization().crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
