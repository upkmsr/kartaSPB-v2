import argparse

from sqlalchemy import text

from app.data.categories import apply_categories, run_osm_category_pipeline
from app.db.session import get_engine


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="KARTASPB catalog category engine")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Canonicalize category candidates and classify them")
    run.add_argument("--source-id", type=int, required=True)
    run.add_argument("--import-run-id", type=int, required=True)
    apply = commands.add_parser("apply", help="Classify existing canonical bindings")
    apply.add_argument("--source-id", type=int, required=True)
    apply.add_argument("--import-run-id", type=int, required=True)
    commands.add_parser("status", help="Show active category counts")
    return root


def main() -> None:
    args = parser().parse_args()
    engine = get_engine()
    if args.command == "run":
        print(run_osm_category_pipeline(args.source_id, args.import_run_id, engine=engine))
    elif args.command == "apply":
        processed, matches = apply_categories(args.source_id, args.import_run_id, engine=engine)
        print(f"processed={processed} matches={matches}")
    else:
        with engine.connect() as connection:
            rows = connection.execute(
                text("""
                SELECT category_key, count(*) FROM catalog.object_categories
                WHERE lifecycle_status='active' GROUP BY category_key ORDER BY category_key
            """)
            ).all()
        for key, count in rows:
            print(f"{key}: {count}")


if __name__ == "__main__":
    main()
