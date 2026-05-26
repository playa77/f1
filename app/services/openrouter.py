"""OpenRouter API client for LLM calls."""

import json
from typing import Any

import httpx
from app.config import get_settings


class OpenRouterError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def chat_completion(
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, Any] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call OpenRouter chat completion API. Returns sanitized response."""
    settings = get_settings()

    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("sk-or-v1-your-"):
        raise OpenRouterError("OpenRouter API key is not configured", status_code=401)

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
        body["provider"] = {"require_parameters": True}

    timeout_val = httpx.Timeout(settings.model_task_timeout)

    try:
        async with httpx.AsyncClient(timeout=timeout_val) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        return _sanitize_response(content, data)
    except httpx.HTTPStatusError as e:
        raise OpenRouterError(
            f"OpenRouter HTTP error: {e.response.status_code}",
            status_code=e.response.status_code,
        )
    except httpx.TimeoutException:
        raise OpenRouterError("OpenRouter request timed out")
    except Exception as e:
        raise OpenRouterError(f"OpenRouter error: {str(e)}")


async def generate_embeddings(model: str, texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    settings = get_settings()

    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("sk-or-v1-your-"):
        raise OpenRouterError("OpenRouter API key is not configured", status_code=401)

    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    result_vectors: list[list[float]] = []

    for text in texts:
        body = {
            "model": model,
            "input": text,
        }

        timeout_val = httpx.Timeout(settings.model_task_timeout)

        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()

            embedding_data = data.get("data", [{}])
            if embedding_data:
                vector = embedding_data[0].get("embedding", [])
                result_vectors.append(vector)
            else:
                result_vectors.append([])
        except Exception as e:
            raise OpenRouterError(f"Embedding generation error: {str(e)}")

    return result_vectors


def validate_embedding_dimension(dimension: int) -> bool:
    """Check if embedding dimension meets minimum requirement."""
    settings = get_settings()
    return dimension >= settings.min_embedding_dimension


def _sanitize_response(content: str, raw_data: dict[str, Any]) -> dict[str, Any]:
    """Extract only sanitized metadata from OpenRouter response."""
    return {
        "content": content,
        "model_used": raw_data.get("model", ""),
        "id": raw_data.get("id", ""),
        "provider": raw_data.get("provider", ""),
        "usage": {
            "prompt_tokens": raw_data.get("usage", {}).get("prompt_tokens"),
            "completion_tokens": raw_data.get("usage", {}).get("completion_tokens"),
            "total_tokens": raw_data.get("usage", {}).get("total_tokens"),
        },
    }
