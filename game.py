import json
from dataclasses import dataclass, asdict

@dataclass
class Cell:
    x: int
    y: int
    number: int | None = None
    opened: bool = False
    mine: bool = False
    flag: bool = False
    incorrect: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Cell":
        return cls(**data)

class Game:
    def __init__(self, width: int, height: int, minecount: int):
        self.width = width
        self.height = height
        self.minecount = minecount
        self.grid = [[Cell(x, y) for x in range(width)] for y in range(height)]

    def __iter__(self):
        for row in self.grid:
            for cell in row:
                yield cell

    def out_of_bounds(self, x: int, y: int) -> bool:
        return x < 0 or x >= self.width or y < 0 or y >= self.height

    def at(self, x: int, y: int) -> Cell | None:
        if self.out_of_bounds(x,y):
            return None
        return self.grid[y][x]

    def add(self, x: int, y: int, number: int | None, opened: bool,
            mine: bool, flag: bool, incorrect: bool):
        if self.out_of_bounds(x, y):
            return
        self.grid[y][x] = Cell(x, y, number, opened, mine, flag, incorrect)

    def is_over(self) -> bool:
        unrevealed = 0
        for cell in self:
            if not cell.opened:
                unrevealed += 1
        return self.minecount == unrevealed

    def loss_trigger(self) -> Cell | None:
        for cell in self:
            if cell.incorrect and cell.mine:
                return cell
        return None

    def count_mines(self) -> int:
        return sum(c.mine for c in self) + sum(c.flag and not c.incorrect for c in self)

    def unflag_all(self):
        for cell in self:
            if cell.flag:
                if cell.incorrect:
                    self.grid[cell.y][cell.x] = Cell(cell.x, cell.y)
                else:
                    cell.flag = False

    def undo_mistake(self):
        mistake = self.loss_trigger()
        if mistake is None:
            return
        self.minecount = self.count_mines()
        self.grid[mistake.y][mistake.x] = Cell(mistake.x, mistake.y)
        self.unflag_all()

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "minecount": self.minecount,
            "grid": [[cell.to_dict() for cell in row] for row in self.grid]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        game = cls(
            width=data["width"], 
            height=data["height"],
            minecount=data["minecount"]
        )
        game.grid = [
            [Cell.from_dict(cell_data) for cell_data in row]
            for row in data["grid"]
        ]
        return game

def read_json(path: str) -> tuple[int | None, str, Game] | None:
    """reads in game json returns game id, game url, and game"""
    try:
        with open(path) as f:
            return read_game_data(json.load(f))
    except (FileNotFoundError, PermissionError, TypeError):
        return None

def read_game_data(data: dict) -> tuple[int | None, str, Game]:
    """reads in game data and returns game id, game url, and game"""
    game = Game.from_dict(data["game"])

    try:
        game_id = int(data["id"])
    except (KeyError, ValueError, TypeError):
        game_id = None
    
    return game_id, data["url"], game
