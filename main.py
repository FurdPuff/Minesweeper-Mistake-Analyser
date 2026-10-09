import json
import ms_toollib as ms     # solver used: https://github.com/eee555/ms-toollib
from pathlib import Path
from game import read_json, Game
from patterns import UNKNOWN, OFF_BOARD, canonical, window, sees_revealed
from pattern_solver import solve_patterns
import sqlite3

SAMPLE_SIZE = 5 # width and height of a board sample that is taken as the boards pattern

init_db = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS pattern_probs;
DROP TABLE IF EXISTS cell_probs;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS patterns;

DROP INDEX IF EXISTS idx_games_pattern;

CREATE TABLE patterns (
    id                  INTEGER PRIMARY KEY,
    canonical           TEXT UNIQUE,
    discovered_info     BOOLEAN NOT NULL DEFAULT 0 CHECK (discovered_info IN (0, 1)),
    frequency           INTEGER DEFAULT 1
);

CREATE TABLE games (
    url         TEXT PRIMARY KEY,
    game_id     INTEGER,
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
);

CREATE TABLE pattern_probs (
    pattern_id INTEGER REFERENCES patterns(id),
    x INTEGER, y INTEGER,
    p_mine REAL NOT NULL,
    PRIMARY KEY (pattern_id, x, y)
);

CREATE TABLE cell_probs (
    game_url TEXT REFERENCES games(url),
    x INTEGER, y INTEGER,
    p_mine REAL NOT NULL,
    PRIMARY KEY (game_url, x, y)
);

CREATE INDEX idx_games_pattern ON games(pattern_id);
"""

file = "minesweeper_losses_size" + str(SAMPLE_SIZE)
if OFF_BOARD == UNKNOWN:
    file += "_off_boards_unknown"
file += ".db"

conn = sqlite3.connect(file)
conn.executescript(init_db)

count = 0
for game_json in sorted(Path("losses").glob("*.json")):
    result = read_json(game_json)
    if result is None:
        print("skipping unreadable file: ", game_json)
        continue
    game_id, game_url, game = result

    click = game.loss_trigger()
    if click is None:
        print("no losing click, skip", game_json)
        continue
    game.undo_mistake()

    board = [[UNKNOWN]*game.width for _ in range(game.height)]
    for c in game:
        if c.opened and not c.mine:
            board[c.y][c.x] = c.number or 0

    try:
        probs, (min_m, cur_m, max_m) = ms.cal_probability_onboard(board, game.minecount)
    except RuntimeError:
            print("bad board:", game_json)
            continue

    unknown = [(c.x, c.y, probs[c.y][c.x]) for c in game if board[c.y][c.x] == UNKNOWN]
    click_p = probs[click.y][click.x]
    best_p = min(p for _, _, p in unknown)
    n_safe = sum(1 for _, _, p in unknown if p == 0)
    
    grade = (1 - click_p / (1 - best_p)) if best_p < 1 else 0.0

    pattern_id = None
    if sees_revealed(board, click.x, click.y):
        sample = window(board, click.x, click.y, SAMPLE_SIZE)
        canon = canonical(sample)
        conn.execute("""
                INSERT INTO patterns (canonical, frequency) VALUES (?, 1)
                ON CONFLICT(canonical) DO UPDATE SET frequency = frequency + 1;
        """, (canon,))
        pattern_id = conn.execute("SELECT id FROM patterns WHERE canonical = ?", (canon,)).fetchone()[0]

    conn.execute("DELETE FROM cell_probs WHERE game_url = ?", (game_url,))
    conn.execute("""
        INSERT OR REPLACE INTO games 
            (url, game_id, width, height, minecount, click_x, click_y, 
            click_p, best_p, n_safe, grade, pattern_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_url, game_id, game.width, game.height, game.minecount, click.x, click.y,
        click_p, best_p, n_safe, grade, pattern_id))
    conn.executemany("INSERT INTO cell_probs VALUES (?, ?, ?, ?)",
                     [(game_url, x, y, p) for x, y, p in unknown])

    count += 1 
    if count % 100 == 0:
        conn.commit()

conn.commit()
print("processed", count, "games;",
      conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0], "distinct patterns")
conn.close()

if __name__ == '__main__':
    solve_patterns(file)
