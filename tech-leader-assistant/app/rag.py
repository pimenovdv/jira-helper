from typing import List, TypedDict, Annotated, Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from app.clients import settings
from app.tools.agentic_tools import (
    query_jira,
    search_gitlab_projects,
    get_gitlab_commits,
    query_gitlab_mrs,
    query_confluence,
    search_technical_docs
)

class RAGState(TypedDict):
    question: str
    messages: Annotated[List[BaseMessage], add_messages]
    answer: str
    documents: List[str]

tools = [
    query_jira,
    search_gitlab_projects,
    get_gitlab_commits,
    query_gitlab_mrs,
    query_confluence,
    search_technical_docs
]
tool_node = ToolNode(tools)

def agent(state: RAGState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)
    llm_with_tools = llm.bind_tools(tools)

    is_initial = not state.get("messages", [])
    messages = state.get("messages", [])
    if is_initial:
        messages = [
            {"role": "system", "content": "Ты — полезный ассистент технического лидера. Твоя задача — отвечать на вопросы и проводить глубокий анализ, используя предоставленные инструменты.\nЕсли информации недостаточно, честно скажи, что не знаешь."},
            {"role": "user", "content": state["question"]}
        ]

    response = llm_with_tools.invoke(messages)
    if is_initial:
        return {"messages": messages + [response]}
    else:
        return {"messages": [response]}



def should_continue(state: RAGState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tools"
    return "finalize"

def finalize(state: RAGState):
    messages = state["messages"]
    last_message = messages[-1]

    documents = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content
            if content:
                documents.append(str(content))

    return {
        "answer": last_message.content,
        "documents": documents
    }

workflow = StateGraph(RAGState)
workflow.add_node("agent", agent)
workflow.add_node("tools", tool_node)
workflow.add_node("finalize", finalize)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "finalize": "finalize"})
workflow.add_edge("tools", "agent")
workflow.add_edge("finalize", END)

app_graph = workflow.compile()
