import argparse
import json
from typing import Any

from sqlalchemy import Engine

from app.analytics.grid import GRID_VERSION
from app.analytics.metrics.catalog import MetricProviderError
from app.analytics.metrics.providers import MetricProviderRegistry
from app.analytics.metrics.publisher import MetricPublishError
from app.analytics.metrics.registry import MetricRegistry, MetricRegistryError
from app.analytics.metrics.runner import MetricSanityError, run_metric
from app.db.session import get_engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and run metric definitions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("list")
    run = subparsers.add_parser("run")
    run.add_argument("--metric", required=True)
    run.add_argument("--grid-version", default=GRID_VERSION)
    run_all = subparsers.add_parser("run-all")
    run_all.add_argument("--grid-version", default=GRID_VERSION)
    return parser


def execute(
    argv: list[str] | None = None,
    *,
    registry: MetricRegistry | None = None,
    providers: MetricProviderRegistry | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    loaded_registry = registry or MetricRegistry.load()
    if args.command == "validate":
        return {
            "status": "valid",
            "metric_count": len(loaded_registry.list(enabled_only=False)),
            "registry_checksum": loaded_registry.checksum(),
        }
    if args.command == "list":
        return {
            "metrics": [definition.snapshot() for definition in loaded_registry.list()]
        }
    provider_registry = providers or MetricProviderRegistry.production()
    if args.command == "run-all":
        target_engine = engine or get_engine()
        reports: list[dict[str, Any]] = []
        for definition in loaded_registry.list():
            provider = provider_registry.get(definition.provider_key)
            if provider is None:
                raise MetricRegistryError(
                    f"provider is not registered: {definition.provider_key}"
                )
            reports.append(
                run_metric(target_engine, definition, provider, args.grid_version)
            )
        return {"metric_count": len(reports), "metrics": reports}
    target_definition = loaded_registry.get(args.metric)
    if target_definition is None:
        raise MetricRegistryError(f"unknown or disabled metric: {args.metric}")
    provider = provider_registry.get(target_definition.provider_key)
    if provider is None:
        raise MetricRegistryError(
            f"provider is not registered: {target_definition.provider_key}"
        )
    target_engine = engine or get_engine()
    return run_metric(target_engine, target_definition, provider, args.grid_version)


def main() -> None:
    try:
        result = execute()
    except (
        MetricProviderError,
        MetricPublishError,
        MetricRegistryError,
        MetricSanityError,
        ValueError,
    ) as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
