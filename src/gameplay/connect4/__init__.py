from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


# from .. import native


class Player(IntEnum):
    BLUE = 1
    RED = 2


Result = Player | Literal["draw"] | None


@dataclass(slots=True)
class State:
    board: tuple[list[int], ...]
    next_player: Player

    def actions(self) -> list[int]:
        return [i for i in range(7) if self.board[i][5] == 0]

    def check(self) -> Result:
        """
        Check for a win or draw.
        """
        # Check rows
        for row in range(0, 6):
            for col in range(0, 4):
                if (
                    self.board[col][row] != 0
                    and self.board[col][row]
                    == self.board[col + 1][row]
                    == self.board[col + 2][row]
                    == self.board[col + 3][row]
                ):
                    return Player(self.board[col][row])
        # Check cols
        for col in range(0, 7):
            for row in range(0, 3):
                if (
                    self.board[col][row] != 0
                    and self.board[col][row]
                    == self.board[col][row + 1]
                    == self.board[col][row + 2]
                    == self.board[col][row + 3]
                ):
                    return Player(self.board[col][row])
        # Check diag up
        for col in range(0, 4):
            for row in range(0, 3):
                if (
                    self.board[col][row] != 0
                    and self.board[col][row]
                    == self.board[col + 1][row + 1]
                    == self.board[col + 2][row + 2]
                    == self.board[col + 3][row + 3]
                ):
                    return Player(self.board[col][row])

        # Check diag down
        for col in range(0, 4):
            for row in range(3, 6):
                if (
                    self.board[col][row] != 0
                    and self.board[col][row]
                    == self.board[col + 1][row - 1]
                    == self.board[col + 2][row - 2]
                    == self.board[col + 3][row - 3]
                ):
                    return Player(self.board[col][row])

        # Check draw
        for col in range(0, 7):
            if self.board[col][5] == 0:
                # There are still moves left
                return None

        return "draw"

    def turn(self, player: Player, column: int) -> Result:
        """
        Take a turn. Returns the result of the game if it is over.
        """
        assert self.next_player == player
        assert self.board[column][5] == 0

        for i in range(6):
            if self.board[column][i] == 0:
                self.board[column][i] = player
                break

        self.next_player = Player.BLUE if self.next_player == Player.RED else Player.RED

        return self.check()
