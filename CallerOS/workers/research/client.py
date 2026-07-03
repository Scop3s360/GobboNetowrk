"""
AI Client
=========
Thin abstraction over the OpenAI Responses API.

Architectural decisions:

    Protocol-based abstraction:
        ``AIClient`` is a ``typing.Protocol`` rather than an abstract base
        class.  Any object that has a ``complete(system, user) -> str`` method
        satisfies the protocol.  This means tests can use plain mock objects
        without inheriting from anything, which keeps test setup minimal.

    Single responsibility:
        The client does one thing: take a system prompt and a user message,
        call the API, and return the text response.  It knows nothing about
        research domains, parsing, or worker lifecycle.

    Environment variables for credentials:
        The API key and model name are read from environment variables at
        construction time.  They are NOT passed through the Settings dataclass
        because AI credentials are not application-configuration — they are
        secrets.  Keeping them out of Settings prevents them from being logged
        accidentally via a Settings.__repr__() call.

        Required env vars:
            OPENAI_API_KEY   — the OpenAI secret key
            OPENAI_MODEL     — the model to use (default: gpt-4o-mini)

    openai SDK dependency:
        The ``openai`` package is imported inside OpenAIClient.__init__() so
        that importing this module does not fail in environments where the
        SDK is not installed (e.g. test environments that mock the client).
        The ImportError is converted to a clear ConfigurationError.

    No streaming, no function calling, no tools:
        Stage 3 uses the simplest possible completion call.  Streaming and
        tool use belong to later stages.

    Timeout:
        A 60-second timeout is applied by default.  Callers can override it
        at construction time.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

from core.exceptions import ConfigurationError

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TIMEOUT_SECONDS = 60


@runtime_checkable
class AIClient(Protocol):
    """
    Protocol that any AI completion client must satisfy.

    Satisfying this protocol requires only one method: ``complete``.
    The OpenAI SDK client and any test double both qualify.
    """

    def complete(self, system_prompt: str, user_message: str) -> str:
        """
        Send a chat completion request and return the response text.

        Args:
            system_prompt: The system-role instructions.
            user_message:  The user-role query.

        Returns:
            The model's response as a plain string.

        Raises:
            AIClientError: If the request fails for any reason.
        """
        ...


class AIClientError(Exception):
    """Raised when the AI client encounters an error."""


class OpenAIClient:
    """
    Production AI client backed by the OpenAI Responses API (chat completions).

    Args:
        api_key: OpenAI secret key.  Defaults to OPENAI_API_KEY from settings.
        model:   Model identifier.  Defaults to OPENAI_MODEL from settings or
                 ``gpt-4o-mini``.
        timeout: Request timeout in seconds.  Defaults to 60.

    Raises:
        ConfigurationError: If the ``openai`` package is not installed.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise ConfigurationError(
                "The 'openai' package is required for OpenAIClient. "
                "Install it with: pip install openai"
            ) from exc

        self._api_key_override = api_key
        self._model_override = model
        self._timeout = timeout
        self._cached_client = None
        self._cached_key = None

    def complete(self, system_prompt: str, user_message: str) -> str:
        """
        Call the OpenAI chat completions endpoint.

        Args:
            system_prompt: The system-role message.
            user_message:  The user-role message.

        Returns:
            The model's reply text.

        Raises:
            AIClientError: On any API error (network, auth, rate-limit, etc.).
        """
        import openai
        from config.settings import get_settings

        settings = get_settings()
        api_key = self._api_key_override or settings.openai_api_key
        model = self._model_override or settings.openai_model or _DEFAULT_MODEL

        log.info("OpenAIClient: Creating request for model=%s", model)

        if not api_key:
            log.warning("OpenAIClient: API key is missing")
            raise AIClientError("OpenAI API key is missing. Please set it in the Settings screen.")

        if self._cached_client is None or self._cached_key != api_key:
            self._cached_client = openai.OpenAI(api_key=api_key, timeout=self._timeout)
            self._cached_key = api_key

        try:
            log.info("OpenAIClient: Sending HTTP request to OpenAI API...")
            response = self._cached_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            log.info("OpenAIClient: HTTP response received successfully")
            content = response.choices[0].message.content or ""
            log.info("OpenAIClient: Parsed response content length=%d chars", len(content))
            return content
        except Exception as exc:
            log.error("OpenAIClient: request failed: %s", exc)
            raise AIClientError(str(exc))
