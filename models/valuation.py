from typing import Any, Dict, Literal


ValuationScore = Literal[1, 2, 3, 4, 5]
ValuationLabel = Literal["Undervalued", "Slightly Undervalued", "Fair Value", "Overvalued", "Highly Overvalued", "Unprofitable"]


def evaluate_pe(
    parsed_data: Dict[str, Any],
    spy_pe: float
) -> Dict[str, Any]:
    """
    Evaluates P/E ratio relative to SPY and assigns a valuation score.
    
    Prioritizes forward P/E when available (more relevant for growth stocks).
    Falls back to trailing P/E if forward is unavailable.
    Returns 'Unprofitable' for negative P/E ratios.
    """
    trailing_pe = parsed_data.get("trailing_pe")
    forward_pe = parsed_data.get("forward_pe")
    
    # Prefer forward P/E for valuation (future earnings matter more)
    if forward_pe is not None and forward_pe > 0:
        company_pe = forward_pe
        pe_type = "Forward P/E"
    elif trailing_pe is not None and trailing_pe > 0:
        company_pe = trailing_pe
        pe_type = "Trailing P/E"
    else:
        # Negative or missing P/E
        return {
            "company_pe": None,
            "spy_pe": spy_pe,
            "relative_multiple": None,
            "score": None,
            "label": "Unprofitable",
            "pe_type": pe_type if 'pe_type' in locals() else "N/A",
            "interpretation": "Company is unprofitable or P/E unavailable"
        }
    
    # Calculate relative multiple
    relative_multiple = company_pe / spy_pe
    
    # Assign score based on relative multiple
    # Non-arbitrary ranges:
    # 5: < 0.6x (significantly cheaper than market)
    # 4: 0.6x - 0.9x (slightly cheaper)
    # 3: 0.9x - 1.3x (fair value relative to market)
    # 2: 1.3x - 2.5x (overvalued)
    # 1: > 2.5x (highly overvalued)
    
    if relative_multiple < 0.6:
        score = 5
        label = "Undervalued"
    elif relative_multiple < 0.9:
        score = 4
        label = "Slightly Undervalued"
    elif relative_multiple < 1.3:
        score = 3
        label = "Fair Value"
    elif relative_multiple < 2.5:
        score = 2
        label = "Overvalued"
    else:
        score = 1
        label = "Highly Overvalued"
    
    # Generate interpretation
    if score >= 4:
        interpretation = f"Trading at {relative_multiple:.1f}x SPY P/E - attractive valuation"
    elif score == 3:
        interpretation = f"Trading at {relative_multiple:.1f}x SPY P/E - fair value vs market"
    else:
        interpretation = f"Trading at {relative_multiple:.1f}x SPY P/E - premium valuation"
    
    return {
        "company_pe": company_pe,
        "spy_pe": spy_pe,
        "relative_multiple": relative_multiple,
        "score": score,
        "label": label,
        "pe_type": pe_type,
        "interpretation": interpretation,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
    }
