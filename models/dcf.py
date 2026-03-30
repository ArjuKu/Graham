import math
from typing import Any, Dict, List


def calculate(parsed_data: Dict[str, Any], assumptions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure DCF calculation engine.
    Takes parsed financial data and user assumptions, returns valuation results.
    """
    risk_free = assumptions["risk_free_rate"]
    equity_risk_premium = assumptions["equity_risk_premium"]
    beta = parsed_data["beta"]
    credit_spread = assumptions["credit_spread"]
    tax_rate = assumptions["tax_rate"]

    market_cap = parsed_data["market_cap"] or 0.0
    total_debt = parsed_data["total_debt"] or 0.0
    cash = parsed_data["cash"] or 0.0

    cost_of_equity = risk_free + beta * equity_risk_premium

    cost_of_debt = risk_free + credit_spread

    # WACC weights: V = E + D (market_cap + total_debt)
    # Note: We do NOT subtract cash here - that's for the equity bridge later
    wacc_denominator = market_cap + total_debt
    if wacc_denominator == 0:
        weight_equity = 0.0
        weight_debt = 0.0
    else:
        weight_equity = market_cap / wacc_denominator
        weight_debt = total_debt / wacc_denominator

    wacc = (
        weight_equity * cost_of_equity
        + weight_debt * cost_of_debt * (1 - tax_rate)
    )

    projection_years = int(assumptions["projection_years"])
    terminal_growth_rate = assumptions["terminal_growth_rate"]

    if wacc <= terminal_growth_rate:
        raise ValueError(
            "WACC must be greater than terminal growth rate. "
            f"WACC={wacc:.4f}, Terminal Growth={terminal_growth_rate:.4f}"
        )

    avg_fcf = parsed_data["avg_fcf"]
    fcf_growth_rate = parsed_data["fcf_growth_rate"]

    fcf_projections = []
    prev_fcf = avg_fcf
    for year in range(1, projection_years + 1):
        fcf = prev_fcf * (1 + fcf_growth_rate)
        fcf_projections.append(fcf)
        prev_fcf = fcf

    terminal_value = (
        fcf_projections[-1] * (1 + terminal_growth_rate)
        / (wacc - terminal_growth_rate)
    )

    pv_fcfs = 0.0
    for t, fcf in enumerate(fcf_projections, start=1):
        pv_fcfs += fcf / math.pow(1 + wacc, t)

    pv_terminal = terminal_value / math.pow(1 + wacc, projection_years)

    enterprise_value = pv_fcfs + pv_terminal

    equity_value = enterprise_value + cash - total_debt

    shares_outstanding = parsed_data["shares_outstanding"]
    if shares_outstanding is None or shares_outstanding == 0:
        intrinsic_value_per_share = 0.0
    else:
        intrinsic_value_per_share = equity_value / shares_outstanding

    margin_of_safety = assumptions.get("margin_of_safety", 0.25)
    mos_price = intrinsic_value_per_share * (1 - margin_of_safety)

    current_price = parsed_data["current_price"] or 0.0
    if current_price > 0:
        upside_pct = (intrinsic_value_per_share - current_price) / current_price
    else:
        upside_pct = 0.0

    return {
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "cost_of_debt": cost_of_debt,
        "weight_equity": weight_equity,
        "weight_debt": weight_debt,
        "fcf_projections": fcf_projections,
        "terminal_value": terminal_value,
        "pv_fcfs": pv_fcfs,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_value_per_share": intrinsic_value_per_share,
        "margin_of_safety_price": mos_price,
        "current_price": current_price,
        "upside_pct": upside_pct,
    }
