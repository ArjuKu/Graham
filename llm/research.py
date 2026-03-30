import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def fetch_analyst_targets(
    ticker: str,
    company_name: str,
    config: Dict[str, Any],
    rate_limiter,
) -> Dict[str, Any]:
    """
    Uses Gemini search grounding to fetch recent analyst target prices.
    Returns structured data with firm names, target prices, and ratings.
    """
    llm_config = config["llm"]
    api_key = llm_config["api_key"]
    model = llm_config["model"]
    base_url = llm_config["base_url"]

    prompt = f"""What is the average analyst target price for {company_name} ({ticker}) stock?
List exactly 5 recent analyst target prices from major research firms.
For each, format EXACTLY like this (one per line):
FirmName: $XXX (Rating)
Example:
Wedbush: $350 (Buy)
Morgan Stanley: $315 (Overweight)
JPMorgan: $325 (Neutral)
Goldman Sachs: $330 (Buy)
Bank of America: $320 (Buy)"""

    estimated_tokens = len(prompt) // 4
    rate_limiter.check_and_wait(estimated_tokens)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {
            "maxOutputTokens": 1000,
            "temperature": 0.1,
        },
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
        logger.warning(f"Research API request failed: {e}")
        return {"analysts": [], "average_target": None, "error": str(e)}

    if response.status_code != 200:
        logger.warning(f"Research API returned {response.status_code}")
        return {"analysts": [], "average_target": None, "error": f"API {response.status_code}"}

    try:
        data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning(f"Failed to parse research response: {e}")
        return {"analysts": [], "average_target": None, "error": "Parse failed"}

    # Track token usage
    usage = data.get("usageMetadata", {})
    tokens_used = usage.get("totalTokenCount", estimated_tokens)
    rate_limiter.record_call(tokens_used)

    # Parse the text response into structured data
    analysts = _parse_analyst_text(content)

    if not analysts:
        return {"analysts": [], "average_target": None, "error": "No analysts found"}

    # Calculate average target
    prices = [a["target_price"] for a in analysts if a.get("target_price")]
    average = sum(prices) / len(prices) if prices else None

    return {
        "analysts": analysts,
        "average_target": average,
        "error": None,
    }


def _parse_analyst_text(text: str) -> List[Dict[str, Any]]:
    """
    Parses Gemini's text response to extract analyst targets.
    Handles multiple formats including markdown bold and varied rating formats.
    """
    analysts = []

    # Remove markdown formatting
    clean = re.sub(r'\*\*', '', text)
    clean = re.sub(r'\*', '', clean)

    # Pattern 1: "FirmName: $XXX (Rating)"
    pattern1 = r'([A-Z][A-Za-z\s&\.\-]+?)[:\s]+\$(\d+(?:\.\d+)?)\s*(?:\((?:Rating:\s*)?([A-Za-z\s]+)\))?'

    # Pattern 2: "FirmName — $XXX" or "FirmName - $XXX"
    pattern2 = r'([A-Z][A-Za-z\s&\.\-]+?)\s*[-–—]\s*\$(\d+(?:\.\d+)?)'

    # Pattern 3: Look for any line with a dollar amount
    pattern3 = r'([A-Za-z][A-Za-z\s&\.\-]+?)[:\s].*?\$(\d+(?:\.\d+)?)'

    for pattern in [pattern1, pattern2, pattern3]:
        matches = re.findall(pattern, clean)
        for match in matches:
            if len(match) >= 2:
                firm = match[0].strip()
                try:
                    price = float(match[1])
                except ValueError:
                    continue
                rating = match[2].strip() if len(match) > 2 and match[2] else "N/A"

                # Clean up firm name
                firm = re.sub(r'\s+', ' ', firm).strip()
                firm = re.sub(r'^(Rating:\s*|As of.*$)', '', firm).strip()

                # Filter out junk
                if len(firm) < 3:
                    continue
                if firm.lower() in ['the', 'and', 'or', 'is', 'here', 'with', 'each', 'for']:
                    continue
                if any(skip in firm.lower() for skip in ['average', 'consensus', 'rating', 'example', 'format']):
                    continue

                analysts.append({
                    "firm": firm,
                    "target_price": price,
                    "rating": rating,
                })

    # Deduplicate by firm name (keep first occurrence)
    seen = set()
    unique = []
    for a in analysts:
        key = a["firm"].lower().strip()
        if key not in seen and len(key) > 2:
            seen.add(key)
            unique.append(a)

    return unique[:5]  # Limit to 5
