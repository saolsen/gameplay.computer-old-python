import sentry_sdk
import os
import procrastinate
import databases
import httpx
from . import service
from gameplay_computer.gameplay import Agent

database_url = os.environ.get("DATABASE_URL")
if database_url is None:
    database_url = os.environ.get("TEST_DATABASE_URL")
assert database_url is not None
database = databases.Database(database_url)

app = procrastinate.App(connector=procrastinate.AiopgConnector(dsn=database_url))


@app.task(queue="test")  # type: ignore
async def test_task() -> None:
    print("Hello world")


@app.task(queue="run_ai_turns")  # type: ignore
async def run_ai_turns(traceparent: str, match_id: int) -> None:
    tx = sentry_sdk.tracing.Transaction.continue_from_headers(
        {"sentry-trace": traceparent}, op="task", name="run_ai_turns"
    )
    with sentry_sdk.start_transaction(tx):
        async with httpx.AsyncClient() as client:
            match = await service.get_match(database, match_id)
            while True:
                if (
                    match is not None
                    and match.state.over is False
                    and match.state.next_player is not None
                    and isinstance(match.players[match.state.next_player], Agent)
                ):
                    match = await service.take_ai_turn(database, client, match)
                else:
                    break
