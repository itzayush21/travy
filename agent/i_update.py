import os
import requests
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY= os.getenv('TAVILY_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def refine_itinerary(current_plan: str, update_prompt: str) -> str:
    """
    Restructures or updates the current itinerary using LLaMA 3.1 (Groq).

    Args:
        current_plan (str): The original or existing itinerary (multi-day).
        update_prompt (str): User's update instruction (e.g., "Change day 2 to include XYZ").

    Returns:
        str: The updated itinerary.
    """
    if not GROQ_API_KEY:
        return "[Groq API Error] Missing API key."

    system_prompt = (
        "You are a travel itinerary assistant that restructures existing trip plans.\n"
        "If the user says a day is completed, do NOT regenerate that day's plan.\n"
        "If the user asks to move a location (e.g., Johari Bazaar) to another day, do so logically.\n"
        "If user asks to extend the trip, add more days as needed with suitable attractions.\n"
        "Ensure timing and activity count are realistic. Avoid repeating places.\n"
        "Output ONLY the updated part of the itinerary, starting from the next uncompleted day."
    )

    user_prompt = (
        f"Current Itinerary:\n{current_plan.strip()}\n\n"
        f"User Instruction:\n{update_prompt.strip()}\n\n"
        f"Give updated itinerary from the next uncompleted day onward."
    )

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
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.5,
                "top_p": 0.95,
                "max_tokens": 1024
            },
            timeout=15
        )
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"[Groq API Error] {str(e)}"
