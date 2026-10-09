import argparse
import json
from typing import Any

from sqlalchemy import Engine

from app.analytics.grid import GRID_VERSION
from app.analytics.scoring.engine import ScoringError, ScoringService
from app.analytics.scoring.publisher import (
    NormalizationPublishError,
    publish_normalized_metric,
)
from app.analytics.scoring.registry import (
    NormalizationRegistry,
    NormalizationRegistryError,
)
from app.db.session import get_engine


def _weight(value: str) -> tuple[str, float]:
    try:
        key, raw_weight = value.rsplit("=", 1)
        return key, float(raw_weight)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("weight must use metric.key=number") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize metrics and evaluate explicit weights")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("--metric", required=True)
    normalize.add_argument("--grid-version", default=GRID_VERSION)
    normalize_all = subparsers.add_parser("normalize-all")
    normalize_all.add_argument("--grid-version", default=GRID_VERSION)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--grid-version", default=GRID_VERSION)
    evaluate.add_argument("--weight", action="append", type=_weight, required=True)
    evaluate.add_argument("--limit", type=int, default=20)
    return parser


def execute(
    argv: list[str] | None = None,
    *,
    registry: NormalizationRegistry | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    loaded_registry = registry or NormalizationRegistry.load()
    if args.command == "validate":
        return {
            "status": "valid",
            "normalization_count": len(loaded_registry.list(enabled_only=False)),
            "registry_checksum": loaded_registry.checksum(),
        }
    target_engine = engine or get_engine()
    if args.command == "normalize":
        definition = loaded_registry.get(args.metric)
        if definition is None:
            raise NormalizationRegistryError(
                f"unknown or disabled normalization: {args.metric}"
            )
        return publish_normalized_metric(
            target_engine, definition, args.grid_version
        ).to_dict()
    if args.command == "normalize-all":
        reports = [
            publish_normalized_metric(target_engine, definition, args.grid_version).to_dict()
            for definition in loaded_registry.list()
        ]
        return {"normalization_count": len(reports), "normalizations": reports}
    weights: dict[str, float] = {}
    for key, weight in args.weight:
        if key in weights:
            raise ScoringError(f"duplicate weight: {key}")
        weights[key] = weight
    return ScoringService(target_engine, loaded_registry).evaluate(
        args.grid_version, weights, limit=args.limit
    ).to_dict()


def main() -> None:
    try:
        result = execute()
    except (
        NormalizationPublishError,
        NormalizationRegistryError,
        ScoringError,
        ValueError,
    ) as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
