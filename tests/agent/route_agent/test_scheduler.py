"""Tests for the multi-worker priority scheduler.

One test per priority level, plus an integration test that runs a small farm
through a full season and asserts nothing was lost to a weed or an escape.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from kaggle_environments import make

from kaggriculture.agent.route_agent.scheduler import (
    P_CARE,
    P_COLLECT,
    P_CRITICAL,
    P_DROP,
    P_FERTILIZE,
    P_HARVEST,
    P_PLANT,
    P_WATER,
    FarmPlan,
    assign,
    build_tasks,
    harvest_age,
    schedule,
    shed_access_tiles,
    target_units,
    water_window,
)
from kaggriculture.env.observation import Observation


def _obs(
    *,
    tiles: dict[tuple[int, int], Any] | None = None,
    farmer: tuple[int, int] = (4, 4),
    hands: list[tuple[int, int]] | None = None,
    day: int = 0,
    hour: int = 0,
    seeds: dict[str, int] | None = None,
    shed: dict[str, int] | None = None,
    inventories: list[dict[str, int]] | None = None,
    locked: bool = True,
) -> Observation:
    grid: list[list[Any]] = [
        [None if (x < 5 and y < 5) or not locked else "LOCKED" for x in range(10)]
        for y in range(10)
    ]
    for (x, y), tile in (tiles or {}).items():
        grid[y][x] = tile
    hands = hands or []
    return Observation.from_dict(
        {
            "player": 0,
            "step": day * 24 + hour,
            "day": day,
            "hour": hour,
            "farms": [
                {
                    "money": 3000.0,
                    "tiles": grid,
                    "farmer": list(farmer),
                    "hands": [list(h) for h in hands],
                    "unlocked_quadrants": ["NW"],
                    "hires_today": 0,
                },
                {
                    "money": 3000.0,
                    "tiles": [[None] * 10 for _ in range(10)],
                    "farmer": [5, 5],
                    "hands": [],
                    "unlocked_quadrants": ["NW"],
                    "hires_today": 0,
                },
            ],
            "market": {"prices": {}, "inventory": {}},
            "town": {"unlocked_shops": []},
            "private": {
                "shed": shed or {},
                "seeds": seeds or {},
                "inventories": inventories or [{} for _ in range(1 + len(hands))],
            },
        }
    )


def _plant(crop: str, **kw: Any) -> dict[str, Any]:
    tile = {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": 0,
        "watered_today": False,
        "consecutive_unwatered": 0,
        "yield_units": 1,
        "max_lifespan_step": 10_000,
        "fertilized_until_day": -1,
    }
    tile.update(kw)
    return tile


def _animal(animal: str, kind: str = "COOP", **kw: Any) -> dict[str, Any]:
    tile = {
        "kind": kind,
        "animal": animal,
        "placed_day": 0,
        "yield_units": 0,
        "fed_today": True,
        "consecutive_unfed": 0,
        "cared_today": True,
        "fertilizer_available": False,
        "pending_care_bonus": 0,
    }
    tile.update(kw)
    return tile


def _levels(tasks: list[Any], op: str) -> list[int]:
    return sorted(t.priority for t in tasks if t.op == op)


# Yield model ---------------------------------------------------------------


def test_water_window_matches_simulator_bonus_window() -> None:
    assert water_window("WHEAT") == (2, 4)
    assert water_window("CARROT") == (2, 3)
    assert water_window("MELON") == (6, 12)
    start, end = water_window("TOMATO")
    assert start > end  # ongoing crops gain nothing from a watering


def test_target_units_caps_at_max_yield() -> None:
    assert target_units("WHEAT") == 4
    assert target_units("WHEAT", fertilized=True) == 6
    assert target_units("MELON") == 6


def test_harvest_age_is_gated_by_first_yield_day() -> None:
    assert harvest_age("WHEAT") == 4
    assert harvest_age("CARROT") == 3
    # Melon caps out at age 10 but cannot be picked before first_yield_day.
    assert harvest_age("MELON") == 10


# Priority levels -----------------------------------------------------------


def test_p0_waters_a_plant_that_would_weed_tonight() -> None:
    obs = _obs(tiles={(1, 1): _plant("WHEAT", consecutive_unwatered=1)})
    tasks = build_tasks(FarmPlan(crops={(1, 1): "WHEAT"}), obs)
    assert _levels(tasks, "WATER") == [P_CRITICAL]


def test_p0_feeds_an_animal_that_would_escape_tonight() -> None:
    obs = _obs(tiles={(1, 1): _animal("GOOSE", fed_today=False, consecutive_unfed=1)})
    tasks = build_tasks(FarmPlan(structures={(1, 1): ("COOP", "GOOSE")}), obs)
    assert _levels(tasks, "FEED") == [P_CRITICAL]


def test_p1_harvests_a_ripe_plant_and_animal_produce() -> None:
    obs = _obs(
        tiles={
            (1, 1): _plant("WHEAT", planted_day=0, yield_units=4),
            (2, 2): _animal("GOOSE", yield_units=2),
        },
        day=4,
    )
    plan = FarmPlan(crops={(1, 1): "WHEAT"}, structures={(2, 2): ("COOP", "GOOSE")})
    assert _levels(build_tasks(plan, obs), "HARVEST") == [P_HARVEST, P_HARVEST]


def test_p1_does_not_harvest_a_plant_still_short_of_its_cap() -> None:
    obs = _obs(tiles={(1, 1): _plant("WHEAT", yield_units=2)}, day=3)
    assert _levels(build_tasks(FarmPlan(crops={(1, 1): "WHEAT"}), obs), "HARVEST") == []


def test_p1_salvage_harvests_a_plant_about_to_decay() -> None:
    obs = _obs(
        tiles={(1, 1): _plant("WHEAT", yield_units=2, max_lifespan_step=120)},
        day=5,
        hour=0,
    )
    assert _levels(build_tasks(FarmPlan(crops={(1, 1): "WHEAT"}), obs), "HARVEST") == [P_HARVEST]


def test_p1_places_a_bought_animal_into_its_empty_structure() -> None:
    obs = _obs(tiles={(1, 1): {"kind": "COOP"}}, shed={"GOOSE": 1})
    tasks = build_tasks(FarmPlan(structures={(1, 1): ("COOP", "GOOSE")}), obs)
    assert [(t.priority, t.op, t.needs) for t in tasks] == [(P_HARVEST, "PLACE", "GOOSE")]


def test_p2_fertilizes_only_crops_the_plan_opted_in() -> None:
    tiles = {(1, 1): _plant("WHEAT", watered_today=True, yield_units=2)}
    plan_off = FarmPlan(crops={(1, 1): "WHEAT"})
    plan_on = FarmPlan(crops={(1, 1): "WHEAT"}, fertilize=frozenset({"WHEAT"}))
    assert _levels(build_tasks(plan_off, _obs(tiles=tiles, day=2)), "FERTILIZE") == []
    assert _levels(build_tasks(plan_on, _obs(tiles=tiles, day=2)), "FERTILIZE") == [P_FERTILIZE]


def test_p3_plants_an_empty_tile_and_clears_a_weed() -> None:
    obs = _obs(tiles={(2, 2): {"kind": "WEED"}}, seeds={"WHEAT": 5})
    plan = FarmPlan(crops={(1, 1): "WHEAT", (2, 2): "WHEAT"})
    tasks = build_tasks(plan, obs)
    assert _levels(tasks, "PLANT") == [P_PLANT]
    assert _levels(tasks, "DIG") == [P_PLANT]


def test_p3_never_plans_more_plantings_than_there_are_seeds() -> None:
    plan = FarmPlan(crops={(x, 0): "WHEAT" for x in range(5)})
    tasks = build_tasks(plan, _obs(seeds={"WHEAT": 2}))
    assert len([t for t in tasks if t.op == "PLANT"]) == 2


def test_p3_does_not_plant_a_crop_that_cannot_ripen_before_the_season_ends() -> None:
    plan = FarmPlan(crops={(1, 1): "MELON"})
    assert build_tasks(plan, _obs(day=18, seeds={"MELON": 1})) != []
    assert build_tasks(plan, _obs(day=20, seeds={"MELON": 1})) == []


def test_p3_builds_a_missing_structure() -> None:
    plan = FarmPlan(structures={(1, 1): ("PASTURE", "COW")})
    tasks = build_tasks(plan, _obs())
    assert [(t.priority, t.op) for t in tasks] == [(P_PLANT, "BUILD_PASTURE")]


def test_p4_waters_a_plant_that_still_gains_yield_today() -> None:
    obs = _obs(tiles={(1, 1): _plant("WHEAT", yield_units=2)}, day=3)
    assert _levels(build_tasks(FarmPlan(crops={(1, 1): "WHEAT"}), obs), "WATER") == [P_WATER]


def test_p4_skips_a_watering_that_would_add_nothing() -> None:
    obs = _obs(tiles={(1, 1): _plant("MELON", yield_units=1)}, day=3)
    assert build_tasks(FarmPlan(crops={(1, 1): "MELON"}), obs) == []


def test_p5_feeds_and_cares_for_an_animal_that_is_not_at_risk() -> None:
    plan = FarmPlan(structures={(1, 1): ("COOP", "GOOSE")})
    unfed = _obs(tiles={(1, 1): _animal("GOOSE", fed_today=False, cared_today=False)})
    assert _levels(build_tasks(plan, unfed), "FEED") == [P_CARE]
    fed = _obs(tiles={(1, 1): _animal("GOOSE", fed_today=True, cared_today=False)})
    assert _levels(build_tasks(plan, fed), "CARE") == [P_CARE]


def test_p5_does_not_care_for_an_unfed_animal() -> None:
    # The care bonus is only banked when the animal was also fed that day.
    obs = _obs(tiles={(1, 1): _animal("GOOSE", fed_today=False, cared_today=False)})
    tasks = build_tasks(FarmPlan(structures={(1, 1): ("COOP", "GOOSE")}), obs)
    assert _levels(tasks, "CARE") == []


def test_p6_collects_available_fertilizer() -> None:
    obs = _obs(tiles={(1, 1): _animal("GOOSE", fertilizer_available=True)})
    tasks = build_tasks(FarmPlan(structures={(1, 1): ("COOP", "GOOSE")}), obs)
    assert _levels(tasks, "COLLECT_FERTILIZER") == [P_COLLECT]


def test_p7_drops_produce_once_a_worker_is_loaded() -> None:
    obs = _obs(inventories=[{"MELON": 4}])
    tasks = build_tasks(FarmPlan(), obs)
    assert [(t.priority, t.op, t.worker) for t in tasks] == [(P_DROP, "DROP", 0)]
    assert build_tasks(FarmPlan(), _obs(inventories=[{"MELON": 3}])) == []


# Assignment ----------------------------------------------------------------


def test_higher_priority_task_takes_the_worker_when_they_compete() -> None:
    obs = _obs(
        tiles={
            (4, 3): _plant("WHEAT", consecutive_unwatered=1),
            (4, 2): _plant("WHEAT", yield_units=2, watered_today=False),
        },
        farmer=(4, 4),
        day=3,
    )
    plan = FarmPlan(crops={(4, 3): "WHEAT", (4, 2): "WHEAT"})
    ops = assign(build_tasks(plan, obs), obs)
    assert ops == {0: ["NORTH"]}


def test_each_task_takes_the_nearest_free_worker() -> None:
    obs = _obs(
        tiles={
            (0, 0): _plant("WHEAT", consecutive_unwatered=1),
            (4, 4): _plant("WHEAT", consecutive_unwatered=1),
        },
        farmer=(4, 4),
        hands=[(0, 0)],
    )
    plan = FarmPlan(crops={(0, 0): "WHEAT", (4, 4): "WHEAT"})
    assert assign(build_tasks(plan, obs), obs) == {0: ["WATER"], 1: ["WATER"]}


def test_only_one_worker_is_sent_to_fetch_feed_for_a_whole_herd() -> None:
    tiles = {(x, 0): _animal("GOOSE", fed_today=False, consecutive_unfed=1) for x in range(4)}
    obs = _obs(tiles=tiles, farmer=(4, 4), hands=[(4, 3), (3, 4)], shed={"WHEAT": 20})
    plan = FarmPlan(structures={(x, 0): ("COOP", "GOOSE") for x in range(4)})
    ops = assign(build_tasks(plan, obs), obs)
    assert list(ops.values()) == [["PICKUP", "WHEAT", 4]]


def test_a_carrier_serves_the_feed_task_instead_of_a_closer_empty_handed_worker() -> None:
    obs = _obs(
        tiles={(0, 0): _animal("GOOSE", fed_today=False, consecutive_unfed=1)},
        farmer=(4, 4),
        hands=[(1, 0)],
        inventories=[{"WHEAT": 3}, {}],
        shed={"WHEAT": 20},
    )
    plan = FarmPlan(structures={(0, 0): ("COOP", "GOOSE")})
    assert assign(build_tasks(plan, obs), obs)[0] == ["WEST"]


def test_idle_workers_pass() -> None:
    obs = _obs(farmer=(4, 4), hands=[(4, 3)])
    action = schedule(FarmPlan(), obs)
    assert action == {"farmer": ["PASS"], "hands": [["PASS"]], "market": []}


def test_schedule_carries_market_orders_through() -> None:
    action = schedule(FarmPlan(), _obs(), market=[["HIRE"]])
    assert action["market"] == [["HIRE"]]


def test_schedule_falls_back_to_pass_when_over_the_time_budget() -> None:
    obs = _obs(farmer=(4, 4), hands=[(4, 3)])
    plan = FarmPlan(crops={(x, y): "WHEAT" for x in range(5) for y in range(5)})
    action = schedule(plan, obs, market=[["HIRE"]], time_budget_seconds=0.0)
    assert action == {"farmer": ["PASS"], "hands": [["PASS"]], "market": [["HIRE"]]}


def test_schedule_stays_well_inside_the_turn_budget_on_a_full_board() -> None:
    tiles = {(x, y): _plant("MELON", yield_units=1) for x in range(10) for y in range(10)}
    obs = _obs(
        tiles=tiles,
        farmer=(4, 4),
        hands=[(x, 4) for x in range(10)],
        locked=False,
        inventories=[{} for _ in range(11)],
    )
    plan = FarmPlan(crops={(x, y): "MELON" for x in range(10) for y in range(10)})
    start = time.perf_counter()
    for _ in range(10):
        schedule(plan, obs)
    assert (time.perf_counter() - start) / 10 < 0.4


# Integration ---------------------------------------------------------------


def _five_tile_agent():
    from kaggriculture.agent.route_agent.runner import RouteAgent
    from kaggriculture.agent.route_agent.schema import (
        CropAssignment,
        HandAssignment,
        MarketPolicy,
        Phase,
        Route,
        StructureAssignment,
    )

    crops = tuple(CropAssignment(tile=t, crop="WHEAT") for t in ((2, 3), (3, 3), (2, 4), (3, 4)))
    route = Route(
        name="five_tile",
        description="four wheat tiles feeding one goose",
        crops=(),
        structures=(),
        hand=HandAssignment((), ()),
        land_buys=(),
        market_policy=MarketPolicy(
            seed_buy_order=("WHEAT",),
            animal_buy_order=("GOOSE",),
            hire=None,
            feed_stockpiles=(),
            sell_order=("EGG", "FERTILIZER", "WHEAT"),
            sell_min_price={},
            liquidate_from_day=28,
            shed_high_water=80,
            feed_days=2,
        ),
        phases=(
            Phase(
                from_day=0,
                crops=crops,
                structures=(StructureAssignment(tile=(4, 3), kind="COOP", animal="GOOSE"),),
                hands=2,
            ),
        ),
    )
    agent_impl = RouteAgent(route)

    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return agent_impl(obs)

    return agent


@pytest.mark.parametrize("seed", [0, 7])
def test_five_tile_season_loses_no_plant_to_weeds_and_no_animal_to_escape(seed: int) -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([_five_tile_agent(), "pass"])

    planned = {(2, 3), (3, 3), (2, 4), (3, 4), (4, 3)}
    weeded = 0
    escaped = 0
    previous: dict[tuple[int, int], Any] = {}
    for state in env.steps:
        tiles = state[0].observation["farms"][0]["tiles"]
        for x, y in planned:
            tile = tiles[y][x]
            was = previous.get((x, y))
            is_weed = isinstance(tile, dict) and tile.get("kind") == "WEED"
            was_weed = isinstance(was, dict) and was.get("kind") == "WEED"
            if is_weed and not was_weed:
                weeded += 1
            if (
                isinstance(was, dict)
                and was.get("animal")
                and isinstance(tile, dict)
                and "animal" not in tile
            ):
                escaped += 1
            previous[(x, y)] = tile
    assert weeded == 0
    assert escaped == 0
    assert env.steps[-1][0].reward > 3000


def test_shed_access_tiles_match_the_simulator_layout() -> None:
    assert shed_access_tiles(10) == ((4, 4), (5, 4), (4, 5), (5, 5))
