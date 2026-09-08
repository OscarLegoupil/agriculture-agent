"""Derive a phased route from the economic model.

`configs/routes/expansion_full.yaml` places every tile by hand. This module
produces the same shape from `build_phased_plan`, so a change to the ROI
tables or a price forecast moves the route instead of being argued about in a
config diff. Its output is what ships: the generated route beats the
hand-authored one 189-11 over 200 paired seats.

The split of responsibilities:

- The allocator decides counts. How many of each animal, how many wheat tiles
  the roster needs, which crop fills the rest, and how many hands each phase
  is budgeted for.
- This module decides addresses. Structures take the tiles closest to the
  shed because they want a worker visit and a wheat delivery every day; wheat
  goes next to them; the fill crop takes what is left. Addresses are assigned
  once from the largest phase and every earlier phase takes a prefix, so a
  tile never changes its job mid-season.

Two things are added on top of the allocator:

- Volume-aware pricing. The allocator prices everything at base and values a
  tile the same whether it is the first melon tile or the twenty-fifth, but a
  plan that sells 400 melons realises an average far under base, and the milk
  and wool curves floor after 76 and 58 units. `generate_route` therefore
  proposes a family of plans (a herd ceiling sweep, each repriced against its
  own projected volumes) and scores every one of them with the same
  volume-aware `plan_revenue`, rather than trusting whatever the last
  repricing pass happened to land on. Repricing alone oscillates between
  corner solutions precisely because the allocator's revenue is linear in
  tiles; scoring the candidates settles it.
- A tail substitution. A phase that starts too late for its fill crop to
  ripen gets the best crop that still can, instead of planting melons that
  will never be picked.

The model ranks shapes well and misses the last few percent, so `main` plays
the shortlist out against an opponent and caches the winner rather than
trusting the top-scoring plan. That distinction is what found the shipped
route: the model's own favourite is a twelve-animal roster split evenly
across three species, which earns slightly less than a goose-heavy one
against a weak opponent but wins the head-to-head, because a herd spread over
three product markets is not competing with the opponent for the same one.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import yaml

from kaggriculture.agent.route_agent.loader import route_to_dict, write_route
from kaggriculture.agent.route_agent.scheduler import SEASON_DAYS, harvest_age, shed_access_tiles
from kaggriculture.agent.route_agent.schema import (
    CropAssignment,
    HandAssignment,
    LandBuy,
    MarketPolicy,
    Phase,
    Route,
    StructureAssignment,
)
from kaggriculture.env.constants import ANIMALS, CROPS, LAND_ORDER, MARKET_PARAMS
from kaggriculture.market.forecaster import average_sale_price
from kaggriculture.planning.crop_roi import crop_roi
from kaggriculture.planning.phased_allocator import PhasedPlan, build_phased_plan
from kaggriculture.search.evaluate import evaluate_config

BOARD_SIZE: Final[int] = 10
# Buy order runs cheapest-first: a goose pays for itself fastest, and every
# species earns the same fertilizer stream regardless of price.
ANIMAL_ORDER: Final[tuple[str, ...]] = ("GOOSE", "COW", "SHEEP")
FILL_CANDIDATES: Final[tuple[str, ...]] = ("MELON", "STRAWBERRY", "TOMATO", "CARROT")


def _ceiling_families() -> tuple[dict[str, int], ...]:
    """Per-species head-count ceilings the plan search sweeps.

    The allocator is free to buy fewer; the ceilings exist because its revenue
    is linear in head count, so an uncapped run always proposes the largest
    roster the tiles allow. Two families: a flat one, and one that grows geese
    faster, because the egg curve absorbs several times the units the milk and
    wool curves do before they floor.
    """
    flat = [dict.fromkeys(ANIMAL_ORDER, c) for c in (0, 2, 4, 6, 8, 10)]
    goose_led = [
        {"GOOSE": g, "COW": max(1, g // 2), "SHEEP": max(1, g // 4)} for g in (4, 8, 12, 16)
    ]
    return tuple(flat + goose_led)


HERD_CEILINGS: Final[tuple[dict[str, int], ...]] = _ceiling_families()


def quadrant_tiles(quadrant: str, board_size: int = BOARD_SIZE) -> list[tuple[int, int]]:
    half = board_size // 2
    xs = range(0, half) if quadrant.endswith("W") else range(half, board_size)
    ys = range(0, half) if quadrant.startswith("N") else range(half, board_size)
    return [(x, y) for y in ys for x in xs]


def tiles_by_shed_distance(
    quadrants: Sequence[str], board_size: int = BOARD_SIZE
) -> list[tuple[int, int]]:
    """Every tile in `quadrants`, nearest the shed first, ties broken by (x, y)."""
    shed = shed_access_tiles(board_size)
    tiles = [t for q in quadrants for t in quadrant_tiles(q, board_size)]
    return sorted(tiles, key=lambda t: (min(abs(t[0] - s[0]) + abs(t[1] - s[1]) for s in shed), t))


def best_fill_crop(*, remaining_days: int, price_map: dict[str, float] | None = None) -> str | None:
    """Highest coins-per-tile-per-day crop that still ripens in `remaining_days`."""
    best: tuple[float, str] | None = None
    for crop in FILL_CANDIDATES:
        if harvest_age(crop) > remaining_days - 1:
            continue
        price = None if price_map is None else price_map.get(crop)
        rate = crop_roi(crop, price=price).coins_per_tile_per_day
        if best is None or rate > best[0]:
            best = (rate, crop)
    return None if best is None else best[1]


def expected_volumes(plan: PhasedPlan) -> dict[str, int]:
    """Units of each product the plan would put on the market over the season.

    Crops are counted per replanting cycle that fits in the phase's remaining
    days. Animals are counted at their cared steady rate of one product unit
    per day after `first_yield_day`, plus the fertilizer unit every animal
    makes every day. Wheat is fed to the herd, not sold.
    """
    volumes: dict[str, int] = {}
    for phase in plan.phases:
        days = phase.length_days
        remaining = plan.season_days - phase.start_day
        fill = phase.allocation.fill_crop
        if fill is not None and phase.allocation.fill_crop_tiles:
            cycles = days / max(1, harvest_age(fill) + 1)
            units = CROPS[fill]["max_yield"] if CROPS[fill]["ongoing"] else _crop_units(fill)
            volumes[fill] = volumes.get(fill, 0) + round(
                phase.allocation.fill_crop_tiles * cycles * units
            )
        for animal, count in phase.allocation.animal_counts.items():
            product = ANIMALS[animal]["product"]
            producing = max(0, min(days, remaining - ANIMALS[animal]["first_yield_day"]))
            volumes[product] = volumes.get(product, 0) + count * producing
            volumes["FERTILIZER"] = volumes.get("FERTILIZER", 0) + count * days
    return volumes


def plan_revenue(plan: PhasedPlan, *, feed_price: float | None = None) -> float:
    """Season coins for `plan`, priced at what its own volumes would realise.

    This is the objective the generator argmaxes over candidate plans. Unlike
    `Allocation.expected_revenue` it is not linear in tiles: the twenty-fifth
    melon tile is worth a fraction of the first, which is what stops the
    search from running every plan to a corner.
    """
    if feed_price is None:
        feed_price = float(MARKET_PARAMS["WHEAT"]["base"])
    volumes = expected_volumes(plan)
    gross = sum(average_sale_price(item, n) * n for item, n in volumes.items())

    animals = {a: 0 for a in ANIMAL_ORDER}
    for phase in plan.phases:
        for animal, count in phase.allocation.animal_counts.items():
            animals[animal] = max(animals[animal], count)
    capex = sum(int(ANIMALS[a]["cost"]) * n for a, n in animals.items())

    feed = 0.0
    hire = 0.0
    seed = 0.0
    for phase in plan.phases:
        head = sum(phase.allocation.animal_counts.values())
        grown = min(head, phase.allocation.wheat_tiles)
        feed += (head - grown) * phase.length_days * feed_price
        hire += phase.daily_hire_cost * phase.length_days
        fill = phase.allocation.fill_crop
        if fill is not None:
            cycles = phase.length_days / max(1, harvest_age(fill) + 1)
            seed += phase.allocation.fill_crop_tiles * cycles * CROPS[fill]["seed"]
    return gross - capex - feed - hire - seed


def _crop_units(crop: str) -> int:
    spec = CROPS[crop]
    start = (spec["max_yield_day"] + 1) // 2
    return min(spec["max_yield"], 1 + (spec["max_yield_day"] - start + 1))


def _repriced(
    volumes: dict[str, int], previous: dict[str, float], damping: float
) -> dict[str, float]:
    """Blend the realised prices for `volumes` with the previous pass's prices.

    Undamped best-response iteration oscillates: a pass that prices animals at
    base buys the whole roster, which crashes milk and wool, so the next pass
    buys none, which restores the prices. Averaging with the previous pass
    settles it on the roster the market can actually absorb.
    """
    blended = dict(previous)
    for item, n in volumes.items():
        if n <= 0:
            continue
        realised = average_sale_price(item, n)
        prior = previous.get(item, float(MARKET_PARAMS[item]["base"]))
        blended[item] = damping * realised + (1.0 - damping) * prior
    return blended


def _quadrants_at(day: int, land_buy_days: dict[str, int]) -> list[str]:
    bought = [q for q in LAND_ORDER if q in land_buy_days and land_buy_days[q] <= day]
    return ["NW", *bought]


def _address_book(
    plan: PhasedPlan, land_buy_days: dict[str, int]
) -> tuple[dict[str, list[tuple[int, int]]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Assign tiles once, from the phase that runs the largest footprint.

    Returns (structure tiles per animal, wheat tiles, fill-crop tiles).
    """
    widest = max(plan.phases, key=lambda p: p.worker_tile_demand)
    ordered = tiles_by_shed_distance(_quadrants_at(widest.start_day, land_buy_days))
    peak_wheat = max(p.allocation.wheat_tiles for p in plan.phases)
    peak_fill = max(p.allocation.fill_crop_tiles for p in plan.phases)

    cursor = 0
    structures: dict[str, list[tuple[int, int]]] = {}
    for animal in ANIMAL_ORDER:
        n = max(p.allocation.animal_counts.get(animal, 0) for p in plan.phases)
        structures[animal] = ordered[cursor : cursor + n]
        cursor += len(structures[animal])
    wheat = ordered[cursor : cursor + peak_wheat]
    cursor += len(wheat)
    fill = ordered[cursor : cursor + peak_fill]
    return structures, wheat, fill


