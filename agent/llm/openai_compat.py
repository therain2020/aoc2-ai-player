import json
import os

import httpx

from agent.llm.base import LLMProvider, LLMError


class OpenAICompatProvider(LLMProvider):
    """DeepSeek / OpenAI / any /v1/chat/completions endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str = None, json_mode: bool = False,
                 track_balance: bool = False, disable_thinking: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.json_mode = json_mode
        self.track_balance = track_balance
        self.disable_thinking = disable_thinking
        self.balance = None
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.total = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def fetch_balance(self):
        """Query DeepSeek /user/balance; returns CNY total or None."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            r = httpx.get(f"{self.base_url}/user/balance", headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            infos = data.get("balance_infos") or []
            for info in infos:
                if info.get("currency") == "CNY":
                    self.balance = float(info.get("total_balance", 0))
                    return self.balance
            return None
        except Exception:
            return None

    def chat(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 700) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        if getattr(self, "disable_thinking", False):
            body["thinking"] = {"type": "disabled"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=120)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage") or {}
            details = usage.get("prompt_tokens_details") or {}
            self.last_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "cache_hit_tokens": usage.get("prompt_cache_hit_tokens",
                                              details.get("cached_tokens", 0)),
            }
            self.total["prompt_tokens"] += self.last_usage["prompt_tokens"]
            self.total["completion_tokens"] += self.last_usage["completion_tokens"]
            self.total["cache_hit_tokens"] = self.total.get("cache_hit_tokens", 0) + self.last_usage["cache_hit_tokens"]
            self.total["calls"] += 1
            content = data["choices"][0]["message"].get("content") or ""
            if not content and data["choices"][0]["message"].get("reasoning_content"):
                content = data["choices"][0]["message"].get("reasoning_content", "")
            return content
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            raise LLMError(f"openai_compat: {e}") from e
