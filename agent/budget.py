import os, json, requests
from typing import Literal
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
import markdown



# === Load your Groq API key ===
load_dotenv()

TAVILY_API_KEY= os.getenv('TAVILY_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def summarize_itinerary(itinerary_text: str) -> str:
    """
    Summarizes a full travel itinerary into day-wise highlights and purposes.
    Each day should have a title, core activities, and type of experiences.

    """
    if not GROQ_API_KEY:
        return "[Groq API Error] Missing API key."

    system_prompt = (
    "You are a travel assistant summarizing a day-wise itinerary for budget planning.\n\n"
    "Given a multi-day travel plan, summarize each day clearly.\n"
    "For each day, output these **seven** fields:\n"
    "1. Day Title (e.g., 'Day 1: Arrival and Fort Visit')\n"
    "2. Key Activities (sightseeing, shopping, cultural events, meals, etc.)\n"
    "3. Estimated Cost Category (High / Moderate / Low / Free)\n"
    "4. Major Transportation Used:\n"
    "   - Include ALL meaningful transport segments like:\n"
    "     - Flight/train arrivals or departures\n"
    "     - Full-day taxi hires, auto/rickshaw trips\n"
    "     - Scenic rides (camel, horse, cable car, boat)\n"
    "     - Transfers to and from hotels or key sights\n"
    "   - DO NOT write 'None' unless the person truly stayed in one place\n"
    "   - If exact mode is unknown, infer based on activity (e.g., 'local rickshaw to city palace')\n"
    "5. Meals / Food Highlights (restaurants, snacks, traditional foods, street food)\n"
    "6. Accommodation Note (mention if staying in a hotel, changing city, overnight travel, etc.)\n"
    "7. Free or Leisure Time (if any)\n\n"
    "DO NOT guess exact prices. Only mark budget level (High/Moderate/Low/Free).\n"
    "Ensure clarity, realism, and accuracy for each field. Do not leave transport undefined or blank."
)


    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": itinerary_text}
                ],
                "temperature": 0.5,
                "top_p": 0.95,
                "max_tokens": 1024
            },
            timeout=15
        )
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        else:
            #print("🚨 Full Response:", json.dumps(data, indent=2))
            return "[Daywise Summary Error] No 'choices' in response."

    except Exception as e:
        return f"[Daywise Summary Exception] {str(e)}"



# ======= Environment Setup ========
MessagesState = dict  # {"messages": [...]}


# ================= Tavily Tool =================

@tool
def tavily_search(query: str) -> str:
    """Search Tavily for travel cost estimates (hotels, food, activities, etc.)."""
    #print(f"[TOOL CALL] tavily_search(query='{query}')")
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
        return f"[Tavily Error] {str(e)}"

# ================= Groq LLM =================

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
                "max_tokens": 2048
            },
            timeout=12
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Groq API Error] {str(e)}"

# ================= Agent =================

class TavilyBudgetAgent:
    def __init__(self):
        self.memory = MemorySaver()
        self.tool_node = ToolNode(tools=[tavily_search])

    def model_node(self, state: MessagesState) -> MessagesState:
        messages = state["messages"]
        user_msg = messages[-1].content if messages else "Plan a travel budget"

        context = "\n".join([msg.content for msg in messages if isinstance(msg, (SystemMessage, HumanMessage))])

        system_prompt = (
    "You are an expert travel budget planner.\n\n"
    "The user will provide a summarized day-wise itinerary, along with:\n"
    "- Number of travelers\n"
    "- Total budget (in ₹)\n"
    "- Travel style preferences (e.g., budget, mid-range, luxury)\n\n"

    "Your responsibilities:\n"
    "1. Estimate realistic costs for each day under these categories:\n"
    "   - Flights / Intercity Travel\n"
    "   - Hotel / Stay\n"
    "   - Food / Dining\n"
    "   - Sightseeing & Activities\n"
    "   - Miscellaneous / Shopping / Entry Fees\n\n"

    "2. Use the `tavily_search` tool wherever required to find real-world cost estimates "
    "(e.g., 'hotel price in Goa', 'boat ride in Udaipur').\n"
    "3. Adjust the plan realistically based on total budget and number of travelers.\n"
    "4. Reflect user preferences in hotel, food, and transport categories.\n\n"

    "Output Format:\n"
    "Day 1: Arrival and Local Visit\n"
    "- Travel: ₹...\n"
    "- Hotel: ₹...\n"
    "- Food: ₹...\n"
    "- Sightseeing: ₹...\n"
    "- Miscellaneous: ₹...\n"
    "Total Day 1: ₹...\n\n"
    "Repeat this format for each day, and then include:\n"
    "Grand Total: ₹...\n"
    "Budget Status: Within / Over\n"
    "Tools Used: List any `tavily_search` queries used"
)

        prompt = f"{context}\n\nUser Request: {user_msg}"
        result = run_groq(prompt, system_prompt)
        return {"messages": messages + [AIMessage(content=result)]}

    def router(self, state: MessagesState) -> Literal["tools", END]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    def __call__(self):
        graph = StateGraph(MessagesState)
        graph.add_node("budget_agent", self.model_node)
        graph.add_node("tools", self.tool_node)

        graph.set_entry_point("budget_agent")
        graph.add_conditional_edges("budget_agent", self.router, {
            "tools": "tools", END: END
        })
        graph.add_edge("tools", "budget_agent")

        return graph.compile(checkpointer=self.memory)

# ================= Chat Entry =================

budget_agent = TavilyBudgetAgent()()
chat_sessions = {}

def budget_reply(session_id: str, user_message: str) -> str:
    system = SystemMessage(content="You help travelers build budgets based on summarized itineraries using Tavily.")
    user = HumanMessage(content=user_message)

    if session_id not in chat_sessions:
        chat_sessions[session_id] = [system, user]
    else:
        chat_sessions[session_id].append(user)

    config = RunnableConfig(configurable={"thread_id": session_id})
    result = budget_agent.invoke({"messages": chat_sessions[session_id]}, config=config)

    response_msg = result["messages"][-1]
    chat_sessions[session_id].append(response_msg)

    #print(f"\n🧠 Context: {[m.content for m in chat_sessions[session_id]]}")
    #print(f"\n✅ Budget Plan:\n{response_msg.content}")
    return response_msg.content


def generate_budget_plan(session_id: str,user_preference,prompt) -> str:
    text=summarize_itinerary(prompt)
    if not text:
        return "Sorry, I couldn't summarize the itinerary. Please try again with a different prompt."
    print(user_preference)
    user_msg = f'''Create a travel budget plan based on the following itinerary:\n\n{text}\n\n'''
    reply = budget_reply(session_id, user_preference+"\n\n\n"+user_msg)
    if not reply:
        return "Sorry, I couldn't generate a budget plan based on your itinerary. Please try again with a different prompt."
    return markdown.markdown(reply)  # Convert to HTML for rendering

