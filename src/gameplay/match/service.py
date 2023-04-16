# so, the point of this is that you can kind of build and test the whole system
# without a database or a frontend.
# I guess that sorta sounds cool, lets see if it's worth the work.
# doing this kind of thing with an explicit effects system could be reallllly sick.
# Time to try ocaml?


# abstracting the whole ass thing to be a message bus is a little extra.
# I think the "commands" really can just be commands, and then events can happen
# and have handlers and that's chill, but doesn't have to all be a queue like this.

from typing import assert_never, TypedDict

from . import commands, events
from .session import Session

Message = commands.Command | events.Event


# todo: process the events after the request is done
async def handle(message: Message, session: Session) -> list[int]:
    results = []
    queue: list[Message] = [message]
    while queue:
        message = queue.pop()
        match message:
            case commands.CreateMatch() | commands.DeleteMatch():
                result = await handle_command(message, queue, session)
                results.append(result)
            case events.MatchCreated() | events.MatchUpdated() | events.MatchOver():
                await handle_event(message, queue, session)
            case _ as unreachable:
                assert_never(unreachable)
    return results


async def handle_command(
    command: commands.Command, queue: list[Message], session: Session
) -> int:
    print("handling command", command)
    try:
        match command:
            case commands.CreateMatch():
                result = await create_match(command, session)
            case commands.DeleteMatch():
                result = 0
            case _ as unreachable:
                assert_never(unreachable)
        queue.extend(session.collect_new_events())
        return result
    except Exception as e:
        print(e)
        raise


async def handle_event(
    event: events.Event, queue: list[Message], session: Session
) -> None:
    match event:
        case events.MatchCreated():
            handlers = [notify_match_created]
            for handler in handlers:
                try:
                    print("handling event", event, "with handler", handler.__name__)
                    await handler(event, session)
                    queue.extend(session.collect_new_events())
                except Exception as e:
                    print(e)
                    continue
        case events.MatchUpdated():
            handlers = []
            for handler in handlers:
                try:
                    print("handling event", event, "with handler", handler.__name__)
                    await handler(event, session)
                    queue.extend(session.collect_new_events())
                except Exception as e:
                    print(e)
                    continue
        case events.MatchOver():
            handlers = []
            for handler in handlers:
                try:
                    print("handling event", event, "with handler", handler.__name__)
                    await handler(event, session)
                    queue.extend(session.collect_new_events())
                except Exception as e:
                    print(e)
                    continue
        case _ as unreachable:
            assert_never(unreachable)


async def create_match(command: commands.CreateMatch, session: Session) -> int:
    async with session.transaction():
        match_id = await session.matches.create()
        session.event(events.MatchCreated(match_id=match_id))
    return match_id


async def delete_match(command: commands.DeleteMatch, session: Session) -> int:
    return 0


async def notify_match_created(event: events.MatchCreated, session: Session) -> None:
    print("match created", event.match_id)


EventHandlers = TypedDict("EventHandlers", {events.MatchCreated: list[callable]})

EVENT_HANDLERS = {
    events.MatchCreated: [],
    events.MatchUpdated: [],
    events.MatchOver: [],
}

COMMAND_HANDLERS = {
    commands.CreateMatch: create_match,
    commands.DeleteMatch: delete_match,
}
