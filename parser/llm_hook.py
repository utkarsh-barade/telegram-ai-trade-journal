"""
Stub interface for an optional LLM fallback parser.

The rule-based parser in trade_parser.py handles all common formats.
When the rule-based result has missing required fields, the system may
call this hook as a last resort.

To plug in a real LLM (e.g. Ollama + Mistral, or Google Gemini free tier):
  1. Implement the `try_llm_parse` function below.
  2. Return a ParseResult dict with the fields the LLM was able to extract.
  3. The caller will merge the LLM result with the rule-based partial result.

Important:
  - This module MUST NOT be required for the common parsing path.
  - If unavailable or erroring, return None — never raise.
  - Never call a paid API without the user's explicit configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from parser.trade_parser import ParseResult


def try_llm_parse(raw_text: str, partial_result: "ParseResult") -> Optional[dict]:
    """
    Attempt to extract missing fields using an optional LLM.

    Parameters
    ----------
    raw_text : str
        The original, unmodified Telegram message text.
    partial_result : ParseResult
        The result from the rule-based parser, which may have missing fields.

    Returns
    -------
    dict or None
        A dict with any additional fields the LLM could extract, keyed by
        ParseResult field names.  Returns None if LLM is unavailable or fails.

    Example (Ollama/Mistral implementation — not active):
    -------------------------------------------------------
    import requests, json

    prompt = f\"\"\"
    Extract trade details from this message: \"{raw_text}\"
    Already extracted: {partial_result}
    Missing fields: {partial_result.missing_fields}
    Return ONLY a JSON object with the missing fields filled in.
    Fields: stock, strike, option_type (CE or PE), expiry, direction (BUY or SELL),
            entry_price, stop_loss, target.
    \"\"\"
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=10,
        )
        data = resp.json()
        return json.loads(data["response"])
    except Exception:
        return None
    """
    # Stub — LLM not configured. Return None to fall through to clarification flow.
    return None


def is_llm_available() -> bool:
    """Return True if an LLM backend is configured and reachable."""
    return False
