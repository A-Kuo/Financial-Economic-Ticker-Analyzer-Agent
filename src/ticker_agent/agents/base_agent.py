"""Base class for all Ollama-backed agents."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import ollama

from ticker_agent.config import get

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base agent that wraps the Ollama API.

    Subclasses implement :meth:`build_prompt` and :meth:`parse_response`.
    The :meth:`run` method handles retry logic, timeout, and logging.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._model: str = get("llm.model", "llama3.2")
        self._base_url: str = get("llm.base_url", "http://localhost:11434")
        self._temperature: float = float(get("llm.temperature", 0.1))
        self._max_tokens: int = int(get("llm.max_tokens", 1024))
        self._timeout: int = int(get("llm.timeout", 60))
        self._system_context: str = get("llm.system_context", "You are a financial analyst.")

    @abstractmethod
    def build_prompt(self, **kwargs: Any) -> str:
        """Construct the user-facing prompt string."""

    @abstractmethod
    def parse_response(self, raw: str) -> Any:
        """Parse the raw LLM text response into a structured result."""

    def _call_llm(self, prompt: str, max_retries: int = 2) -> str:
        """Call Ollama with retry on transient errors. Returns raw text."""
        client = ollama.Client(host=self._base_url)
        for attempt in range(max_retries + 1):
            try:
                response = client.chat(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": self._system_context},
                        {"role": "user", "content": prompt},
                    ],
                    options={
                        "temperature": self._temperature,
                        "num_predict": self._max_tokens,
                    },
                )
                return response["message"]["content"].strip()
            except Exception as exc:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "[%s] LLM call failed (attempt %d/%d): %s — retrying in %ds",
                        self.name, attempt + 1, max_retries + 1, exc, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("[%s] LLM call failed after %d attempts: %s", self.name, max_retries + 1, exc)
                    raise

    def run(self, **kwargs: Any) -> Any:
        """Execute the full agent cycle: build prompt → call LLM → parse result."""
        prompt = self.build_prompt(**kwargs)
        logger.debug("[%s] Prompt (%d chars): %s…", self.name, len(prompt), prompt[:120])
        t0 = time.perf_counter()
        raw = self._call_llm(prompt)
        elapsed = time.perf_counter() - t0
        logger.debug("[%s] LLM response in %.2fs (%d chars)", self.name, elapsed, len(raw))
        return self.parse_response(raw)
