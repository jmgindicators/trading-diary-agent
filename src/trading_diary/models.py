"""Pydantic models for trades, analyses, and summaries."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class SetupType(str, Enum):
    """Classification of trade setup type."""

    ZONE_BOUNCE = "zone_bounce"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    TREND_FOLLOW = "trend_follow"
    NEWS_DRIVEN = "news_driven"
    OTHER = "other"


class Trade(BaseModel):
    """A single trade execution."""

    id: int | None = None
    instrument: str
    entry_time: datetime
    exit_time: datetime
    direction: TradeDirection
    entry_price: float
    exit_price: float
    quantity: int = Field(gt=0)
    pnl: float
    commission: float = 0.0
    notes: str = ""

    @property
    def duration_minutes(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


class TradeAnalysis(BaseModel):
    """LLM-generated analysis of a trade."""

    trade_id: int
    setup_type: SetupType
    quality_score: int = Field(ge=1, le=5, description="1=impulsive, 5=textbook")
    entry_quality: str
    exit_quality: str
    lesson_learned: str
    pattern_tags: list[str] = Field(default_factory=list)


class DailySummary(BaseModel):
    """Aggregated summary for a trading day."""

    date: str
    total_trades: int
    wins: int
    losses: int
    breakevens: int
    net_pnl: float
    win_rate: float
    best_setup: str
    worst_setup: str
    key_observations: list[str]
    tomorrow_focus: str
