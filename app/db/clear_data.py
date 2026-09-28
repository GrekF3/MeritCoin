from __future__ import annotations

import argparse

from sqlalchemy import delete, func, inspect, select, text

from app.db.base import Base
from app.db.session import SessionLocal, engine


def application_tables():
    return [table for table in Base.metadata.sorted_tables if table.name != "alembic_version"]


def table_counts() -> list[tuple[str, int]]:
    with SessionLocal() as db:
        counts = []
        for table in application_tables():
            total = db.execute(select(func.count()).select_from(table)).scalar_one()
            counts.append((table.name, int(total)))
        return counts


def print_summary() -> None:
    counts = table_counts()
    total = sum(count for _, count in counts)
    print("Current application data:")
    for name, count in counts:
        print(f"  {name}: {count}")
    print(f"Total rows: {total}")


def clear_data() -> None:
    with SessionLocal() as db:
        for table in reversed(application_tables()):
            db.execute(delete(table))
        db.commit()

    if engine.dialect.name == "sqlite" and inspect(engine).has_table("sqlite_sequence"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM sqlite_sequence WHERE name NOT IN ('alembic_version')"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear Neuro Coin application data.")
    parser.add_argument("--summary", action="store_true", help="Print table row counts.")
    parser.add_argument("--yes", action="store_true", help="Delete application data without an interactive prompt.")
    args = parser.parse_args()

    if args.summary or not args.yes:
        print_summary()
    if args.yes:
        clear_data()
        print("Application data deleted.")


if __name__ == "__main__":
    main()
