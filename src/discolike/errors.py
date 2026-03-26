"""Typed error hierarchy for DiscoLike CLI."""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import click

F = TypeVar("F", bound=Callable[..., Any])


class DiscoLikeError(Exception):
    """Base error for all DiscoLike CLI errors."""
    exit_code: int = 1
    suggestion: str = ""

    def __init__(self, message: str, suggestion: str = "") -> None:
        super().__init__(message)
        self.suggestion = suggestion or self.__class__.suggestion


class APIError(DiscoLikeError):
    """Generic API error (exit code 1)."""
    exit_code = 1
    suggestion = "Check the DiscoLike API status or try again later."


class AuthError(DiscoLikeError):
    """Authentication error — missing or invalid API key (exit code 2)."""
    exit_code = 2
    suggestion = (
        "Set your API key: export DISCOLIKE_API_KEY='dk_...' "
        "or run: discolike config set api_key <key>"
    )


class RateLimitError(DiscoLikeError):
    """Rate limited by the API (exit code 3)."""
    exit_code = 3
    retry_after: float | None = None

    def __init__(
        self, message: str, retry_after: float | None = None, suggestion: str = ""
    ) -> None:
        super().__init__(message, suggestion or "Wait and retry, or reduce request frequency.")
        self.retry_after = retry_after


class PlanGateError(DiscoLikeError):
    """Feature requires a higher plan (exit code 4)."""
    exit_code = 4

    def __init__(self, command: str, required_plan: str, current_plan: str) -> None:
        message = (
            f"The '{command}' command requires {required_plan.title()} plan or above. "
            f"Current plan: {current_plan.title()}."
        )
        super().__init__(message, suggestion="Upgrade your DiscoLike plan to access this feature.")


class BudgetExceededError(DiscoLikeError):
    """Monthly budget exhausted (exit code 5)."""
    exit_code = 5
    suggestion = "Wait for the next billing cycle or increase your budget limit."


class ValidationError(DiscoLikeError):
    """Invalid input or validation error (exit code 6)."""
    exit_code = 6


def handle_errors(f: F) -> F:
    """Click decorator that catches DiscoLikeError and exits cleanly."""
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except DiscoLikeError as e:
            # JSON mode: structured error output to stdout
            ctx = click.get_current_context(silent=True)
            use_json = getattr(ctx.obj, "json_output", False) if ctx and ctx.obj else False
            if use_json:
                import json
                error_data = {
                    "error": str(e),
                    "code": type(e).__name__.upper(),
                    "suggestion": e.suggestion,
                }
                click.echo(json.dumps(error_data, indent=2))
            else:
                click.secho(f"Error: {e}", fg="red", err=True)
                if e.suggestion:
                    click.secho(f"  Hint: {e.suggestion}", fg="yellow", err=True)
            sys.exit(e.exit_code)
    return wrapper  # type: ignore[return-value]
