from .schemas import MatchCreate, Match, TurnCreate, Turn
import random


# just hack this together to start with
next_id = 0
matches: dict[int, Match] = {}


async def create_match(new_match: MatchCreate) -> Match:
    global next_id
    global matches

    match_id = next_id
    next_id += 1
    match = Match(
        **new_match.dict(),
        id=match_id,
        state=(
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
        ),
        turn=0,
        next_player=1,
        turns=[],
    )
    matches[match_id] = match
    return match


async def get_match(match_id: int) -> Match:
    global matches

    match = matches[match_id]
    return match


async def follow_match():
    pass


async def stop_following_match():
    pass


async def take_turn(match_id: int, new_turn: TurnCreate) -> Match:
    global matches

    # todo validate
    match = matches[match_id]
    turn = Turn(
        **new_turn.dict(),
        id=len(match.turns) + 1,
        number=len(match.turns) + 1,
        match_id=match_id,
    )
    match.turns.append(turn)
    match.turn += 1

    for i in range(6):
        if match.state[new_turn.column][i] == 0:
            match.state[new_turn.column][i] = new_turn.player
            break

    # @hack: do a random inline turn for the other team.
    other = random.randint(0, 6)
    for i in range(6):
        if match.state[other][i] == 0:
            match.state[other][i] = 2
            break

    # todo: update next player

    # todo: notify followers

    return match
