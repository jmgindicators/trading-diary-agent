"""LLM-powered trade analyzer using Anthropic Claude."""

import os

from anthropic import Anthropic

from .models import SetupType, Trade, TradeAnalysis

DEFAULT_MODEL = os.environ.get("DIARY_ANALYZER_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """Eres un coach técnico de trading que analiza operaciones de futuros para
un trader profesional discrecional.

Perfil del trader:
- Opera MNQ (Micro Nasdaq) en NinjaTrader 8
- Usa Smart Money Concepts, VWAP y zonas de oferta/demanda
- Gráficos de 5 minutos con medias móviles MM20 / MM50 / MM200
- Opera 3 contratos por setup
- Metodología: solo opera cuando el precio llega a una zona predefinida, nunca antes,
  nunca después
- Objetivo: 77-80% win rate diario

Para cada trade que recibas debes clasificarlo y dar feedback honesto y accionable.

Tono: profesional, directo, técnico. Trato de usted al trader. Sin coloquialismos,
sin "hermano", "bro", "tío" o similares. Eres un coach técnico, no un colega.

IMPORTANTE: Responde SIEMPRE en español con tono profesional. NUNCA en inglés.
Todos los campos de texto (entry_quality, exit_quality, lesson_learned) deben estar en español
con trato de usted. Solo los tags y el setup_type pueden ir en inglés porque son etiquetas
técnicas del sistema."""

# Tool definition forces a structured output that maps directly to TradeAnalysis
ANALYZER_TOOL = {
    "name": "record_trade_analysis",
    "description": "Registra el análisis estructurado de un trade individual.",
    "input_schema": {
        "type": "object",
        "properties": {
            "setup_type": {
                "type": "string",
                "enum": [s.value for s in SetupType],
                "description": "El tipo de setup que representa este trade",
            },
            "quality_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "1 = impulsivo / fuera de plan, 5 = ejecución de manual",
            },
            "entry_quality": {
                "type": "string",
                "description": "Evaluación de 1-2 frases de la entrada, en español profesional",
            },
            "exit_quality": {
                "type": "string",
                "description": "Evaluación de 1-2 frases de la salida, en español profesional",
            },
            "lesson_learned": {
                "type": "string",
                "description": "Una lección concreta y accionable para la próxima vez, "
                               "en español profesional",
            },
            "pattern_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 tags cortos en inglés snake_case (ej: 'overnight_zone', "
                               "'chased_entry')",
            },
        },
        "required": [
            "setup_type",
            "quality_score",
            "entry_quality",
            "exit_quality",
            "lesson_learned",
            "pattern_tags",
        ],
    },
}


def _build_user_message(trade: Trade) -> str:
    return f"""Analice este trade y llame a la herramienta record_trade_analysis con sus conclusiones.

Trade #{trade.id}
- Instrumento: {trade.instrument}
- Dirección: {trade.direction.value.upper()}
- Entrada: {trade.entry_time.isoformat()} @ {trade.entry_price}
- Salida:  {trade.exit_time.isoformat()} @ {trade.exit_price}
- Cantidad: {trade.quantity}
- Duración: {trade.duration_minutes:.1f} minutos
- P&L neto: ${trade.pnl:.2f}
- Notas del trader: {trade.notes or "(ninguna)"}"""


def analyze_trade(trade: Trade, client: Anthropic | None = None,
                  model: str = DEFAULT_MODEL) -> TradeAnalysis:
    """Send a trade to Claude and return a structured TradeAnalysis."""
    if trade.id is None:
        raise ValueError("Trade must have an id before analysis")

    client = client or Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[ANALYZER_TOOL],
        tool_choice={"type": "tool", "name": "record_trade_analysis"},
        messages=[{"role": "user", "content": _build_user_message(trade)}],
    )

    tool_use = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_use is None:
        raise RuntimeError(
            f"Model did not call the analysis tool. Response: {response.content!r}"
        )

    data = tool_use.input
    return TradeAnalysis(
        trade_id=trade.id,
        setup_type=SetupType(data["setup_type"]),
        quality_score=data["quality_score"],
        entry_quality=data["entry_quality"],
        exit_quality=data["exit_quality"],
        lesson_learned=data["lesson_learned"],
        pattern_tags=data["pattern_tags"],
    )
