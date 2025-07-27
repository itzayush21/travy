import os, requests, markdown
from typing import Literal
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

# ========== ENV SETUP ==========
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MessagesState = dict  # {"messages": [...]}

# ========== TAVILY TOOL ==========

@tool
def research_via_tavily(query: str) -> str:
    """Use Tavily to search live travel information about a destination."""
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
            json={"query": query, "search_depth": "advanced", "include_answer": True},
            timeout=10
        )
        data = response.json()
        if data.get("answer"):
            return data["answer"]
        elif data.get("results"):
            texts = []
            for result in data["results"]:
                soup = BeautifulSoup(result.get("content", ""), "html.parser")
                texts.append(soup.get_text(separator=" ", strip=True)[:300])
            return "\n\n".join(texts[:2])
        return "No relevant info found."
    except Exception as e:
        return f"[Tavily Search Error] {str(e)}"

# ========== GROQ LLM CALL ==========

def run_groq(prompt: str, system_prompt: str) -> str:
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 512
            },
            timeout=12
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Groq API Error] {str(e)}"

def run_research_llm(user_prompt: str, context: str = "") -> str:
    system_prompt = (
        "You are a destination research assistant.\n"
        "The user will ask about places, activities, tips, and best times for travel.\n\n"
        "You should:\n"
        "- Break the query into subtopics if needed (like weather, attractions, food, safety).\n"
        "- Use `research_via_tavily` to gather facts.\n"
        "- Return a concise and structured guide in Markdown.\n"
        "Avoid guessing. Say 'No info found' if data is missing.\n"
        "KEEP THE ANSWER UNDER 500 WORDS.\n\n"
    )
    return run_groq(user_prompt, system_prompt)

# ========== AGENT DEFINITION ==========

class DestinationResearchAgent:
    def __init__(self):
        self.memory = MemorySaver()
        self.tool_node = ToolNode(tools=[research_via_tavily])

    def model_node(self, state: MessagesState) -> MessagesState:
        messages = state["messages"]
        user_msg = messages[-1].content if messages else "Tell me about a travel destination"

        context = "\n".join([msg.content for msg in messages if isinstance(msg, (SystemMessage, HumanMessage))])
        result = run_research_llm(user_msg, context)
        return {"messages": messages + [AIMessage(content=result)]}

    def router(self, state: MessagesState) -> Literal["tools", END]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    def __call__(self):
        graph = StateGraph(MessagesState)
        graph.add_node("research_agent", self.model_node)
        graph.add_node("tools", self.tool_node)

        graph.set_entry_point("research_agent")
        graph.add_conditional_edges("research_agent", self.router, {
            "tools": "tools", END: END
        })
        graph.add_edge("tools", "research_agent")

        return graph.compile(checkpointer=self.memory)


# ========== CHAT WRAPPER ==========
app= DestinationResearchAgent()()

chat_sessions = {}

def research_reply(session_id: str, user_message: str) -> str:
    system = SystemMessage(content="You help travelers research destinations with facts and structure.")
    user = HumanMessage(content=user_message)

    if session_id not in chat_sessions:
        chat_sessions[session_id] = [system, user]
    else:
        chat_sessions[session_id].append(user)

    config = RunnableConfig(configurable={"thread_id": session_id})
    result = app.invoke({"messages": chat_sessions[session_id]}, config=config)

    response_msg = result["messages"][-1]
    chat_sessions[session_id].append(response_msg)

    return markdown.markdown(response_msg.content)  # For frontend HTML rendering