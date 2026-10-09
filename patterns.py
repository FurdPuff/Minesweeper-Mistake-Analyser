UNKNOWN = 10
OFF_BOARD = -1

def neighbours(board, x, y):
    h, w = len(board), len(board[0])
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dx or dy) and 0 <= x + dx < w and 0 <= y + dy < h:
                yield x + dx, y + dy

def sees_revealed(board, x, y) -> bool:
    """unknown cell has at least one revealed neighbour"""
    return board[y][x] == UNKNOWN and any(board[j][i] != UNKNOWN for i, j in neighbours(board, x, y))

def window(board, cx, cy, size):
    """returns a window of a given size containing cell (cx, cy)"""
    r = size // 2
    h, w = len(board), len(board[0])
    return [[board[y][x] if 0 <= x < w and 0 <= y < h else OFF_BOARD
             for x in range(cx - r, cx + r + 1)]
            for y in range(cy - r, cy + r + 1)]

def _symmetries(g):
    """returns all 8 symmetries of 2d array g"""
    out = []
    for _ in range(4):
        g = [list(row) for row in zip(*g[::-1])]    # rotate 90 degrees
        out.append(g)
        out.append([row[::-1] for row in g])        # and its mirror image
    return out

def _encode(g):
    sym = {OFF_BOARD: "X", UNKNOWN: "#", 0: "."}
    return "/".join("".join(sym.get(v, str(v)) for v in row) for row in g)

def canonical(g) -> str:
    """lexicographically smallest encoding over the 8 rotations/reflections"""
    return min(_encode(s) for s in _symmetries(g))
