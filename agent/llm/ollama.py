import json

import httpx

from agent.llm.base import LLMProvider, LLMError


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.total = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    def chat(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 700) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=180)
            r.raise_for_status()
            data = r.json()
            self.last_usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            }
            self.total["prompt_tokens"] += self.last_usage["prompt_tokens"]
            self.total["completion_tokens"] += self.last_usage["completion_tokens"]
            self.total["calls"] += 1
            return data["message"]["content"]
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            raise LLMError(f"ollama: {e}") from e
