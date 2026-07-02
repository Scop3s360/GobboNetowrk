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
        api_key: OpenAI secret key.  Defaults to OPENAI_API_KEY env var.
        model:   Model identifier.  Defaults to OPENAI_MODEL env var or
                 ``gpt-4o-mini``.
        timeout: Request timeout in seconds.  Defaults to 60.

    Raises:
        ConfigurationError: If the ``openai`` package is not installed, or if
                            the API key cannot be resolved.
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

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if resolved_key in ("sk-your-key-here", "your-actual-api-key-here"):
            resolved_key = ""
        if not resolved_key:
            raise ConfigurationError(
                "OpenAI API key is not set. "
                "Set the OPENAI_API_KEY environment variable."
            )

        self._model = model or os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
        self._timeout = timeout
        # The openai client is stored as _client; injected via env vars above.
        self._client = openai.OpenAI(api_key=resolved_key, timeout=timeout)
        log.info("OpenAIClient initialised: model=%s", self._model)

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
        log.debug("OpenAIClient: sending request to model=%s", self._model)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            text = response.choices[0].message.content or ""
            log.debug("OpenAIClient: received response  length=%d chars", len(text))
            return text
        except Exception as exc:
            log.error("OpenAIClient: request failed: %s", exc)
            raise AIClientError(f"OpenAI request failed: {exc}") from exc
