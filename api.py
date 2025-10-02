from __future__ import annotations
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from openrouter_client import OpenRouterClient
from engine import FermiGameEngine
from models import SessionState, RoundReport

# ---------- Pydantic IO models ----------
class StartSessionIn(BaseModel):
    question: str = Field(..., example="How many breaths does an average person take in a day?")

class StartSessionOut(BaseModel):
    session_id: str
    question: str

class QuoteIn(BaseModel):
    bid: float
    ask: float
    rationale: Optional[str] = None

class RoundReportOut(BaseModel):
    round_index: int
    bid: float
    ask: float
    mid: float
    width: float
    width_pct_of_bid: float
    # Rounds 1–3:
    hint_or_reveal: Optional[str] = None
    coaching_or_teaching: Optional[str] = None
    # Round 4:
    final_report: Optional[str] = None

class SessionStateOut(BaseModel):
    session_id: str
    question: str
    round_number: int
    final_done: bool
    reports: list[RoundReportOut]

# ---------- App ----------
app = FastAPI(title="Fermi Market-Making API", version="1.0.0")

_client = OpenRouterClient()
_engine = FermiGameEngine(client=_client)

def _to_round_out(r: RoundReport) -> RoundReportOut:
    return RoundReportOut(
        round_index=r.round_index,
        bid=r.bid,
        ask=r.ask,
        mid=r.mid,
        width=r.width,
        width_pct_of_bid=r.width_pct_of_bid,
        # Only include hint/coaching for rounds 1–3
        hint_or_reveal=r.hint_or_reveal if r.round_index != 4 else None,
        coaching_or_teaching=r.coaching_or_teaching if r.round_index != 4 else None,
        # Only include final_report for round 4
        final_report=r.final_report if r.round_index == 4 else None,
    )

@app.post("/v1/fermi/sessions", response_model=StartSessionOut)
def start_session(payload: StartSessionIn):
    st = _engine.start_session(question=payload.question)
    return StartSessionOut(session_id=st.session_id, question=st.question)

@app.get(
    "/v1/fermi/sessions/{session_id}",
    response_model=SessionStateOut,
    response_model_exclude_none=True
)
def get_state(session_id: str):
    st = _engine.get_state(session_id)
    if not st:
        raise HTTPException(404, "Session not found")
    return SessionStateOut(
        session_id=st.session_id,
        question=st.question,
        round_number=st.round_number,
        final_done=st.final_done,
        reports=[_to_round_out(r) for r in st.reports],
    )

@app.post(
    "/v1/fermi/sessions/{session_id}/quote",
    response_model=RoundReportOut,
    response_model_exclude_none=True
)
def submit_quote(session_id: str, q: QuoteIn):
    try:
        rep = _engine.submit_quote(session_id, bid=q.bid, ask=q.ask, rationale=q.rationale)
        return _to_round_out(rep)
    except RuntimeError as e:
        # Forward OpenRouter message to the client (bad gateway)
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/v1/fermi/sessions/{session_id}/finalize",
    response_model=RoundReportOut,
    response_model_exclude_none=True
)
def finalize(session_id: str, q: QuoteIn):
    try:
        rep = _engine.finalize_round4(session_id, bid=q.bid, ask=q.ask, rationale=q.rationale)
        return _to_round_out(rep)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
