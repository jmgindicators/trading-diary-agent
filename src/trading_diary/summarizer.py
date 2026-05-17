"""Generate human-readable daily / weekly / monthly summaries with Claude."""

import os
from collections import Counter
from collections.abc import Iterable

from anthropic import Anthropic

from .database import fetch_analysis
from .models import Trade

DEFAULT_MODEL = os.environ.get("DIARY_SUMMARIZER_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """Eres el coach personal de un trader profesional de futuros que opera MNQ
(Micro Nasdaq) en NinjaTrader 8. El trader es disciplinado, técnico, y opera con metodología
basada en zonas predefinidas, VWAP, Smart Money Concepts y medias móviles MM20/MM50/MM200.

Tu trabajo: transformar un batch de análisis de trades en un resumen claro, profesional
y directamente accionable.

Tono: profesional, directo, honesto. Trato de usted al trader. Sin coloquialismos,
sin "hermano", "bro", "tío" o similares. Eres un coach técnico, no un colega.

Principios:
- Sé honesto sobre los errores sin suavizarlos.
- Destaca patrones reales en los datos, no consejos genéricos.
- Las recomendaciones deben ser específicas y aplicables a la próxima sesión.
- Cierra siempre con UNA acción concreta para mejorar.

Formato de salida:

**Resumen**
2-3 líneas con el balance general del periodo (P&L, win rate, contexto).

**Patrones detectados**
2-4 bullets con patrones reales identificados en la operativa (cada bullet en negrita el patrón,
luego explicación de 1-2 frases).

**Foco para la próxima sesión**
Una recomendación concreta y única. Una sola acción que el trader debe priorizar."""


def _aggregate_stats(trades: list[Trade]) -> dict:
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    breakevens = [t for t in trades if t.pnl == 0]
    net_pnl = sum(t.pnl - t.commission for t in trades)
    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": len(breakevens),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
        "net_pnl": net_pnl,
        "avg_win": (sum(t.pnl for t in wins) / len(wins)) if wins else 0.0,
        "avg_loss": (sum(t.pnl for t in losses) / len(losses)) if losses else 0.0,
    }


def _format_trade_lines(trades: Iterable[Trade]) -> str:
    lines = []
    for t in trades:
        analysis = fetch_analysis(t.id) if t.id else None
        base = (
            f"#{t.id} {t.entry_time.strftime('%H:%M')} {t.direction.value} "
            f"{t.instrument} qty={t.quantity} pnl=${t.pnl:.2f}"
        )
        if analysis:
            base += (
                f" | setup={analysis.setup_type.value} "
                f"quality={analysis.quality_score}/5 "
                f"lesson={analysis.lesson_learned}"
            )
        lines.append(base)
    return "\n".join(lines)


def _pattern_tag_summary(trades: list[Trade]) -> str:
    tags: Counter[str] = Counter()
    for t in trades:
        if t.id is None:
            continue
        analysis = fetch_analysis(t.id)
        if analysis:
            tags.update(analysis.pattern_tags)
    if not tags:
        return "(no analyses available)"
    top = tags.most_common(8)
    return ", ".join(f"{tag}({count})" for tag, count in top)


def generate_summary(period_label: str, trades: list[Trade],
                     client: Anthropic | None = None,
                     model: str = DEFAULT_MODEL) -> str:
    """Generate a human-readable summary for the given trades."""
    if not trades:
        return f"No trades found for {period_label}."

    client = client or Anthropic()
    stats = _aggregate_stats(trades)

    user_msg = f"""Periodo: {period_label}

Estadísticas:
- Total de trades: {stats['total']}
- Ganadores / Perdedores / Breakeven: {stats['wins']} / {stats['losses']} / {stats['breakevens']}
- Win rate: {stats['win_rate']:.1f}%
- P&L neto: ${stats['net_pnl']:.2f}
- Ganancia media: ${stats['avg_win']:.2f} | Pérdida media: ${stats['avg_loss']:.2f}

Tags de patrones (frecuencia): {_pattern_tag_summary(trades)}

Trades del periodo:
{_format_trade_lines(trades)}

Genera el resumen siguiendo el formato indicado, con tono profesional y trato de usted."""

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text_blocks = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_blocks).strip()
