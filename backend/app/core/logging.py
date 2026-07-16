import structlog


def configure_logging() -> None:
    """Configure structlog for JSON-formatted structured logging.

    Called once at app startup. This is what makes the audit-trail story
    (every agent turn logs its question, tool calls, and answer) actually
    machine-readable from Phase 3 onward.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )
