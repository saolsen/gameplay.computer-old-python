from typing import Literal, assert_never

from gameplay_computer.common import ALogic
from gameplay_computer.gameplay import (
    Connect4Action as Action,
    Connect4Board as Board,
    Connect4State as State,
    Connect4Space as Space,
)


def get_player(space: Space) -> int:
    match space:
        case Space.BLUE:
            return 0
        case Space.RED:
            return 1
        case Space.EMPTY:
            assert None
        case _space as unreachable:
            assert_never(unreachable)


def get_space(player: int) -> Space:
    match player:
        case 0:
            return Space.BLUE
        case 1:
            return Space.RED
        case _player as unreachable:
            assert False, unreachable


Result = int | Literal["draw"] | None


def check(board: Board) -> Result:
    """
    Check for a win or draw.
    """
    # Check rows
    for row in range(0, 6):
        for col in range(0, 4):
            if (
                board[col][row] != Space.EMPTY
                and board[col][row]
                == board[col + 1][row]
                == board[col + 2][row]
                == board[col + 3][row]
            ):
                return get_player(board[col][row])
    # Check cols
    for col in range(0, 7):
        for row in range(0, 3):
            if (
                board[col][row] != Space.EMPTY
                and board[col][row]
                == board[col][row + 1]
                == board[col][row + 2]
                == board[col][row + 3]
            ):
                return get_player(board[col][row])
    # Check diag up
    for col in range(0, 4):
        for row in range(0, 3):
            if (
                board[col][row] != Space.EMPTY
                and board[col][row]
                == board[col + 1][row + 1]
                == board[col + 2][row + 2]
                == board[col + 3][row + 3]
            ):
                return get_player(board[col][row])

    # Check diag down
    for col in range(0, 4):
        for row in range(3, 6):
            if (
                board[col][row] != Space.EMPTY
                and board[col][row]
                == board[col + 1][row - 1]
                == board[col + 2][row - 2]
                == board[col + 3][row - 3]
            ):
                return get_player(board[col][row])

    # Check draw
    for col in range(0, 7):
        if board[col][5] == Space.EMPTY:
            # There are still moves left
            return None

    return "draw"


class Connect4Logic(ALogic[Action, State]):
    @staticmethod
    def initial_state() -> State:
        board = list([Space.EMPTY] * 6 for _ in range(7))
        return State(over=False, winner=None, next_player=0, board=board)

    @staticmethod
    def actions(s: State) -> list[Action]:
        return [Action(column=i) for i in range(7) if s.board[i][5] == Space.EMPTY]

    @staticmethod
    def turn(s: State, player: int, action: Action) -> None:
        assert s.next_player == player
        assert s.board[action.column][5] == Space.EMPTY

        for i in range(6):
            if s.board[action.column][i] == Space.EMPTY:
                s.board[action.column][i] = get_space(player)
                break

        result = check(s.board)

        match result:
            case (0 | 1) as player:
                s.over = True
                s.winner = player
                s.next_player = None
            case "draw":
                s.over = True
                s.winner = None
                s.next_player = None
            case None:
                s.over = False
                s.winner = None
                s.next_player = 0 if s.next_player == 1 else 1
            case _result as unknown:
                assert False, unknown
