"""Typed views over the raw observation dict.

The kaggle-environments observation is a nested dict. Agents index into it
directly hundreds of times per turn. These dataclasses give the same access
with typed attributes and `me`/`opponent` shortcuts, at the cost of one
`Observation.from_dict(obs)` call per turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

Quadrant: TypeAlias = Literal["NW", "NE", "SW", "SE"]
StructureKind: TypeAlias = Literal["COOP", "PASTURE"]


@dataclass(frozen=True, slots=True)
class Empty:
    """An unlocked tile with nothing on it."""


@dataclass(frozen=True, slots=True)
class Locked:
    """A tile in a quadrant the player has not bought."""


@dataclass(frozen=True, slots=True)
class Plant:
    crop: str
    planted_day: int
    watered_today: bool
    consecutive_unwatered: int
    yield_units: int
    max_lifespan_step: int
    fertilized_until_day: int


@dataclass(frozen=True, slots=True)
class Weed:
    pass


@dataclass(frozen=True, slots=True)
class Structure:
    """Coop or pasture, optionally occupied by an animal."""

    kind: StructureKind
    animal: str | None
    placed_day: int
    yield_units: int
    fed_today: bool
    consecutive_unfed: int
    cared_today: bool
    fertilizer_available: bool
    pending_care_bonus: int


Tile: TypeAlias = Empty | Locked | Plant | Weed | Structure


def _parse_tile(raw: Any) -> Tile:
    if raw is None:
        return Empty()
    if raw == "LOCKED":
        return Locked()
    if not isinstance(raw, dict):
        raise ValueError(f"unexpected tile: {raw!r}")
    kind = raw.get("kind")
    if kind == "PLANT":
        return Plant(
            crop=raw["crop"],
            planted_day=int(raw["planted_day"]),
            watered_today=bool(raw["watered_today"]),
            consecutive_unwatered=int(raw["consecutive_unwatered"]),
            yield_units=int(raw["yield_units"]),
            max_lifespan_step=int(raw["max_lifespan_step"]),
            fertilized_until_day=int(raw["fertilized_until_day"]),
        )
    if kind == "WEED":
        return Weed()
    if kind in ("COOP", "PASTURE"):
        return Structure(
            kind=kind,
            animal=raw.get("animal"),
            placed_day=int(raw.get("placed_day", 0)),
            yield_units=int(raw.get("yield_units", 0)),
            fed_today=bool(raw.get("fed_today", False)),
            consecutive_unfed=int(raw.get("consecutive_unfed", 0)),
            cared_today=bool(raw.get("cared_today", False)),
            fertilizer_available=bool(raw.get("fertilizer_available", False)),
            pending_care_bonus=int(raw.get("pending_care_bonus", 0)),
        )
    raise ValueError(f"unknown tile kind: {kind!r}")


@dataclass(frozen=True, slots=True)
class Farm:
    money: float
    tiles: tuple[tuple[Tile, ...], ...]
    farmer: tuple[int, int]
    hands: tuple[tuple[int, int], ...]
    unlocked_quadrants: tuple[Quadrant, ...]
    hires_today: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Farm:
        return cls(
            money=float(d["money"]),
            tiles=tuple(tuple(_parse_tile(t) for t in row) for row in d["tiles"]),
            farmer=(int(d["farmer"][0]), int(d["farmer"][1])),
            hands=tuple((int(h[0]), int(h[1])) for h in d.get("hands", [])),
            unlocked_quadrants=tuple(d.get("unlocked_quadrants", ["NW"])),
            hires_today=int(d.get("hires_today", 0)),
        )


@dataclass(frozen=True, slots=True)
class Market:
    inventory: dict[str, int]
    prices: dict[str, int]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Market:
        return cls(
            inventory={k: int(v) for k, v in d.get("inventory", {}).items()},
            prices={k: int(v) for k, v in d.get("prices", {}).items()},
        )


@dataclass(frozen=True, slots=True)
class Town:
    unlocked_shops: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Town:
        return cls(unlocked_shops=tuple(d.get("unlocked_shops", [])))


@dataclass(frozen=True, slots=True)
class Private:
    shed: dict[str, int]
    seeds: dict[str, int]
    # inventories[0] = main farmer; hands appended each day.
    inventories: tuple[dict[str, int], ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Private:
        return cls(
            shed={k: int(v) for k, v in d.get("shed", {}).items()},
            seeds={k: int(v) for k, v in d.get("seeds", {}).items()},
            inventories=tuple(
                {k: int(v) for k, v in inv.items()} for inv in d.get("inventories", [{}])
            ),
        )


@dataclass(frozen=True, slots=True)
class Observation:
    player: int
    step: int
    day: int
    hour: int
    farms: tuple[Farm, ...]
    market: Market
    town: Town
    private: Private

    @property
    def me(self) -> Farm:
        return self.farms[self.player]

    @property
    def opponent(self) -> Farm:
        return self.farms[1 - self.player]

    @classmethod
    def from_dict(cls, obs: dict[str, Any]) -> Observation:
        return cls(
            player=int(obs["player"]),
            step=int(obs.get("step", 0)),
            day=int(obs.get("day", 0)),
            hour=int(obs.get("hour", 0)),
            farms=tuple(Farm.from_dict(f) for f in obs["farms"]),
            market=Market.from_dict(obs.get("market", {})),
            town=Town.from_dict(obs.get("town", {})),
            private=Private.from_dict(obs.get("private", {})),
        )
