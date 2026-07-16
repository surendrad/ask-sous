"""Domain exceptions for the agent layer. Vertex AI/SDK failures are always
translated into one of these before crossing out of app/agent/ — callers
(the /chat endpoint) never see raw google.genai exceptions.
"""


class AgentUnavailableError(Exception):
    """The underlying model call failed (rate limit, outage, auth failure).

    Never retried automatically — see docs/decisions/007 and CLAUDE.md's
    "never retried indefinitely" rule.
    """


class AgentIncompleteError(Exception):
    """The agent ran but could not reach a final answer within the
    tool-call round cap."""
