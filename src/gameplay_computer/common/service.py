from pydantic import Json
from typing import Any, assert_never

from gameplay_computer.gameplay import (
    Action,
    State,
    Game,
    Connect4State,
    Connect4Action,
)


def serialize_action(action: Action) -> Json[Any]:
    match action.game:
        case "connect4":
            assert isinstance(action, Connect4Action)
            return action.column
        case _game as unreachable:
            assert_never(unreachable)


def deserialize_action(game: Game, json: Json[Any]) -> Action:
    match game:
        case "connect4":
            assert isinstance(json, int)
            assert json in range(0, 7)
            return Connect4Action(column=json)
        case _game as unreachable:
            assert_never(unreachable)


def serialize_state(state: State) -> Json[Any]:
    match state.game:
        case "connect4":
            assert isinstance(state, Connect4State)
            return state.board
        case _game as unreachable:
            assert_never(unreachable)


def deserialize_state(
    game: Game, over: bool, winner: int | None, next_player: int | None, json: Json[Any]
) -> State:
    match game:
        case "connect4":
            assert isinstance(json, list)
            assert len(json) == 7
            assert all(isinstance(col, list) for col in json)
            assert all(len(col) == 6 for col in json)
            assert all(isinstance(space, str) for col in json for space in col)
            return Connect4State(
                over=over, winner=winner, next_player=next_player, board=json
            )
        case _game as unreachable:
            assert_never(unreachable)
