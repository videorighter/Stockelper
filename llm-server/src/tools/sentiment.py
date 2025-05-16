import os
import praw
import asyncio
from datetime import datetime, timedelta
from typing import Type, Optional, Dict, List
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from pymongo import AsyncMongoClient
import json
import dotenv

dotenv.load_dotenv(override=True)


class NewsSentimentAnalysisInput(BaseModel):
    company_name: str = Field(
        description="Company name to analyze. e.g. 삼성전자"
    )

class ReportSentimentAnalysisInput(BaseModel):
    ticker_symbol: str = Field(
        description="Stock ticker symbol to analyze. e.g. 005930"
    )

class BaseSentimentAnalysisTool(BaseTool):
    name: str = "base_sentiment_analysis"
    client: Optional[AsyncOpenAI] = None

    def __init__(self):
        super().__init__()
        self.client = AsyncOpenAI()

    async def analyze_sentiments_batch(self, texts: List[Dict]) -> List[Dict]:
        """한 번의 API 호출로 여러 텍스트의 감성 분석"""
        if not texts:
            return []
        
        formatted_texts = "\n\n".join([
            f"{text['date']}: {text['summary']}"
            for i, text in enumerate(texts)
        ])

        prompt = f"""여러 텍스트의 감성 분석을 진행합니다. 각 텍스트의 긍정/부정 점수를 0과 1 사이의 숫자로만 출력해주세요. 

입력 텍스트:
{formatted_texts}

다음 형식으로만 출력하세요:
[
    {{
        "date": "2025/01/01",
        "positive": 0.8,
        "negative": 0.2,
    }},
    {{
        "date": "2025/01/02",
        "positive": 0.6,
        "negative": 0.4,
    }},
    ...
]"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "금융 텍스트의 감성을 분석하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
        )

        try:
            results = response.choices[0].message.content.strip()
        except Exception as e: 
            print(e)
            return []
        return results

    async def analyze_trends(self, results: str) -> str:
        """Analyze sentiment trends and key points."""
        prompt = f"""
        다음 금융 감성 분석 데이터를 분석하여 주요 감성 트렌드와 핵심 포인트를 파악해주세요:
        {results}

        다음 형식으로 분석 결과를 제공해주세요:
        1. 전반적인 시장 심리 동향
        2. 주요 변곡점과 그 원인
        3. 향후 전망에 영향을 미칠 수 있는 핵심 요소
        """

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial analyst expert."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

class ReportSentimentAnalysisTool(BaseSentimentAnalysisTool):
    name: str = "report_sentiment_analysis"
    description: str = "Analyzes sentiment trends from stock market reports."
    args_schema: Type[BaseModel] = ReportSentimentAnalysisInput  
    return_direct: bool = False

    async def get_report_data(self, ticker_symbol: str, days: int = 30) -> List[Dict]:
        """Get report data from MongoDB collection."""
        end_date = datetime.now()
        start_date = (end_date - timedelta(days=days)).strftime("%Y/%m/%d")
        
        mongo_client = AsyncMongoClient(os.getenv("MONGO_URI"))
        collection = mongo_client['stockelper']['report']
        
        data = []
        async for doc in collection.find(
            {"$and": [{"date": {"$gte": start_date}}, {"code": f"A{ticker_symbol}"}]},
            {"_id": False, "date": True, "summary": True}
        ):
            data.append(doc)
        
        return data
    
    def _run(
        self,
        ticker_symbol: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return asyncio.run(self._arun(ticker_symbol, run_manager))
    
    async def _arun(
        self,
        ticker_symbol: str, 
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="report_sentiment_analysis", input=ticker_symbol)
        else:
            span = None

        reports = await self.get_report_data(ticker_symbol)
        reports = sorted(reports, key=lambda x: x['date'])
        results = await self.analyze_sentiments_batch(reports)
        
        try:
            output = json.loads(results)
        except Exception as e:
            output = {"error": str(e)}

        if span:
            span.end(output=output)

        return output

class NewsSentimentAnalysisTool(BaseSentimentAnalysisTool):

    name: str = "news_sentiment_analysis"
    description: str = "Analyzes sentiment trends from news articles."    
    args_schema: Type[BaseModel] = NewsSentimentAnalysisInput  
    return_direct: bool = False


    async def get_news_data(self, company_name: str, days: int = 30) -> List[Dict]:
        """뉴스 데이터 조회 및 일자별 그룹화"""
        end_date = datetime.now()
        start_date = (end_date - timedelta(days=days))
        
        mongo_client = AsyncMongoClient(os.getenv("MONGO_URI"))
        collection = mongo_client['stockelper']['naver_news']
        
        pipeline = [
            {"$match": {
                "$and": [
                    {"datetime": {"$gte": start_date}},
                    {"stock_name": company_name}
                ]
            }},
            {"$project": {
                "_id": 0,
                "date": {"$dateToString": {"format": "%Y/%m/%d", "date": "$datetime"}},
                "title": "$title"
            }},
            {"$group": {
                "_id": "$date",
                "titles": {"$push": "$title"}
            }},
            {"$sort": {"_id": -1}}
        ]
        
        data = []
        cursor = await collection.aggregate(pipeline)
        async for doc in cursor:
            data.append(doc)
        return data

    async def summarize_daily_news(self, headlines: List[str]) -> str:
        """일자별 뉴스 요약"""
        if not headlines:
            return ""
            
        prompt = f"""다음은 특정 기업의 하루 동안의 뉴스 제목들입니다. 이를 하나의 종합적인 요약으로 만들어주세요.
                            
                    주요 지침:
                    - 핵심 내용만 간단히 요약 (200자 이내)
                    - 중복되는 내용은 한 번만 포함
                    - 주가나 실적에 영향을 줄 수 있는 내용 위주로 요약
                    - 가장 중요한 뉴스를 먼저 언급

                    원문:
                    {' '.join(headlines)}

                    요약본:"""

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 전문 경제 뉴스 에디터입니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()

    def _run(
        self,
        company_name: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return asyncio.run(self._arun(company_name, run_manager))
    
    async def _arun(
        self,
        company_name: str,
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="news_sentiment_analysis", input=company_name)
        else:
            span = None

        daily_news = await self.get_news_data(company_name)
        daily_summaries = []
        
        # 각 일자별 뉴스 요약 병렬 처리
        date_titles_list = [(day_news['_id'], day_news['titles'][:10]) for day_news in daily_news]
        summaries = await asyncio.gather(
            *[self.summarize_daily_news(titles) for _, titles in date_titles_list]
        )
        for (date, _), summary in zip(date_titles_list, summaries):
            if summary:
                daily_summaries.append({
                    'date': date,
                    'summary': summary
                })
        
        daily_summaries = sorted(daily_summaries, key=lambda x: x['date'])
        results = await self.analyze_sentiments_batch(daily_summaries)
        # output = await self.analyze_trends(results)
        try:
            output = json.loads(results)
        except Exception as e:
            output = {"error": str(e)}

        if span:
            span.end(output=output)

        return output
