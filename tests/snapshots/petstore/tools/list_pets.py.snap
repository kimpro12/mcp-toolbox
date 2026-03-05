"""Implementation for tool `list_pets`."""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import TypeAdapter

from ..client import request_with_retry
from ..models import Pet


class AppContextProtocol(Protocol):
    """Protocol view of app context consumed by tool implementations."""

    client: httpx.AsyncClient
    max_retries: int
    backoff_seconds: float
    retry_unsafe_methods: bool


async def list_pets_impl(ctx: AppContextProtocol, limit: Any, offset: Any) -> Any:
    """List pets"""

    path = "/pets"

    request_kwargs: dict[str, object] = {}

    params: dict[str, object] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if params:
        request_kwargs["params"] = params

    try:
        response = await request_with_retry(
            ctx.client,
            "GET",
            path,
            max_retries=ctx.max_retries,
            backoff_seconds=ctx.backoff_seconds,
            request_kwargs=request_kwargs,
            allow_unsafe_retries=ctx.retry_unsafe_methods,
        )
        response.raise_for_status()
        if response.content:
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("Expected JSON response but received non-JSON payload") from exc

        else:
            payload = None
        return TypeAdapter(list[Pet]).validate_python(payload)

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"API error {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc
