from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CandidateQuote:
    bid: float
    ask: float
    rationale: Optional[str] = None

@dataclass
class RoundReport:
    round_index: int
    bid: float
    ask: float
    mid: float
    width: float
    width_pct_of_bid: float
    hint_or_reveal: str
    coaching_or_teaching: str

@dataclass
class SessionState:
    session_id: str
    question: str
    round_number: int = 0
    quotes: List[CandidateQuote] = field(default_factory=list)
    reports: List[RoundReport] = field(default_factory=list)
    final_done: bool = False
