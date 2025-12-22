from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from fantasy_premier_league_optimization.tools.fpl_fixture_outlook_tool import (
    FPLFixtureOutlookTool,
)
from fantasy_premier_league_optimization.tools.fpl_player_watchlist_tool import (
    FPLPlayerWatchlistTool,
)
from fantasy_premier_league_optimization.tools.fpl_optimize_squad_tool import (
    FPLOptimizeSquadTool,
)
from fantasy_premier_league_optimization.tools.fpl_generate_report_tool import (
    FPLGenerateReportTool,
)
from fantasy_premier_league_optimization.tools.fetch_url_tool import FetchUrlTool

@CrewBase
class FantasyPremierLeagueOptimization():
    """FantasyPremierLeagueOptimization crew"""

    agents: List[BaseAgent]
    tasks: List[Task]


    @agent
    def fixture_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["fixture_analyst"],  # type: ignore[index]
            tools=[FPLFixtureOutlookTool(), FetchUrlTool()],
            verbose=True,
        )

    @agent
    def player_scout(self) -> Agent:
        return Agent(
            config=self.agents_config["player_scout"],  # type: ignore[index]
            tools=[FPLPlayerWatchlistTool(), FetchUrlTool()],
            verbose=True,
        )

    @agent
    def optimization_engineer(self) -> Agent:
        return Agent(
            config=self.agents_config["optimization_engineer"],  # type: ignore[index]
            tools=[FPLOptimizeSquadTool()],
            verbose=True,
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],  # type: ignore[index]
            tools=[FPLGenerateReportTool()],
            verbose=True,
        )


    @task
    def analyze_fixtures_task(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_fixtures_task"],  # type: ignore[index]
            output_file="artifacts/fixtures.md",
        )

    @task
    def research_players_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_players_task"],  # type: ignore[index]
            context=[self.analyze_fixtures_task()],
            output_file="artifacts/player_watchlist.md",
        )

    @task
    def optimize_team_task(self) -> Task:
        return Task(
            config=self.tasks_config["optimize_team_task"],  # type: ignore[index]
            context=[self.analyze_fixtures_task(), self.research_players_task()],
            output_file="artifacts/optimized_squad.json",
        )

    @task
    def write_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["write_report_task"],  # type: ignore[index]
            context=[
                self.analyze_fixtures_task(),
                self.research_players_task(),
                self.optimize_team_task(),
            ],
            output_file="report.md",
        )

    @crew
    def crew(self) -> Crew:
        """Creates the FantasyPremierLeagueOptimization crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
