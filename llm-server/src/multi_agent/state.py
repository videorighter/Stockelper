import operator
from dataclasses import dataclass, field
from typing import List, Annotated

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.messages.base import BaseMessage
from langgraph.graph.message import add_messages


def custom_add_messages(existing: list, update: list):
    for message in update:
        if not isinstance(message, BaseMessage):
            if message["role"] == "user":
                existing.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                existing.append(AIMessage(content=message["content"]))
            else:
                raise ValueError(f"Invalid message type: {type(message)}")
        else:
            existing.append(message)
    return existing[-10:]


def custom_truncate_agent_results(existing: list, update: list):
    return update[-10:]


@dataclass
class State:
    user_id: int = field(default=None)
    messages: Annotated[list, custom_add_messages] = field(default_factory=list)
    query: str = field(default="")
    agent_messages: list = field(default_factory=list)
    agent_results: Annotated[list, custom_truncate_agent_results] = field(default_factory=list)
    execute_agent_count: int = field(default=0)
    trading_action: dict = field(default_factory=dict)
    stock_name: str = field(default="")
    subgraph: dict = field(default_factory=dict)

@dataclass
class Config:
    max_execute_agent_count: int = field(default=3)


@dataclass
class SubState:
    messages: Annotated[list, custom_add_messages] = field(default_factory=list)
    execute_tool_count: int = field(default=0)

@dataclass
class SubConfig:
    max_execute_tool_count: int = field(default=5)