import requests
import os
import json
import markdown
from dotenv import load_dotenv

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
            print("🚨 Full Response:", json.dumps(data, indent=2))
            return "[Daywise Summary Error] No 'choices' in response."

    except Exception as e:
        return f"[Daywise Summary Exception] {str(e)}"

import os, requests
from typing import Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

# ======= Environment Setup ========
MessagesState = dict  # {"messages": [...]}


# ======= Groq LLM Call Function ========
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

# ======= Packing List Agent ========
class PackingListAgent:
    def __init__(self):
        self.memory = MemorySaver()

    def model_node(self, state: MessagesState) -> MessagesState:
        messages = state["messages"]
        user_msg = messages[-1].content if messages else "Create a packing list."

        context = "\n".join([msg.content for msg in messages if isinstance(msg, (SystemMessage, HumanMessage))])

        system_prompt = (
            "You are a smart travel assistant that generates personalized packing lists based on a travel itinerary.\n\n"
            "The user will provide a summarized day-wise itinerary, number of travelers, destination type, and duration.\n\n"
            "Generate a categorized packing list including (but not limited to):\n"
            "- Clothing (based on weather, culture, activities)\n"
            "- Toiletries\n"
            "- Travel Essentials (documents, ID, cash, tickets)\n"
            "- Electronics (chargers, power banks, adapters)\n"
            "- Activity-specific items (hiking gear, swimwear, etc.)\n"
            "- Emergency/Health items\n\n"
            "Only include reasonable items for the trip duration and preferences.\n"
            "Group similar items under clear headers. Avoid repeating common sense items unless important.\n"
            "Avoid emojis. Keep formatting clear and minimal."
        )

        prompt = f"{context}\n\nUser Request: {user_msg}"
        result = run_groq(prompt, system_prompt)
        return {"messages": messages + [AIMessage(content=result)]}

    def router(self, state: MessagesState) -> Literal[END]:
        return END

    def __call__(self):
        graph = StateGraph(MessagesState)
        graph.add_node("packing_agent", self.model_node)
        graph.set_entry_point("packing_agent")
        graph.add_edge("packing_agent", END)
        return graph.compile(checkpointer=self.memory)

# ======= Chat Entry ========
packing_agent = PackingListAgent()()
chat_sessions = {}

def packing_reply(session_id: str, user_message: str) -> str:
    system = SystemMessage(content="You generate travel packing lists from summarized itineraries.")
    user = HumanMessage(content=user_message)

    if session_id not in chat_sessions:
        chat_sessions[session_id] = [system, user]
    else:
        chat_sessions[session_id].append(user)

    config = RunnableConfig(configurable={"thread_id": session_id})
    result = packing_agent.invoke({"messages": chat_sessions[session_id]}, config=config)

    response_msg = result["messages"][-1]
    chat_sessions[session_id].append(response_msg)

    print(f"\n🧠 Context: {[m.content for m in chat_sessions[session_id]]}")
    return response_msg.content

def generate_packing_list(session_id,existing_itinerary):
    itinerary=summarize_itinerary(existing_itinerary)
    user_msg = f'''create a packing list with following itinerary.\n \n{itinerary}\n
    '''
    reply = packing_reply(session_id, user_msg)
    if not reply:
        return "Sorry, I couldn't generate a packing list based on your itinerary. Please try again with a different prompt."
    return markdown.markdown(reply)
