from typing import Any


def success(data: Any) -> dict:
    """The success-shape response envelope: `{"data": ..., "error": null}`."""
    return {"data": data, "error": None}


def error_response(message: str, code: str) -> dict:
    """The error-shape response envelope: `{"data": null, "error": {...}}`."""
    return {"data": None, "error": {"message": message, "code": code}}
