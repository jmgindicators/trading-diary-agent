#!/usr/bin/env bash
# One-shot setup: create venv, install, init DB, import sample, run analysis.
set -e

echo "==> Creating virtual environment"
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing package"
pip install --upgrade pip
pip install -e ".[dev]"

echo "==> Initializing database"
diary init

echo "==> Importing sample trades"
diary import data/sample_trades.csv

echo
echo "Setup complete. Next steps:"
echo "  1. Copy .env.example to .env and add your ANTHROPIC_API_KEY"
echo "  2. Run: diary analyze"
echo "  3. Run: diary summary day 2026-04-16"
echo "  4. Run: diary list -n 10"
