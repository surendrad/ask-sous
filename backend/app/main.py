from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.api import chat, health
from app.core.errors import (
    agent_incomplete_exception_handler,
    agent_unavailable_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Ask Sous")

# Local-dev-only origins — the Vite dev server runs on a different port than
# the API, so the browser enforces CORS between them. No user accounts exist
# (master-plan.md §2), so this isn't gating access to anything sensitive.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(AgentUnavailableError, agent_unavailable_exception_handler)
app.add_exception_handler(AgentIncompleteError, agent_incomplete_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
