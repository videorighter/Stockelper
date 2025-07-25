import os
import logging
from fastapi import APIRouter, HTTPException, status
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from langfuse.langchain import CallbackHandler

from multi_agent import multi_agent
from .models import ChatRequest, Response

logger = logging.getLogger(__name__)

langfuse_handler = CallbackHandler()

CHECKPOINT_DATABASE_URI = os.getenv("CHECKPOINT_DATABASE_URI")

router = APIRouter(prefix="/stock", tags=["stock"])

@router.post("/chat", response_model=Response, status_code=status.HTTP_200_OK)
async def stock_chat(request: ChatRequest) -> Response:
    """주식 채팅 API"""
    try:
        async with AsyncConnectionPool(
            conninfo=CHECKPOINT_DATABASE_URI, 
            kwargs={"autocommit": True}
        ) as pool:
            user_id = request.user_id
            thread_id = request.thread_id
            query = request.message
            human_feedback = request.human_feedback
            checkpointer = AsyncPostgresSaver(pool)

            logger.info(f"Received query: {query}")

            await checkpointer.setup()

            # 기존 그래프에 checkpointer 설정
            multi_agent.checkpointer = checkpointer

            config = {
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_session_id": thread_id,
                    "langfuse_user_id": user_id,
                },
                "configurable": {
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "max_execute_agent_count": 5,
                },
            }
            logger.info(f"Using config: {config}")

            if human_feedback is None:
                messages = [
                    {"role": "user", "content": query},
                ]
                response = await multi_agent.ainvoke(
                    {"messages": messages}, 
                    config=config
                )
            else:
                response = await multi_agent.ainvoke(
                    Command(resume=human_feedback), 
                    config=config
                )

        logger.info("Invoking graph with messages")
        logger.info(f"Graph response: {response}")

        if (
            response
            and isinstance(response, dict)
            and "messages" in response
            and response["messages"]
        ):
            logger.info("Returning streaming response")
            return Response(
                message=response["messages"][-1].content, 
                trading_action=response["trading_action"], 
                subgraph=response["subgraph"]
            )

        logger.error("No valid response generated from graph")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid response generated"
        )

    except Exception as e:
        import traceback

        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"Error in stock_chat: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) 