def route_from_plan(
    plan: PhasedPlan,
    *,
    name: str,
    description: str = "",
    land_buy_days: dict[str, int] | None = None,
    land_money_buffer: int = 0,
    price_map: dict[str, float] | None = None,
    money_reserve: int = 0,
    feed_days: int = 1,
    liquidate_from_day: int = 28,
) -> Route:
    """Turn a `PhasedPlan` into a phased `Route` with concrete tile addresses."""
    land_buy_days = land_buy_days or {}
    structure_tiles, wheat_tiles, fill_tiles = _address_book(plan, land_buy_days)

    phases: list[Phase] = []
    crops_used: set[str] = set()
    for phase in plan.phases:
        structures: list[StructureAssignment] = []
        for animal in ANIMAL_ORDER:
            n = phase.allocation.animal_counts.get(animal, 0)
            structures.extend(
                StructureAssignment(tile=t, kind=ANIMALS[animal]["structure"], animal=animal)
                for t in structure_tiles[animal][:n]
            )
        crops = [
            CropAssignment(tile=t, crop="WHEAT")
            for t in wheat_tiles[: phase.allocation.wheat_tiles]
        ]
        fill = phase.allocation.fill_crop
        remaining = plan.season_days - phase.start_day
        if fill is not None and harvest_age(fill) > remaining - 1:
            fill = best_fill_crop(remaining_days=remaining, price_map=price_map)
        if fill is not None:
            crops.extend(
                CropAssignment(tile=t, crop=fill)
                for t in fill_tiles[: phase.allocation.fill_crop_tiles]
            )
        crops_used.update(c.crop for c in crops)
        phases.append(
            Phase(
                from_day=phase.start_day,
                crops=tuple(crops),
                structures=tuple(structures),
                hands=phase.hands,
            )
        )

    seed_order = tuple(sorted(crops_used, key=lambda c: -crop_roi(c).coins_per_tile_per_day))
    sell_order = tuple(sorted(MARKET_PARAMS, key=lambda p: -int(MARKET_PARAMS[p]["base"])))
    return Route(
        name=name,
        description=description,
        crops=(),
        structures=(),
        hand=HandAssignment((), ()),
        land_buys=tuple(
            LandBuy(quadrant=q, money_buffer=land_money_buffer, from_day=d)
            for q, d in sorted(land_buy_days.items(), key=lambda kv: kv[1])
        ),
        market_policy=MarketPolicy(
            seed_buy_order=seed_order,
            animal_buy_order=ANIMAL_ORDER,
            hire=None,
            feed_stockpiles=(),
            sell_order=sell_order,
            sell_min_price={},
            liquidate_from_day=liquidate_from_day,
            shed_high_water=80,
            money_reserve=money_reserve,
            feed_days=feed_days,
        ),
        phases=tuple(phases),
    )


