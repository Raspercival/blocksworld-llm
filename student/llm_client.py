"""
Simple LLM Client — Teacher-Provided

A minimal OpenAI-compatible LLM client for students to use.
Supports OpenAI, Anthropic, and any OpenAI-compatible endpoint (vLLM, Ollama, etc.).

Usage:
    client = LLMClient(provider="openai", model="gpt-4o", api_key="...")
    response = client.chat("Hello, world!")
"""

import os
from typing import Optional


class LLMClient:
    """Minimal LLM client wrapper. Students should not need to modify this."""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
    ):
        """
        Parameters
        ----------
        provider : str
            "openai", "anthropic", or "openai-compatible".
        model : str, optional
            Model name. Defaults: openai→"gpt-4o", anthropic→"claude-sonnet-4-6".
        api_key : str, optional
            API key. If None, reads from environment:
            - OPENAI_API_KEY for openai / openai-compatible
            - ANTHROPIC_API_KEY for anthropic
        base_url : str, optional
            Base URL for openai-compatible providers.
        temperature : float
            Sampling temperature (default 0.0 for deterministic output).
        """
        self.provider = provider.lower()
        self.temperature = temperature

        # Resolve model
        default_models = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-6",
            "openai-compatible": "gpt-4o",
        }
        self.model = model or default_models.get(self.provider, "gpt-4o")

        # Resolve API key
        if api_key is None:
            env_keys = {
                "openai": "OPENAI_API_KEY",
                "openai-compatible": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }
            key_env = env_keys.get(self.provider, "OPENAI_API_KEY")
            api_key = os.environ.get(key_env, "")
            if not api_key:
                raise ValueError(
                    f"No API key provided and {key_env} not set in environment. "
                    f"Set it via: export {key_env}=your-key"
                )
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, prompt: str) -> str:
        """
        Send a prompt to the LLM and return the text response.

        Parameters
        ----------
        prompt : str
            The prompt string.

        Returns
        -------
        str
            The model's text response.
        """
        if self.provider == "anthropic":
            return self._chat_anthropic(prompt)
        else:
            # openai / openai-compatible
            return self._chat_openai(prompt)

    def _chat_openai(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""

    def _chat_anthropic(self, prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic returns a list of content blocks
        text_blocks = [
            b.text for b in response.content if b.type == "text"
        ]
        return "".join(text_blocks)
