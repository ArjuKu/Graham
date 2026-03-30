import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def parse(
    raw_data: Dict[str, Any],
    ticker: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Transforms raw yfinance data into a clean dict ready for DCF engine.
    Handles missing values gracefully with fallbacks.
    """
    info = raw_data.get("info", {})
    financials = raw_data.get("financials")
    balance_sheet = raw_data.get("balance_sheet")
    cashflow = raw_data.get("cashflow")
    news = raw_data.get("news", [])

    company_name = info.get("shortName", ticker)
    current_price = info.get("currentPrice")
    shares_outstanding = info.get("sharesOutstanding")
    market_cap = info.get("marketCap")
    sector = info.get("sector", "Unknown")
    industry = info.get("industry", "Unknown")
    beta = info.get("beta")
    
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    eps_ttm = info.get("epsTrailingTwelveMonths")

    if beta is None:
        beta = config["dcf"].get("beta_fallback", 1.0)
        logger.warning(f"Beta not available for {ticker}, using fallback: {beta}")

    total_debt = _get_latest_value(balance_sheet, "Total Debt")
    cash = _get_latest_value(balance_sheet, "Cash And Cash Equivalents")
    equity = _get_latest_value(balance_sheet, "Stockholders Equity")

    fcf_history = _get_fcf_history(cashflow)
    if not fcf_history or len(fcf_history) < 3:
        logger.warning(f"Insufficient FCF history for {ticker}, using default 0")
        avg_fcf = 0.0
        fcf_growth_rate = 0.0
    else:
        avg_fcf = sum(fcf_history) / len(fcf_history)
        fcf_growth_rate = _calculate_growth_rate(fcf_history, config)

    news_headlines = []
    for article in news:
        title = article.get("title", "No Title")
        publisher = article.get("publisher", "Unknown")
        news_headlines.append(f"{title} — {publisher}")

    # Parse historical financials
    historical = parse_historical(financials, balance_sheet, cashflow)

    # Parse holders data
    institutional_holders = parse_institutional_holders(
        raw_data.get("institutional_holders")
    )
    insider_purchases = parse_insider_purchases(
        raw_data.get("insider_purchases")
    )

    return {
        "ticker": ticker,
        "company_name": company_name,
        "current_price": current_price,
        "shares_outstanding": shares_outstanding,
        "market_cap": market_cap,
        "sector": sector,
        "industry": industry,
        "beta": beta,
        "total_debt": total_debt,
        "cash": cash,
        "equity": equity,
        "fcf_history": fcf_history,
        "avg_fcf": avg_fcf,
        "fcf_growth_rate": fcf_growth_rate,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "eps_ttm": eps_ttm,
        "news_headlines": news_headlines,
        "historical": historical,
        "institutional_holders": institutional_holders,
        "insider_purchases": insider_purchases,
        "insider_transactions": parse_insider_transactions(raw_data.get("insider_transactions")),
    }


def parse_historical(
    financials: Optional[pd.DataFrame],
    balance_sheet: Optional[pd.DataFrame],
    cashflow: Optional[pd.DataFrame]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extracts 5 years of historical financial data for display.
    Returns a dict with 'years', 'income', 'balance', 'cashflow' keys.
    """
    result = {
        "years": [],
        "income": {},
        "balance": {},
        "cashflow": {},
    }

    if financials is None or financials.empty:
        return result

    # Get year labels from columns (most recent first)
    dates = financials.columns
    years = [str(d.year) if hasattr(d, 'year') else str(d)[:4] for d in dates]
    result["years"] = years

    # Income statement metrics
    income_metrics = ["Total Revenue", "Net Income", "EBITDA"]
    for metric in income_metrics:
        if metric in financials.index:
            values = financials.loc[metric].dropna()
            result["income"][metric] = [float(v) for v in values]

    # Balance sheet metrics
    if balance_sheet is not None and not balance_sheet.empty:
        balance_metrics = ["Total Debt", "Stockholders Equity", "Cash And Cash Equivalents"]
        for metric in balance_metrics:
            if metric in balance_sheet.index:
                values = balance_sheet.loc[metric].dropna()
                result["balance"][metric] = [float(v) for v in values]

    # Cashflow metrics
    if cashflow is not None and not cashflow.empty:
        cashflow_metrics = ["Free Cash Flow", "Operating Cash Flow"]
        for metric in cashflow_metrics:
            if metric in cashflow.index:
                values = cashflow.loc[metric].dropna()
                result["cashflow"][metric] = [float(v) for v in values]

    return result


def parse_institutional_holders(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """
    Parses institutional holders DataFrame into a list of dicts.
    """
    if df is None or df.empty:
        return []

    holders = []
    for _, row in df.iterrows():
        try:
            holder = {
                "name": str(row.get("Holder", "Unknown")),
                "shares": float(row.get("Shares", 0)),
                "pct_held": float(row.get("pctHeld", 0)),
                "value": float(row.get("Value", 0)),
                "date_reported": str(row.get("Date Reported", "")),
            }
            holders.append(holder)
        except Exception as e:
            logger.warning(f"Error parsing holder row: {e}")
    return holders


def parse_insider_purchases(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Parses insider purchases DataFrame into a summary dict.
    """
    if df is None or df.empty:
        return {"purchases": 0, "sales": 0, "net": 0, "details": []}

    details = []
    purchases = 0
    sales = 0

    for _, row in df.iterrows():
        try:
            detail = {
                "insider": str(row.get("Insider", "Unknown")),
                "transaction": str(row.get("Text", "")),
                "shares": float(row.get("Shares", 0)),
                "date": str(row.get("Start Date", "")),
            }
            details.append(detail)

            shares = float(row.get("Shares", 0))
            if shares > 0:
                purchases += shares
            else:
                sales += abs(shares)
        except Exception as e:
            logger.warning(f"Error parsing insider row: {e}")

    return {
        "purchases": purchases,
        "sales": sales,
        "net": purchases - sales,
        "details": details[:5],  # Limit to 5 most recent
    }


def parse_insider_transactions(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """
    Parses insider transactions DataFrame into a list of individual transactions.
    These have proper insider names, share counts, and dates.
    """
    if df is None or df.empty:
        return []

    transactions = []
    for _, row in df.iterrows():
        try:
            insider = str(row.get("Insider", "")).strip()
            shares = row.get("Shares")
            start_date = row.get("Start Date")
            text = str(row.get("Text", "")).strip()
            position = str(row.get("Position", "")).strip()
            txn_type = str(row.get("Transaction", "")).strip()

            # Skip rows with missing key data
            if not insider or insider == "nan" or insider == "":
                continue
            if shares is None:
                continue

            shares = float(shares)
            date_str = ""
            if start_date is not None:
                if hasattr(start_date, 'strftime'):
                    date_str = start_date.strftime("%Y-%m-%d")
                else:
                    date_str = str(start_date)[:10]

            transactions.append({
                "insider": insider,
                "shares": shares,
                "date": date_str,
                "text": text if text else "",
                "position": position if position else "",
                "transaction_type": txn_type if txn_type else "",
            })
        except Exception as e:
            logger.warning(f"Error parsing insider transaction row: {e}")

    return transactions[:5]  # Limit to 5 most recent


def _get_latest_value(df: Optional[pd.DataFrame], row_name: str) -> float:
    """
    Extracts the latest annual value from a DataFrame row.
    yfinance DataFrames have dates as columns and items as rows.
    """
    if df is None or df.empty:
        logger.warning(f"DataFrame is None or empty for row: {row_name}")
        return 0.0
    if row_name not in df.index:
        logger.warning(f"Row '{row_name}' not found in DataFrame. Available: {df.index.tolist()[:5]}...")
        return 0.0
    try:
        values = df.loc[row_name].dropna()
        if values.empty:
            return 0.0
        return float(values.iloc[0])
    except Exception as e:
        logger.warning(f"Error extracting {row_name}: {e}")
        return 0.0


def _get_fcf_history(cashflow: Optional[pd.DataFrame]) -> List[float]:
    """
    Extracts last 3 years of Free Cash Flow.
    In yfinance, 'Free Cash Flow' is a row index, not a column.
    """
    if cashflow is None or cashflow.empty:
        return []
    if "Free Cash Flow" not in cashflow.index:
        logger.warning("'Free Cash Flow' row not found in cashflow DataFrame")
        return []
    try:
        fcf_series = cashflow.loc["Free Cash Flow"].dropna()
        fcf_list = [float(x) for x in fcf_series.head(3)]
        return fcf_list
    except Exception as e:
        logger.warning(f"Error extracting FCF history: {e}")
        return []


def _calculate_growth_rate(fcf_history: List[float], config: Dict[str, Any]) -> float:
    """
    Calculates average YoY growth rate from FCF history,
    applying override, cap, and floor from config.
    """
    dcf_config = config["dcf"]

    override = dcf_config.get("fcf_growth_rate_override")
    if override is not None:
        growth_rate = float(override)
    else:
        if len(fcf_history) < 2:
            growth_rate = 0.0
        else:
            growths = []
            for i in range(1, len(fcf_history)):
                prev = fcf_history[i]
                curr = fcf_history[i - 1]
                if prev != 0:
                    growth = (curr - prev) / abs(prev)
                    growths.append(growth)
            if growths:
                growth_rate = sum(growths) / len(growths)
            else:
                growth_rate = 0.0

    cap = dcf_config.get("fcf_growth_cap", 0.30)
    floor = dcf_config.get("fcf_growth_floor", -0.10)

    return max(floor, min(cap, growth_rate))
