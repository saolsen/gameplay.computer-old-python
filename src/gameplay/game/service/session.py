import abc

from ..adapters import repository
from ..events import Event


# this is maybe broader, it might be the whole of postgres
# it's the UOW thing in the book.
class Session(abc.ABC):
    games: repository.Repository

    def transaction(self):
        pass

    def event(self, event: messagebus.Event):
        pass
