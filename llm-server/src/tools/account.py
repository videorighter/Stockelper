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
import dotenv
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.multi_agent.utils import get_user_kis_credentials, get_access_token, check_account_balance, update_user_kis_credentials

dotenv.load_dotenv(override=True)


class GetAccountInfoTool(BaseTool):
    name: str = "get_account_info"
    description: str = "retrieves a user’s account cash balance and the total valuation of the account."
    return_direct: bool = False

    async_engine: object

    def __init__(self, async_database_url: str):
        super().__init__(
            async_engine=create_async_engine(async_database_url, echo=False)
        )

    def _run(self, user_id: int):
        return asyncio.run(self._arun(user_id))
    
    async def _arun(self, user_id: int, config: Optional[RunnableConfig] = None, run_manager: Optional[AsyncCallbackManagerForToolRun] = None):
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="get_account_tool", input=user_id)
        else:
            span = None
            
        user_info = await get_user_kis_credentials(self.async_engine, user_id)
        update_access_token_flag = False
        if not user_info:
            return "There is no account information available."
        
        if not user_info['kis_access_token']:
            access_token = await get_access_token(user_info['kis_app_key'], user_info['kis_app_secret'])
            user_info['kis_access_token'] = access_token
            update_access_token_flag = True
        
        account_info = await check_account_balance(user_info['kis_app_key'], user_info['kis_app_secret'], user_info['kis_access_token'], user_info['account_no'])
        if account_info is None:
            return "There is no account information available."
        
        if account_info == "기간이 만료된 token 입니다.":
            user_info['kis_access_token'] = await get_access_token(user_info['kis_app_key'], user_info['kis_app_secret'])
            account_info = await check_account_balance(user_info['kis_app_key'], user_info['kis_app_secret'], user_info['kis_access_token'], user_info['account_no'])
            update_access_token_flag = True
            
        if update_access_token_flag:
            await update_user_kis_credentials(self.async_engine, user_id, user_info['kis_access_token'])
        
        if span:
            span.end(output=account_info)
            
        return account_info