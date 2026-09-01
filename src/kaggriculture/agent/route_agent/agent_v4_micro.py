"""Kaggle-loadable agent: v4_baseline route wrapped with the micro-controller.

The route config is embedded as a YAML string so this file can be loaded
by `kaggle_environments` without any filesystem access. The first call
constructs the route agent and micro-controller; subsequent calls in the
same episode reuse them. When the observation step goes backwards
(episode boundary in a re-used worker), the micro-controller resets its
per-episode state.
"""

from __future__ import annotations

from typing import Any

import yaml

from kaggriculture.agent.route_agent.loader import route_from_dict
from kaggriculture.agent.route_agent.micro import wrap_with_micro
from kaggriculture.agent.route_agent.runner import RouteAgent

_V4_ROUTE_YAML = """
name: v4_baseline
description: v4 port for micro-controller A/B.
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
"""


_route = route_from_dict(yaml.safe_load(_V4_ROUTE_YAML))
_ra = RouteAgent(_route)
_agent = wrap_with_micro(
    lambda obs: _ra(obs),
    sell_thresholds=dict(_route.market_policy.sell_min_price),
)


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    return _agent(obs)
