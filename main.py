from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Optional, Dict, Any, Tuple, List

import requests

from dotenv import load_dotenv
load_dotenv()

# -----------------------------
# Config defaults
# -----------------------------ç
DEFAULT_BASE_URL = os.getenv("FERMI_BOT_BASE_URL", "http://127.0.0.1:8000")


# -----------------------------
# Simple HTTP client helpers
# -----------------------------
def _post(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def _get(base_url: str, path: str) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


# -----------------------------
# API wrappers
# -----------------------------
def start_session(base_url: str, question: str) -> Tuple[str, str]:
    """POST /v1/fermi/sessions"""
    data = _post(base_url, "/v1/fermi/sessions", {"question": question})
    return data["session_id"], data["question"]

def submit_quote(base_url: str, session_id: str, bid: float, ask: float, rationale: Optional[str]) -> Dict[str, Any]:
    """POST /v1/fermi/sessions/{session_id}/quote"""
    payload = {"bid": bid, "ask": ask, "rationale": rationale}
    return _post(base_url, f"/v1/fermi/sessions/{session_id}/quote", payload)

def finalize_round4(base_url: str, session_id: str, bid: float, ask: float, rationale: Optional[str]) -> Dict[str, Any]:
    """POST /v1/fermi/sessions/{session_id}/finalize"""
    payload = {"bid": bid, "ask": ask, "rationale": rationale}
    return _post(base_url, f"/v1/fermi/sessions/{session_id}/finalize", payload)

def get_state(base_url: str, session_id: str) -> Dict[str, Any]:
    """GET /v1/fermi/sessions/{session_id}"""
    return _get(base_url, f"/v1/fermi/sessions/{session_id}")


# -----------------------------
# Pretty printers
# -----------------------------
def print_report(label: str, rep: Dict[str, Any]) -> None:
    print(f"\n===== {label} =====")
    print(f"Round:           {rep['round_index']}")
    print(f"Bid / Ask:       {rep['bid']}  /  {rep['ask']}")
    print(f"Midpoint:        {rep['mid']}")
    print(f"Spread width:    {rep['width']}")
    print(f"Width % of bid:  {rep['width_pct_of_bid']:.2f}%")
    print(f"\n--- Hint / Reference ---\n{rep['hint_or_reveal']}")
    print(f"\n--- Coaching / Teaching ---\n{rep['coaching_or_teaching']}")
    print("=" * 32)

def print_state(state: Dict[str, Any]) -> None:
    print("\n===== SESSION STATE =====")
    print(json.dumps(state, indent=2))
    print("=" * 26)


# -----------------------------
# Interactive play loop
# -----------------------------
def interactive_play(base_url: str, question: str) -> None:
    sess_id, q = start_session(base_url, question)
    print(f"\n✅ Session started: {sess_id}")
    print(f"Question: {q}")

    # Rounds 1–3
    for rnd in (1, 2, 3):
        print(f"\n--- Round {rnd}: Enter your quote ---")
        bid = float(input("Bid (number): ").strip())
        ask = float(input("Ask (number; must be >= bid): ").strip())
        rationale = input("Rationale (short text, optional): ").strip() or None

        rep = submit_quote(base_url, sess_id, bid, ask, rationale)
        print_report(f"Round {rnd} Report", rep)

    # Round 4 - finalize
    print("\n--- Round 4 (Final): Enter your final quote ---")
    bid = float(input("Final Bid: ").strip())
    ask = float(input("Final Ask: ").strip())
    rationale = input("Final Rationale (optional): ").strip() or None

    rep = finalize_round4(base_url, sess_id, bid, ask, rationale)
    print_report("Final Report", rep)

    # Show entire session state
    state = get_state(base_url, sess_id)
    print_state(state)


# -----------------------------
# Auto-demo play loop
# -----------------------------
def auto_demo_play(base_url: str, question: str) -> None:
    """
    Runs a canned 4-round session for quick verification.
    You can change the quotes sequence for any question.
    """
    print("\n🤖 Running auto-demo...")
    sess_id, q = start_session(base_url, question)
    print(f"✅ Session started: {sess_id}")
    print(f"Question: {q}")

    # Demo quotes (tweak these for your own canned flows)
    demo_rounds: List[Tuple[float, float, str]] = [
        (100.0, 10000.0, "Fermi start: very wide, high uncertainty"),
        (500.0, 3000.0, "Narrowing with first hint"),
        (1000.0, 2000.0, "Using capacity/service logic to refine"),
    ]

    for i, (bid, ask, rat) in enumerate(demo_rounds, start=1):
        rep = submit_quote(base_url, sess_id, bid, ask, rat)
        print_report(f"Round {i} Report", rep)
        time.sleep(0.5)  # small pause so you can read logs

    # Finalize (Round 4)
    final_bid, final_ask, final_rat = (1200.0, 1800.0, "Converged; locking range")
    rep = finalize_round4(base_url, sess_id, final_bid, final_ask, final_rat)
    print_report("Final Report", rep)

    # Show session state
    state = get_state(base_url, sess_id)
    print_state(state)


# -----------------------------
# Run server (programmatically)
# -----------------------------
def run_server(port: int, host: str = "127.0.0.1", reload: bool = True) -> None:
    """
    Starts the FastAPI app (api.py) using uvicorn programmatically.
    Equivalent to: uvicorn api:app --reload --port <PORT>
    """
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    # Important: If you're on Windows and want reload, ensure watchdog/permissions are OK.
    uvicorn.run("api:app", host=host, port=port, reload=reload)


# -----------------------------
# Health checker
# -----------------------------
def health_check(base_url: str) -> None:
    """
    Tries to call /docs (HTML) and start a throwaway session to verify JSON endpoints.
    """
    print(f"🔎 Checking server at {base_url} ...")
    try:
        # /docs is HTML; just make sure it returns 200
        r = requests.get(f"{base_url.rstrip('/')}/docs", timeout=10)
        r.raise_for_status()
        print("✅ /docs reachable")

        # try starting a dummy session
        sess_id, _ = start_session(base_url, "Health check question")
        print(f"✅ JSON API ok (session_id={sess_id})")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)


# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fermi Market-Making Bot: server + client in one file"
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # serve
    ps = sub.add_parser("serve", help="Start the FastAPI server (uvicorn)")
    ps.add_argument("--port", type=int, default=8000, help="Port to bind")
    ps.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    ps.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    # play
    pp = sub.add_parser("play", help="Play a 4-round Fermi session (interactive or auto)")
    pp.add_argument("--question", type=str, required=True, help="Fermi question to ask")
    pp.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="API base URL")
    pp.add_argument("--auto-demo", action="store_true", help="Run a canned demo instead of prompting")

    # health
    ph = sub.add_parser("health", help="Check server availability")
    ph.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="API base URL")

    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.cmd == "serve":
        # Starts the FastAPI server
        run_server(port=args.port, host=args.host, reload=(not args.no_reload))
        return

    if args.cmd == "play":
        # sanity check that server is reachable
        try:
            requests.get(f"{args.base_url.rstrip('/')}/docs", timeout=5).raise_for_status()
        except Exception:
            print("⚠️  Could not reach the server. Is it running?\n"
                  "    Start it in another terminal:\n"
                  "    python -m uvicorn api:app --host 127.0.0.1 --port 8000 --env-file .env")
            sys.exit(1)

        # interactive or auto-demo
        if args.auto_demo:
            auto_demo_play(args.base_url, args.question)
        else:
            interactive_play(args.base_url, args.question)
        return

    if args.cmd == "health":
        health_check(args.base_url)
        return

    # Fallback (should never hit because argparse requires a subcommand)
    print("Unknown command. Try: python main.py --help")
    sys.exit(2)


if __name__ == "__main__":
    main()

