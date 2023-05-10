import os
from typing import Any

import sentry_sdk


def skip_health(ctx: Any) -> bool:
    if "asgi_scope" in ctx:
        asgi = ctx["asgi_scope"]
        path = asgi.get("path")
        if path is not None:
            if path.startswith("/health"):
                return False
    return True


def setup_tracing() -> None:
    sentry_dsn = os.environ.get("SENTRY_DSN")
    sentry_environment = os.environ.get("SENTRY_ENVIRONMENT")
    if sentry_dsn is not None and sentry_environment is not None:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=sentry_environment,
            profiles_sample_rate=1.0,
            traces_sampler=skip_health,
        )