def candidate_routes(
    *,
    name: str,
    description: str = "",
    season_days: int = SEASON_DAYS,
    land_buy_days: dict[str, int] | None = None,
    hire_ramp: dict[int, int] | None = None,
    price_map: dict[str, float] | None = None,
    max_animals_per_species: dict[str, int] | None = None,
    feed_cost_per_day: float | None = None,
    money_reserve: int = 0,
    feed_days: int = 1,
    liquidate_from_day: int = 28,
    price_passes: int = 4,
    price_damping: float = 0.5,
    herd_ceilings: Sequence[dict[str, int]] = HERD_CEILINGS,
    top_k: int = 5,
) -> list[Route]:
    """The allocator's most promising plans, addressed as routes, best first.

    For every herd ceiling in `herd_ceilings` the allocator is run
    `price_passes` times, each pass repriced towards the average price the
    previous pass's volumes would realise. Distinct footprints along the way
    are scored with `plan_revenue` and the top `top_k` come back as routes.
    The model is good at ranking shapes and bad at the last few percent, so
    the driver re-ranks this shortlist by playing it.
    """
    if feed_cost_per_day is None:
        feed_cost_per_day = float(MARKET_PARAMS["WHEAT"]["base"])
    overrides = dict(price_map or {})
    hire_ramp = _with_tail_boundary(hire_ramp, season_days)

    def build(prices: dict[str, float], caps: dict[str, int] | None) -> PhasedPlan:
        return build_phased_plan(
            season_days=season_days,
            land_buy_days=land_buy_days,
            hire_ramp=hire_ramp,
            price_map=prices or None,
            feed_cost_per_day=feed_cost_per_day,
            max_animals_per_species=caps,
        )

    ceilings: list[dict[str, int] | None]
    if max_animals_per_species is not None:
        ceilings = [max_animals_per_species]
    else:
        ceilings = list(herd_ceilings)

    seen: set[tuple[tuple[str, int], ...]] = set()
    scored: list[tuple[float, PhasedPlan, dict[str, float]]] = []
    for caps in ceilings:
        prices = dict(overrides)
        plan = build(prices, caps)
        for _ in range(max(1, price_passes)):
            key = _roster_key(plan)
            if key not in seen:
                seen.add(key)
                scored.append((plan_revenue(plan, feed_price=feed_cost_per_day), plan, prices))
            prices = _repriced(expected_volumes(plan), prices, price_damping) | overrides
            plan = build(prices, caps)

    scored.sort(key=lambda s: -s[0])
    return [
        route_from_plan(
            plan,
            name=f"{name}_{i}" if i else name,
            description=description,
            land_buy_days=land_buy_days,
            price_map=prices or None,
            money_reserve=money_reserve,
            feed_days=feed_days,
            liquidate_from_day=liquidate_from_day,
        )
        for i, (_score, plan, prices) in enumerate(scored[:top_k])
    ]


