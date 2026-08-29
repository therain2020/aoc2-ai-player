from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    """Abstract decision brain. Implementations: OpenAI-compatible, Ollama."""

    # token accounting (filled by implementations after each chat call)
    last_usage: dict = {}
    total: dict = {"prompt_tokens": 0, "completion_tokens": 0}
    track_balance: bool = False
    cached_hits: int = 0

    @abstractmethod
    def chat(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 700) -> str:
        """Return assistant text (JSON body expected by agent/actions.py)."""

    def fetch_balance(self) -> float | None:
        return None
