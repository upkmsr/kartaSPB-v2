import argparse

from app.data.facilities import dry_run_facilities, refresh_facilities, report_json


def main() -> None:
    command_parser = argparse.ArgumentParser(
        description="Conservative logical facility representation refresh"
    )
    commands = command_parser.add_subparsers(dest="command", required=True)
    commands.add_parser("dry-run", help="Report bounded candidates without writing")
    commands.add_parser("refresh", help="Refresh logical facilities transactionally")
    args = command_parser.parse_args()
    report = dry_run_facilities() if args.command == "dry-run" else refresh_facilities()
    print(report_json(report))


if __name__ == "__main__":
    main()
