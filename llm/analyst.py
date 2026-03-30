import json
import logging
from typing import Any, Dict

import requests

from models.schemas import NewsReport

logger = logging.getLogger(__name__)


class GeminiRateLimitError(Exception):
    """Raised when Gemini returns 429."""
    pass


def analyze_news(
    ticker: str,
    company_name: str,
    headlines: list[str],
    config: Dict[str, Any],
    rate_limiter
) -> NewsReport:
    """
    Sends news headlines to Gemini 2.5 Flash Lite via Google Generative Language API
    and returns a structured NewsReport.
    """
    llm_config = config["llm"]
    api_key = llm_config["api_key"]
    model = llm_config["model"]
    base_url = llm_config["base_url"]
    max_tokens = llm_config["max_tokens"]
    temperature = llm_config["temperature"]

    if not headlines:
        raise ValueError("No headlines provided for analysis.")

    formatted_headlines = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""You are a senior financial analyst. Analyze the following recent news headlines
for {company_name} ({ticker}) and return a structured JSON report.

News Headlines:
{formatted_headlines}

Focus your analysis on: earnings, revenue, partnerships, investments, ventures,
acquisitions, legal risks, regulatory actions, macroeconomic factors, and
leadership changes. Be objective and base your analysis only on the headlines
provided — do not invent information.
"""

    estimated_tokens = len(prompt) // 4
    rate_limiter.check_and_wait(estimated_tokens)

    schema_json = NewsReport.model_json_schema()

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema_json,
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        }
    }

    try:
        response = requests.post(
            f"{base_url}/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
    except Exception as e:
        raise RuntimeError(f"API request failed: {e}")

    if response.status_code == 429:
        raise GeminiRateLimitError(
            "Rate limit hit (HTTP 429). Please wait a moment and try again."
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"API request failed with status {response.status_code}: {response.text}"
        )

    try:
        resp_data = response.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse API response as JSON: {e}")

    try:
        content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected API response structure: {e}")

    try:
        report = NewsReport.model_validate_json(content)
    except Exception as e:
        logger.error(f"Invalid JSON from LLM: {content[:500]}")
        raise RuntimeError(f"LLM returned malformed JSON: {e}")

    usage = resp_data.get("usageMetadata", {})
    tokens_used = usage.get("totalTokenCount", estimated_tokens)
    rate_limiter.record_call(tokens_used)

    return report
