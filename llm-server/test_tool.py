import asyncio
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

# from src.tools.chart_analysis_tool import StockChartAnalysisTool
from src.tools.stock import AnalysisStockTool

# from src.tools.basic import InvestMethodTool
# from src.tools.chart_analysis_tool import StockChartAnalysisTool
# from src.tools.dart import AnalysisFinancialStatementTool
from src.tools.news import SearchNewsTool
from src.tools.report import SearchReportTool
from src.tools.sentiment import NewsSentimentAnalysisTool, ReportSentimentAnalysisTool
from src.tools.youtube_tool import YouTubeSearchTool
import os


embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-m3", model_kwargs={"device": "cpu"}
)

llm = ChatOpenAI(model="gpt-4o", max_tokens=1000, temperature=0)

from langfuse import Langfuse

langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


async def main():
    # 차트 분석 도구 초기화
    # tool = StockChartAnalysisTool()
    # tool = AnalysisStockTool()
    # tool = InvestMethodTool(embeddings=embeddings)
    # tool = StockChartAnalysisTool(llm=llm)
    # tool = AnalysisFinancialStatementTool()
    # tool = SearchNewsTool(embeddings=embeddings)
    # tool = SearchReportTool()
    # tool = NewsSentimentAnalysisTool()
    tool = ReportSentimentAnalysisTool()
    # tool = YouTubeSearchTool()
    # tool = GetAccountTool()
    
    result = await tool._arun(
        ticker_symbol="005930",
        config={
            "configurable": {
                "tracer": langfuse.trace(
                    name="test_tool",
                )
            }
        },
        # start_date="2024-01-01",
        # end_date="2024-01-31"
    )

    # 결과 출력
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
