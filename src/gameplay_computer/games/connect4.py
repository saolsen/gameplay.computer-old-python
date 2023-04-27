from enum import IntEnum
from typing import Literal, Self, assert_never

from pydantic import Json

from gameplay_computer.common.schemas import BaseAction, BaseState


class Player(IntEnum):
    BLUE = 1
    RED = 2


Result = Player | Literal["draw"] | None


class Action(BaseAction[Json[int]]):
    game: Literal["connect4"] = "connect4"
    column: int

    @classmethod
    def deserialize(cls, t: Json[int]) -> Self:
        return cls(column=t)

    def serialize(self) -> Json[int]:
        return self.column


Board = list[list[int]]


def initial_state() -> Board:
    return list([0] * 6 for _ in range(7))


def check(board: Board) -> Result:
    """
    Check for a win or draw.
    """
    # Check rows
    for row in range(0, 6):
        for col in range(0, 4):
            if (
                board[col][row] != 0
                and board[col][row]
                == board[col + 1][row]
                == board[col + 2][row]
                == board[col + 3][row]
            ):
                return Player(board[col][row])
    # Check cols
    for col in range(0, 7):
        for row in range(0, 3):
            if (
                board[col][row] != 0
                and board[col][row]
                == board[col][row + 1]
                == board[col][row + 2]
                == board[col][row + 3]
            ):
                return Player(board[col][row])
    # Check diag up
    for col in range(0, 4):
        for row in range(0, 3):
            if (
                board[col][row] != 0
                and board[col][row]
                == board[col + 1][row + 1]
                == board[col + 2][row + 2]
                == board[col + 3][row + 3]
            ):
                return Player(board[col][row])

    # Check diag down
    for col in range(0, 4):
        for row in range(3, 6):
            if (
                board[col][row] != 0
                and board[col][row]
                == board[col + 1][row - 1]
                == board[col + 2][row - 2]
                == board[col + 3][row - 3]
            ):
                return Player(board[col][row])

    # Check draw
    for col in range(0, 7):
        if board[col][5] == 0:
            # There are still moves left
            return None

    return "draw"


class State(BaseState[Action, Json[Board]]):
    game: Literal["connect4"] = "connect4"
    over: bool = False
    winner: Player | None = None
    next_player: Player | None = Player.BLUE

    board: Board = initial_state()

    @classmethod
    def deserialize(
        cls,
        over: bool,
        winner: int | None,
        next_player: int | None,
        json: Json[list[list[int]]],
    ) -> Self:
        return cls(over=over, winner=winner, next_player=next_player, board=json)

    def serialize(self) -> Json[Board]:
        return self.board

    def actions(self) -> list[Action]:
        return [Action(column=i) for i in range(7) if self.board[i][5] == 0]


    def turn(self, player: int, action: Action) -> None:
        assert self.next_player == Player(player)
        assert self.board[action.column][5] == 0

        for i in range(6):
            if self.board[action.column][i] == 0:
                self.board[action.column][i] = player
                break

        result = check(self.board)

        match result:
            case (Player.BLUE | Player.RED) as player:
                self.over = True
                self.winner = player
                self.next_player = None
            case "draw":
                self.over = True
                self.winner = None
                self.next_player = None
            case None:
                self.over = False
                self.winner = None
                self.next_player = (
                    Player.BLUE if self.next_player == Player.RED else Player.RED
                )
            case _other as unknown:
                assert_never(unknown)
