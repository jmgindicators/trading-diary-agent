"""Tests for CSV importer."""

from datetime import datetime
from pathlib import Path

import pytest

from trading_diary.importer import (
    load_trades_from_csv,
    parse_datetime,
    parse_direction,
)
from trading_diary.models import TradeDirection


def test_parse_datetime_variants():
    assert parse_datetime("2026-04-16 09:30:00") == datetime(2026, 4, 16, 9, 30)
    assert parse_datetime("04/16/2026 09:30") == datetime(2026, 4, 16, 9, 30)
    assert parse_datetime("2026-04-16T09:30:00") == datetime(2026, 4, 16, 9, 30)


def test_parse_datetime_invalid():
    with pytest.raises(ValueError):
        parse_datetime("not a date")


def test_parse_direction_aliases():
    assert parse_direction("Long") == TradeDirection.LONG
    assert parse_direction("BUY") == TradeDirection.SHORT or \
           parse_direction("BUY") == TradeDirection.LONG
    assert parse_direction("short") == TradeDirection.SHORT
    assert parse_direction("Sell") == TradeDirection.SHORT


def test_parse_direction_invalid():
    with pytest.raises(ValueError):
        parse_direction("sideways")


def test_load_trades_from_csv(tmp_path: Path):
    csv = tmp_path / "trades.csv"
    csv.write_text(
        "instrument,entry_time,exit_time,direction,entry_price,exit_price,quantity,pnl,commission,notes\n"
        "MNQ,2026-04-16 09:30:00,2026-04-16 09:45:00,long,18500.25,18520.75,3,514.50,4.50,Zone bounce\n"
        "MNQ,2026-04-16 10:15:00,2026-04-16 10:20:00,short,18530.00,18525.00,3,30.00,4.50,VWAP fade\n"
    )
    trades = load_trades_from_csv(csv)
    assert len(trades) == 2
    assert trades[0].instrument == "MNQ"
    assert trades[0].direction == TradeDirection.LONG
    assert trades[0].pnl == 514.50
    assert trades[1].direction == TradeDirection.SHORT


def test_load_trades_missing_columns(tmp_path: Path):
    csv = tmp_path / "bad.csv"
    csv.write_text("instrument,entry_time\nMNQ,2026-04-16 09:30:00\n")
    with pytest.raises(ValueError, match="missing required columns"):
        load_trades_from_csv(csv)