def _with_tail_boundary(hire_ramp: dict[int, int] | None, season_days: int) -> dict[int, int]:
    """Add a phase boundary on the last day the best fill crop can still ripen.

    Phase boundaries otherwise only fall on land buys and hire changes, so
    without this the tail substitution in `route_from_plan` never gets a phase
    to fire on and the melon tiles sit empty for the last stretch.
    """
    ramp = dict(hire_ramp or {})
    fill = best_fill_crop(remaining_days=season_days)
    if fill is None:
        return ramp
    tail_day = season_days - harvest_age(fill)
    if tail_day <= 0 or tail_day >= season_days or tail_day in ramp:
        return ramp
    earlier = [d for d in ramp if d <= tail_day]
    ramp[tail_day] = ramp[max(earlier)] if earlier else 0
    return ramp


def _roster_key(plan: PhasedPlan) -> tuple[tuple[str, int], ...]:
    """Identity of a plan's footprint, so the sweep does not score a shape twice."""
    return tuple(
        (f"{i}:{k}", v)
        for i, phase in enumerate(plan.phases)
        for k, v in sorted(
            {
                **{a: n for a, n in phase.allocation.animal_counts.items()},
                "WHEAT": phase.allocation.wheat_tiles,
                str(phase.allocation.fill_crop): phase.allocation.fill_crop_tiles,
            }.items()
        )
    )


