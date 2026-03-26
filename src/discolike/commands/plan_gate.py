"""Plan gate decorator for commands requiring higher plans."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import click

from discolike.constants import PLAN_GATED_FEATURES, PLAN_LEVELS
from discolike.errors import PlanGateError

F = TypeVar("F", bound=Callable[..., Any])


def require_plan(command_name: str) -> Callable[[F], F]:
    """Decorator: check cached plan level before executing command.

    Must be placed BELOW @handle_errors and ABOVE @click.pass_context
    in the decorator stack so errors are caught properly.
    """
    required = PLAN_GATED_FEATURES.get(command_name)
    if required is None:
        raise ValueError(f"No plan gate defined for '{command_name}'")

    def decorator(f: F) -> F:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get ctx from Click's context stack
            ctx = click.get_current_context()
            from discolike.cli import _get_context

            cli_ctx = _get_context(ctx)
            current_plan = cli_ctx.cost_tracker.plan

            required_level = PLAN_LEVELS.index(required)
            current_level = (
                PLAN_LEVELS.index(current_plan) if current_plan in PLAN_LEVELS else 0
            )

            if current_level < required_level:
                raise PlanGateError(command_name, required, current_plan)

            return f(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
