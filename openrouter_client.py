from __future__ import annotations
import os, requests
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
load_dotenv()

class OpenRouterClient:
    """
    Minimal OpenRouter chat client.
    Docs: https://openrouter.ai/docs/api-reference/chat-completion
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        referer: Optional[str] = None,
        title: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY")

        # define API URL here 
        self.api_url = api_url or os.getenv("OPENROUTER_URL")

        # If you're unsure about model access, you can use "openrouter/auto"
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-5-chat:online")

        # Optional attribution headers recommended by OpenRouter
        self.referer = referer or os.getenv("APP_REFERER")
        self.title = title or os.getenv("APP_TITLE")
        self.timeout = timeout
        
         # DEBUG LOG (safe): prints once at startup
        masked = (self.api_key[:6] + "..." + self.api_key[-4:]) if self.api_key and len(self.api_key) > 10 else str(bool(self.api_key))
        print(
            "[OpenRouterClient] ENV OK:\n"
            f"  API_KEY : {masked}\n"
            f"  MODEL   : {self.model}\n"
            f"  URL     : {self.api_url}\n"
            f"  REFERER : {self.referer}\n"
            f"  TITLE   : {self.title}"
        )

    def _headers(self) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if stream:
            payload["stream"] = True
        if extra:
            payload.update(extra)

        # use self.api_url instead of undefined OPENROUTER_URL
        resp = requests.post(self.api_url, json=payload, headers=self._headers(), timeout=self.timeout)

        # Optional but helpful: show upstream errors clearly
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]
