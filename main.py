import json, ms_toollib as ms
from pathlib import Path
from game import read_json, Game
from patterns import UNKNOWN, canonical, window, sees_revealed
import sqlite3

SAMPLE_SIZE = 7 # width and height of a board sample that is taken as the boards pattern

init_db = """
CREATE TABLE IF NOT EXISTS patterns (
    id          INTEGER PRIMARY KEY,
    canonical   TEXT UNIQUE  -- Fixed: Removed trailing comma
);

CREATE TABLE IF NOT EXISTS games (
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

CREATE TABLE IF NOT EXISTS pattern_probs (
    pattern_id  INTEGER,     -- Fixed: Changed type to INTEGER to match patterns(id)
    game_url    TEXT,        -- Fixed: Added missing column required by the composite PRIMARY KEY
    x           INTEGER, 
    y           INTEGER,
    p_mine      REAL NOT NULL,
    PRIMARY KEY (game_url, x, y),
    FOREIGN KEY (pattern_id) REFERENCES patterns(id) -- Fixed: Clean separation of PK and FK syntax
);

CREATE TABLE IF NOT EXISTS cell_probs (
    game_url TEXT REFERENCES games(url),
    x INTEGER, y INTEGER,
    p_mine REAL NOT NULL,
    PRIMARY KEY (game_url, x, y)
);

CREATE INDEX IF NOT EXISTS idx_games_pattern ON games(pattern_id);
"""

file = "minesweeper_losses_size" + str(SAMPLE_SIZE) + ".db"

conn = sqlite3.connect(file)
conn.execute("PRAGMA foreign_keys = ON")
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
        conn.execute("INSERT OR IGNORE INTO patterns (canonical) VALUES (?)", (canon,))
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
