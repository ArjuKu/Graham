import math
from typing import Any, Dict, List, Tuple


def compute_sensitivity(
    parsed_data: Dict[str, Any],
    assumptions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes a 3x3 sensitivity matrix showing intrinsic value per share
    across variations of WACC and FCF growth rate.
    
    WACC varies by ±1%, FCF Growth varies by ±2%.
    Returns a dict with the grid data for display.
    """
    base_wacc = assumptions.get("wacc", 0.10)
    base_growth = parsed_data.get("fcf_growth_rate", 0.0)
    avg_fcf = parsed_data.get("avg_fcf", 0)
    shares = parsed_data.get("shares_outstanding", 1)
    cash = parsed_data.get("cash", 0)
    debt = parsed_data.get("total_debt", 0)
    terminal_growth = assumptions.get("terminal_growth_rate", 0.025)
    projection_years = int(assumptions.get("projection_years", 5))
    margin_of_safety = assumptions.get("margin_of_safety", 0.25)

    # Define variations
    wacc_variations = [-0.01, 0, 0.01]  # -1%, base, +1%
    growth_variations = [0.02, 0, -0.02]  # +2%, base, -2%

    wacc_labels = []
    growth_labels = []
    matrix = []

    # Pre-calculate growth labels to ensure uniqueness
    for g_var in growth_variations:
        growth = base_growth + g_var
        growth_labels.append(f"{growth*100:.1f}%")

    for wacc_var in wacc_variations:
        wacc = base_wacc + wacc_var
        if wacc <= terminal_growth:
            wacc = terminal_growth + 0.001  # Ensure valid

        row = []
        wacc_labels.append(f"{wacc*100:.1f}%")

        for growth_var in growth_variations:
            growth = base_growth + growth_var
            # Compute IV for this combination
            iv = _compute_iv(
                avg_fcf=avg_fcf,
                growth=growth,
                wacc=wacc,
                terminal_growth=terminal_growth,
                projection_years=projection_years,
                cash=cash,
                debt=debt,
                shares=shares,
            )
            row.append(iv)

        matrix.append(row)

    return {
        "wacc_labels": wacc_labels,
        "growth_labels": growth_labels,
        "matrix": matrix,
        "base_wacc": base_wacc,
        "base_growth": base_growth,
        "min_iv": min(min(row) for row in matrix),
        "max_iv": max(max(row) for row in matrix),
    }


def _compute_iv(
    avg_fcf: float,
    growth: float,
    wacc: float,
    terminal_growth: float,
    projection_years: int,
    cash: float,
    debt: float,
    shares: float,
) -> float:
    """
    Computes intrinsic value per share for a given set of parameters.
    """
    if wacc <= terminal_growth or shares <= 0 or avg_fcf <= 0:
        return 0.0

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
    equity_value = enterprise_value + cash - debt

    return equity_value / shares
