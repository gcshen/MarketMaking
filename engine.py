from __future__ import annotations
import uuid
from typing import Dict, Optional
from dataclasses import asdict

from openrouter_client import OpenRouterClient
from models import SessionState, CandidateQuote, RoundReport
from prompts import FERMI_SYSTEM_PROMPT

def _calc_mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0

def _calc_width(bid: float, ask: float) -> float:
    return max(0.0, ask - bid)

def _calc_width_pct_of_bid(bid: float, width: float) -> float:
    if bid <= 0:
        return 0.0
    return 100.0 * width / bid

def uniform_range_sigma(bid: float, ask: float) -> float:
    """
    Classroom shortcut: If you only have a range [a,b] for a single quantity,
    SD ≈ (b - a) / sqrt(12).
    """
    import math
    return _calc_width(bid, ask) / math.sqrt(12.0)

class FermiGameEngine:
    """
    Orchestrates 4-round Fermi market-making game.
    - Rounds 1–3: accept quote, compute metrics, ask LLM for ONE hint + brief coaching.
    - Round 4: reveal reference value + ask how to gauge σ; teach Uniform-range shortcut.
    """
    def __init__(self, client: OpenRouterClient):
        self.client = client
        self._sessions: Dict[str, SessionState] = {}

    # ---------- Session lifecycle ----------
    def start_session(self, question: str) -> SessionState:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, question=question, round_number=0)
        self._sessions[sid] = state
        return state

    def get_state(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    # ---------- Round handling ----------
    def submit_quote(self, session_id: str, bid: float, ask: float, rationale: str | None) -> RoundReport:
        state = self._require_session(session_id)
        if state.final_done:
            raise ValueError("Session already finalized.")
        if state.round_number >= 3:
            raise ValueError("Use finalize_round4 for the last step.")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError("Invalid quote: require 0 < bid <= ask")

        state.round_number += 1
        cq = CandidateQuote(bid=bid, ask=ask, rationale=rationale)
        state.quotes.append(cq)

        # Compute spread metrics
        mid = _calc_mid(bid, ask)
        width = _calc_width(bid, ask)
        pct = _calc_width_pct_of_bid(bid, width)

        # Build messages for LLM (one crisp hint per round)
        messages = [
            {"role": "system", "content": FERMI_SYSTEM_PROMPT},
            {"role": "user", "content": f"Fermi Question: {state.question}"},
            {"role": "user", "content": f"Round {state.round_number} - Candidate quote: bid={bid}, ask={ask}. Rationale: {rationale or '(none)'}"},
            {"role": "user", "content": "Produce one crisp 'Hint' and a short 'Coaching' section. Do not reveal the final answer."}
        ]
        content = self.client.chat(messages=messages, temperature=0.2)

        # Split content into hint+coaching gracefully
        hint, coaching = _split_hint_and_coaching(content)

        report = RoundReport(
            round_index=state.round_number,
            bid=bid, ask=ask, mid=mid, width=width, width_pct_of_bid=pct,
            hint_or_reveal=hint, coaching_or_teaching=coaching
        )
        state.reports.append(report)
        return report

    def finalize_round4(self, session_id: str, bid: float, ask: float, rationale: str | None) -> RoundReport:
        state = self._require_session(session_id)
        if state.final_done:
            raise ValueError("Session already finalized.")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError("Invalid quote: require 0 < bid <= ask")

        # Record final quote as Round 4
        state.round_number = 4
        cq = CandidateQuote(bid=bid, ask=ask, rationale=rationale)
        state.quotes.append(cq)

        mid = _calc_mid(bid, ask)
        width = _calc_width(bid, ask)
        pct = _calc_width_pct_of_bid(bid, width)
        sigma_guess = uniform_range_sigma(bid, ask)

        messages = [
            {"role": "system", "content": FERMI_SYSTEM_PROMPT},
            {"role": "user", "content": f"Fermi Question: {state.question}"},
            {"role": "user", "content": f"Round 4 - Final candidate quote: bid={bid}, ask={ask}. Rationale: {rationale or '(none)'}"},
            {"role": "user", "content": (
                "Now perform the final reveal. Provide:\n"
                "1) 'Reference Value' with one-sentence derivation,\n"
                "2) 'σ Prompt' asking them how they'd gauge SD,\n"
                "3) 'Teaching' that includes the Uniform-range shortcut and one alternative method.\n"
                "Keep it concise."
            )}
        ]
        content = self.client.chat(messages=messages, temperature=0.2)
        reveal, teaching = _split_reveal_and_teaching(content)

        state.final_done = True
        report = RoundReport(
            round_index=4,
            bid=bid, ask=ask, mid=mid, width=width, width_pct_of_bid=pct,
            hint_or_reveal=reveal,
            coaching_or_teaching=(teaching + f"\n\n(Platform note) Uniform-range σ from your final range ≈ {sigma_guess:,.0f}.")
        )
        state.reports.append(report)
        return report

    # ---------- helpers ----------
    def _require_session(self, session_id: str) -> SessionState:
        st = self._sessions.get(session_id)
        if not st:
            raise ValueError("Unknown session_id")
        return st

def _split_hint_and_coaching(content: str) -> tuple[str, str]:
    # Very light parsing to keep it robust across models; fallback to whole text as hint.
    lower = content.lower()
    if "coaching" in lower and "hint" in lower:
        # crude segmentation
        parts = []
        current = ""
        for line in content.splitlines():
            if line.strip().lower().startswith("hint"):
                if current:
                    parts.append(current.strip())
                    current = ""
                current = line + "\n"
            elif line.strip().lower().startswith("coaching"):
                parts.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"
        parts.append(current.strip())
        hint = parts[0].replace("Hint:", "").strip() if parts else content
        coaching = parts[1].replace("Coaching:", "").strip() if len(parts) > 1 else ""
        return hint, coaching
    # fallback
    return content.strip(), ""

def _split_reveal_and_teaching(content: str) -> tuple[str, str]:
    lower = content.lower()
    if "reference value" in lower and ("σ prompt" in lower or "sigma prompt" in lower):
        # Return all as "reveal", and "teaching" as the remainder after 'Teaching'
        lines = content.splitlines()
        rev, teach = [], []
        into_teach = False
        for ln in lines:
            if ln.strip().lower().startswith("teaching"):
                into_teach = True
                continue
            (teach if into_teach else rev).append(ln)
        return "\n".join(rev).strip(), "\n".join(teach).strip()
    return content.strip(), ""
