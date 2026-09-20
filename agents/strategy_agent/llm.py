"""Chat model selection for the Strategy stage.

Set STRATEGY_LLM in .env as "openai:<model>" to change the model (needs OPENAI_API_KEY):

    STRATEGY_LLM=openai:gpt-5.6-luna      (default; the model the Qualification Agent already uses)

Built the same way as the Qualification Agent's model (Responses API, no temperature or reasoning
overrides), the configuration known to work with this project's OpenAI key.
"""

import os

DEFAULT_SPEC = "openai:gpt-5.6-luna"


def parse_spec(spec: str | None = None) -> tuple[str, str]:
    provider, _, model = (spec or os.getenv("STRATEGY_LLM") or DEFAULT_SPEC).partition(":")
    provider, model = provider.strip().lower(), model.strip()
    if not model:
        raise ValueError(f"STRATEGY_LLM must look like 'openai:gpt-5.6-luna', got '{provider}'.")
    return provider, model


def build_llm(spec: str | None = None):
    provider, model = parse_spec(spec)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, use_responses_api=True)
    raise ValueError(f"Unsupported STRATEGY_LLM provider '{provider}'. Only 'openai' is supported.")
