"""YAML loader round-trip and the v4 baseline config check."""

from __future__ import annotations

from pathlib import Path

import pytest
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
    assert route.micro.as_kwargs() == {}


def test_route_micro_block_parses_and_defaults() -> None:
    raw = {
        "name": "with_micro",
        "crops": [],
        "structures": [],
        "market_policy": {},
        "micro": {
            "tail_start_day": 22,
            "salvage_ratio": 0.85,
            "drop_ratio": 0.75,
        },
    }
    route = route_from_dict(raw)
    assert route.micro.tail_start_day == 22
    assert route.micro.salvage_ratio == 0.85
    assert route.micro.drop_ratio == 0.75
    assert route.micro.tail_floor is None
    assert route.micro.as_kwargs() == {
        "tail_start_day": 22,
        "salvage_ratio": 0.85,
        "drop_ratio": 0.75,
    }


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


def test_phases_parse_with_defaults() -> None:
    raw = {
        "name": "phased",
        "market_policy": {"money_reserve": 400, "feed_days": 2},
        "phases": [
            {"from_day": 0, "crops": [{"tile": [1, 2], "crop": "MELON"}], "hands": 3},
            {
                "from_day": 6,
                "crops": [{"tile": [1, 2], "crop": "MELON"}],
                "structures": [{"tile": [4, 3], "kind": "COOP", "animal": "GOOSE"}],
                "hands": 8,
                "fertilize": ["WHEAT"],
            },
        ],
    }
    route = route_from_dict(raw)
    assert [p.from_day for p in route.phases] == [0, 6]
    assert route.phases[0].crops[0].tile == (1, 2)
    assert route.phases[0].structures == ()
    assert route.phases[1].hands == 8
    assert route.phases[1].fertilize == ("WHEAT",)
    assert route.market_policy.money_reserve == 400
    assert route.market_policy.feed_days == 2


def test_unphased_route_has_no_phases_and_default_market_fields() -> None:
    route = route_from_dict({"name": "flat", "market_policy": {}})
    assert route.phases == ()
    assert route.market_policy.money_reserve == 0
    assert route.market_policy.feed_days == 3


@pytest.mark.parametrize("days", [[4, 0], [0, 0]])
def test_phases_must_have_strictly_increasing_from_day(days: list[int]) -> None:
    raw = {
        "name": "bad",
        "market_policy": {},
        "phases": [{"from_day": d, "hands": 1} for d in days],
    }
    with pytest.raises(ValueError, match="strictly increasing"):
        route_from_dict(raw)
