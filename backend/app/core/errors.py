import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.responses import error_response

logger = structlog.get_logger()


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Logs the full exception server-side; returns only a generic message.

    Internal details (exception message, traceback, file paths, query
    fragments) must never be echoed back in the response body.
    """
    logger.error("unhandled_exception", exc_info=exc, path=str(getattr(request, "url", "")))
    return JSONResponse(
        status_code=500,
        content=error_response("An unexpected error occurred.", "internal_error"),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.error("validation_error", errors=exc.errors(), path=str(getattr(request, "url", "")))
    return JSONResponse(
        status_code=422,
        content=error_response("Invalid request.", "validation_error"),
    )


def _make_domain_exception_handler(*, status_code: int, log_event: str, message: str, code: str):
    """Builds a handler for a domain exception whose response is always the
    same fixed shape — log full detail server-side, return only a generic
    envelope. Adding a new domain exception this way is a one-line call
    instead of a new near-identical function; extend this factory (not a
    copy-pasted `async def`) for the next one."""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(log_event, exc_info=exc, path=str(getattr(request, "url", "")))
        return JSONResponse(status_code=status_code, content=error_response(message, code))

    return handler


agent_unavailable_exception_handler = _make_domain_exception_handler(
    status_code=503,
    log_event="agent_unavailable",
    message="The agent is temporarily unavailable. Please try again.",
    code="agent_unavailable",
)

agent_incomplete_exception_handler = _make_domain_exception_handler(
    status_code=502,
    log_event="agent_incomplete",
    message="The agent couldn't complete this request. Try rephrasing your question.",
    code="agent_incomplete",
)
