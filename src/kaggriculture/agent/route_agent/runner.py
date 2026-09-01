"""RouteAgent: consumes a `Route` and produces per-turn actions.

The decision tree mirrors the v4 baseline. Given the right route YAML the
runner reproduces v4's rewards on a fixed seed. The tree is parameterised on
route entries (tile assignments, coop / pasture location, hire schedule, land
buys, market policy) so other routes can share the runner.

Later milestones will layer a micro-controller on top; this file stays
observation -> action, no external state.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from kaggriculture.agent.route_agent.loader import load_route
from kaggriculture.agent.route_agent.schema import Route, StructureAssignment
from kaggriculture.env.constants import ANIMALS, CROPS

_TURNS_PER_DAY: Final[int] = 24
# NW shed access tiles are fixed by the environment.
_SHED_ACCESS: Final[frozenset[tuple[int, int]]] = frozenset({(4, 4), (5, 4), (4, 5), (5, 5)})
_HOME: Final[tuple[int, int]] = (4, 4)
_LAND_PRICES: Final[dict[str, int]] = {"NE": 1000, "SW": 2000, "SE": 4000}


def _crop_cap(crop: str, fertilized: bool) -> int:
    spec = CROPS[crop]
    return spec["max_yield"] if fertilized else spec["max_yield_day"]


def _first_yield_day(crop: str) -> int:
    return CROPS[crop]["first_yield_day"]


def _step_towards(fx: int, fy: int, tx: int, ty: int) -> list[Any]:
    if fx < tx:
        return ["EAST"]
    if fx > tx:
        return ["WEST"]
    if fy < ty:
        return ["SOUTH"]
    return ["NORTH"]


def _crop_needed_op(
    tile: Any,
    crop: str,
    day: int,
    hour: int,
    seeds: int,
    carrying_fert: bool,
) -> str | None:
    if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
        if not tile.get("watered_today"):
            return "WATER"
        age = day - int(tile["planted_day"])
        yield_units = int(tile.get("yield_units", 0))
        fertilized = int(tile.get("fertilized_until_day", -1)) >= day
        cap = _crop_cap(crop, fertilized)
        if yield_units >= cap and age >= _first_yield_day(crop):
            return "HARVEST"
        if carrying_fert and not fertilized and age == _first_yield_day(crop):
            return "FERTILIZE"
        return None
    if tile is None and seeds > 0 and hour < _TURNS_PER_DAY - 1:
        return "PLANT"
    return None


def _hand_op(
    hx: int,
    hy: int,
    tiles: list[list[Any]],
    day: int,
    hour: int,
    seeds: dict[str, int],
    primary: list[tuple[tuple[int, int], str]],
    fallback: list[tuple[tuple[int, int], str]],
) -> list[Any]:
    for group in (primary, fallback):
        for (tx, ty), _crop in group:
            tile = tiles[ty][tx]
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and not tile.get("watered_today")
            ):
                if (hx, hy) == (tx, ty):
                    return ["WATER"]
                return _step_towards(hx, hy, tx, ty)
        for (tx, ty), crop in group:
            tile = tiles[ty][tx]
            if not (
                isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop
            ):
                continue
            age = day - int(tile.get("planted_day", day))
            fertilized = int(tile.get("fertilized_until_day", -1)) >= day
            cap = _crop_cap(crop, fertilized)
            if int(tile.get("yield_units", 0)) >= cap and age >= _first_yield_day(crop):
                if (hx, hy) == (tx, ty):
                    return ["HARVEST"]
                return _step_towards(hx, hy, tx, ty)
        for (tx, ty), crop in group:
            tile = tiles[ty][tx]
            if tile is None and seeds.get(crop, 0) > 0 and hour < _TURNS_PER_DAY - 1:
                if (hx, hy) == (tx, ty):
                    return ["PLANT", crop]
                return _step_towards(hx, hy, tx, ty)
    return ["PASS"]


class RouteAgent:
    """Kaggle-callable agent driven by a `Route`."""

    def __init__(self, route: Route) -> None:
        self.route = route
        self._crop_by_tile: dict[tuple[int, int], str] = {
            (c.tile[0], c.tile[1]): c.crop for c in route.crops
        }
        self._structure_by_tile: dict[tuple[int, int], StructureAssignment] = {
            (s.tile[0], s.tile[1]): s for s in route.structures
        }
        self._structures_by_animal: dict[str, StructureAssignment] = {
            s.animal: s for s in route.structures
        }
        self._hand_primary: list[tuple[tuple[int, int], str]] = self._resolve_hand(
            route.hand.primary_tiles
        )
        self._hand_fallback: list[tuple[tuple[int, int], str]] = self._resolve_hand(
            route.hand.fallback_tiles
        )
        self._overrides: dict[tuple[int, str], list[Any]] = {
            (o.turn, o.unit): o.action for o in route.overrides
        }

    def _resolve_hand(
        self, tiles: tuple[tuple[int, int], ...]
    ) -> list[tuple[tuple[int, int], str]]:
        return [(t, self._crop_by_tile[t]) for t in tiles if t in self._crop_by_tile]

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        return self._decide(obs)

    def _decide(self, obs: dict[str, Any]) -> dict[str, Any]:
        player = int(obs.get("player", 0))
        farms = obs.get("farms", [])
        private = obs.get("private", {}) or {}
        if not farms or player >= len(farms):
            return {"farmer": ["PASS"], "hands": [], "market": []}

        me = farms[player]
        fx, fy = me["farmer"]
        tiles = me["tiles"]
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        step = int(obs.get("step", day * _TURNS_PER_DAY + hour))
        seeds: dict[str, int] = private.get("seeds", {}) or {}
        shed: dict[str, int] = private.get("shed", {}) or {}
        inventories = private.get("inventories", [{}]) or [{}]
        farmer_inv: dict[str, int] = inventories[0] if inventories else {}
        money = float(me.get("money", 0.0))
        market_prices: dict[str, int] = (obs.get("market", {}) or {}).get("prices", {}) or {}
        hands_positions = [tuple(p) for p in me.get("hands", [])]
        unlocked: set[str] = set(me.get("unlocked_quadrants", ["NW"]))
        hires_today = int(me.get("hires_today", 0))

        market = self._market_actions(
            day=day,
            money=money,
            seeds=seeds,
            shed=shed,
            farmer_inv=farmer_inv,
            market_prices=market_prices,
            tiles=tiles,
            hires_today=hires_today,
            unlocked=unlocked,
        )

        def hand_ops() -> list[list[Any]]:
            return [
                _hand_op(
                    hx,
                    hy,
                    tiles,
                    day,
                    hour,
                    seeds,
                    self._hand_primary,
                    self._hand_fallback,
                )
                for hx, hy in hands_positions
            ]

        def resp(farmer_op: list[Any]) -> dict[str, Any]:
            hops = hand_ops()
            # Apply per-turn overrides on top.
            if (step, "farmer") in self._overrides:
                farmer_op = self._overrides[(step, "farmer")]
            for i in range(len(hops)):
                key = (step, f"hand:{i}")
                if key in self._overrides:
                    hops[i] = self._overrides[key]
            return {"farmer": farmer_op, "hands": hops, "market": market}

        farmer_op = self._farmer_action(
            fx=fx,
            fy=fy,
            tiles=tiles,
            day=day,
            hour=hour,
            seeds=seeds,
            shed=shed,
            farmer_inv=farmer_inv,
        )
        return resp(farmer_op)

    def _farmer_action(
        self,
        *,
        fx: int,
        fy: int,
        tiles: list[list[Any]],
        day: int,
        hour: int,
        seeds: dict[str, int],
        shed: dict[str, int],
        farmer_inv: dict[str, int],
    ) -> list[Any]:
        # Pick up / deliver / place each configured animal that is not yet placed.
        for animal, struct in self._structures_by_animal.items():
            tx, ty = struct.tile
            struct_tile = tiles[ty][tx]
            struct_built = isinstance(struct_tile, dict) and struct_tile.get("kind") == struct.kind
            animal_placed = struct_built and struct_tile.get("animal") == animal
            if animal_placed:
                continue
            if int(shed.get(animal, 0)) > 0 and int(farmer_inv.get(animal, 0)) == 0:
                if (fx, fy) in _SHED_ACCESS:
                    return ["PICKUP", animal, 1]
                return _step_towards(fx, fy, *_HOME)
            if int(farmer_inv.get(animal, 0)) > 0:
                if (fx, fy) == (tx, ty) and struct_built:
                    return ["PLACE", animal, 1]
                if (fx, fy) == (tx, ty) and struct_tile is None:
                    return self._build_op(struct)
                return _step_towards(fx, fy, tx, ty)
            if not struct_built and struct_tile is None:
                if (fx, fy) == (tx, ty):
                    return self._build_op(struct)
                return _step_towards(fx, fy, tx, ty)

        # Tend each placed animal.
        for animal, struct in self._structures_by_animal.items():
            tx, ty = struct.tile
            struct_tile = tiles[ty][tx]
            if not (isinstance(struct_tile, dict) and struct_tile.get("animal") == animal):
                continue
            op = self._tend_animal_at(
                fx=fx,
                fy=fy,
                struct_tile=struct_tile,
                tx=tx,
                ty=ty,
                shed=shed,
                farmer_inv=farmer_inv,
            )
            if op is not None:
                return op

        # Drop carried produce at the shed.
        carrying_produce = any(int(farmer_inv.get(p, 0)) > 0 for p in _CARRIABLE_PRODUCE)
        if carrying_produce and (fx, fy) in _SHED_ACCESS:
            return ["DROP"]

        # Tend crops in route order.
        carrying_fert = int(farmer_inv.get("FERTILIZER", 0)) > 0
        for crop_assign in self.route.crops:
            tx, ty = crop_assign.tile
            tile = tiles[ty][tx]
            crop_op = _crop_needed_op(
                tile, crop_assign.crop, day, hour, seeds.get(crop_assign.crop, 0), carrying_fert
            )
            if crop_op is None:
                continue
            if (fx, fy) == (tx, ty):
                return [crop_op] if crop_op != "PLANT" else ["PLANT", crop_assign.crop]
            return _step_towards(fx, fy, tx, ty)

        return ["PASS"]

    def _tend_animal_at(
        self,
        *,
        fx: int,
        fy: int,
        struct_tile: dict[str, Any],
        tx: int,
        ty: int,
        shed: dict[str, int],
        farmer_inv: dict[str, int],
    ) -> list[Any] | None:
        eggs_ready = int(struct_tile.get("yield_units", 0)) > 0
        needs_feed = not bool(struct_tile.get("fed_today", False))
        needs_care = not bool(struct_tile.get("cared_today", False))
        fert_available = bool(struct_tile.get("fertilizer_available", False))
        # Every configured animal in this repo eats WHEAT.
        feed_product = "WHEAT"
        has_feed = int(farmer_inv.get(feed_product, 0)) > 0

        if (fx, fy) == (tx, ty):
            if eggs_ready:
                return ["HARVEST"]
            if needs_feed and has_feed:
                return ["FEED"]
            if fert_available:
                return ["COLLECT_FERTILIZER"]
            if needs_care and not needs_feed:
                return ["CARE"]
        elif eggs_ready or fert_available or (needs_feed and has_feed):
            return _step_towards(fx, fy, tx, ty)
        if needs_feed and not has_feed and int(shed.get(feed_product, 0)) > 0:
            if (fx, fy) in _SHED_ACCESS:
                return ["PICKUP", feed_product, 1]
            return _step_towards(fx, fy, *_HOME)
        return None

    @staticmethod
    def _build_op(struct: StructureAssignment) -> list[Any]:
        if struct.kind == "COOP":
            return ["BUILD_COOP"]
        if struct.kind == "PASTURE":
            return ["BUILD_PASTURE"]
        raise ValueError(f"unknown structure kind: {struct.kind!r}")

    def _market_actions(
        self,
        *,
        day: int,
        money: float,
        seeds: dict[str, int],
        shed: dict[str, int],
        farmer_inv: dict[str, int],
        market_prices: dict[str, int],
        tiles: list[list[Any]],
        hires_today: int,
        unlocked: set[str],
    ) -> list[list[Any]]:
        mp = self.route.market_policy
        market: list[list[Any]] = []

        # Seed buys, in explicit order.
        for crop in mp.seed_buy_order:
            if seeds.get(crop, 0) == 0 and money >= CROPS[crop]["seed"]:
                market.append(["BUY_SEED", crop, 1])

        # Animal buys, gated on the associated crop pipeline having produced feed.
        for animal in mp.animal_buy_order:
            struct = self._structures_by_animal.get(animal)
            if struct is None:
                continue
            already_owned = self._animal_owned(animal, shed, farmer_inv, tiles, struct)
            if already_owned:
                continue
            if not self._feed_pipeline_ready(animal, day, shed, farmer_inv, tiles):
                continue
            price = _animal_price(animal)
            if money >= price:
                market.append(["BUY_ANIMAL", animal, 1])

        # Land buys.
        for lb in self.route.land_buys:
            if lb.quadrant in unlocked:
                continue
            if day < lb.from_day:
                continue
            price = _LAND_PRICES.get(lb.quadrant, 0)
            if money >= max(price, lb.money_buffer):
                market.append(["BUY_LAND", lb.quadrant])

        # Hire.
        if (
            mp.hire is not None
            and day >= mp.hire.from_day
            and hires_today < mp.hire.per_day
            and money >= mp.hire.price_cap
        ):
            market.append(["HIRE"])

        # Feed stockpile buys.
        for fs in mp.feed_stockpiles:
            struct = self._structures_by_animal.get(fs.for_animal)
            placed = struct is not None and self._animal_placed(fs.for_animal, tiles, struct)
            if not placed:
                continue
            total_on_hand = int(shed.get(fs.product, 0)) + int(farmer_inv.get(fs.product, 0))
            price = int(market_prices.get(fs.product, 0))
            if total_on_hand < fs.cap and 0 < price <= fs.buy_below and money >= price:
                market.append(["BUY_PRODUCT", fs.product, 1])
            if total_on_hand == 0:
                market.append(["BUY_PRODUCT", fs.product, 1])

        # Sells.
        shed_load = sum(int(v) for v in shed.values())
        liquidate = day >= mp.liquidate_from_day or shed_load >= mp.shed_high_water
        reserve_by_product = _reserve_by_product(
            mp.feed_stockpiles, tiles, self._structures_by_animal
        )
        for product in mp.sell_order:
            n = int(shed.get(product, 0))
            reserve = reserve_by_product.get(product, 0)
            sellable = n - reserve
            if sellable <= 0:
                continue
            price = int(market_prices.get(product, 0))
            min_price = mp.sell_min_price.get(product, 1)
            if liquidate or price >= min_price:
                market.append(["SELL", product, sellable])
        return market

    @staticmethod
    def _animal_placed(animal: str, tiles: list[list[Any]], struct: StructureAssignment) -> bool:
        tx, ty = struct.tile
        struct_tile = tiles[ty][tx]
        return (
            isinstance(struct_tile, dict)
            and struct_tile.get("kind") == struct.kind
            and struct_tile.get("animal") == animal
        )

    def _animal_owned(
        self,
        animal: str,
        shed: dict[str, int],
        farmer_inv: dict[str, int],
        tiles: list[list[Any]],
        struct: StructureAssignment,
    ) -> bool:
        return int(shed.get(animal, 0)) + int(farmer_inv.get(animal, 0)) > 0 or self._animal_placed(
            animal, tiles, struct
        )

    def _feed_pipeline_ready(
        self,
        animal: str,
        day: int,
        shed: dict[str, int],
        farmer_inv: dict[str, int],
        tiles: list[list[Any]],
    ) -> bool:
        """Buy the animal only once feed production is close, matching v4."""
        mp = self.route.market_policy
        feed_product = "WHEAT"
        need = 2
        for fs in mp.feed_stockpiles:
            if fs.for_animal == animal:
                feed_product = fs.product
                need = fs.reserve
                break
        on_hand = int(shed.get(feed_product, 0)) + int(farmer_inv.get(feed_product, 0))
        if on_hand >= need:
            return True
        threshold = _first_yield_day(feed_product)
        for crop_assign in self.route.crops:
            if crop_assign.crop != feed_product:
                continue
            tx, ty = crop_assign.tile
            tile = tiles[ty][tx]
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and tile.get("crop") == feed_product
                and day - int(tile.get("planted_day", day)) >= threshold
            ):
                return True
        return False


_CARRIABLE_PRODUCE: Final[tuple[str, ...]] = (
    "EGG",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "MILK",
    "WOOL",
)


def _animal_price(animal: str) -> int:
    return int(ANIMALS[animal]["cost"])


def _reserve_by_product(
    feed_stockpiles: tuple[Any, ...],
    tiles: list[list[Any]],
    structures_by_animal: dict[str, StructureAssignment],
) -> dict[str, int]:
    """Reserve is only enforced while the associated animal is placed."""
    reserve: dict[str, int] = {}
    for fs in feed_stockpiles:
        struct = structures_by_animal.get(fs.for_animal)
        if struct is None:
            continue
        tx, ty = struct.tile
        st = tiles[ty][tx]
        placed = (
            isinstance(st, dict)
            and st.get("kind") == struct.kind
            and st.get("animal") == fs.for_animal
        )
        if placed:
            reserve[fs.product] = max(reserve.get(fs.product, 0), fs.reserve)
    return reserve


def agent_from_yaml(path: str | Path) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Load `path` and return a Kaggle-compatible `agent(obs)` closure."""
    route = load_route(path)
    ra = RouteAgent(route)

    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return ra(obs)

    return agent
