from typing import TypedDict, List, Annotated, Dict, Any, Optional
import operator
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from langgraph.prebuilt import create_react_agent
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

class SubTask(BaseModel):
    id: str = Field(description="Уникальный идентификатор подзадачи (например, 'task_1').")
    description: str = Field(description="Подробное описание того, что нужно сделать в этой подзадаче.")
    dependencies: List[str] = Field(description="Список ID подзадач, которые должны быть выполнены до этой (оставьте пустым, если нет).", default=[])

class Plan(BaseModel):
    steps: List[SubTask] = Field(description="Список подзадач для выполнения запроса.")

class ReviewDecision(BaseModel):
    approved: bool = Field(description="True, если результат работы приемлем, иначе False.")
    feedback: str = Field(description="Отзыв о проделанной работе, что нужно исправить (если approved=False), либо комментарий об успехе.")

class DeepResearchState(TypedDict):
    original_query: str
    plan: List[SubTask]
    current_task_id: Optional[str]
    completed_tasks: Annotated[Dict[str, str], operator.ior]
    task_results: Annotated[Dict[str, str], operator.ior]
    final_report: str
    messages: Annotated[List[BaseMessage], operator.add]

def planner_node(state: DeepResearchState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key)
    structured_llm = llm.with_structured_output(Plan)

    system_prompt = (
        "Ты — Агент-Планировщик в системе Deep Research. "
        "Твоя задача — разбить сложный запрос пользователя на дерево простых подзадач (sub-tasks). "
        "Учитывай, что Исполнители (Worker Agents) имеют доступ к инструментам: Jira API, GitLab API, Confluence API и векторному поиску по базе знаний (OpenSearch). "
        "Подумай логически: например, сначала нужно найти ID проекта, потом вытащить MR, потом найти связанные таски и т.д. "
        "Напиши план на русском языке."
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["original_query"])]
    plan = structured_llm.invoke(messages)

    # Initialize the current task
    first_task_id = None
    if plan and plan.steps:
        # Simple strategy: Just execute in order provided
        first_task_id = plan.steps[0].id

    return {"plan": plan.steps if plan else [], "current_task_id": first_task_id}

def worker_node(state: DeepResearchState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    # Create an agent that uses the tools
    worker_agent = create_react_agent(llm, tools=tools)

    current_task_id = state.get("current_task_id")
    if not current_task_id:
        return {}

    # Find the task definition
    task_def = next((t for t in state["plan"] if t.id == current_task_id), None)
    if not task_def:
        return {}

    # Provide context of previous tasks to the worker
    context = ""
    if state.get("task_results"):
        context = "Контекст из предыдущих задач:\n"
        for t_id, res in state["task_results"].items():
            context += f"--- {t_id} ---\n{res}\n"

    system_prompt = (
        "Ты — Агент-Исполнитель. Твоя цель выполнить текущую подзадачу, используя доступные инструменты.\n\n"
        f"Текущая подзадача: {task_def.description}\n\n"
        f"{context}\n"
        "Отвечай подробно, приводя все найденные факты на русском языке."
    )

    # Invoke the react agent

    # Invoke the react agent
    # Incorporate previous messages (e.g. feedback from reviewer)
    worker_messages = [SystemMessage(content=system_prompt)]
    if state.get("messages"):
        worker_messages.extend(state["messages"])
    worker_messages.append(HumanMessage(content="Приступай к выполнению подзадачи."))

    inputs = {"messages": worker_messages}

    response = worker_agent.invoke(inputs)

    final_message = response["messages"][-1].content

    return {
        "task_results": {current_task_id: final_message}
    }

def reviewer_node(state: DeepResearchState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key)
    structured_llm = llm.with_structured_output(ReviewDecision)

    current_task_id = state.get("current_task_id")
    if not current_task_id:
        return {}

    task_def = next((t for t in state["plan"] if t.id == current_task_id), None)
    worker_result = state.get("task_results", {}).get(current_task_id, "")

    system_prompt = (
        "Ты — Агент-Рецензент. Твоя задача — проверить результат работы Агента-Исполнителя. "
        f"Оригинальный запрос: {state['original_query']}\n"
        f"Текущая подзадача: {task_def.description if task_def else ''}\n"
        f"Результат исполнителя:\n{worker_result}\n\n"
        "Проверь: достаточен ли результат? Ответил ли он на вопрос подзадачи? "
        "Если да, верни approved=True. Если нет, верни approved=False и укажи, что нужно доделать."
    )

    decision = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content="Оцени результат.")])

    if decision.approved:
        # Move to next task
        plan = state["plan"]
        current_idx = next((i for i, t in enumerate(plan) if t.id == current_task_id), -1)
        next_task_id = plan[current_idx + 1].id if current_idx != -1 and current_idx + 1 < len(plan) else None

        return {
            "completed_tasks": {current_task_id: "approved"},
            "current_task_id": next_task_id
        }
    else:
        # Modify the task description based on feedback so worker tries again with feedback
        # Not modifying state["plan"] directly as it's complex, instead pass a message to state
        feedback_msg = f"Рецензент отклонил результат. Причина: {decision.feedback}. Попробуй еще раз, используя эту обратную связь."
        return {
            "messages": [SystemMessage(content=feedback_msg)] # This will just accumulate, worker node can see it if we updated it, but simplest is just not advance current_task_id
        }

