import os
import json
from pydantic import BaseModel, Field, Extra
from typing import Optional, Dict, List, Any
import asyncio
from dataclasses import asdict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt
from langgraph.graph import StateGraph
from neo4j import GraphDatabase
from sqlalchemy.ext.asyncio import create_async_engine
from .state import SubState, State, SubConfig, Config
from .utils import place_order, get_user_kis_credentials

class ReactAgent:
    def __new__(cls, llm, tools, system, name):
        instance = super().__new__(cls)
        instance.__init__(llm, tools, system, name)
        return instance.graph

    def __init__(self, llm, tools, system, name):
        self.llm_with_tools = llm.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        self.name = name
        self.system_message = SystemMessage(content=system)

        workflow = StateGraph(SubState)
        workflow.add_node("agent", self.agent)
        workflow.add_node("execute_tool", self.execute_tool)

        workflow.add_edge("__start__", "agent")
        self.graph = workflow.compile()
        self.graph.name = name

    async def agent(self, state: SubState, config: RunnableConfig):
        if "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="agent", input=asdict(state))
        else:
            span = None


        messages = [self.system_message] + state.messages

        # result = await self.llm_with_tools.ainvoke(messages, config={"callbacks": [span.get_langchain_handler()]} if span else {})
        result = await self.llm_with_tools.ainvoke(messages)
        result.name = self.name

        update = None
        goto = None

        if result.tool_calls:
            if (
                state.execute_tool_count
                >= config["configurable"]["max_execute_tool_count"]
            ):
                update = {"messages": [AIMessage(content="더 이상 실행할 수 없습니다.")]}
                goto = "__end__"
            else:
                update = {"messages": [result]}
                goto = "execute_tool"
        else:
            update = {"messages": [AIMessage(content=result.content)]}
            goto = "__end__"

        if span:
            span.end(output=update)
        return Command(update=update, goto=goto)

    async def execute_tool(self, state: SubState, config: RunnableConfig):
        if "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="execute_tool", input=asdict(state))
        else:
            span = None

        outputs = []

        # 모든 tool_call을 병렬로 처리하기 위한 태스크 리스트 생성
        tasks = []
        for tool_call in state.messages[-1].tool_calls:
            task = self.tools_by_name[tool_call["name"]]._arun(**tool_call["args"], config={"configurable": {"tracer": span}} if span else {})
            tasks.append((tool_call, task))

        results = await asyncio.gather(*[task for _, task in tasks])

        # 모든 태스크 비동기적으로 실행
        for (tool_call, _), result in zip(tasks, results):
            outputs.append(
                ToolMessage(
                    name=tool_call["name"],
                    content=json.dumps(result, indent=2, ensure_ascii=False),
                    tool_call_id=tool_call["id"],
                )
            )

        update = {
            "messages": outputs,
            "execute_tool_count": state.execute_tool_count + 1,
        }
        goto = "agent"

        if span:
            span.end(output=update)
        return Command(update=update, goto=goto)



class Router(BaseModel):
    target: str = Field(
        description="The target of the message, either 'User' or 'MarketAnalysisAgent' or 'FundamentalAnalysisAgent' or 'TechnicalAnalysisAgent' or 'InvestmentStrategyAgent'"
    )
    message: str = Field(description="The message in korean to be sent to the target")

class RouterList(BaseModel):
    routers: List[Router] = Field(description="The list of one or more routers")


class TradingAction(BaseModel):
    stock_code: str = Field(description="Stock code of the security to be ordered, referring to <Stock_Code>.")
    order_side: str = Field(description="The side of the order to be traded. buy or sell")
    order_type: str = Field(description="The type of the order to be traded. market or limit")
    order_price: Optional[float] = Field(description="The price of the stock to be traded. If the order_type is ‘market’, then use None.")
    order_quantity: int = Field(description="The quantity of the stock to be traded")


