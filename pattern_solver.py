import sys
import sqlite3
from mines import Solver, UnsolveableException, Information # madewokherd's solver

def decode(canon: str):
    rows = canon.split("/")     # assume square board
    size = len(rows)
    cells = {(x, y): rows[y][x] for y in range(size) for x in range(size)}
    spaces = {p for p, ch in cells.items() if ch != "X"}
    solver = Solver(spaces)

    for (x, y), ch in cells.items():
        if ch not in ".12345678":
            continue
        solver.add_known_value((x, y), 0)              # a revealed cell is safe
        n = 0 if ch == "." else int(ch)
        neighbours = frozenset((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)) & spaces
        on_ring = x in (0, size - 1) or y in (0, size - 1)
        if n == 0 or not on_ring:
            solver.add_information(Information(neighbours, n))
    
    return solver, cells

def solve_patterns(db):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DROP TABLE IF EXISTS pattern_probs")

    conn.execute("""
    CREATE TABLE pattern_probs (
        pattern_id INTEGER REFERENCES patterns(id),
        x INTEGER, y INTEGER,
        p_mine REAL NOT NULL,
        PRIMARY KEY (pattern_id, x, y)
    )""")

    patterns = conn.execute("SELECT id, canonical FROM patterns").fetchall()
    seen = solve_count = impossible_count = 0
    for id, canon in patterns:
        seen += 1

        try:
            solver, cells = decode(canon)
            solver.solve()
            probs, total = solver.get_probabilities()
        except UnsolveableException:
            print("Pattern ", id, " is impossible")
            impossible_count += 1
            continue
        
        rows = []
        for (x, y), ch in cells.items():
            if ch != "#":
                continue
            if (x, y) in solver.solved_spaces:            # forced safe (0) or forced mine (1)
                rows.append((id, x, y, float(solver.solved_spaces[(x, y)])))
            elif (x, y) in probs:
                rows.append((id, x, y, probs[(x, y)] / total))

        conn.executemany("INSERT INTO pattern_probs VALUES (?, ?, ?, ?)", rows)
        if any(p in (0.0, 1.0) for _, _, _, p in rows):                # if any tiles were confirmed to be safe or mines
            solve_count += 1

    conn.commit()
    print("Analyzed", seen, "patterns\n",
          "Solved", solve_count, "patterns (# of patterns with confirmed information)\n",
          "Found ", impossible_count, "many impossible patterns")
    conn.close()

if __name__ == '__main__':
    solve_patterns(sys.argv[1])
