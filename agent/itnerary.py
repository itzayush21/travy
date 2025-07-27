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


# === Load Environment Variables ===
load_dotenv()

TAVILY_API_KEY= os.getenv('TAVILY_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')


MessagesState = dict  # {"messages": [...]}

# ===================== TOOLS =====================

@tool
def tavily_search(query: str) -> str:
    """Search the web using Tavily and return the top result or brief answer."""
    print(f"[TOOL CALL] tavily_search(query='{query}')")
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
            json={"query": query, "search_depth": "advanced", "include_answer": True},
            timeout=8
        )
        if not resp.ok:
            return f"[Tavily Error] {resp.status_code}"
        data = resp.json()
        if data.get("answer"):
            return data["answer"]
        elif data.get("results"):
            texts = []
            for result in data["results"]:
                soup = BeautifulSoup(result.get("content", ""), "html.parser")
                texts.append(soup.get_text(separator=" ", strip=True)[:400])
            return "\n\n".join(texts[:2])
        return "No useful info found."
    except Exception as e:
        return f"[Tavily Error] {str(e)}"

@tool
def tripadvisor_restaurants(query: str) -> str:
    """Fetch top restaurants from TripAdvisor using location query."""
    print(f"[TOOL CALL] tripadvisor_restaurants(query='{query}')")
    try:
        url = "https://tripadvisor-scraper.p.rapidapi.com/restaurants/search"
        headers = {
            "x-rapidapi-key": '08b0082826msh6db2c2cda14039cp1e7d8djsn94fb7a7b53ed',
            "x-rapidapi-host": "tripadvisor-scraper.p.rapidapi.com"
        }
        params = {"query": query}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data and "data" in data:
            names = [r["name"] for r in data["data"][:5]]
            return f"🍽️ Top restaurants in {query}:\n- " + "\n- ".join(names)
        return "No restaurant data found."
    except Exception as e:
        return f"[TripAdvisor Error] {str(e)}"

@tool
def travel_guide_places(region: str, interests: list) -> str:
    """Get top places based on region and interests using Travel Guide API."""
    print(f"[TOOL CALL] travel_guide_places(region='{region}', interests={interests})")
    try:
        url = "https://travel-guide-api-city-guide-top-places.p.rapidapi.com/check"
        headers = {
            "x-rapidapi-key": '08b0082826msh6db2c2cda14039cp1e7d8djsn94fb7a7b53ed',
            "x-rapidapi-host": "travel-guide-api-city-guide-top-places.p.rapidapi.com",
            "Content-Type": "application/json"
        }
        payload = {
            "region": region,
            "language": "en",
            "interests": interests
        }
        resp = requests.post(url, json=payload, headers=headers, params={"noqueue": "1"}, timeout=12)
        data = resp.json()
        if data and isinstance(data, list):
            names = [place.get("name", "Unknown") for place in data[:5]]
            return f"🏛️ Top places in {region} for {', '.join(interests)}:\n- " + "\n- ".join(names)
        return "No places found for this region."
    except Exception as e:
        return f"[Travel Guide Error] {str(e)}"

# ===================== LLM CALL =====================

def run_groq(prompt: str, system_prompt: str = "You are helpful.") -> str:
    if not GROQ_API_KEY:
        return "[Groq API Error] Missing API Key"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gemma2-9b-it",
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
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Groq API Error] {str(e)}"

# ===================== AGENT =====================

class ItineraryPlannerAgent:
    def __init__(self):
        self.memory = MemorySaver()
        self.tool_node = ToolNode(tools=[
            tavily_search,
            tripadvisor_restaurants,
            travel_guide_places
        ])

    def model_node(self, state: MessagesState) -> MessagesState:
        messages = state["messages"]
        user_msg = messages[-1].content if messages else "Plan an itinerary"

        context = "\n".join([msg.content for msg in messages if isinstance(msg, (SystemMessage, HumanMessage))])

        system_prompt = (
            "You are a travel itinerary planner. "
            "Based on the user's input (destination, duration, interests), create a personalized plan. "
            "Structure the itinerary day-wise and include local attractions, food recommendations, and free time. "
            "Use tools like `tripadvisor_restaurants`, `travel_guide_places`, and `tavily_search` for accuracy. "
            "Ensure that each day's attractions are **distance-wise feasible** — group nearby places together to avoid long travel between spots. "
            "Also, **consider the user's arrival or landing time** to plan Day 1 realistically — avoid cramming full-day activities if they arrive late."
            "Try to complete the answer in 2048 token length"
        )


        prompt = f"{context}\n\nUser Request: {user_msg}"
        reply = run_groq(prompt, system_prompt)
        return {"messages": messages + [AIMessage(content=reply)]}

    def router(self, state: MessagesState) -> Literal["tools", END]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    def __call__(self):
        graph = StateGraph(MessagesState)
        graph.add_node("itinerary_agent", self.model_node)
        graph.add_node("tools", self.tool_node)

        graph.set_entry_point("itinerary_agent")
        graph.add_conditional_edges("itinerary_agent", self.router, {
            "tools": "tools", END: END
        })
        graph.add_edge("tools", "itinerary_agent")

        return graph.compile(checkpointer=self.memory)

# ===================== CHAT ENTRY =====================

itinerary_app = ItineraryPlannerAgent()()
chat_sessions = {}

def itinerary_reply(session_id: str, user_message: str) -> str:
    system = SystemMessage(content="You help plan amazing travel itineraries with local insights and dining.")
    user = HumanMessage(content=user_message)

    if session_id not in chat_sessions:
        chat_sessions[session_id] = [system, user]
    else:
        chat_sessions[session_id].append(user)

    config = RunnableConfig(configurable={"thread_id": session_id})
    result = itinerary_app.invoke({"messages": chat_sessions[session_id]}, config=config)

    response_msg = result["messages"][-1]
    chat_sessions[session_id].append(response_msg)

    print(f"🧠 Context:\n{[msg.content for msg in chat_sessions[session_id]]}")
    print(f"✅ Response:\n{response_msg.content}")
    return response_msg.content

# ===================== TEST RUN =====================

def generate_itinerary_from_prompt(session_id,prompt):
    reply= itinerary_reply(session_id, prompt)
    if not reply:
        return "Sorry, I couldn't generate an itinerary based on your request. Please try again with a different prompt."
    
    return markdown.markdown(reply) 
    

