"""Kaggle-loadable agent: route selector over a 4-route portfolio.

Loads four v4-variant route YAMLs embedded as string literals, wraps each
with the micro-controller, and dispatches per turn through
:class:`RouteSelector`. Selection fires at the end of day 2 using signals
from the shared opponent inventory tracker.

All portfolio members share the same physical setup (wheat at (3, 4),
carrots at (4, 4) and (3, 3), coop with goose at (4, 3), one hire per
day from day 3, no land buys). Only market policy differs, so the switch
is consistent with actions already emitted.
"""

from __future__ import annotations

from typing import Any

import yaml

from kaggriculture.agent.route_agent.loader import route_from_dict
from kaggriculture.agent.route_agent.micro import wrap_with_micro
from kaggriculture.agent.route_agent.runner import RouteAgent
from kaggriculture.agent.route_agent.selector import build_default_selector

_PORTFOLIO_YAML: dict[str, str] = {
    "v4_baseline": """
name: v4_baseline
description: v4 baseline port.
crops:
  - {tile: [3, 4], crop: WHEAT}
  - {tile: [4, 4], crop: CARROT}
  - {tile: [3, 3], crop: CARROT}
structures:
  - {tile: [4, 3], kind: COOP, animal: GOOSE}
hand:
  primary_tiles: [[3, 3]]
  fallback_tiles: [[4, 4], [3, 4]]
land_buys: []
market_policy:
  seed_buy_order: [WHEAT, CARROT]
  animal_buy_order: [GOOSE]
  hire:
    from_day: 3
    per_day: 1
    price_cap: 10
  feed_stockpiles:
    - {product: WHEAT, for_animal: GOOSE, buy_below: 20, cap: 10, reserve: 2}
  sell_order: [WHEAT, CARROT, EGG, FERTILIZER]
  sell_min_price:
    WHEAT: 25
    CARROT: 35
    EGG: 50
    FERTILIZER: 90
  liquidate_from_day: 29
  shed_high_water: 80
""",
    "v4_wheat_agg": """
name: v4_wheat_agg
description: aggressive wheat / carrot sells, earlier liquidate.
crops:
  - {tile: [3, 4], crop: WHEAT}
  - {tile: [4, 4], crop: CARROT}
  - {tile: [3, 3], crop: CARROT}
structures:
  - {tile: [4, 3], kind: COOP, animal: GOOSE}
hand:
  primary_tiles: [[3, 3]]
  fallback_tiles: [[4, 4], [3, 4]]
land_buys: []
market_policy:
  seed_buy_order: [WHEAT, CARROT]
  animal_buy_order: [GOOSE]
  hire:
    from_day: 3
    per_day: 1
    price_cap: 10
  feed_stockpiles:
    - {product: WHEAT, for_animal: GOOSE, buy_below: 20, cap: 10, reserve: 2}
  sell_order: [WHEAT, CARROT, EGG, FERTILIZER]
  sell_min_price:
    WHEAT: 22
    CARROT: 32
    EGG: 50
    FERTILIZER: 90
  liquidate_from_day: 28
  shed_high_water: 80
""",
    "v4_premium_hold": """
name: v4_premium_hold
description: hold eggs longer, larger wheat stockpile.
crops:
  - {tile: [3, 4], crop: WHEAT}
  - {tile: [4, 4], crop: CARROT}
  - {tile: [3, 3], crop: CARROT}
structures:
  - {tile: [4, 3], kind: COOP, animal: GOOSE}
hand:
  primary_tiles: [[3, 3]]
  fallback_tiles: [[4, 4], [3, 4]]
land_buys: []
market_policy:
  seed_buy_order: [WHEAT, CARROT]
  animal_buy_order: [GOOSE]
  hire:
    from_day: 3
    per_day: 1
    price_cap: 10
  feed_stockpiles:
    - {product: WHEAT, for_animal: GOOSE, buy_below: 22, cap: 14, reserve: 3}
  sell_order: [EGG, WHEAT, CARROT, FERTILIZER]
  sell_min_price:
    WHEAT: 25
    CARROT: 35
    EGG: 55
    FERTILIZER: 90
  liquidate_from_day: 29
  shed_high_water: 80
""",
    "v4_early_tail": """
name: v4_early_tail
description: earlier tail liquidation, halved shed high water.
crops:
  - {tile: [3, 4], crop: WHEAT}
  - {tile: [4, 4], crop: CARROT}
  - {tile: [3, 3], crop: CARROT}
structures:
  - {tile: [4, 3], kind: COOP, animal: GOOSE}
hand:
  primary_tiles: [[3, 3]]
  fallback_tiles: [[4, 4], [3, 4]]
land_buys: []
market_policy:
  seed_buy_order: [WHEAT, CARROT]
  animal_buy_order: [GOOSE]
  hire:
    from_day: 3
    per_day: 1
    price_cap: 10
  feed_stockpiles:
    - {product: WHEAT, for_animal: GOOSE, buy_below: 20, cap: 10, reserve: 2}
  sell_order: [WHEAT, CARROT, EGG, FERTILIZER]
  sell_min_price:
    WHEAT: 25
    CARROT: 35
    EGG: 50
    FERTILIZER: 90
  liquidate_from_day: 27
  shed_high_water: 40
""",
}


def _build_portfolio() -> dict[str, Any]:
    portfolio: dict[str, Any] = {}
    micro_kwargs = {"tail_start_day": 22, "salvage_ratio": 0.85}
    for key, text in _PORTFOLIO_YAML.items():
        route = route_from_dict(yaml.safe_load(text))
        ra = RouteAgent(route)
        thresholds = dict(route.market_policy.sell_min_price)

        def _base(obs: dict[str, Any], _ra: RouteAgent = ra) -> dict[str, Any]:
            return _ra(obs)

        portfolio[key] = wrap_with_micro(_base, sell_thresholds=thresholds, **micro_kwargs)
    return portfolio


_agent = build_default_selector(_build_portfolio(), default_key="v4_baseline")


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    return _agent(obs)
