from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from app.clients import settings
from app.tools.agentic_tools import (
    query_jira,
    search_gitlab_projects,
    get_gitlab_commits,
    query_gitlab_mrs,
    query_confluence,
    search_technical_docs
)

tools = [
    query_jira,
    search_gitlab_projects,
    get_gitlab_commits,
    query_gitlab_mrs,
    query_confluence,
    search_technical_docs
]

def agent(state: MessagesState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)
    llm_with_tools = llm.bind_tools(tools)

    system_prompt = (
        "Ты — полезный ассистент технического лидера. Твоя задача — отвечать на вопросы, "
        "используя предоставленные инструменты для извлечения информации из Jira, GitLab, "
        "Confluence и технической документации. Выбирай подходящие инструменты для решения задачи."
    )

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}

workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent)
tool_node = ToolNode(tools)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

app_graph = workflow.compile()
