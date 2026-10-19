import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

def sanitize_sqlite_database(input_db: str | Path, output_db: str | Path) -> None:
    input_path = Path(input_db).resolve(strict=True)
    output_path = Path(output_db).resolve()
    if input_path == output_path:
        raise ValueError("The output database must differ from the input database.")
    if not output_path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output_path.parent}")

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    source = sqlite3.connect(input_path)
    destination: sqlite3.Connection | None = None

    try:
        destination = sqlite3.connect(temporary_path)
        source.backup(destination)
        destination.execute("PRAGMA foreign_keys = OFF")
        destination.execute("PRAGMA secure_delete = ON")

        tables = {
            row[0]
            for row in destination.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not {"games", "cell_probs"} <= tables:
            raise ValueError("Database must contain both 'games' and 'cell_probs' tables.")
        if {"games_sanitized", "cell_probs_sanitized"} & tables:
            raise ValueError("Database already contains a reserved sanitization table name.")

        game_columns = {
            row[1] for row in destination.execute("PRAGMA table_info(games)")
        }
        cell_prob_columns = {
            row[1] for row in destination.execute("PRAGMA table_info(cell_probs)")
        }
        if not {"url", "game_id"} <= game_columns or "game_url" not in cell_prob_columns:
            raise ValueError(
                "Database does not have the expected private columns "
                "'games.url', 'games.game_id', and 'cell_probs.game_url'."
            )

        destination.execute("BEGIN")
        destination.execute("""
            CREATE TABLE games_sanitized (
                id          INTEGER PRIMARY KEY,
                width       INTEGER NOT NULL,
                height      INTEGER NOT NULL,
                minecount   INTEGER NOT NULL,
                click_x     INTEGER NOT NULL,
                click_y     INTEGER NOT NULL,
                click_p     REAL NOT NULL,
                best_p      REAL NOT NULL,
                n_safe      INTEGER NOT NULL,
                grade       REAL,
                pattern_id  INTEGER REFERENCES patterns(id)
            )
        """)
        destination.execute("""
            CREATE TABLE cell_probs_sanitized (
                game_id INTEGER REFERENCES games_sanitized(id),
                x INTEGER,
                y INTEGER,
                p_mine REAL NOT NULL,
                PRIMARY KEY (game_id, x, y)
            )
        """)

        game_ids: dict[str, int] = {}
        games = destination.execute("""
            SELECT url, width, height, minecount, click_x, click_y,
                   click_p, best_p, n_safe, grade, pattern_id
            FROM games
            ORDER BY rowid
        """)
        for row in games:
            url, *game_data = row
            cursor = destination.execute("""
                INSERT INTO games_sanitized (
                    width, height, minecount, click_x, click_y,
                    click_p, best_p, n_safe, grade, pattern_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, game_data)
            game_ids[url] = cursor.lastrowid

        for game_url, x, y, p_mine in destination.execute(
            "SELECT game_url, x, y, p_mine FROM cell_probs"
        ):
            try:
                game_id = game_ids[game_url]
            except KeyError as error:
                raise ValueError(
                    "cell_probs contains a game_url that is missing from games."
                ) from error
            destination.execute(
                "INSERT INTO cell_probs_sanitized VALUES (?, ?, ?, ?)",
                (game_id, x, y, p_mine),
            )

        destination.execute("DROP TABLE cell_probs")
        destination.execute("DROP TABLE games")
        destination.execute("ALTER TABLE games_sanitized RENAME TO games")
        destination.execute("ALTER TABLE cell_probs_sanitized RENAME TO cell_probs")
        destination.execute(
            "CREATE INDEX idx_games_pattern ON games(pattern_id)"
        )
        destination.commit()

        destination.execute("VACUUM")
        if destination.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise sqlite3.DatabaseError("Sanitized database failed integrity_check.")
        if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.DatabaseError("Sanitized database contains foreign-key violations.")
        destination.close()
        destination = None
        os.replace(temporary_path, output_path)
    finally:
        source.close()
        if destination is not None:
            destination.close()
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a sanitized copy of a Minesweeper SQLite database."
    )
    parser.add_argument("input_db", type=Path, help="source .db file")
    parser.add_argument(
        "output_db",
        type=Path,
        nargs="?",
        help="destination .db file (defaults to clean_<input>.db)",
    )
    args = parser.parse_args()
    output_db = args.output_db or args.input_db.with_name(
        f"clean_{args.input_db}"
    )
    sanitize_sqlite_database(args.input_db, output_db)
    print(f"Sanitized database saved to: {output_db}")


if __name__ == "__main__":
    main()
