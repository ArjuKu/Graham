from pydantic import BaseModel, Field
from typing import Literal


class NewsReport(BaseModel):
    summary: str = Field(
        description=(
            "2-3 sentence summary of the company's recent news landscape. "
            "Be concise and factual."
        )
    )
    sentiment_score: float = Field(
        description=(
            "Overall sentiment score from -1.0 (very negative) to 1.0 "
            "(very positive), based solely on the news headlines provided."
        ),
        ge=-1.0,
        le=1.0,
    )
    positives: list[str] = Field(
        description=(
            "Up to 4 bullet points of positive signals, tailwinds, or "
            "good news for the company. Each bullet is 1 sentence max."
        ),
        max_length=4,
    )
    negatives: list[str] = Field(
        description=(
            "Up to 4 bullet points of negative signals, risks, or concerns "
            "from the news. Each bullet is 1 sentence max."
        ),
        max_length=4,
    )
    verdict: Literal[
        "Bullish", "Slightly Bullish", "Neutral", "Slightly Bearish", "Bearish"
    ] = Field(
        description=(
            "One-word verdict based on the overall news sentiment. "
            "Must be exactly one of the allowed values."
        )
    )
