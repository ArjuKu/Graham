import math
from typing import Any, Dict, Optional


def compute_implied_growth(
    parsed_data: Dict[str, Any],
    dcf_result: Dict[str, Any],
    assumptions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Reverse DCF: Solves for the FCF growth rate that justifies the current price.
    
    Uses binary search to find the growth rate where:
    intrinsic_value_per_share = current_price
    
    Returns the implied growth rate and interpretation.
    """
    current_price = parsed_data.get("current_price", 0)
    avg_fcf = parsed_data.get("avg_fcf", 0)
    shares = parsed_data.get("shares_outstanding", 1)
    cash = parsed_data.get("cash", 0)
    debt = parsed_data.get("total_debt", 0)

    wacc = dcf_result.get("wacc", 0.10)
    terminal_growth = assumptions.get("terminal_growth_rate", 0.025)
    projection_years = int(assumptions.get("projection_years", 5))

    if current_price <= 0 or avg_fcf <= 0 or shares <= 0:
        return {
            "implied_growth": None,
            "interpretation": "Insufficient data for reverse DCF",
        }

    # Target equity value
    target_equity = current_price * shares

    # Binary search for growth rate
    implied_growth = _binary_search_growth(
        avg_fcf=avg_fcf,
        wacc=wacc,
        terminal_growth=terminal_growth,
        projection_years=projection_years,
        cash=cash,
        debt=debt,
        shares=shares,
        target_equity=target_equity,
    )

    if implied_growth is None:
        return {
            "implied_growth": None,
            "interpretation": "Could not solve for implied growth",
        }

    # Interpret the result
    base_growth = parsed_data.get("fcf_growth_rate", 0)
    interpretation = _interpret_implied_growth(
        implied_growth, base_growth, wacc, terminal_growth
    )

    return {
        "implied_growth": implied_growth,
        "implied_growth_pct": implied_growth * 100,
        "base_growth": base_growth,
        "base_growth_pct": base_growth * 100,
        "interpretation": interpretation,
        "current_price": current_price,
        "wacc": wacc,
    }


def _binary_search_growth(
    avg_fcf: float,
    wacc: float,
    terminal_growth: float,
    projection_years: int,
    cash: float,
    debt: float,
    shares: float,
    target_equity: float,
    max_iterations: int = 100,
    tolerance: float = 0.01,
) -> Optional[float]:
    """
    Uses binary search to find the growth rate that produces target equity value.
    """
    # Search range: -50% to +100% growth
    low = -0.50
    high = 1.00

    for _ in range(max_iterations):
        mid = (low + high) / 2
        equity_value = _compute_equity_value(
            avg_fcf, mid, wacc, terminal_growth, projection_years, cash, debt
        )

        if abs(equity_value - target_equity) < tolerance * target_equity:
            return mid

        if equity_value < target_equity:
            low = mid
        else:
            high = mid

    return mid if abs(equity_value - target_equity) < tolerance * target_equity * 2 else None


def _compute_equity_value(
    avg_fcf: float,
    growth: float,
    wacc: float,
    terminal_growth: float,
    projection_years: int,
    cash: float,
    debt: float,
) -> float:
    """
    Computes equity value for a given growth rate.
    """
    if wacc <= terminal_growth:
        return float('inf')

    # Project FCFs
    fcf_projections = []
    prev_fcf = avg_fcf
    for _ in range(projection_years):
        fcf = prev_fcf * (1 + growth)
        fcf_projections.append(fcf)
        prev_fcf = fcf

    # Terminal value
    terminal_value = (
        fcf_projections[-1] * (1 + terminal_growth)
        / (wacc - terminal_growth)
    )

    # Present values
    pv_fcfs = sum(
        fcf / math.pow(1 + wacc, t)
        for t, fcf in enumerate(fcf_projections, start=1)
    )
    pv_terminal = terminal_value / math.pow(1 + wacc, projection_years)

    # Equity bridge
    enterprise_value = pv_fcfs + pv_terminal
    return enterprise_value + cash - debt


def _interpret_implied_growth(
    implied_growth: float,
    base_growth: float,
    wacc: float,
    terminal_growth: float,
) -> str:
    """
    Generates a human-readable interpretation of the implied growth.
    """
    if implied_growth > 0.30:
        return "Market expects extreme growth — likely overvalued"
    elif implied_growth > 0.15:
        return "Market expects aggressive growth — high expectations"
    elif implied_growth > 0.08:
        return "Market expects solid growth — reasonable for growth stocks"
    elif implied_growth > terminal_growth:
        return "Market expects moderate growth — fairly valued"
    elif implied_growth > 0:
        return "Market expects slow growth — potentially undervalued"
    else:
        return "Market expects declining FCF — bearish pricing"
