from __future__ import annotations

import textwrap
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FetchUrlInput(BaseModel):
    url: str = Field(..., description="URL to fetch (HTML or JSON).")
    max_chars: int = Field(6000, description="Truncate response to this many characters.")
    timeout_seconds: int = Field(20, description="HTTP timeout in seconds.")


class FetchUrlTool(BaseTool):
    name: str = "fetch_url"
    description: str = (
        "Fetch a URL for lightweight web scraping / API calls when official endpoints are insufficient. "
        "Returns the response text truncated to max_chars."
    )
    args_schema: Type[BaseModel] = FetchUrlInput

    def _run(self, url: str, max_chars: int = 6000, timeout_seconds: int = 20) -> str:
        resp = requests.get(url, timeout=timeout_seconds, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        text = resp.text
        text = textwrap.shorten(text, width=int(max_chars), placeholder="... [truncated]")
        return text


