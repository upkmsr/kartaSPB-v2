import argparse
import json
import sys
from pathlib import Path

from app.db.session import get_engine
from app.upi.adapters import TorisConstructionAdapter
from app.upi.config import RawRetentionMode, load_source_config
from app.upi.service import probe_source, report_json, snapshot_fixture


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="KARTASPB UPI evidence source engine")
    commands = command_parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-config", help="Validate one source profile")
    validate.add_argument("--source", required=True)
    probe = commands.add_parser("probe", help="Run a bounded read-only source probe")
    probe.add_argument("--source", required=True)
    snapshot = commands.add_parser("snapshot", help="Persist one complete evidence snapshot")
    snapshot.add_argument("--source", required=True)
    snapshot.add_argument("--fixture", type=Path)
    return command_parser


def main() -> None:
    args = parser().parse_args()
    try:
        config = load_source_config(args.source)
        if args.command == "validate-config":
            print(
                json.dumps(
                    {
                        "source": config.source_key,
                        "status": "VALID",
                        "adapter_version": config.adapter_version,
                        "normalization_version": config.normalization_version,
                        "terms_status": config.terms_status.value,
                        "raw_retention_mode": config.raw_retention_mode.value,
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "probe":
            print(report_json(probe_source(TorisConstructionAdapter(config))))
        elif args.command == "snapshot":
            if args.fixture is None:
                if config.raw_retention_mode is not RawRetentionMode.FULL_RAW_ALLOWED:
                    raise PermissionError(
                        "Live snapshot is blocked: source terms do not authorize persistent raw "
                        "retention; use a deterministic fixture"
                    )
                raise NotImplementedError("Live snapshot execution is not enabled in UPI-A")
            print(report_json(snapshot_fixture(get_engine(), config, args.fixture.resolve())))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": getattr(exc, "code", type(exc).__name__),
                    "message": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
