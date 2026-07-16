from unittest.mock import MagicMock

from fastapi.exceptions import RequestValidationError

from app.core.errors import unhandled_exception_handler, validation_exception_handler


async def test_unhandled_exception_handler_returns_generic_message():
    request = MagicMock()
    exc = ValueError("some internal detail that should not leak")

    response = await unhandled_exception_handler(request, exc)

    assert response.status_code == 500
    body = response.body.decode()
    assert '"message":"An unexpected error occurred."' in body
    assert '"code":"internal_error"' in body
    assert "internal detail" not in body


async def test_validation_exception_handler_returns_validation_error_shape():
    request = MagicMock()
    exc = RequestValidationError(errors=[])

    response = await validation_exception_handler(request, exc)

    assert response.status_code == 422
    body = response.body.decode()
    assert '"message":"Invalid request."' in body
    assert '"code":"validation_error"' in body
