from __future__ import annotations

import asyncio
import json
from typing import Any, Optional, Protocol

import httpx

from app.config import Settings, get_settings


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, schema: dict) -> Any: ...


class UnmarkedClient:
    async def complete(self, system: str, user: str, schema: dict) -> Any:
        return {"verdicts": [], "summary": None, "findings": []}


SCHEMA_NAME = "response"

MAX_RETRY_DELAY_SECONDS = 60.0


def _retry_delay(response: httpx.Response) -> Optional[float]:
    raw = response.headers.get("retry-after")
    if raw:
        try:
            delay = float(raw)
        except ValueError:
            return None
        return delay if 0 < delay <= MAX_RETRY_DELAY_SECONDS else None
    # No header: a per-minute window is the only limit worth waiting out, and
    # only when the day still has budget left.
    day_left = response.headers.get("x-ratelimit-remaining-tokens-day")
    if day_left is not None and day_left.isdigit() and int(day_left) <= 0:
        return None
    return 20.0


def _quota(response: httpx.Response) -> str:
    parts = [
        f"{key.rsplit('-', 1)[-1]}={value}"
        for key, value in sorted(response.headers.items())
        if key.lower().startswith("x-ratelimit-remaining")
    ]
    return ", ".join(parts) or "no quota headers"


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 2000,
        max_retries: int = 3,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self._transport = transport

    async def complete(self, system: str, user: str, schema: dict) -> Any:
        strict = {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "schema": schema, "strict": True},
        }
        try:
            return await self._post(system, user, strict)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 400:
                raise
        return await self._post(
            f"{system}\n\nОтвет верни строго по этой JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}",
            user,
            {"type": "json_object"},
        )

    async def _post(self, system: str, user: str, response_format: dict) -> Any:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": response_format,
            "max_tokens": self.max_output_tokens,
            "temperature": 0,
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self._transport
        ) as client:
            for attempt in range(self.max_retries + 1):
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                if response.status_code != 429:
                    break

                delay = _retry_delay(response)
                if delay is None or attempt == self.max_retries:
                    raise ValueError(
                        f"rate limited by {self.base_url}, waiting will not help: "
                        f"{_quota(response)} — {response.text[:200]}"
                    )
                await asyncio.sleep(delay)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise httpx.HTTPStatusError(
                    f"{error}\nresponse body: {response.text[:500]}",
                    request=error.request,
                    response=error.response,
                ) from error
            body = response.json()

        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(f"unexpected response shape from {self.base_url}") from error

        if choice.get("finish_reason") == "length":
            raise ValueError(
                f"model output hit max_tokens ({self.max_output_tokens}) and was cut off; "
                "raise LLM_MAX_OUTPUT_TOKENS"
            )
        return content


def build_llm_client(settings: Optional[Settings] = None) -> LLMClient:
    settings = settings or get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        return UnmarkedClient()
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        max_retries=settings.llm_max_retries,
    )
