from typing import List, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_core.prompts import ChatPromptTemplate
from .clients import settings

class RAGState(TypedDict):
    question: str
    documents: List[str]
    answer: str

def retrieve(state: RAGState):
    question = state["question"]
    openai_api_key = settings.get("OPENAI_API_KEY", "")

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    os_url = settings.get("OPENSEARCH_URL")
    os_user = settings.get("OPENSEARCH_USER")
    os_password = settings.get("OPENSEARCH_PASSWORD")
    verify_certs = settings.get("OPENSEARCH_VERIFY_CERTS", default=True)

    vectorstore = OpenSearchVectorSearch(
        opensearch_url=os_url,
        index_name="confluence-rag-index",
        embedding_function=embeddings,
        http_auth=(os_user, os_password),
        use_ssl=True,
        verify_certs=verify_certs,
        ssl_assert_hostname=verify_certs,
        ssl_show_warn=not verify_certs,
    )

    retriever = vectorstore.as_retriever()
    docs = retriever.invoke(question)

    return {"documents": [doc.page_content for doc in docs]}

def generate(state: RAGState):
    question = state["question"]
    documents = state.get("documents", [])

    context = "\n\n".join(documents)

    prompt = ChatPromptTemplate.from_template(
        "Ты — полезный ассистент технического лидера. Твоя задача — отвечать на вопросы, основываясь на предоставленном контексте.\n"
        "Если в контексте нет информации для ответа, честно скажи, что не знаешь.\n"
        "\n"
        "Контекст:\n{context}\n"
        "\n"
        "Вопрос: {question}"
    )

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)

    chain = prompt | llm

    response = chain.invoke({"context": context, "question": question})

    return {"answer": response.content}

# Define the graph
workflow = StateGraph(RAGState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

app_graph = workflow.compile()
