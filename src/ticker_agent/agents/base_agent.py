"""Base Ollama agent — wraps the ollama Python library with a tool-use agentic loop."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Thin wrapper around the Ollama client that supports:
      - Simple one-shot prompts
      - Agentic chat loops with tool calling (llama3.2+ natively supports this)
    Gracefully degrades if Ollama is not running or the package is missing.
    """

    def __init__(self, model: str = "llama3.2", host: str | None = None):
        self.model = model
        self._host = host
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        try:
            import ollama  # noqa: F401 — confirm importable
            if self._host:
                import ollama as _ollama
                self._client = _ollama.Client(host=self._host)
            else:
                import ollama as _ollama
                self._client = _ollama.Client()
            self._available = True
        except ImportError:
            logger.error("ollama package not installed — run: pip install ollama")
        except Exception as exc:
            logger.warning("Ollama not reachable at %s: %s", self._host or "localhost:11434", exc)

    @property
    def available(self) -> bool:
        return self._available

    # ── Core chat loop ─────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_handlers: dict[str, Callable[..., Any]] | None = None,
        max_rounds: int = 6,
    ) -> str:
        """
        Run the Ollama chat loop, executing any tool calls the model makes.

        Args:
            messages:      Conversation history in OpenAI-style format.
            tools:         Tool definitions (JSON schema) exposed to the model.
            tool_handlers: {tool_name: callable} executed when the model calls a tool.
            max_rounds:    Cap on tool-call/response cycles to prevent infinite loops.

        Returns:
            The model's final text response, or an error string on failure.
        """
        if not self._available:
            return "[Ollama unavailable — start Ollama and ensure the model is pulled]"

        tool_handlers = tool_handlers or {}
        current_messages = list(messages)

        for round_num in range(max_rounds):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": current_messages,
                }
                if tools:
                    kwargs["tools"] = tools

                response = self._client.chat(**kwargs)
                msg = response.message

                # No tool calls → model is done, return text
                if not msg.tool_calls:
                    return msg.content or ""

                # Append assistant message (with tool calls) to history
                tool_calls_serialised = [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or {},
                        }
                    }
                    for tc in msg.tool_calls
                ]
                current_messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": tool_calls_serialised,
                    }
                )

                # Execute each tool call and append results
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = tc.function.arguments or {}
                    handler = tool_handlers.get(fn_name)
                    if handler:
                        try:
                            result = handler(**fn_args)
                        except Exception as exc:
                            result = f"Error in tool {fn_name}: {exc}"
                    else:
                        result = f"Unknown tool: {fn_name}"

                    current_messages.append(
                        {
                            "role": "tool",
                            "content": (
                                json.dumps(result)
                                if not isinstance(result, str)
                                else result
                            ),
                        }
                    )

            except Exception as exc:
                logger.error("Ollama chat error (round %d): %s", round_num, exc)
                return f"[Agent error: {exc}]"

        return "[Max tool-call rounds reached without final response]"

    def simple_prompt(self, system: str, user: str) -> str:
        """One-shot prompt — no tool use."""
        return self.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )

    def check_connectivity(self) -> bool:
        """Ping Ollama with a minimal request. Returns True if responsive."""
        if not self._available:
            return False
        try:
            resp = self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "Say ONLINE"}],
            )
            return bool(resp.message.content)
        except Exception:
            return False
