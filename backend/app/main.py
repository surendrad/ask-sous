import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.api import campaigns, chat, dashboard, health, restaurants
from app.core.config import get_settings
from app.core.errors import (
    agent_incomplete_exception_handler,
    agent_unavailable_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.seed.trickle import run_trickle_loop

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # No manual on-demand trigger — ENABLE_TRICKLE is the only control,
    # per implementation-plan.md 7.1's agreed testability approach. See
    # docs/decisions/012-live-trickle-generator.md.
    trickle_task: asyncio.Task | None = None
    if get_settings().enable_trickle:
        trickle_task = asyncio.create_task(run_trickle_loop())
    try:
        yield
    finally:
        if trickle_task is not None:
            trickle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await trickle_task


app = FastAPI(title="Ask Sous", lifespan=lifespan)

# Local-dev-only origins — the Vite dev server runs on a different port than
# the API, so the browser enforces CORS between them. No user accounts exist
# (master-plan.md §2), so this isn't gating access to anything sensitive.
# Vite auto-increments past 5173 if that port is already taken (e.g. by
# another project's dev server on the same machine), so a small fixed range
# is allowed rather than a single hardcoded port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{port}" for port in range(5173, 5176)],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(campaigns.router)
app.include_router(restaurants.router)
app.include_router(dashboard.router)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AgentUnavailableError, agent_unavailable_exception_handler)
app.add_exception_handler(AgentIncompleteError, agent_incomplete_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
