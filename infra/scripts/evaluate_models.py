"""Operational multi-model evaluation CLI (M2.2).

Evaluates every configured provider/model combination against ONE shared
M2 research context for a symbol, runs grounding + critic per model, and
prints/persists a comparable report.

Run (requires a migrated PostgreSQL database):

    python -m infra.scripts.evaluate_models --symbol ACME \
        --model anthropic:<model-id> --model openai:<model-id>

Add --dry-run to evaluate without persisting the run.

Notes:
- Providers are resolved through the existing Model Gateway adapters
  (anthropic/openai/ollama today; new adapters plug in without changes
  here). A provider that is unknown or unconfigured fails ONLY its own
  model's record — other models still evaluate.
- The requested model id is recorded alongside the model id the PROVIDER
  actually reported serving (model_version); a mismatch is printed as a
  warning so comparisons stay honest.
- Tests never invoke this module's live factory — CI uses mocked gateways.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate multiple provider/model combinations "
            "against one shared research context."
        )
    )
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. ACME")
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        metavar="PROVIDER:MODEL",
        help="Provider/model pair to evaluate; repeatable, order preserved",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate and print the report WITHOUT persisting an evaluation run",
    )
    return parser.parse_args(argv)


def _parse_targets(pairs: list[str]):
    from fundamentals.research.evaluation import ModelTarget

    targets: list[ModelTarget] = []
    for raw in pairs:
        if ":" not in raw:
            raise SystemExit(f"--model must be PROVIDER:MODEL, got {raw!r}")
        provider, model = raw.split(":", 1)
        if not provider.strip() or not model.strip():
            raise SystemExit(f"--model must be PROVIDER:MODEL, got {raw!r}")
        targets.append(ModelTarget(provider=provider.strip(), model=model.strip()))
    return targets


def _default_gateway_factory(target):
    """Resolve ANY registered provider through the SINGLE gateway registry.

    Zero provider-specific logic lives here: openrouter / ollama / custom /
    anthropic / openai all resolve identically via get_model_gateway, and an
    unknown provider fails cleanly (isolated to this one target's record).
    """
    from model_gateway.gateway import get_model_gateway

    return get_model_gateway(target.provider, model=target.model)


def _warn_on_model_mismatch(records) -> None:
    for r in records:
        if r.status == "completed" and r.model_version and r.model_version != r.model:
            print(
                f"WARNING: {r.provider}/{r.model}: provider actually served "
                f"model_version={r.model_version}",
                file=sys.stderr,
            )


async def _main_async(args: argparse.Namespace) -> int:
    from app.db.session import get_session_factory
    from app.services.research_service import _build_context
    from fundamentals.research.evaluation import run_evaluation

    targets = _parse_targets(args.model)

    async def _evaluate(session):
        # ONE context for the whole run — built exactly once.
        ctx = await _build_context(session, args.symbol)
        result = await run_evaluation(
            args.symbol.upper(),
            targets,
            emitter=None,
            context=ctx,
            gateway_factory=_default_gateway_factory,
        )
        return result

    if args.dry_run:
        factory = get_session_factory()
        async with factory() as session:
            result = await _evaluate(session)
        _warn_on_model_mismatch(result.records)
        print(json.dumps({"summary": result.summary(), "unavailable": result.unavailable},
                         indent=2, sort_keys=True))
        return 0

    from app.db.repositories.fundamentals_repo import EvaluationRunRepository
    from app.services.evaluation_service import run_evaluation_for_symbol

    factory = get_session_factory()
    async with factory() as session:
        run_id = await run_evaluation_for_symbol(
            session, args.symbol.upper(), targets, gateway_factory=_default_gateway_factory
        )
        await session.commit()
        run = await EvaluationRunRepository(session).get_run(run_id)
    if run is None:
        raise SystemExit(f"evaluation run {run_id} not found after completion")
    report = run.report or {}
    records = report.get("records", [])
    _warn_on_model_mismatch([_record_namespace(r) for r in records])
    summary = {f"{r['provider']}/{r['model']}": r["status"] for r in records}
    print(
        json.dumps(
            {"evaluation_run_id": str(run_id), "status": run.status, "models": summary},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


class _record_namespace:
    """Minimal attribute view over a persisted record dict."""

    def __init__(self, d: dict) -> None:
        self.__dict__.update(d)


def main() -> None:
    args = _parse_args()
    try:
        raise SystemExit(asyncio.run(_main_async(args)))
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