def reviewer_router(state: DeepResearchState):
    current_task_id = state.get("current_task_id")
    # If the task ID didn't change and it's not None, it means the reviewer rejected it
    # But wait, how do we know it rejected it if we just don't change the task_id?
    # Let's check completed_tasks
    completed = state.get("completed_tasks", {})

    if current_task_id is None:
        return "synthesizer" # No more tasks

    # Wait, the current_task_id is updated in reviewer_node if approved.
    # If it's approved, it advances to next_task_id.
    # If it's rejected, it stays the SAME task_id.
    # So if the task we just reviewed is still the current_task_id, it means it was rejected.
    # But we need to know WHICH task we just reviewed.
    # Let's just say if current_task_id is still in the state but not in completed_tasks, it's rejected.
    if current_task_id not in completed:
        return "worker" # try again

    return "worker" # approved, move to the newly assigned current_task_id

def synthesizer_node(state: DeepResearchState):
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key)

    context = ""
    if state.get("task_results"):
        for t_id, res in state["task_results"].items():
            context += f"--- Подзадача: {t_id} ---\n{res}\n\n"

    system_prompt = (
        "Ты — Главный Агент-Синтезатор системы Deep Research. "
        "Твоя задача — составить финальный, комплексный и хорошо структурированный отчет на основе собранных данных. "
        "Отвечай на русском языке, используй Markdown."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Оригинальный запрос: {state['original_query']}\n\nСобранные данные:\n{context}")
    ]

    response = llm.invoke(messages)

    return {"final_report": response.content}


deep_research_graph_builder = StateGraph(DeepResearchState)

deep_research_graph_builder.add_node("planner", planner_node)
deep_research_graph_builder.add_node("worker", worker_node)
deep_research_graph_builder.add_node("reviewer", reviewer_node)
deep_research_graph_builder.add_node("synthesizer", synthesizer_node)

deep_research_graph_builder.add_edge(START, "planner")
deep_research_graph_builder.add_edge("planner", "worker")
deep_research_graph_builder.add_edge("worker", "reviewer")

# Router after reviewer:
deep_research_graph_builder.add_conditional_edges(
    "reviewer",
    reviewer_router,
    {
        "worker": "worker",
        "synthesizer": "synthesizer"
    }
)

deep_research_graph_builder.add_edge("synthesizer", END)

deep_research_graph = deep_research_graph_builder.compile()
