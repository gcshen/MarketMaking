# Architecture Overview

## Goal
This bot trains candidates to think like **market makers** when solving
Fermi estimation problems.

## Flow
1. Candidate posts bid/ask.
2. Bot computes midpoint, spread width, spread % of bid.
3. Bot sends structured prompts to OpenRouter GPT-5.
4. Rounds 1–3: one new hint per round, candidate tightens.
5. Round 4: final reveal + teaching σ.

## Layers
- **openrouter_client.py**: handles API calls.
- **engine.py**: game state machine.
- **api.py**: HTTP endpoints (FastAPI).
- **models.py**: session, quote, report data structures.
- **prompts.py**: system prompt design.

## Extensibility
- Add new games in `gamepacks/`.
- Swap prompts easily.
- Decouple storage: can replace in-memory dict with Redis/DB.

