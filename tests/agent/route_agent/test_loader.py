"""YAML loader round-trip and the v4 baseline config check."""

from __future__ import annotations

from pathlib import Path

import yaml

from kaggriculture.agent.route_agent import load_route
from kaggriculture.agent.route_agent.loader import route_from_dict

_V4_YAML = Path(__file__).resolve().parents[3] / "configs" / "routes" / "v4_baseline.yaml"


def test_v4_baseline_loads() -> None:
    route = load_route(_V4_YAML)
    assert route.name == "v4_baseline"
    tiles = {(c.tile, c.crop) for c in route.crops}
    assert ((3, 4), "WHEAT") in tiles
    assert ((4, 4), "CARROT") in tiles
    assert ((3, 3), "CARROT") in tiles
    assert len(route.structures) == 1
    assert route.structures[0].animal == "GOOSE"
    assert route.market_policy.hire is not None
    assert route.market_policy.hire.from_day == 3
    assert route.market_policy.sell_min_price["WHEAT"] == 25


def test_route_from_dict_defaults() -> None:
    raw = {
        "name": "min",
        "crops": [],
        "structures": [],
        "market_policy": {},
    }
    route = route_from_dict(raw)
    assert route.name == "min"
    assert route.market_policy.hire is None
    assert route.market_policy.feed_stockpiles == ()
    assert route.overrides == ()


def test_yaml_roundtrip_preserves_tile_coords(tmp_path: Path) -> None:
    yml = tmp_path / "r.yaml"
    yml.write_text(
        yaml.safe_dump(
            {
                "name": "rt",
                "crops": [{"tile": [2, 1], "crop": "WHEAT"}],
                "structures": [],
                "hand": {"primary_tiles": [[2, 1]], "fallback_tiles": []},
                "market_policy": {
                    "seed_buy_order": ["WHEAT"],
                    "sell_order": ["WHEAT"],
                    "sell_min_price": {"WHEAT": 25},
                    "liquidate_from_day": 29,
                    "shed_high_water": 80,
                },
            }
        )
    )
    route = load_route(yml)
    assert route.crops[0].tile == (2, 1)
    assert route.hand.primary_tiles == ((2, 1),)
