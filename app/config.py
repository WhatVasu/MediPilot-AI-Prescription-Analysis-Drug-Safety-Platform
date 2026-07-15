"""
Central config. Everything that's an env var or a tunable threshold lives here —
nodes and clients should import from this module rather than reading os.environ
directly, so there's exactly one place to look when something needs tuning.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM / Vision provider ---
# "groq", "anthropic", or "openai" — llm_client.py branches on this
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- OCR ---
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

# --- Tavily (web search grounding for drug-name resolution) ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# --- RxNorm (public API, no key required) ---
RXNORM_BASE_URL = os.getenv("RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
RXNORM_MAX_CANDIDATES = int(os.getenv("RXNORM_MAX_CANDIDATES", "5"))

# --- Thresholds ---
# Below this, an OCR'd item is flagged for the user to double check (never hidden).
OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.6"))
# Below this RxNorm match score, the drug name is flagged as unresolved.
MATCH_CONFIDENCE_THRESHOLD = float(os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.7"))
