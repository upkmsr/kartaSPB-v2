import argparse

from app.data.streets import dry_run_streets, refresh_streets, report_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservative logical street refresh")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("dry-run", help="Report street groups without writing")
    commands.add_parser("refresh", help="Refresh logical streets transactionally")
    args = parser.parse_args()
    report = dry_run_streets() if args.command == "dry-run" else refresh_streets()
    print(report_json(report))


if __name__ == "__main__":
    main()
