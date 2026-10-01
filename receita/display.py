"""Exibição de quantidades: unidade legível e no máximo duas casas decimais."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from receita.types import Amount
from receita.units import Dimension

SECONDS_PER_DAY = 24 * 60 * 60


def format_decimal(value: Fraction) -> str:
    """Arredonda para duas casas (meio para cima) e remove zeros à direita: 1.2, 750, 0.33."""
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    rounded = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def format_amount(amount: Amount) -> str:
    """Quantidade na unidade mais legível da dimensão.

    Massa e volume passam a kg e l a partir de 1000; tempo usa h e min; contagem
    fracionária é arredondada para cima, com o valor exato entre parênteses.
    """
    value = amount.value
    match amount.dimension:
        case Dimension.MASSA:
            return _with_larger_unit(value, "g", "kg")
        case Dimension.VOLUME:
            return _with_larger_unit(value, "ml", "l")
        case Dimension.CONTAGEM:
            if value.denominator == 1:
                return f"{value} un"
            return f"{math.ceil(value)} un ({format_decimal(value)})"
        case Dimension.TEMPO:
            return format_duration(value)
    return format_decimal(value)


def _with_larger_unit(value: Fraction, unit: str, larger: str) -> str:
    if abs(value) >= 1000:
        return f"{format_decimal(value / 1000)} {larger}"
    return f"{format_decimal(value)} {unit}"


def format_duration(minutes: Fraction) -> str:
    """Duração em minutos como '40 min', '1 h' ou '1 h 40 min'."""
    if minutes < 60:
        return f"{format_decimal(minutes)} min"
    hours = math.floor(minutes / 60)
    rest = minutes - hours * 60
    if rest == 0:
        return f"{hours} h"
    return f"{hours} h {format_decimal(rest)} min"


def format_clock(minutes: Fraction, start: tuple[int, int] | None = None) -> str:
    """Instante do cronograma: relativo ('T+1:05') ou absoluto a partir de `start` ('15:05').

    Segundos aparecem só quando o instante não cai num minuto inteiro ('T+0:01:30').
    """
    seconds = round(minutes * 60)
    if start is None:
        return "T+" + _hours_minutes_seconds(seconds, pad_hours=False)
    seconds += (start[0] * 60 + start[1]) * 60
    days, seconds = divmod(seconds, SECONDS_PER_DAY)
    return _hours_minutes_seconds(seconds, pad_hours=True) + (f" (+{days}d)" if days else "")


def _hours_minutes_seconds(seconds: int, pad_hours: bool) -> str:
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    text = f"{hours:02d}:{minutes:02d}" if pad_hours else f"{hours}:{minutes:02d}"
    return text + (f":{seconds:02d}" if seconds else "")
