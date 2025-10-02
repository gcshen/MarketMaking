import pytest
from engine import FermiGameEngine
from openrouter_client import OpenRouterClient

class DummyClient(OpenRouterClient):
    def __init__(self): pass
    def chat(self, messages, **kwargs):
        # Just echo a fake hint/teaching for tests
        return "Hint: test\nCoaching: tighten your spread"

def test_engine_flow():
    eng = FermiGameEngine(client=DummyClient())
    st = eng.start_session("How many breaths per day?")
    rep1 = eng.submit_quote(st.session_id, bid=10000, ask=30000, rationale="first guess")
    assert rep1.round_index == 1
    rep2 = eng.finalize_round4(st.session_id, bid=19000, ask=21000, rationale="final guess")
    assert rep2.round_index == 4
