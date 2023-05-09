import os
import asyncio
import sentry_sdk
import logging

from gameplay_computer.web import tasks


async def async_main() -> None:
    sentry_dsn = os.environ.get("SENTRY_DSN")
    sentry_environment = os.environ.get("SENTRY_ENVIRONMENT")
    if sentry_dsn is not None and sentry_environment is not None:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=sentry_environment,
            profiles_sample_rate=1.0,
            traces_sample_rate=1.0,
        )

    # Start the worker
    await tasks.database.connect()
    async with tasks.app.open_async():
        await tasks.app.run_worker_async(concurrency=30)
    await tasks.database.disconnect()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting Worker")
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