class SupervisorAgent:
    def __new__(cls, llm, system, agents, trading_system, checkpointer, async_database_url: str):
        instance = super().__new__(cls)
        instance.__init__(llm, system, agents, trading_system, checkpointer, async_database_url)
        return instance.graph

    def __init__(self, llm, system, agents, trading_system, checkpointer, async_database_url: str):
        self.async_engine = create_async_engine(async_database_url, echo=False)
        self.llm = llm
        self.llm_with_router = llm.with_structured_output(RouterList)
        self.llm_with_trading = llm.with_structured_output(TradingAction)
        self.agents_by_name = {agent.name: agent for agent in agents}
        self.system_message = {
            "role": "system",
            "content": system,
        }
        self.trading_system = trading_system
        # 그래프 구성
        self.workflow = StateGraph(State)
        self.workflow.add_node("agent", self.agent)
        self.workflow.add_node("execute_agent", self.execute_agent)
        self.workflow.add_node("execute_trading", self.execute_trading)
        # 엣지 추가
        self.workflow.add_edge("__start__", "agent")

        # 그래프 컴파일
        self.graph = self.workflow.compile(checkpointer=checkpointer)
        self.graph.name = "stockelper SupervisorAgent"

    async def agent(self, state: State, config: RunnableConfig) -> State:
        if "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="supervisor", input=asdict(state))
        else:
            span = None

        update = None
        goto = None

        if (
            state.agent_results
            and state.execute_agent_count > 0
            and state.agent_results[-1]["target"] == "InvestmentStrategyAgent"
        ):
            result = state.agent_results[-1]["result"]
            trading_messages = [
                {
                    "role": "system",
                    "content": self.trading_system + "\n" + "<Investment_Report>\n" + result + "\n</Investment_Report>",
                }
            ]
            # trading_action = await self.llm_with_trading.ainvoke(trading_messages, config={"callbacks": [span.get_langchain_handler()]} if span else {})
            trading_action = await self.llm_with_trading.ainvoke(trading_messages)
            messages = [AIMessage(content=result + "\n\n아래 주문 정보를 수락하겠습니까?\n" + trading_action.model_dump_json())]

            stock_name = self.get_stock_name_by_query(state.messages[-1].content)
            if stock_name == "없음":
                subgraph = state.subgraph
            else:
                if stock_name == state.stock_name:
                    subgraph = state.subgraph
                else:
                    subgraph = self.get_subgraph_by_stock_name(stock_name)

            update = {"messages": messages, "trading_action": trading_action.model_dump(), "subgraph": subgraph, "stock_name": stock_name}
            goto = "execute_trading"
        
        else:
            if state.agent_results:
                agent_results_str = json.dumps(
                    state.agent_results, indent=2, ensure_ascii=False
                )
            else:
                agent_results_str = "[]"
            human_message = [HumanMessage(content=f"<user>\n{state.messages[-1].content}\n<user>\n\n<agent_analysis_result>\n{agent_results_str}\n<agent_analysis_result>")]

            messages = [self.system_message] + state.messages[:-1] + human_message

            # response = await self.llm_with_router.ainvoke(messages, config={"callbacks": [span.get_langchain_handler(update_parent=True)]} if span else {})
            response = await self.llm_with_router.ainvoke(messages, config={"callbacks": [span.get_langchain_handler(update_parent=True)]} if span else {})

            if response.routers[0].target == "User":
                stock_name = self.get_stock_name_by_query(state.messages[-1].content)
                if stock_name == "없음":
                    subgraph = state.subgraph
                else:
                    if stock_name == state.stock_name:
                        subgraph = state.subgraph
                    else:
                        subgraph = self.get_subgraph_by_stock_name(stock_name)
                update = State(
                    messages=[AIMessage(content=response.routers[0].message)],
                    agent_results=state.agent_results,
                    subgraph=subgraph,
                    stock_name=stock_name
                )
                goto = "__end__"
            else:
                if (
                    state.execute_agent_count
                    >= config["configurable"]["max_execute_agent_count"]
                ):
                    stock_name = self.get_stock_name_by_query(state.messages[-1].content)
                    if stock_name == "없음":
                        subgraph = state.subgraph
                    else:
                        if stock_name == state.stock_name:
                            subgraph = state.subgraph
                        else:
                            subgraph = self.get_subgraph_by_stock_name(stock_name)
                    update = State(
                        messages=[AIMessage(content="더 이상 실행할 수 없습니다.")],
                        agent_results=state.agent_results,
                        subgraph=subgraph,
                        stock_name=stock_name
                    )
                    goto = "__end__"
                else:
                    update = {
                        "agent_messages": [
                            router.model_dump() for router in response.routers
                        ],
                        "execute_agent_count": state.execute_agent_count + 1,
                    }
                    goto = "execute_agent"

        if span:
            span.end(output=update)
        return Command(update=update, goto=goto)

    async def execute_agent(self, state: State, config: RunnableConfig):
        if "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="execute_agent", input=asdict(state))
        else:
            span = None

        tasks = []
        for router in state.agent_messages:
            if state.agent_results:
                agent_results_str = json.dumps(
                    state.agent_results, indent=2, ensure_ascii=False
                )
                content = f"<user>\n{router['message']}\n</user>\n\n<agent_analysis_result>\n{agent_results_str}\n<agent_analysis_result>\n"
            else:
                content = f"<user>\n{router['message']}\n</user>\n"
            
            input = {"messages": [HumanMessage(content=content)]}
            task = self.agents_by_name[router["target"]].ainvoke(
                input,
                config=RunnableConfig(configurable={"max_execute_tool_count": 5, "tracer": span.span(name=router["target"], input=input) if span else None}),
            )
            tasks.append((router, task))

        results = await asyncio.gather(*[task for _, task in tasks])

        agent_results = []
        for (router, _), result in zip(tasks, results):
            agent_results.append(
                router | {"result": result["messages"][-1].content}
            )

        update = {
            "agent_messages": [],
            "agent_results": state.agent_results + agent_results,
            "execute_agent_count": state.execute_agent_count + 1,
        }
        goto = "agent"

        if span:
            span.end(output=update)
        return Command(update=update, goto=goto)
    
    async def execute_trading(self, state: State, config: RunnableConfig):
        if "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="execute_trading", input=asdict(state))
        else:
            span = None

        human_check = interrupt("interrupt")
        print("human_check", human_check)
        
        if human_check:
            user_info = await get_user_kis_credentials(self.async_engine, state.user_id)
            kwargs = state.trading_action | user_info

            trading_result = place_order(**kwargs)

            # update = {"messages": [AIMessage(content=trading_result)], "trading_action": {}}
            update = State(
                messages=[AIMessage(content=trading_result)],
                agent_results=[],
                stock_name=state.stock_name,
                subgraph=state.subgraph
            )
            goto = "__end__"
        else:
            update = State(
                messages=[AIMessage(content="주문을 취소합니다.")],
                agent_results=state.agent_results,
                stock_name=state.stock_name,
                subgraph=state.subgraph
            )
            goto = "__end__"

        if span:
            span.end(output=update)
        return Command(update=update, goto=goto)
            
    def get_stock_name_by_query(self, query):
        prompt_filter_stock_name = '''
        문장에서 종목명(stock_name)만 정확히 추출해 주세요.
        단, 반드시 종목명만 한 줄로 출력해 주세요. 불필요한 설명이나 다른 정보는 포함하지 마세요.
        만약, 종목명이 없으면 '없음'으로 출력해 주세요.

        예를들면, 종목명이 있는 문장은 다음과 같습니다.
        <query>
            SK하이닉스의 경쟁사를 알려주고, 경쟁사의 pbr, per, bps, eps을 알려줘"
        </query>
        <output>
            SK하이닉스
        </output>

        예를들면, 종목명이 없는 문장은 다음과 같습니다.
        <query>
            안녕하세요. 스톡헬퍼 챗봇입니다. 종목명을 입력해주세요.
        </query>
        <output>
            없음
        </output>

        다음 문장에서 종목명(stock_name)만 정확히 추출해 주세요.
        <query>
            {query}
        </query>
        
        <output>
        </output>
        '''
        final_query = prompt_filter_stock_name.format(query=query)
        stock_name = self.llm.invoke(final_query).content
        return stock_name
    
    def get_subgraph_by_stock_name(self, stock_name):
        driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
        
        query = """
        MATCH (c:Company {stock_name: $stock_name})
        CALL {
            WITH c
            MATCH (c)-[r]->(n)
            WHERE type(r) IN ['HAS_COMPETITOR', 'BELONGS_TO']
            RETURN collect({
                node_type: labels(n)[0],
                properties: properties(n),
                node_name: CASE 
                    WHEN labels(n)[0] = 'Company' THEN n.stock_name
                    WHEN labels(n)[0] = 'Sector' THEN n.sector
                END
            }) as nodes,
            collect({
                start: {
                    name: c.stock_name,
                    type: labels(c)[0]
                },
                relationship: type(r),
                end: {
                    name: CASE 
                        WHEN type(r) = 'HAS_COMPETITOR' THEN n.stock_name
                        WHEN type(r) = 'BELONGS_TO' THEN n.sector
                    END,
                    type: labels(n)[0]
                }
            }) as relations
        }
        WITH nodes, relations, c
        RETURN nodes + [{
            node_type: labels(c)[0],
            properties: properties(c),
            node_name: c.stock_name
        }] as nodes,
        relations as relations
        """
        
        with driver.session() as session:
            result = session.run(query, stock_name=stock_name)
            record = result.single()
            if record:
                return {
                    "node": record["nodes"],
                    "relation": record["relations"]
                }
            return {}