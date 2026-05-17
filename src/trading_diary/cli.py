"""Command-line interface for the trading diary agent."""

from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import analyzer, database, importer, summarizer

load_dotenv()

app = typer.Typer(
    name="diary",
    help="AI-powered trading diary. Import trades, analyze with Claude, generate insights.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init():
    """Initialize the SQLite database (safe to run multiple times)."""
    database.init_db()
    console.print(f"[green]✓[/green] Database ready at {database.DEFAULT_DB}")


@app.command("import")
def import_cmd(csv_file: Path = typer.Argument(..., help="CSV file with trades")):
    """Import trades from a CSV file."""
    database.init_db()
    trades = importer.load_trades_from_csv(csv_file)
    inserted = 0
    for trade in trades:
        database.insert_trade(trade)
        inserted += 1
    console.print(f"[green]✓[/green] Imported {inserted} trades from {csv_file}")


@app.command()
def analyze(
    all_trades: bool = typer.Option(False, "--all", help="Re-analyze every trade"),
    limit: int | None = typer.Option(None, help="Only process N trades"),
):
    """Run Claude analysis on trades (defaults to unanalyzed ones)."""
    trades = (
        database.fetch_trades(limit=limit)
        if all_trades
        else database.fetch_unanalyzed_trades()
    )
    if not trades:
        console.print("[yellow]No trades to analyze.[/yellow]")
        return

    console.print(f"Analyzing {len(trades)} trades with Claude...")
    for trade in trades:
        try:
            result = analyzer.analyze_trade(trade)
            database.upsert_analysis(result)
            console.print(
                f"  [green]✓[/green] #{trade.id} "
                f"setup={result.setup_type.value} "
                f"quality={result.quality_score}/5"
            )
        except Exception as e:  # noqa: BLE001
            console.print(f"  [red]✗[/red] #{trade.id} failed: {e}")
    console.print("[green]Done.[/green]")


@app.command()
def summary(
    period: str = typer.Argument(..., help="day | week | month"),
    date: str = typer.Argument(..., help="YYYY-MM-DD (day) or YYYY-MM (month)"),
):
    """Generate a coaching summary for a day, week, or month."""
    if period == "day":
        trades = database.fetch_trades(date_prefix=date)
    elif period == "month":
        if len(date) == 7:
            trades = database.fetch_trades(date_prefix=date)
        else:
            trades = database.fetch_trades(date_prefix=date[:7])
    elif period == "week":
        # Treat the supplied date as the start of the week (simple version)
        start = datetime.fromisoformat(date)
        trades = [
            t for t in database.fetch_trades()
            if 0 <= (t.entry_time - start).days < 7
        ]
    else:
        console.print(f"[red]Unknown period: {period}[/red]")
        raise typer.Exit(1)

    if not trades:
        console.print("[yellow]No trades found for that period.[/yellow]")
        return

    console.print(f"Generating {period} summary for {date}...")
    content = summarizer.generate_summary(f"{period} {date}", trades)
    database.save_summary(period, date, content)
    console.print(Panel(content, title=f"{period.title()} {date}", border_style="cyan"))


@app.command("list")
def list_cmd(
    recent: int = typer.Option(10, "--recent", "-n", help="How many trades to show"),
):
    """Show recent trades with their analyses."""
    trades = database.fetch_trades()[-recent:]
    if not trades:
        console.print("[yellow]No trades in database. Run 'diary import' first.[/yellow]")
        return

    table = Table(title=f"Last {len(trades)} trades")
    table.add_column("#", style="cyan")
    table.add_column("Time")
    table.add_column("Inst")
    table.add_column("Dir")
    table.add_column("Qty", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("Setup")
    table.add_column("Q")

    for t in trades:
        analysis = database.fetch_analysis(t.id) if t.id else None
        pnl_color = "green" if t.pnl >= 0 else "red"
        table.add_row(
            str(t.id),
            t.entry_time.strftime("%Y-%m-%d %H:%M"),
            t.instrument,
            t.direction.value,
            str(t.quantity),
            f"[{pnl_color}]${t.pnl:+.2f}[/{pnl_color}]",
            analysis.setup_type.value if analysis else "-",
            f"{analysis.quality_score}/5" if analysis else "-",
        )
    console.print(table)


@app.command()
def show(trade_id: int):
    """Show a single trade with full analysis."""
    trade = database.fetch_trade(trade_id)
    if not trade:
        console.print(f"[red]Trade #{trade_id} not found[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]{trade.instrument}[/bold] {trade.direction.value.upper()} "
        f"qty={trade.quantity}\n"
        f"Entry: {trade.entry_time} @ {trade.entry_price}\n"
        f"Exit:  {trade.exit_time} @ {trade.exit_price}\n"
        f"P&L: ${trade.pnl:+.2f}  Duration: {trade.duration_minutes:.1f} min\n"
        f"Notes: {trade.notes or '(none)'}",
        title=f"Trade #{trade.id}",
    ))

    analysis = database.fetch_analysis(trade_id)
    if analysis:
        console.print(Panel(
            f"[bold]Setup:[/bold] {analysis.setup_type.value} "
            f"[bold]Quality:[/bold] {analysis.quality_score}/5\n\n"
            f"[bold]Entry:[/bold] {analysis.entry_quality}\n\n"
            f"[bold]Exit:[/bold] {analysis.exit_quality}\n\n"
            f"[bold]Lesson:[/bold] {analysis.lesson_learned}\n\n"
            f"[bold]Tags:[/bold] {', '.join(analysis.pattern_tags)}",
            title="Claude analysis",
            border_style="magenta",
        ))
    else:
        console.print("[yellow]No analysis yet. Run 'diary analyze'.[/yellow]")


if __name__ == "__main__":
    app()
