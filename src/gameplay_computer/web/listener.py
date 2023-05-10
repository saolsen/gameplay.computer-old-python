import asyncio
from asyncio import Queue
from collections import defaultdict
from typing import AsyncIterator, Callable

import asyncpg_listen


class Listener:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.queues: dict[int, dict[int, Queue[str]]] = defaultdict(dict)
        self.running = False

    def _start(self) -> None:
        if not self.running:
            # @note: listener makes its own connections to the database
            # and doesn't use the pool that route handlers use.
            self.listener = asyncpg_listen.NotificationListener(
                asyncpg_listen.connect_func(self.database_url)
            )
            self.listener_task = asyncio.create_task(
                self.listener.run(
                    {"test": self.handle_test},
                    policy=asyncpg_listen.ListenPolicy.ALL,
                )
            )
            self.running = True

    async def handle_test(
        self, notification: asyncpg_listen.NotificationOrTimeout
    ) -> None:
        if isinstance(notification, asyncpg_listen.Notification):
            print(f"got notification: {notification.channel} {notification.payload}")
            if notification.payload is not None:
                match_id = int(notification.payload)
                for _, queue in self.queues[match_id].items():
                    queue.put_nowait(notification.payload)
        elif isinstance(notification, asyncpg_listen.Timeout):
            pass
            # print(f"got timeout: {notification.channel}")

    def listen(self, match_id: int) -> Callable[[], AsyncIterator[str]]:
        self._start()
        queue: Queue[str] = Queue()
        self.queues[match_id][id(queue)] = queue

        async def listener() -> AsyncIterator[str]:
            try:
                while True:
                    item = await queue.get()
                    yield item
            except asyncio.CancelledError as e:
                if id(queue) in self.queues[match_id]:
                    del self.queues[match_id][id(queue)]
                raise e

        return listener