def generate_route(**kwargs: Any) -> Route:
    """The single highest-scoring route from `candidate_routes`."""
    return candidate_routes(**{**kwargs, "top_k": 1})[0]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="kagg-generate-route")
    ap.add_argument("--family", default="expansion", help="Opponent-family cache key")
    ap.add_argument(
        "--opponent",
        default="starter",
        help="Agent the shortlist is played against to pick the winner",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("configs") / "routes" / "tuned",
        help="Where to write the generated YAML",
    )
    ap.add_argument("--season-days", type=int, default=SEASON_DAYS)
    ap.add_argument(
        "--hire-ramp",
        default="0:4,2:7,5:9",
        help="Comma-separated day:hands pairs for the hire schedule",
    )
    ap.add_argument("--top-k", type=int, default=5, help="Shortlist size to play out")
    ap.add_argument("--eval-seeds", type=int, default=12, help="Seeds per candidate (with swap)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--feed-days", type=int, default=1)
    ap.add_argument("--money-reserve", type=int, default=0)
    ap.add_argument("--mlflow", action="store_true", help="Log the run to MLflow")
    return ap.parse_args(argv)


def _summarize(route: Route) -> str:
    final = route.phases[-1]
    herd: dict[str, int] = {}
    for s in final.structures:
        herd[s.animal] = herd.get(s.animal, 0) + 1
    crops: dict[str, int] = {}
    for c in final.crops:
        crops[c.crop] = crops.get(c.crop, 0) + 1
    return f"herd={herd} crops={crops} hands={final.hands}"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    hire_ramp = {
        int(day): int(hands)
        for day, hands in (pair.split(":") for pair in args.hire_ramp.split(","))
    }
    routes = candidate_routes(
        name=f"generated_{args.family}",
        description=(
            f"Allocator-derived phased route, picked from a {args.top_k}-plan shortlist "
            f"by paired-seed play against opponent family '{args.family}'. "
            f"Regenerate with python -m kaggriculture.agent.route_agent.generate."
        ),
        season_days=args.season_days,
        hire_ramp=hire_ramp,
        feed_days=args.feed_days,
        money_reserve=args.money_reserve,
        top_k=args.top_k,
    )

    seeds = list(range(args.eval_seeds))
    results = []
    for route in routes:
        result = evaluate_config(
            yaml_text=yaml.safe_dump(route_to_dict(route), sort_keys=False),
            micro_kwargs={},
            opponent_agent_path=args.opponent,
            seeds=seeds,
            workers=args.workers,
        )
        results.append((result, route))
        print(f"  {_summarize(route)}  score={result.score:+.3f}  gap={result.mean_gap:+.0f}")

    best_result, best_route = max(results, key=lambda r: (r[0].score, r[0].mean_gap))
    path = write_route(
        dataclasses.replace(best_route, name=f"generated_{args.family}"),
        args.out_dir / f"generated_{args.family}.yaml",
    )
    print(f"\nBEST {_summarize(best_route)}  gap={best_result.mean_gap:+.0f}\nWrote {path}")

    if args.mlflow:
        _log_to_mlflow(args, results, best_route)


def _log_to_mlflow(
    args: argparse.Namespace,
    results: list[tuple[Any, Route]],
    best: Route,
) -> None:
    import mlflow

    mlflow.set_experiment("kaggriculture")
    with mlflow.start_run(
        tags={"milestone": "M8-scale-d", "issue": "62", "opponent_family": args.family}
    ):
        mlflow.log_params(
            {
                "family": args.family,
                "opponent": args.opponent,
                "eval_seeds": args.eval_seeds,
                "top_k": args.top_k,
                "hire_ramp": args.hire_ramp,
                "n_candidates": len(results),
                "best_shape": _summarize(best),
            }
        )
        mlflow.log_metrics(
            {
                "best_score": max(r.score for r, _ in results),
                "best_mean_gap": max(r.mean_gap for r, _ in results),
            }
        )


if __name__ == "__main__":
    main()
