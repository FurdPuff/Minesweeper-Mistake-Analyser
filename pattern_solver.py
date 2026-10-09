import sys
import sqlite3
from mines import Solver, UnsolveableException, Information # madewokherd's solver

def decode(canon: str):
    rows = canon.split("/")     # assume square board
    size = len(rows)
    cells = {(x, y): rows[y][x] for y in range(size) for x in range(size)}
    spaces = {p for p, ch in cells.items() if ch != "X"}

    off_board_sides = {
        "left": any(
            cells[(0, y)] == "X"
            and any(cells[(x, y)] != "X" for x in range(1, size))
            for y in range(size)
        ),
        "right": any(
            cells[(size - 1, y)] == "X"
            and any(cells[(x, y)] != "X" for x in range(size - 1))
            for y in range(size)
        ),
        "top": any(
            cells[(x, 0)] == "X"
            and any(cells[(x, y)] != "X" for y in range(1, size))
            for x in range(size)
        ),
        "bottom": any(
            cells[(x, size - 1)] == "X"
            and any(cells[(x, y)] != "X" for y in range(size - 1))
            for x in range(size)
        ),
    }
    solver = Solver(spaces)

    for (x, y), ch in cells.items():
        if ch not in ".12345678":
            continue
        solver.add_known_value((x, y), 0)              # a revealed cell is safe
        n = 0 if ch == "." else int(ch)
        neighbour_coordinates = {
            (x + dx, y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if dx or dy
        }
        neighbours = frozenset(neighbour_coordinates & spaces)
        complete = all(
            (nx, ny) in cells
            or (nx < 0 and off_board_sides["left"])
            or (nx >= size and off_board_sides["right"])
            or (ny < 0 and off_board_sides["top"])
            or (ny >= size and off_board_sides["bottom"])
            for nx, ny in neighbour_coordinates
        )
        if n == 0 or complete:
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
    seen = discovered_count = impossible_count = 0
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
        if any(p in (0.0, 1.0) for _, _, _, p in rows):   # if any tiles were confirmed to be safe or mines
            discovered_count += 1
            conn.execute("UPDATE patterns SET discovered_info = 1 WHERE id = ?", (id,))

    conn.commit()
    print("Analyzed", seen, "patterns\n",
          "Discovered new information in", discovered_count, "patterns\n",
          "Found ", impossible_count, " impossible patterns")
    conn.close()

if __name__ == '__main__':
    solve_patterns(sys.argv[1])
