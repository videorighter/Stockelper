import os
import json
import requests
import httpx
import asyncio
from dotenv import load_dotenv
from typing import Type, Optional
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

load_dotenv(override=True)

class BraveSearchInput(BaseModel):
    query: str = Field(
        description="Mandatory search query you want to use to search the internet"
    )

class BraveSearchTool(BaseTool):
    name: str = "investment_strategy_search"
    description: str = "A tool for searching investment strategies on the web"
    args_schema: Type[BaseModel] = BraveSearchInput
    return_direct: bool = False

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None):
        return asyncio.run(self._arun(query, run_manager))

    async def _arun(
        self,
        query: str,
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ):
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="search", input=query)
        else:
            span = None

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": os.getenv("BRAVE_API_KEY")
        }
        params = {"q": query}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        results = data['web']['results'][:10]
        results = [
            {"title": item['title'], "time": item.get('page_age', ''), "content": item['description']}
            for item in results
        ]

        if span:
            span.end(output=results)

        return results
