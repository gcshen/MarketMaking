from __future__ import annotations
import uuid
import re
from typing import Dict, Optional

from openrouter_client import OpenRouterClient
from models import SessionState, CandidateQuote, RoundReport
from prompts import FERMI_SYSTEM_PROMPT

# ---------- basic metrics ----------
def _calc_mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0

def _calc_width(bid: float, ask: float) -> float:
    return max(0.0, ask - bid)

def _calc_width_pct_of_bid(bid: float, width: float) -> float:
    if bid <= 0:
        return 0.0
    return 100.0 * width / bid

# ---------- memory + formatting helpers ----------
def _format_round_memory(state: SessionState) -> str:
    """Summarize prior rounds so the LLM can avoid redundancy and escalate detail."""
    if not state.reports:
        return "(none)"
    lines = []
    for r in state.reports:
        lines.append(f"- Round {r.round_index}: bid={r.bid:g}, ask={r.ask:g}")
        if r.hint_or_reveal:
            lines.append(f"  • Prior Hint: {r.hint_or_reveal.strip()[:400]}")
        if r.coaching_or_teaching:
            lines.append(f"  • Prior Coaching: {r.coaching_or_teaching.strip()[:400]}")
        if r.final_report:
            lines.append(f"  • Prior Final Report: {r.final_report.strip()[:400]}")
    return "\n".join(lines)

# ---------- parsing helpers ----------
def _split_hint_and_coaching(content: str) -> tuple[str, str]:
    """
    Expect strict sections:
      Hint:
      Coaching:
    Fall back gracefully if headers are missing.
    """
    lower = content.lower()
    if "hint:" in lower and "coaching:" in lower:
        hint, coach, which = [], [], None
        for line in content.splitlines():
            ll = line.strip().lower()
            if ll.startswith("hint:"):
                which = "hint"; continue
            if ll.startswith("coaching:"):
                which = "coach"; continue
            if which == "hint":
                hint.append(line)
            elif which == "coach":
                coach.append(line)
        return "\n".join(hint).strip(), "\n".join(coach).strip()
    # fallback: everything to hint
    return content.strip(), ""

def _extract_final_report(content: str) -> str:
    """
    For Round 4 we want ONLY 'Final Report:'.
    If header exists, return from there; else return all content.
    """
    lower = content.lower()
    key = "final report:"
    if key in lower:
        i = lower.index(key)
        return content[i:].strip()
    return content.strip()

# ---------- engine ----------
class FermiGameEngine:
    """
    Orchestrates 4-round Fermi market-making game.
    - Rounds 1–3: accept quote, compute metrics, ask LLM for ONE 'Hint:' + 'Coaching:' (non-redundant).
    - Round 4: output ONLY 'Final Report:' (no sigma content, no other sections).
    """
    def __init__(self, client: OpenRouterClient):
        self.client = client
        self._sessions: Dict[str, SessionState] = {}

    # ----- Session lifecycle -----
    def start_session(self, question: str) -> SessionState:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, question=question, round_number=0)
        self._sessions[sid] = state
        return state

    def get_state(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    # ----- Rounds 1–3 -----
    def submit_quote(self, session_id: str, bid: float, ask: float, rationale: str | None) -> RoundReport:
        state = self._require_session(session_id)
        if state.final_done:
            raise ValueError("Session already finalized.")
        if state.round_number >= 3:
            raise ValueError("Use finalize_round4 for the last step.")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError("Invalid quote: require 0 < bid <= ask")

        state.round_number += 1
        state.quotes.append(CandidateQuote(bid=bid, ask=ask, rationale=rationale))

        # metrics
        mid = _calc_mid(bid, ask)
        width = _calc_width(bid, ask)
        pct = _calc_width_pct_of_bid(bid, width)

        # build prompt with round memory + anti-redundancy instruction
        memory = _format_round_memory(state)
        messages = [
            {"role": "system", "content": FERMI_SYSTEM_PROMPT},
            {"role": "user", "content":
                f"QUESTION: {state.question}\n"
                f"ROUND: {state.round_number} (Output EXACTLY 'Hint:' then 'Coaching:')\n"
                f"ROUND MEMORY (prior quotes + your outputs):\n{memory}\n\n"
                f"CURRENT QUOTE: bid={bid:g}, ask={ask:g}; rationale={rationale or '(none)'}\n"
                "REQUEST: Produce a NEW, non-overlapping 'Hint:' (1–2 bullets max) that builds on prior hints, "
                "and a 'Coaching:' section (1–3 bullets) tailored to this quote. Do NOT repeat earlier phrasing."
            },
        ]
        content = self.client.chat(messages=messages, temperature=0.2)

        hint, coaching = _split_hint_and_coaching(content)

        report = RoundReport(
            round_index=state.round_number,
            bid=bid, ask=ask, mid=mid, width=width, width_pct_of_bid=pct,
            hint_or_reveal=hint, coaching_or_teaching=coaching,
            final_report=None
        )
        state.reports.append(report)
        return report

    # ----- Round 4 -----
    def finalize_round4(self, session_id: str, bid: float, ask: float, rationale: str | None) -> RoundReport:
        state = self._require_session(session_id)
        if state.final_done:
            raise ValueError("Session already finalized.")
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError("Invalid quote: require 0 < bid <= ask")

        state.round_number = 4
        state.quotes.append(CandidateQuote(bid=bid, ask=ask, rationale=rationale))

        mid = _calc_mid(bid, ask)
        width = _calc_width(bid, ask)
        pct = _calc_width_pct_of_bid(bid, width)

        memory = _format_round_memory(state)
        messages = [
            {"role": "system", "content": FERMI_SYSTEM_PROMPT},
            {"role": "user", "content":
                f"QUESTION: {state.question}\n"
                f"ROUND: 4 (Output ONLY 'Final Report:')\n"
                f"ROUND MEMORY (prior quotes + your outputs):\n{memory}\n\n"
                f"FINAL QUOTE: bid={bid:g}, ask={ask:g}; rationale={rationale or '(none)'}\n"
                "REQUEST: Output ONLY 'Final Report:' with exactly these subsections: "
                "'Estimation Steps', 'Reference Value', 'Market Recap', 'Efficiency Tips'. "
                "Do NOT include sigma/standard deviation, and do NOT output any 'Hint:' or 'Coaching:' sections."
            },
        ]
        content = self.client.chat(messages=messages, temperature=0.2)

        final_report = _extract_final_report(content)

        state.final_done = True
        report = RoundReport(
            round_index=4,
            bid=bid, ask=ask, mid=mid, width=width, width_pct_of_bid=pct,
            hint_or_reveal=None,
            coaching_or_teaching=None,
            final_report=final_report
        )
        state.reports.append(report)
        return report

    # ----- internal -----
    def _require_session(self, session_id: str) -> SessionState:
        st = self._sessions.get(session_id)
        if not st:
            raise ValueError("Unknown session_id")
        return st
