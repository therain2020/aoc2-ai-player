from agent.llm.base import LLMProvider, LLMError
from agent.llm.openai_compat import OpenAICompatProvider
from agent.llm.ollama import OllamaProvider


def create_provider(config: dict) -> LLMProvider:
    cfg = config.get("llm", {})
    provider = cfg.get("provider", "openai_compat")
    if provider == "openai_compat":
        oc = cfg.get("openai_compat", {})
        return OpenAICompatProvider(oc.get("base_url", "https://api.deepseek.com/v1"),
                                    oc.get("model", "deepseek-chat"),
                                    oc.get("api_key"),
                                    json_mode=bool(cfg.get("json_mode", False)),
                                    track_balance=bool(cfg.get("track_balance", False)),
                                    disable_thinking=bool(cfg.get("disable_thinking", True)))
    if provider == "ollama":
        ol = cfg.get("ollama", {})
        return OllamaProvider(ol.get("base_url", "http://localhost:11434"), ol.get("model", "llama3.1"))
    raise LLMError(f"unknown llm provider: {provider}")
