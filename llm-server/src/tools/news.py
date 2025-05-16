import os
from typing import Type, Optional
from langchain_core.tools import BaseTool
from langchain_milvus import Milvus
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.vectorstores import VectorStore
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json
import dotenv
import asyncio

dotenv.load_dotenv(override=True)


class SearchNewsInput(BaseModel):
    query: str = Field(
        description='query string provided by the user (e.g., "삼성전자 최신 뉴스")'
    )
    # start_date: str = Field(
    #     description=f'date to start searching, if user don\'t mention a specific date, then "{(datetime.today()-timedelta(7)).strftime("%Y-%m-%d")}".'
    # )
    # end_date: str = Field(
    #     description=f'date to complete searching, if user don\'t mention a specific date, then "{datetime.today().strftime("%Y-%m-%d")}"'
    # )


class SearchNewsTool(BaseTool):
    name: str = "search_news"
    description: str = (
        "Search for relevant news in a vector database based on the user query. "
        "Use this tool when you need news of companies."
    )
    args_schema: Type[BaseModel] = SearchNewsInput
    return_direct: bool = False
    vectorstore: VectorStore

    def __init__(self, embeddings):
        super().__init__(
            vectorstore=Milvus(
                embedding_function=embeddings,
                collection_name="stockelper",
                connection_args={"uri": os.environ["MILVUS_URI"]},
                vector_field="embedding",
                text_field="body",
            )
        )

    def remove_duplicates(self, docs):
        seen_titles = set()
        unique_list = []

        for doc in docs:
            title = doc.metadata["title"]
            if title not in seen_titles:
                unique_list.append(doc)
                seen_titles.add(title)

        return unique_list

    def _run(
        self,
        query: str,
        start_date: str = (datetime.today() - timedelta(7)).strftime("%Y-%m-%d"),
        end_date: str = datetime.today().strftime("%Y-%m-%d"),
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ):
        return asyncio.run(self._arun(query, start_date, end_date, run_manager))

    async def _arun(
        self,
        query: str,
        start_date: str = (datetime.today() - timedelta(30)).strftime("%Y-%m-%d"),
        end_date: str = datetime.today().strftime("%Y-%m-%d"),
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ):
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="search_news", input=query)
        else:
            span = None

        start_stamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_stamp = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() + 86400)

        # Milvus 비동기 검색 사용
        retriever = self.vectorstore.as_retriever(
            search_type="similarity_score_threshold", 
            search_kwargs={
                "k": 10, 
                "score_threshold": 0.5,
                "param": {
                    "ef": 20,
                },
                "expr": f"(datetime >= {start_stamp}) && (datetime <= {end_stamp})",
            }
        )
        documents = await retriever.ainvoke(
            query
        )
        documents = self.remove_duplicates(documents)
        documents = sorted(documents, key=lambda x: x.metadata['datetime'], reverse=True)

        news_data = {"searched_news": {}}

        for i, doc in enumerate(documents):
            news_data["searched_news"][f"article_{i}"] = {
                "title": doc.metadata['title'],
                "content": doc.page_content[:200],
                "timestamp": datetime.fromtimestamp(doc.metadata['datetime']).strftime('%Y-%m-%d %H:%M:%S')
            }

        if span:
            span.end(output=news_data)

        return news_data
