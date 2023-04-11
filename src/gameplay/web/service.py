from .schemas import MatchCreate, Match, TurnCreate, Turn


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
        state="playing",
        turn=1,
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

    # todo: notify followers

    return match
