"""Dimensões físicas, tabela de unidades e conversões."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Iterable, Iterator


class Dimension(Enum):
    """Dimensão de uma quantidade. ESCALAR representa número sem unidade."""

    MASSA = "massa"
    VOLUME = "volume"
    CONTAGEM = "contagem"
    TEMPO = "tempo"
    ESCALAR = "escalar"

    @property
    def base_unit(self) -> str | None:
        return _BASE_UNITS.get(self)

    def describe(self) -> str:
        """Nome da dimensão com a unidade base, como aparece nas mensagens: 'massa (g)'."""
        base = self.base_unit
        return f"{self.value} ({base})" if base else self.value


_BASE_UNITS: dict[Dimension, str] = {
    Dimension.MASSA: "g",
    Dimension.VOLUME: "ml",
    Dimension.CONTAGEM: "un",
    Dimension.TEMPO: "min",
}


class UnitError(ValueError):
    """Operação inválida sobre unidades (conversão ou registro)."""


@dataclass(frozen=True)
class Unit:
    """Unidade de medida: `factor` é quanto 1 desta unidade vale na unidade base."""

    name: str
    dimension: Dimension
    factor: Fraction

    def to_base(self, value: Fraction) -> Fraction:
        return value * self.factor

    def from_base(self, value: Fraction) -> Fraction:
        return value / self.factor


NATIVE_UNITS: tuple[Unit, ...] = (
    Unit("mg", Dimension.MASSA, Fraction(1, 1000)),
    Unit("g", Dimension.MASSA, Fraction(1)),
    Unit("kg", Dimension.MASSA, Fraction(1000)),
    Unit("ml", Dimension.VOLUME, Fraction(1)),
    Unit("l", Dimension.VOLUME, Fraction(1000)),
    Unit("xicara", Dimension.VOLUME, Fraction(240)),
    Unit("colher_sopa", Dimension.VOLUME, Fraction(15)),
    Unit("colher_cha", Dimension.VOLUME, Fraction(5)),
    Unit("un", Dimension.CONTAGEM, Fraction(1)),
    Unit("duzia", Dimension.CONTAGEM, Fraction(12)),
    Unit("s", Dimension.TEMPO, Fraction(1, 60)),
    Unit("min", Dimension.TEMPO, Fraction(1)),
    Unit("h", Dimension.TEMPO, Fraction(60)),
)


class UnitTable:
    """Tabela de unidades conhecidas: as nativas mais as declaradas no programa."""

    def __init__(self, units: Iterable[Unit] = NATIVE_UNITS) -> None:
        self._units: dict[str, Unit] = {}
        for unit in units:
            self.register(unit)

    def __contains__(self, name: object) -> bool:
        return name in self._units

    def __iter__(self) -> Iterator[Unit]:
        return iter(self._units.values())

    def __len__(self) -> int:
        return len(self._units)

    def get(self, name: str) -> Unit | None:
        return self._units.get(name)

    def lookup(self, name: str) -> Unit:
        """Retorna a unidade `name` ou lança UnitError se ela não existir."""
        unit = self._units.get(name)
        if unit is None:
            raise UnitError(f"unidade '{name}' inexistente")
        return unit

    def register(self, unit: Unit) -> None:
        """Adiciona uma unidade; rejeita nomes repetidos, dimensão escalar e fator não positivo."""
        if unit.name in self._units:
            raise UnitError(f"unidade '{unit.name}' já declarada")
        if unit.dimension is Dimension.ESCALAR:
            raise UnitError(f"unidade '{unit.name}' precisa ter dimensão não escalar")
        if unit.factor <= 0:
            raise UnitError(f"unidade '{unit.name}' precisa ter valor positivo")
        self._units[unit.name] = unit

    def define(self, name: str, value: Fraction, unit_name: str) -> Unit:
        """Declara `name` como `value unit_name` (ex.: pitada = 0.5 g) e a registra."""
        base = self.lookup(unit_name)
        unit = Unit(name, base.dimension, base.to_base(Fraction(value)))
        self.register(unit)
        return unit

    def convert(self, value: Fraction, source: str, target: str) -> Fraction:
        """Converte `value` de `source` para `target`; exige a mesma dimensão."""
        src = self.lookup(source)
        dst = self.lookup(target)
        if src.dimension is not dst.dimension:
            raise UnitError(
                f"não é possível converter {src.dimension.describe()} "
                f"em {dst.dimension.describe()}"
            )
        return dst.from_base(src.to_base(Fraction(value)))

    def to_base(self, value: Fraction, unit_name: str) -> Fraction:
        """Converte `value unit_name` para a unidade base da sua dimensão."""
        return self.lookup(unit_name).to_base(Fraction(value))
