import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("policydesk")


class AppError(Exception):
    """Base application error. Knows no HTTP and no SQL."""

    code: str = "APP_ERROR"
    status_code: int = 400

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFound(AppError):
    code = "NOT_FOUND"
    status_code = 404


class Conflict(AppError):
    code = "CONFLICT"
    status_code = 409


class VersionConflict(AppError):
    code = "VERSION_CONFLICT"
    status_code = 409


class Forbidden(AppError):
    code = "FORBIDDEN"
    status_code = 403


class DomainValidation(AppError):
    code = "DOMAIN_VALIDATION"
    status_code = 422


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
        )
