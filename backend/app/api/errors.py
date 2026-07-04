"""RFC 7807 Problem Details error handling.

All error responses across the API use ``application/problem+json`` with the
fields ``type``, ``title``, ``status``, ``detail``, ``instance``. Raise
``ProblemException`` from handlers/dependencies; the registered handlers below
also convert FastAPI's built-in ``HTTPException`` and request-validation errors
into the same shape so no endpoint ever returns an ad-hoc error body.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

PROBLEM_JSON = "application/problem+json"


class ProblemException(Exception):
    """An error that renders as an RFC 7807 problem+json response."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        title: str | None = None,
        type_: str = "about:blank",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.title = title or HTTPStatus(status_code).phrase
        self.type = type_
        self.headers = headers
        super().__init__(detail)


def _problem_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str | None,
    type_: str = "about:blank",
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "type": type_,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type=PROBLEM_JSON,
        headers=headers,
    )


async def _handle_problem(request: Request, exc: ProblemException) -> JSONResponse:
    return _problem_response(
        request,
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        type_=exc.type,
        headers=exc.headers,
    )


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _problem_response(
        request,
        status_code=exc.status_code,
        title=HTTPStatus(exc.status_code).phrase,
        detail=str(exc.detail) if exc.detail is not None else None,
        headers=getattr(exc, "headers", None),
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Compact, human-readable summary of the first-level field errors.
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    detail = "; ".join(parts) or "Request validation failed."
    return _problem_response(
        request,
        status_code=422,  # literal: the starlette 422 constant is deprecated/renamed
        title="Unprocessable Entity",
        detail=detail,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals to the client; the exception still propagates to logs.
    return _problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemException, _handle_problem)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected)
