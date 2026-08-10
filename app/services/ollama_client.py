"""Minimal Ollama HTTP client used by local LLM benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class OllamaClientError(RuntimeError):
    """Base error raised by the Ollama client."""


class OllamaTransportError(OllamaClientError):
    """Raised when the Ollama HTTP request fails."""


class OllamaResponseError(OllamaClientError):
    """Raised when Ollama returns an invalid response."""


class OllamaHttpClient(Protocol):
    """Subset of the httpx client interface required by OllamaClient."""

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> Any:
        """Send one POST request."""


@dataclass(frozen=True)
class OllamaGenerateResponse:
    """Normalized response from Ollama /api/generate."""

    model: str
    response: str
    thinking: str
    done: bool
    done_reason: str | None
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int

    @property
    def total_duration_seconds(self) -> float:
        """Return total Ollama duration in seconds."""
        return self.total_duration_ns / 1_000_000_000

    @property
    def load_duration_seconds(self) -> float:
        """Return model load duration in seconds."""
        return self.load_duration_ns / 1_000_000_000

    @property
    def prompt_eval_duration_seconds(self) -> float:
        """Return prompt evaluation duration in seconds."""
        return self.prompt_eval_duration_ns / 1_000_000_000

    @property
    def eval_duration_seconds(self) -> float:
        """Return generation duration in seconds."""
        return self.eval_duration_ns / 1_000_000_000

    @property
    def prompt_tokens_per_second(self) -> float | None:
        """Return prompt evaluation throughput."""
        seconds = self.prompt_eval_duration_seconds
        if self.prompt_eval_count == 0 or seconds <= 0:
            return None
        return self.prompt_eval_count / seconds

    @property
    def generation_tokens_per_second(self) -> float | None:
        """Return generated-token throughput."""
        seconds = self.eval_duration_seconds
        if self.eval_count == 0 or seconds <= 0:
            return None
        return self.eval_count / seconds


class OllamaClient:
    """Call a local Ollama server through the generate API."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        http_client: OllamaHttpClient | None = None,
    ) -> None:
        cleaned_base_url = base_url.strip().rstrip("/")
        if not cleaned_base_url:
            raise ValueError("base_url must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._base_url = cleaned_base_url
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    @property
    def base_url(self) -> str:
        """Return configured Ollama base URL."""
        return self._base_url

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        think: bool,
        stream: bool = False,
        keep_alive: str | int | None = None,
        num_predict: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> OllamaGenerateResponse:
        """Generate one completion and normalize Ollama metrics."""
        cleaned_model = model.strip()
        cleaned_prompt = prompt.strip()

        if not cleaned_model:
            raise ValueError("model must not be blank")
        if not cleaned_prompt:
            raise ValueError("prompt must not be blank")
        if stream:
            raise ValueError(
                "stream=True is not supported by the benchmark client"
            )

        payload: dict[str, Any] = {
            "model": cleaned_model,
            "prompt": cleaned_prompt,
            "stream": False,
            "think": think,
        }
        if keep_alive is not None:
            payload["keep_alive"] = self._validate_keep_alive(
                keep_alive
            )

        options: dict[str, Any] = {}
        if num_predict is not None:
            if isinstance(num_predict, bool):
                raise TypeError("num_predict must be an integer")
            if num_predict < 1:
                raise ValueError("num_predict must be positive")
            options["num_predict"] = num_predict

        if temperature is not None:
            if isinstance(temperature, bool):
                raise TypeError("temperature must be numeric")
            if temperature < 0:
                raise ValueError("temperature must be nonnegative")
            options["temperature"] = temperature

        if seed is not None:
            if isinstance(seed, bool):
                raise TypeError("seed must be an integer")
            options["seed"] = seed

        if options:
            payload["options"] = options

        data = self._post_generate(payload)
        return self._parse_generate_response(data)

    def unload(self, *, model: str) -> None:
        """Unload one model immediately through keep_alive=0."""
        cleaned_model = model.strip()
        if not cleaned_model:
            raise ValueError("model must not be blank")

        data = self._post_generate(
            {
                "model": cleaned_model,
                "keep_alive": 0,
                "stream": False,
            }
        )

        done = data.get("done")
        if done is not True:
            raise OllamaResponseError(
                "Ollama unload response was not complete"
            )

    def _post_generate(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST one request to /api/generate and return JSON object."""
        try:
            if self._http_client is None:
                with httpx.Client() as client:
                    response = client.post(
                        f"{self._base_url}/api/generate",
                        json=payload,
                        timeout=self._timeout_seconds,
                    )
            else:
                response = self._http_client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                    timeout=self._timeout_seconds,
                )
        except httpx.HTTPError as error:
            raise OllamaTransportError(
                "failed to call Ollama generate API"
            ) from error

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise OllamaTransportError(
                "Ollama generate API returned HTTP error"
            ) from error

        try:
            data = response.json()
        except ValueError as error:
            raise OllamaResponseError(
                "Ollama generate API returned invalid JSON"
            ) from error

        if not isinstance(data, dict):
            raise OllamaResponseError(
                "Ollama generate API response must be an object"
            )
        return data

    @staticmethod
    def _validate_keep_alive(value: str | int) -> str | int:
        if isinstance(value, bool):
            raise TypeError("keep_alive must be a string or integer")
        if isinstance(value, int):
            return value
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "keep_alive must be a nonblank string or integer"
            )
        return value.strip()

    @staticmethod
    def _parse_generate_response(
        data: dict[str, Any],
    ) -> OllamaGenerateResponse:
        """Validate and normalize one non-streaming generate response."""
        model = OllamaClient._require_text(data, "model")
        response_text = OllamaClient._optional_text(
            data,
            "response",
            default="",
        )
        thinking = OllamaClient._optional_text(
            data,
            "thinking",
            default="",
        )
        done = OllamaClient._require_bool(data, "done")
        done_reason = OllamaClient._nullable_text(data, "done_reason")

        if not done:
            raise OllamaResponseError(
                "non-streaming Ollama response was not complete"
            )

        return OllamaGenerateResponse(
            model=model,
            response=response_text,
            thinking=thinking,
            done=done,
            done_reason=done_reason,
            total_duration_ns=OllamaClient._require_nonnegative_int(
                data,
                "total_duration",
            ),
            load_duration_ns=OllamaClient._require_nonnegative_int(
                data,
                "load_duration",
            ),
            prompt_eval_count=OllamaClient._require_nonnegative_int(
                data,
                "prompt_eval_count",
            ),
            prompt_eval_duration_ns=(
                OllamaClient._require_nonnegative_int(
                    data,
                    "prompt_eval_duration",
                )
            ),
            eval_count=OllamaClient._require_nonnegative_int(
                data,
                "eval_count",
            ),
            eval_duration_ns=OllamaClient._require_nonnegative_int(
                data,
                "eval_duration",
            ),
        )

    @staticmethod
    def _require_text(
        data: dict[str, Any],
        field_name: str,
    ) -> str:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise OllamaResponseError(
                f"{field_name} must be a nonblank string"
            )
        return value

    @staticmethod
    def _optional_text(
        data: dict[str, Any],
        field_name: str,
        *,
        default: str,
    ) -> str:
        value = data.get(field_name, default)
        if not isinstance(value, str):
            raise OllamaResponseError(
                f"{field_name} must be a string"
            )
        return value

    @staticmethod
    def _nullable_text(
        data: dict[str, Any],
        field_name: str,
    ) -> str | None:
        value = data.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise OllamaResponseError(
                f"{field_name} must be null or a nonblank string"
            )
        return value

    @staticmethod
    def _require_bool(
        data: dict[str, Any],
        field_name: str,
    ) -> bool:
        value = data.get(field_name)
        if not isinstance(value, bool):
            raise OllamaResponseError(
                f"{field_name} must be a boolean"
            )
        return value

    @staticmethod
    def _require_nonnegative_int(
        data: dict[str, Any],
        field_name: str,
    ) -> int:
        value = data.get(field_name)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise OllamaResponseError(
                f"{field_name} must be a nonnegative integer"
            )
        return value
