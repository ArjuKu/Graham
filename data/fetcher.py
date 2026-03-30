import logging
import random
import time
from typing import Any, Dict, List, Optional

import requests_cache
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

requests_cache.install_cache(
    "graham_cache",
    backend="sqlite",
    expire_after=1800,
)

_spy_pe_cache: Optional[float] = None
_spy_pe_cache_time: float = 0


def _sleep_random(min_sec: float, max_sec: float) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def search_ticker(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Searches for stocks by name or ticker using yfinance.
    Returns a list of matches with symbol, name, exchange.
    """
    try:
        search = yf.Search(query, max_results=max_results, news_count=0)
        quotes = search.quotes or []
        results = []
        for q in quotes:
            if q.get("quoteType") == "EQUITY":
                results.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname", ""),
                    "exchange": q.get("exchange", ""),
                })
        return results[:max_results]
    except Exception as e:
        logger.warning(f"Search failed for '{query}': {e}")
        return []


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=10),
    reraise=True,
)
def fetch_ticker_data(ticker: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetches raw financial data, news, and holders from yfinance.
    """
    rl_config = config["rate_limits"]
    sleep_min = rl_config["yfinance_sleep_min"]
    sleep_max = rl_config["yfinance_sleep_max"]
    news_max = rl_config["news_max_articles"]

    _sleep_random(sleep_min, sleep_max)

    try:
        ticker_obj = yf.Ticker(ticker)
    except Exception as e:
        logger.warning(f"Failed to create ticker object for {ticker}: {e}")
        raise

    info = ticker_obj.info
    _sleep_random(sleep_min, sleep_max)

    financials = ticker_obj.financials
    _sleep_random(sleep_min, sleep_max)

    balance_sheet = ticker_obj.balance_sheet
    _sleep_random(sleep_min, sleep_max)

    cashflow = ticker_obj.cashflow
    _sleep_random(sleep_min, sleep_max)

    news_raw = ticker_obj.news or []
    news = []
    for article in news_raw[:news_max]:
        try:
            content = article.get("content", {})
            title = content.get("title", "No Title")
            provider = content.get("provider", {})
            publisher = provider.get("displayName", "Unknown")
            canonical = content.get("canonicalUrl", {})
            link = canonical.get("url", "")
        except Exception as e:
            logger.warning(f"Error parsing news article: {e}")
            title = "No Title"
            publisher = "Unknown"
            link = ""
        news.append({"title": title, "publisher": publisher, "link": link})

    _sleep_random(sleep_min, sleep_max)

    try:
        institutional_holders = ticker_obj.institutional_holders
    except Exception:
        institutional_holders = None
    _sleep_random(sleep_min, sleep_max)

    try:
        insider_purchases = ticker_obj.insider_purchases
    except Exception:
        insider_purchases = None

    try:
        insider_transactions = ticker_obj.insider_transactions
    except Exception:
        insider_transactions = None

    return {
        "info": info,
        "financials": financials,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "news": news,
        "institutional_holders": institutional_holders,
        "insider_purchases": insider_purchases,
        "insider_transactions": insider_transactions,
    }


def fetch_spy_pe() -> float:
    """
    Fetches SPY (S&P 500 ETF) trailing P/E ratio.
    Cached in memory for 1 hour.
    """
    global _spy_pe_cache, _spy_pe_cache_time

    current_time = time.time()
    if _spy_pe_cache is not None and (current_time - _spy_pe_cache_time) < 3600:
        return _spy_pe_cache

    try:
        spy = yf.Ticker("SPY")
        info = spy.info
        pe = info.get("trailingPE")
        if pe is not None and pe > 0:
            _spy_pe_cache = float(pe)
            _spy_pe_cache_time = current_time
            return _spy_pe_cache
    except Exception as e:
        logger.warning(f"Failed to fetch SPY P/E: {e}")

    return 25.0
