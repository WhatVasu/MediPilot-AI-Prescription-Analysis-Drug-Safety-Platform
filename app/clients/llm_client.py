"""
Single place that hands back a LangChain chat model instance.
Nodes should call get_chat_model() rather than importing a provider-specific
chat class directly — keeps provider-swapping to one file.
"""
import logging
from functools import lru_cache

from app import config

logger = logging.getLogger(__name__)


class _FallbackModel:
    """Used when no LLM provider could be initialized (missing/invalid API
    key, import failure, etc). Keeps the pipeline degrading gracefully
    instead of crashing: plain invoke() returns a harmless "UNKNOWN" content
    response, and with_structured_output() returns an object whose result
    won't match the expected schema — callers already treat "couldn't parse
    a structured result" as a normal, handled case (empty drug list / low
    confidence), never as a hard failure.
    """

    def invoke(self, _messages):
        return type("Response", (), {"content": "UNKNOWN"})()

    def with_structured_output(self, _schema):
        return self


@lru_cache(maxsize=1)
def get_chat_model():
    provider = (config.LLM_PROVIDER or "groq").strip().lower()
    if provider not in {"groq", "openai", "anthropic"}:
        logger.warning("Unsupported LLM_PROVIDER '%s'. Falling back to groq.", provider)
        provider = "groq"

    try:
        if provider == "groq":
            from langchain_groq import ChatGroq

            if not config.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is not set. Add it to your environment or .env file.")

            return ChatGroq(
                model=config.GROQ_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0,
            )

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            if not config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not set. Add it to your environment or .env file.")

            return ChatOpenAI(
                model=config.OPENAI_MODEL,
                api_key=config.OPENAI_API_KEY,
                temperature=0,
            )

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            if not config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your environment or .env file.")

            return ChatAnthropic(
                model=config.ANTHROPIC_MODEL,
                api_key=config.ANTHROPIC_API_KEY,
                temperature=0,
            )
    except Exception as exc:
        logger.error("LLM initialization failed: %s. Falling back to a safe stub model.", exc)

    return _FallbackModel()


def get_8b_chat():
    return ChatGroq(
                model="llama-3.1-8b-instant",
                api_key=config.GROQ_API_KEY2,
                temperature=0,
            )
    
