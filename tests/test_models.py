"""Tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from trading_diary.models import (
    SetupType,
    Trade,
    TradeAnalysis,
    TradeDirection,
)


def _sample_trade(**overrides) -> Trade:
    defaults = dict(
        id=1,
        instrument="MNQ",
        entry_time=datetime(2026, 4, 16, 9, 30),
        exit_time=datetime(2026, 4, 16, 9, 45),
        direction=TradeDirection.LONG,
        entry_price=18500.25,
        exit_price=18520.75,
        quantity=3,
        pnl=514.50,
        commission=4.50,
        notes="Zone bounce off MM50",
    )
    defaults.update(overrides)
    return Trade(**defaults)


def test_trade_duration_minutes():
    trade = _sample_trade()
    assert trade.duration_minutes == 15.0


def test_trade_is_winner():
    assert _sample_trade(pnl=100).is_winner is True
    assert _sample_trade(pnl=-100).is_winner is False
    assert _sample_trade(pnl=0).is_winner is False


def test_trade_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        _sample_trade(quantity=0)


def test_trade_direction_enum():
    assert TradeDirection("long") == TradeDirection.LONG
    assert TradeDirection("short") == TradeDirection.SHORT


def test_trade_analysis_quality_score_bounds():
    valid = TradeAnalysis(
        trade_id=1,
        setup_type=SetupType.ZONE_BOUNCE,
        quality_score=5,
        entry_quality="Clean entry at zone",
        exit_quality="Took partial at 1R, ran the rest",
        lesson_learned="Trust the plan",
        pattern_tags=["zone_bounce", "vwap_confluence"],
    )
    assert valid.quality_score == 5

    with pytest.raises(ValidationError):
        TradeAnalysis(
            trade_id=1,
            setup_type=SetupType.ZONE_BOUNCE,
            quality_score=6,
            entry_quality="x",
            exit_quality="x",
            lesson_learned="x",
            pattern_tags=[],
        )
