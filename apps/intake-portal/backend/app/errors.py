"""User-facing API errors with stable codes."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str = "Request") -> ApiError:
    # Same response for "does not exist" and "not yours" so ids cannot be probed.
    return ApiError(404, "not_found", f"{what} not found.")
