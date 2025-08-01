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
    print(f"[GROQ CALL] run_groq(prompt='{prompt[:50]}...')")
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

# ========== GROQ LLM CALL FOR GOVERNANCE ==========
def run_governance_llm(user_prompt: str, context: str = "") -> str:
    system_prompt = (
    "You are a travel assistant specialized in local governance, fair pricing, regulations, and helping travelers navigate local conditions.\n\n"
    "You help users with:\n"
    "- Local prices (fair shopping rates, food, transport, etc.)\n"
    "- Local norms and cultural do’s and don’ts\n"
    "- Rules, fines, restrictions (e.g., drinking age, dress codes, tipping laws)\n"
    "- How to avoid scams and unfair practices\n"
    "- Basic translations (if asked)\n"
    "- Emergency info (hospitals, police) if relevant to the query\n"
    "- Advice on specific user problems (e.g., what to pay for a shawl, how to use local metro, avoiding overcharging)\n\n"
    "Instructions:\n"
    "- Try to solve exactly what the user is asking, clearly and directly.\n"
    "- If the user asks about prices or shopping, provide fair market rates and bargaining advice.\n"
    "- If the query needs updated data, use `research_via_tavily`.\n"
    "- Organize your reply into short sections or bullet points.\n"
    "- Keep it under 200 words.\n"
    "- If info isn't found, reply: 'Local information is not available.'\n"
)

    return run_groq(user_prompt, system_prompt)


# ========== AGENT DEFINITION ==========
class GovernanceInfoAgent:
    def __init__(self):
        self.memory = MemorySaver()
        self.tool_node = ToolNode(tools=[research_via_tavily])

    def model_node(self, state: MessagesState) -> MessagesState:
        messages = state["messages"]
        user_msg = messages[-1].content if messages else "What are the local rules?"

        context = "\n".join([msg.content for msg in messages if isinstance(msg, (SystemMessage, HumanMessage))])
        result = run_governance_llm(user_msg, context)
        return {"messages": messages + [AIMessage(content=result)]}

    def router(self, state: MessagesState) -> Literal["tools", END]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    def __call__(self):
        graph = StateGraph(MessagesState)
        graph.add_node("governance_agent", self.model_node)
        graph.add_node("tools", self.tool_node)

        graph.set_entry_point("governance_agent")
        graph.add_conditional_edges("governance_agent", self.router, {
            "tools": "tools", END: END
        })
        graph.add_edge("tools", "governance_agent")

        return graph.compile(checkpointer=self.memory)



# ========== CHAT WRAPPER ==========
gov_app = GovernanceInfoAgent()()

gov_chat_sessions = {}

def governance_reply(session_id: str,user_detail:str, user_message: str) -> str:
    system = SystemMessage(content="You assist travelers with local laws, rules, pricing, and basic language help.")
    user_info= HumanMessage(content=user_detail)
    user = HumanMessage(content=user_message)

    if session_id not in gov_chat_sessions:
        gov_chat_sessions[session_id] = [system,user_info,user]
    else:
        gov_chat_sessions[session_id].append([user, user_info])

    config = RunnableConfig(configurable={"thread_id": session_id})
    result = gov_app.invoke({"messages": gov_chat_sessions[session_id]}, config=config)

    response_msg = result["messages"][-1]
    gov_chat_sessions[session_id].append(response_msg)

    return markdown.markdown(response_msg.content)  # For frontend HTML rendering
