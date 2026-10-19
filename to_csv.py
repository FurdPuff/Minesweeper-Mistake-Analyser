import argparse
import csv
import sqlite3
from pathlib import Path


TABLES = ("games", "cell_probs", "patterns", "pattern_probs")


def export_tables(database: str | Path, output_dir: str | Path | None = None) -> list[Path]:
    database_path = Path(database).resolve(strict=True)
    destination_dir = (
        Path(output_dir).resolve()
        if output_dir is not None
        else database_path.parent
    )
    if not destination_dir.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {destination_dir}")

    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing_tables = set(TABLES) - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise ValueError(f"Database is missing required table(s): {missing}")

        csv_paths = []
        for table in TABLES:
            cursor = connection.execute(f'SELECT * FROM "{table}"')
            csv_path = destination_dir / f"{database_path.stem}_{table}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(column[0] for column in cursor.description)
                writer.writerows(cursor)
            csv_paths.append(csv_path)
        return csv_paths
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the four Minesweeper database tables to CSV files."
    )
    parser.add_argument("database", type=Path, help="source SQLite .db file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="directory for CSV files (defaults to the database's directory)",
    )
    args = parser.parse_args()

    for csv_path in export_tables(args.database, args.output_dir):
        print(f"CSV saved to: {csv_path}")


if __name__ == "__main__":
    main()