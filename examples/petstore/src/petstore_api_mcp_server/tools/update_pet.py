"""Implementation for tool `update_pet`."""

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


async def update_pet_impl(ctx: AppContextProtocol, pet_id: Any, name: Any, tag: Any, status: Any) -> Any:
    """Update an existing pet"""

    path = "/pets/{petId}"
    path = path.replace("{petId}", str(pet_id))

    request_kwargs: dict[str, object] = {}

    json_body: dict[str, object] = {}
    json_body["name"] = name
    if tag is not None:
        json_body["tag"] = tag
    if status is not None:
        json_body["status"] = status
    if json_body:
        request_kwargs["json"] = json_body

    try:
        response = await request_with_retry(
            ctx.client,
            "PUT",
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
        return TypeAdapter(Pet).validate_python(payload)

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"API error {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc
