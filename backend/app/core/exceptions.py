import re

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()


class AppError(Exception):
    """Business error with a stable code. Message is safe to show to clients."""

    status_code = 400
    code = "BAD_REQUEST"
    message = "Bad request"

    def __init__(self, message: str | None = None, *, code: str | None = None, details: object = None):
        self.message = message or self.message
        self.code = code or self.code
        self.details = details  # client-safe structured info, e.g. which variants are out of stock
        super().__init__(self.message)


class NotFound(AppError):
    status_code, code, message = 404, "NOT_FOUND", "Resource not found"


class Conflict(AppError):
    status_code, code, message = 409, "CONFLICT", "Conflict"


class Unauthorized(AppError):
    status_code, code, message = 401, "UNAUTHORIZED", "Authentication required"


class Forbidden(AppError):
    status_code, code, message = 403, "FORBIDDEN", "You do not have permission to do this"


class RateLimited(AppError):
    status_code, code, message = 429, "RATE_LIMITED", "Too many requests, slow down"


class InvalidStateTransition(AppError):
    status_code, code, message = 409, "INVALID_STATE_TRANSITION", "Invalid state transition"


# Postgres constraint name -> (error code, message). Add an entry when adding a user-facing unique constraint.
CONSTRAINT_ERRORS = {
    "uq_product_variants_sku": ("SKU_TAKEN", "One or more SKUs are already in use"),
    "uq_products_slug": ("SLUG_TAKEN", "That slug is already in use"),
    "uq_categories_slug": ("SLUG_TAKEN", "That slug is already in use"),
    "uq_collections_slug": ("SLUG_TAKEN", "That slug is already in use"),
    "uq_attributes_code": ("SLUG_TAKEN", "An attribute with that code already exists"),
    "uq_users_email_active": ("EMAIL_TAKEN", "An account with this email already exists"),
    "uq_coupons_code": ("COUPON_CODE_TAKEN", "A coupon with this code already exists"),
    "uq_reviews_user_product": (
        "REVIEW_EXISTS",
        "You've already reviewed this product; edit your review instead",
    ),
}


def _error(status: int, code: str, message: str, details: object = None) -> JSONResponse:
    body: dict = {"success": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(map(str, e["loc"][1:])), "message": e["msg"]} for e in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "Invalid request", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        # The database is the final arbiter of uniqueness/references (races included);
        # translate its constraint names into stable, client-safe codes.
        match = re.search(r'constraint "([^"]+)"', str(exc.orig))
        name = match.group(1) if match else ""
        if name in CONSTRAINT_ERRORS:
            code, message = CONSTRAINT_ERRORS[name]
        elif "foreign key constraint" in str(exc.orig):
            code, message = "IN_USE", "This item is referenced elsewhere; deactivate it instead"
        else:
            log.warning("unmapped_integrity_error", constraint=name)
            code, message = "CONFLICT", "This conflicts with existing data"
        return _error(409, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "Something went wrong")
