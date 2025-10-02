# Fermi Market-Making Bot 🎯

This project is a **training bot** that helps candidates practice
Fermi estimation through a **market-making style game**.  
Built with **FastAPI** + **OpenRouter GPT-5 Chat API**.

---

## 🚀 Features
- 4-round Fermi market-making game:
  1. Candidate posts initial bid/ask.
  2. Bot returns new information (hints).
  3. Candidate adjusts quotes each round.
  4. Final round reveals fair value + teaches how to estimate σ.
- Spread width tracked as % of bid → measure quote tightness.
- Modular prompt system → can swap Fermi for other market-making games.
- OOP + API-first design, decoupled and reusable.

---

## 🛠 Setup

1. Clone this repo.
2. Create a `.env` file:
   ```env
   OPENROUTER_API_KEY=sk-or-YOUR_KEY
   OPENROUTER_MODEL=openai/gpt-5-chat:online
   APP_REFERER=http://localhost:8000
   APP_TITLE=Fermi-MarketMaker


# MarketMaking
