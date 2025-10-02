from __future__ import annotations
import os, requests
from typing import List, Optional, Dict, Any

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class OpenRouterClient:
    """
    Minimal OpenRouter chat client.
    Docs: https://openrouter.ai/docs/api-reference/chat-completion
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        referer: Optional[str] = None,
        title: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-5-chat:online")
        self.referer = referer or os.getenv("APP_REFERER")
        self.title = title or os.getenv("APP_TITLE")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Optional attribution headers:
        if self.referer:
            h["HTTP-Referer"] = self.referer
        if self.title:
            h["X-Title"] = self.title
        return h

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        stream: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Sends a chat completion request and returns the assistant content.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if stream:
            payload["stream"] = True
        if extra:
            payload.update(extra)

        resp = requests.post(
            OPENROUTER_URL, json=payload, headers=self._headers(), timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        # Non-streaming path: return first choice content
        return data["choices"][0]["message"]["content"]
