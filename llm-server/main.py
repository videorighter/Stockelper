from typing import List, Optional
from pydantic import BaseModel, Field
import dotenv
import logging
import json
import sys
import os
from uuid import uuid4
dotenv.load_dotenv(".env", override=True)

from psycopg_pool import AsyncConnectionPool
from langfuse import Langfuse
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.multi_agent.agent import SupervisorAgent, ReactAgent
from src.multi_agent.prompt import (
    SUPERVISOR_AGENT,
    MARKET_ANALYSIS_AGENT,
    FUNDAMENTAL_ANALYSIS_AGENT,
    TECHNICAL_ANALYSIS_AGENT,
    INVESTMENT_STRATEGY_AGENT,
    TRADING_AGENT,
)
from src.tools import *


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Initialize Langfuse for monitoring (if configured)
langfuse = None
if all(os.getenv(key) for key in ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_HOST"]):
    langfuse = Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.environ["LANGFUSE_HOST"],
    )

app = FastAPI(debug=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "Stockelper is ready to help with your investment questions!"}


class ChatRequest(BaseModel):
    user_id: int = Field(
        description="사용자 ID",
        default=1
    )
    thread_id: str = Field(
        description="스레드 ID",
        default="test_thread_id"
    )
    message: str = Field(
        description="채팅 메시지",
        default="삼성전자에 대한 투자전략을 추천해줘"
    )
    human_feedback: Optional[bool] = Field(
        description="사용자 피드백",
        default=None
    )

class Response(BaseModel):
    message: str = Field(
        description="채팅 메시지",
        default="삼성전자에 대한 투자전략은 다음과 같습니다. ..."
    )
    subgraph: dict = Field(
        description="종목에 대한 서브그래프. 만약 서브그래프가 없는경우 빈 딕셔너리를 반환",
        default={}
    )
    trading_action: Optional[dict] = Field(
        description="투자전략 추천시 구체적인 트레이딩 액션. 트레이딩 액션이 없는 경우 None. order_side는 buy, sell 중 하나. order_type는 market, limit 중 하나. order_price는 주문 가격으로 order_type이 limit인 경우에만 주문 가격이 존재하고 market인 경우 null. order_quantity는 주문 수량.",
        default={
            "order_side": "buy",
            "order_type": "limit",
            "stock_code": "005930",
            "order_price": 100000,
            "order_quantity": 20
        }
    )
    error: Optional[str] = Field(
        description="에러 메시지",
        default=None
    )


# Initialize embeddings model
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3", 
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini")

# Initialize multimodal LLM for image processing
multi_modal_llm = ChatOpenAI(
    model="gpt-4o",
    max_tokens=1000,
    temperature=0
)

