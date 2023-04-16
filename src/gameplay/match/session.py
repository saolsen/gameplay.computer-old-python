import abc

from typing import AsyncIterator

from . import repository
from . import events

from contextlib import asynccontextmanager


class Session(abc.ABC):
    matches: repository.Repository

    def event(self, event: events.Event) -> None:
        pass

    def collect_new_events(self) -> list[events.Event]:
        return []

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        try:
            yield
        except Exception as e:
            print(e)
            raise
