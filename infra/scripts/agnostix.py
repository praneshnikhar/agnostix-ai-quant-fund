"""agnostix — terminal access to the autonomous options desk.

Structured JSON output for long-running agent sessions, cron, and CI —
the same trading functions as the web War Room, from a command line.

Usage:
    python -m infra.scripts.agnostix status
    python -m infra.scripts.agnostix chain SPY
    python -m infra.scripts.agnostix decide AAPL --execute
    python -m infra.scripts.agnostix journal --verify
    python -m infra.scripts.agnostix kill

The CLI talks to the running FastAPI API over HTTP (base URL configurable via
AGNOSTIX_API_URL, default http://localhost:8000). It never holds credentials
or places orders directly — execution authority lives behind the API's
deterministic risk gates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

API_URL = os.environ.get("AGNOSTIX_API_URL", "http://localhost:8000")


def _call(method: str, path: str, **kw) -> dict:
    try:
        with httpx.Client(base_url=API_URL, timeout=120.0) as client:
            resp = client.request(method, path, **kw)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        print(f"error {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError as exc:
        print(f"error: cannot reach API at {API_URL} ({exc})", file=sys.stderr)
        sys.exit(1)


def _out(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_status() -> None:
    _out(_call("GET", "/trading/status"))


def cmd_chain(symbol: str) -> None:
    _out(_call("GET", f"/options/chain/{symbol.upper()}"))


def cmd_decide(symbol: str, execute: bool) -> None:
    _out(_call("POST", "/trading/decide", json={"symbol": symbol.upper(), "execute": execute}))


def cmd_run(symbols: list[str]) -> None:
    _out(_call("POST", "/trading/run", json={"symbols": [s.upper() for s in symbols]}))


def cmd_journal(verify: bool, limit: int) -> None:
    data = _call("GET", f"/trading/journal?limit={limit}")
    _out(data)
    if verify:
        ok = data.get("verified", False)
        print(f"\njournal chain verified: {'OK' if ok else 'FAILED'}", file=sys.stderr)
        sys.exit(0 if ok else 1)


def cmd_kill(resume: bool) -> None:
    _out(_call("POST", "/trading/resume" if resume else "/trading/kill"))


def main() -> None:
    parser = argparse.ArgumentParser(prog="agnostix", description="Agnostix options desk CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="desk status + account")
    p_chain = sub.add_parser("chain", help="enriched option chain")
    p_chain.add_argument("symbol")
    p_decide = sub.add_parser("decide", help="run one decision")
    p_decide.add_argument("symbol")
    p_decide.add_argument("--execute", action="store_true", help="place a paper order (default dry-run)")
    p_run = sub.add_parser("run", help="run a cycle over symbols")
    p_run.add_argument("symbols", nargs="+")
    p_journal = sub.add_parser("journal", help="read the hash-chained journal")
    p_journal.add_argument("--verify", action="store_true", help="verify chain integrity")
    p_journal.add_argument("--limit", type=int, default=200)
    p_kill = sub.add_parser("kill", help="engage the kill switch")
    p_kill.add_argument("--resume", action="store_true", help="resume instead")

    args = parser.parse_args()
    if args.command == "status":
        cmd_status()
    elif args.command == "chain":
        cmd_chain(args.symbol)
    elif args.command == "decide":
        cmd_decide(args.symbol, args.execute)
    elif args.command == "run":
        cmd_run(args.symbols)
    elif args.command == "journal":
        cmd_journal(args.verify, args.limit)
    elif args.command == "kill":
        cmd_kill(args.resume)


if __name__ == "__main__":
    main()