@app.post("/stock/chat", response_model=Response, status_code=status.HTTP_200_OK)
async def stock_chat(request: ChatRequest) -> Response:
    try:
        # Load stock code dictionary
        with open("./set.json", "r") as f:
            code_dict = json.load(f)

        # Initialize database connection pool
        async with AsyncConnectionPool(conninfo=os.getenv("CHECKPOINT_DATABASE_URI"), kwargs={"autocommit": True}) as pool:
            user_id = request.user_id
            thread_id = request.thread_id
            query = request.message
            human_feedback = request.human_feedback
            checkpointer = AsyncPostgresSaver(pool)

            logger.info(f"Received query: {query}")

            await checkpointer.setup()

            # Initialize SupervisorAgent with all specialized agents
            graph = SupervisorAgent(
                llm=llm,
                system=SUPERVISOR_AGENT,
                agents=[
                    ReactAgent(
                        llm=llm,
                        tools=[
                            SearchNewsTool(embeddings=embeddings),
                            SearchReportTool(),
                            NewsSentimentAnalysisTool(),
                            ReportSentimentAnalysisTool(),
                            YouTubeSearchTool(),
                            GraphQATool(),
                        ],
                        system=MARKET_ANALYSIS_AGENT.format(code_dict=json.dumps(code_dict, indent=4, ensure_ascii=False)),
                        name="MarketAnalysisAgent",
                    ),
                    ReactAgent(
                        llm=llm,
                        tools=[
                            AnalysisFinancialStatementTool(),
                        ],
                        system=FUNDAMENTAL_ANALYSIS_AGENT.format(code_dict=json.dumps(code_dict, indent=4, ensure_ascii=False)),
                        name="FundamentalAnalysisAgent",
                    ),
                    ReactAgent(
                        llm=llm,
                        tools=[
                            AnalysisStockTool(),
                            PredictStockTool(),
                            StockChartAnalysisTool(llm=multi_modal_llm),
                        ],
                        system=TECHNICAL_ANALYSIS_AGENT.format(code_dict=json.dumps(code_dict, indent=4, ensure_ascii=False)),
                        name="TechnicalAnalysisAgent",
                    ),
                    ReactAgent(
                        llm=llm,
                        tools=[
                            GetAccountInfoTool(async_database_url=os.environ["ASYNC_DATABASE_URL"]),
                            BraveSearchTool(),
                        ],
                        system=INVESTMENT_STRATEGY_AGENT,
                        name="InvestmentStrategyAgent",
                    ),
                ],
                trading_system=TRADING_AGENT.format(code_dict=json.dumps(code_dict, indent=4, ensure_ascii=False)),
                checkpointer=checkpointer,
                async_database_url=os.environ["ASYNC_DATABASE_URL"]
            )

            # Setup configuration with tracing
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "max_execute_agent_count": 5,
                }
            }
            
            # Add tracing if Langfuse is configured
            if langfuse:
                config["configurable"]["tracer"] = langfuse.trace(
                    name="stockelper",
                    user_id=user_id,
                    session_id=thread_id,
                    metadata={"query": query}
                )
                
            logger.info(f"Using config: {config}")

            # Process the user's message
            if human_feedback is None:
                # This is a new query
                messages = [
                    {"role": "user", "content": query}
                ]
                
                # Initialize the state
                state = {
                    "messages": messages,
                    "thread_id": thread_id,
                    "current_query": query,
                    "current_agent": "",
                    "graph": {"nodes": [], "edges": []},
                    "trading_action": None,
                    "human_feedback": None,
                    "is_investment_advice": False,
                    "is_graph_query": False,
                    "error": None,
                }
            else:
                # This is a feedback response
                state = await checkpointer.get_state(f"stockelper-{thread_id}")
                if not state:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Thread {thread_id} not found"
                    )
                    
                # Update the state with the human feedback
                state["human_feedback"] = human_feedback
                
                # Prepare trading action confirmation
                if human_feedback:
                    # User confirmed the trading action
                    result = "Your trading order has been submitted. Thank you for confirming."
                else:
                    # User rejected the trading action
                    result = "Trading order was not submitted. You can ask me for different investment advice if needed."
                    
                state["messages"].append({"role": "assistant", "content": result})
                
                # No need to run the graph for feedback responses
                return Response(
                    message=result,
                    subgraph={},
                    trading_action=None,
                    error=None
                )

            # Run the graph to get a response
            result = await graph(config=config)
            
            # Extract the final message from the state
            final_messages = result.get("messages", [])
            assistant_messages = [m for m in final_messages if m["role"] == "assistant"]
            
            if not assistant_messages:
                raise ValueError("No assistant messages were generated")
                
            response_message = assistant_messages[-1]["content"]
            trading_action = result.get("trading_action", None)
            graph_data = result.get("graph", {"nodes": [], "edges": []})
            error = result.get("error", None)
            
            return Response(
                message=response_message,
                subgraph=graph_data,
                trading_action=trading_action,
                error=error
            )
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return Response(
            message="Sorry, I encountered an error processing your request. Please try again.",
            subgraph={},
            trading_action=None,
            error=str(e)
        )

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "stockelper-llm"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("APP_PORT", "21009")), reload=True)
