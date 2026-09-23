import argparse
import sys

from app.data.osm.config import load_regions
from app.data.osm.pipeline import (
    download_source,
    extract_region,
    import_region,
    inspect,
    status,
)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="KARTASPB OSM ingestion engine")
    commands = command_parser.add_subparsers(dest="command", required=True)

    download = commands.add_parser("download", help="Download and validate provider PBF")
    download.add_argument("--force", action="store_true", help="Fetch the current remote file")

    extract = commands.add_parser("extract", help="Create a configured geographic extract")
    extract.add_argument("--region", required=True, choices=sorted(load_regions()))
    extract.add_argument("--force", action="store_true", help="Rebuild an existing extract")

    import_command = commands.add_parser("import", help="Import an extract into staging")
    import_command.add_argument("--region", required=True, choices=sorted(load_regions()))

    smoke = commands.add_parser("smoke", help="Download, extract, and import spb_smoke")
    smoke.add_argument("--force-download", action="store_true")
    smoke.add_argument("--force-extract", action="store_true")

    commands.add_parser("status", help="Show source metadata and staging counts")
    commands.add_parser("inspect", help="Print useful staging inspection queries")
    commands.add_parser("versions", help="Print external tool versions")
    return command_parser


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "download":
            download_source(force=args.force)
        elif args.command == "extract":
            extract_region(args.region, force=args.force)
        elif args.command == "import":
            import_region(args.region)
        elif args.command == "smoke":
            download_source(force=args.force_download)
            extract_region("spb_smoke", force=args.force_extract)
            import_region("spb_smoke")
        elif args.command == "status":
            status()
        elif args.command == "inspect":
            inspect()
        elif args.command == "versions":
            import subprocess

            subprocess.run(["osmium", "--version"], check=True)
            subprocess.run(["osm2pgsql", "--version"], check=True)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
