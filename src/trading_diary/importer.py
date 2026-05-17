"""Import trades from CSV files (NinjaTrader 8 export format or custom)."""

import csv
from datetime import datetime
from pathlib import Path

from .models import Trade, TradeDirection

# Canonical column names this importer expects.
# Many broker/platform exports can be mapped to these with a small adapter.
EXPECTED_COLUMNS = {
    "instrument",
    "entry_time",
    "exit_time",
    "direction",
    "entry_price",
    "exit_price",
    "quantity",
    "pnl",
}


def parse_datetime(value: str) -> datetime:
    """Parse common datetime formats found in trading exports."""
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {value!r}")


def parse_direction(value: str) -> TradeDirection:
    """Map various direction labels to canonical TradeDirection."""
    v = value.strip().lower()
    if v in {"long", "buy", "l", "b"}:
        return TradeDirection.LONG
    if v in {"short", "sell", "s"}:
        return TradeDirection.SHORT
    raise ValueError(f"Unknown direction: {value!r}")


def load_trades_from_csv(csv_path: Path) -> list[Trade]:
    """Load trades from a CSV file with the canonical schema.

    Expected columns: instrument, entry_time, exit_time, direction,
                      entry_price, exit_price, quantity, pnl,
                      [commission], [notes]
    """
    trades: list[Trade] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {csv_path} has no header row")

        cols = {c.strip().lower() for c in reader.fieldnames}
        missing = EXPECTED_COLUMNS - cols
        if missing:
            raise ValueError(
                f"CSV missing required columns: {sorted(missing)}. "
                f"Found: {sorted(cols)}"
            )

        for i, row in enumerate(reader, start=2):
            try:
                trades.append(
                    Trade(
                        instrument=row["instrument"].strip(),
                        entry_time=parse_datetime(row["entry_time"]),
                        exit_time=parse_datetime(row["exit_time"]),
                        direction=parse_direction(row["direction"]),
                        entry_price=float(row["entry_price"]),
                        exit_price=float(row["exit_price"]),
                        quantity=int(row["quantity"]),
                        pnl=float(row["pnl"]),
                        commission=float(row.get("commission") or 0),
                        notes=(row.get("notes") or "").strip(),
                    )
                )
            except (ValueError, KeyError) as e:
                raise ValueError(f"Row {i} invalid: {e}") from e

    return trades
