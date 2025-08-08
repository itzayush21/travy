# Travy – AI-Powered Collaborative Travel Planner

Travy is an **agentic AI travel planning application** built with **LangGraph**, **LangChain**, **Groq**, and real-time travel APIs like **Tavily**, **TripAdvisor Scraper**, and **Travel Guide API**.  
It transforms **natural language trip descriptions** into **personalized, structured itineraries**, complete with **budget estimates** and **collaboration pods** where friends can plan together in real time.  

---

## 🚀 Features

- **Natural Language to Itinerary** – Just describe your trip in plain English, and Travy generates a detailed day-by-day plan.
- **Real-Time Data Integration** – Live hotels, restaurants, events, and weather info.
- **Conditional Tool Use** – Smart API calls based on location, season, or preferences.
- **Budget Planner** – Auto-estimates travel, food, and accommodation costs.
- **Collaboration Pods** – Invite friends to join and co-edit your trip plan.
- **Role-based Contributions** – Assign who handles activities, lodging, or budgeting.
- **Quick Side Plan Chat Space** – Instantly query the AI for alternate or last-minute activities without disrupting the main itinerary.
- **Locale Governance Check** – Dedicated panel to verify visa rules, travel restrictions, and local regulations before confirming plans.
- **Notes Writing Space** – A shared area where pod members can jot down ideas, reminders, packing lists, or custom tips for the trip.
- **Packing Suggestor** – AI-powered recommendations on what to pack based on destination, weather forecast, trip duration, and planned activities.

---

## 📸 Screenshots & Demo

<img width="1889" height="902" alt="Screenshot 2025-08-09 015102" src="https://github.com/user-attachments/assets/b95ad33e-a5fd-4395-a029-7cec854e0cc2" />

<img width="1887" height="898" alt="Screenshot 2025-08-09 015203" src="https://github.com/user-attachments/assets/1c748636-ac11-4898-b8f6-8dcf8f3fe05a" />



<img width="1897" height="892" alt="Screenshot 2025-08-09 015227" src="https://github.com/user-attachments/assets/d776920e-f380-429c-be5a-3fb09c5d12cf" />



<img width="1843" height="753" alt="Screenshot 2025-08-09 015247" src="https://github.com/user-attachments/assets/30c7204c-e37e-456c-9453-154580db2c36" />



<img width="914" height="501" alt="Screenshot 2025-08-09 015913" src="https://github.com/user-attachments/assets/396b1ac2-6aad-4df4-a53a-305aeb668ad7" />

---

## 🛠️ Tech Stack

**Backend**
- [LangGraph](https://www.langchain.com/langgraph) – Agent workflow orchestration
- [LangChain](https://www.langchain.com/) – AI logic and tool integration
- [Groq](https://groq.com/) – Fast LLM inference
- Flask / FastAPI – API endpoints
- MySQL – Primary relational database for trip data, budgets, and itineraries
- Supabase – User authentication (login, signup) and optional profile storage

**Frontend**
- HTML
- CSS
- JAVASCRIPT

**Data Sources / APIs**
- Tavily Search – Destination & activity research
- TripAdvisor Scraper – Restaurants, attractions
- Travel Guide API – Local insights
- Weather API – Forecast integration

---

## 🧩 Architecture

```plaintext
User
  ↓
Frontend (Flask Templates: HTML, CSS, JS)
  ↓
Backend (Flask)
  ↳ LangGraph Agent Flow
  ↳ Tavily API – Destination & activity research
  ↳ TripAdvisor API – Restaurants, attractions
  ↳ Weather API – Forecast data
  ↳ Budget Estimation Module
  ↳ WebSocket Server – Real-time Pod Sync


## 📦 Installation

```bash
# Clone repository
git clone https://github.com/yourusername/travy.git
cd travy

# Install dependencies
pip install -r requirements.txt

# Run Flask app
python app.py





