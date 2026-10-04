import argparse
import json
from typing import Any

from app.analytics.grid import GRID_VERSION
from app.analytics.metrics.providers import MetricProviderContext, MetricProviderRegistry
from app.analytics.metrics.publisher import MetricPublishError, publish_metric
from app.analytics.metrics.registry import MetricRegistry, MetricRegistryError
from app.db.session import get_engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and run metric definitions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("list")
    run = subparsers.add_parser("run")
    run.add_argument("--metric", required=True)
    run.add_argument("--grid-version", default=GRID_VERSION)
    run.add_argument("--input-fingerprint", required=True)
    return parser


def execute(
    argv: list[str] | None = None,
    *,
    registry: MetricRegistry | None = None,
    providers: MetricProviderRegistry | None = None,
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
    definition = loaded_registry.get(args.metric)
    if definition is None:
        raise MetricRegistryError(f"unknown or disabled metric: {args.metric}")
    provider = (providers or MetricProviderRegistry()).get(definition.provider_key)
    if provider is None:
        raise MetricRegistryError(f"provider is not registered: {definition.provider_key}")
    engine = get_engine()
    values = provider.calculate(
        MetricProviderContext(
            engine=engine, definition=definition, grid_version=args.grid_version
        )
    )
    return publish_metric(
        engine,
        definition,
        args.grid_version,
        args.input_fingerprint,
        values,
    ).to_dict()


def main() -> None:
    try:
        result = execute()
    except (MetricPublishError, MetricRegistryError, ValueError) as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
