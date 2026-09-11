"""Separate price forecast errors and stress public crop admissions.

Saved future trades, town draws and harvests are used only to diagnose forecast
errors. Hypothetical rival expansion rankings use checkpoint observations alone.
No new game is run and no opponent policy is executed.
"""

import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path

import numpy as np
from phase3_field_economics import analyze
from shop_option_diagnostic import forecast_parts

PARENT = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
COHORT = "9a83bb475173e00d1b5e2b28dada9c472e9e751139a5493ddbf1d3e5eb6a4652"
CHECKPOINTS = (3, 6, 9)


def telemetry(path, game):
    """Replay only official action/market helpers, preserving the $1 sale rule."""
    unit, commit, market = game._apply_unit_action, game._commit_unit, game._process_market
    seats = {}
    current_day = 0
    flows = np.zeros((2, 30, len(game.PRODUCTS)))
    harvests = []

    def apply(farm, private, worker, action, *rest):
        nonlocal current_day
        current_day = rest[1]
        seat = seats.setdefault(id(farm), len(seats))
        pos = game._farmer_position(farm, worker)
        tile = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos else None
        before = dict(private["inventories"][worker]) if pos else {}
        result = unit(farm, private, worker, action, *rest)
        if pos and action and action[0] == "HARVEST" and isinstance(tile, dict):
            product = tile.get("crop") or game.ANIMALS.get(tile.get("animal"), {}).get("product")
            if product:
                count = private["inventories"][worker].get(product, 0) - before.get(product, 0)
                if count:
                    harvests.append(
                        dict(
                            seat=seat,
                            day=current_day,
                            born=tile.get("planted_day", tile.get("placed_day")),
                            product=product,
                            units=count,
                        )
                    )
        return result

    def trade(op, item, price, farm, private, *rest):
        result = commit(op, item, price, farm, private, *rest)
        if result and op in ("SELL", "BUY_PRODUCT"):
            flows[seats[id(farm)], current_day, game.PRODUCTS.index(item)] += (
                int(price > 1) if op == "SELL" else -1
            )
        return result

    def execute(state, env):
        result = market(state, env)
        seats.clear()
        return result

    game._apply_unit_action, game._commit_unit, game._process_market = apply, trade, execute
    try:
        result = analyze(path)
    finally:
        game._apply_unit_action, game._commit_unit, game._process_market = unit, commit, market
    return flows, harvests, result["verified_cash_transitions"]


def shop_demand(shops, game):
    demand = np.array([float(item != "FERTILIZER") for item in game.PRODUCTS])
    for shop in shops:
        for item in game.SHOPS[shop]:
            demand[game.PRODUCTS.index(item)] += 12 if len(game.SHOPS[shop]) == 1 else 6
    return demand


def future_berries(obs, target, game):
    """Public stress scenario, not a financed opponent rollout.

    At most four new berries are planted daily, after an annual's first possible
    harvest or after an assumed land expansion every three days. The first three
    quadrants bound available land. Existing plants are never replaced early.
    New berries receive perfect fertilizer, an explicit supply stress assumption.
    """
    day = obs["day"]
    farm = obs["farms"][1 - obs["player"]]
    existing = 0
    available = []
    quadrants = len(farm["unlocked_quadrants"])
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY":
                existing += 1
                continue
            if isinstance(tile, dict) and "animal" in tile:
                continue
            if x >= 5 and y >= 5:
                continue
            ready = day + 1
            if tile == "LOCKED":
                order = 2 if x >= 5 else 3
                ready = day + max(1, order - quadrants) * 3
            elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                spec = game.CROPS[tile["crop"]]
                if spec["ongoing"]:
                    ready = max(
                        ready,
                        tile["planted_day"]
                        + spec["first_yield_day"]
                        + (spec["max_yield"] - 1) * spec["interval"]
                        + 1,
                    )
                else:
                    ready = max(ready, tile["planted_day"] + spec["first_yield_day"] + 1)
            available.append((ready, x, y))
    dates, per_day = [], Counter()
    extra = np.zeros((30, len(game.PRODUCTS)))
    for ready, x, y in sorted(available)[: max(0, target - existing)]:
        while per_day[ready] >= 4:
            ready += 1
        if ready + 10 > 29:
            continue
        per_day[ready] += 1
        dates.append(dict(day=ready, x=x, y=y))
        for event in range(ready + 10, min(30, ready + 17), 2):
            extra[event, game.PRODUCTS.index("STRAWBERRY")] += 2
    return extra, dates


def prices(inventories, params, game):
    return np.array(
        [
            [game.market_price(item, float(row[j]), params) for j, item in enumerate(game.PRODUCTS)]
            for row in inventories
        ]
    )


def care_bank_adjustment(obs, game, care_rate):
    """Public-state supply correction, conditional on feeding and collection."""
    extra = np.zeros((30, len(game.PRODUCTS)))
    for farm in obs["farms"]:
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict) or "animal" not in tile:
                    continue
                spec = game.ANIMALS[tile["animal"]]
                product = game.PRODUCTS.index(spec["product"])
                bank = tile.get("pending_care_bonus", 0)
                for current in range(obs["day"], 29):
                    age = current + 1 - tile["placed_day"]
                    if (
                        age >= spec["first_yield_day"]
                        and (age - spec["first_yield_day"]) % spec["interval"] == 0
                    ):
                        extra[current + 1, product] += min(spec["max_held"], 1 + bank) - min(
                            spec["max_held"], 1 + 0.8 * spec["interval"]
                        )
                        bank = 0
                    bank += care_rate
    return extra


def verify_perfect_care(obs, inherited, game):
    """The perfect-care correction must match official observed-animal refresh."""
    expected = np.zeros_like(inherited[0])
    for farm in obs["farms"]:
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict) or "animal" not in tile:
                    continue
                spec = game.ANIMALS[tile["animal"]]
                j = game.PRODUCTS.index(spec["product"])
                expected[obs["day"] + 1, j] += tile["yield_units"]
                animal = deepcopy(tile)
                animal["yield_units"] = 0
                single = dict(tiles=[[animal]])
                for current in range(obs["day"], 29):
                    animal.update(fed_today=True, cared_today=True)
                    game._daily_refresh_animals(single, current)
                    expected[current + 1, j] += animal["yield_units"]
                    animal["yield_units"] = 0
    selected = [game.PRODUCTS.index(item) for item in ("EGG", "MILK", "WOOL")]
    predicted = inherited[0] + inherited[1] + care_bank_adjustment(obs, game, 1.0)
    assert np.allclose(predicted[:, selected], expected[:, selected])


def checkpoint(replay, source, cohort_namespace, flows, harvests, day, seat, game):
    obs = deepcopy(replay["steps"][day * 24][0]["observation"])
    obs.update(deepcopy(replay["steps"][day * 24][seat]["observation"]))
    obs["player"] = seat
    _, expected, inherited = forecast_parts(source, obs)
    verify_perfect_care(obs, inherited, game)
    params = obs["market"].get("params") or game.MARKET_PARAMS
    initial = np.array([obs["market"]["inventory"][item] for item in game.PRODUCTS])
    actual_inventory = np.array(
        [
            [
                replay["steps"][(future + 1) * 24][0]["observation"]["market"]["inventory"][item]
                for item in game.PRODUCTS
            ]
            for future in range(day + 1, 25)
        ]
    )
    actual_demand = np.array(
        [
            shop_demand(
                replay["steps"][future * 24][0]["observation"]["town"]["unlocked_shops"], game
            )
            for future in range(30)
        ]
    )
    average_shop = np.mean(
        [shop_demand([shop], game) - shop_demand([], game) for shop in game.SHOPS], axis=0
    )
    forecast_demand = np.array(
        [
            shop_demand(obs["town"]["unlocked_shops"], game)
            + max(0, min(8 - len(obs["town"]["unlocked_shops"]), future // 3 - day // 3))
            * average_shop
            for future in range(30)
        ]
    )
    predicted_net = np.array(inherited)
    for player, farm in enumerate(obs["farms"]):
        animals = sum(
            isinstance(tile, dict) and "animal" in tile for row in farm["tiles"] for tile in row
        )
        predicted_net[player, day + 1 :, game.PRODUCTS.index("WHEAT")] -= animals
    n = len(actual_inventory)
    omitted_checkpoint_day = flows[:, day].sum(axis=0) - actual_demand[day]
    own_residual = np.cumsum((flows[seat] - predicted_net[seat])[day + 1 : day + 1 + n], axis=0)
    rival_residual = np.cumsum(
        (flows[1 - seat] - predicted_net[1 - seat])[day + 1 : day + 1 + n], axis=0
    )
    shop_residual = np.cumsum((forecast_demand - actual_demand)[day + 1 : day + 1 + n], axis=0)
    assert np.allclose(
        expected[:n] + omitted_checkpoint_day + own_residual + rival_residual + shop_residual,
        actual_inventory,
    )
    predicted_quotes = prices(expected[:n], params, game)
    actual_quotes = prices(actual_inventory, params, game)
    shop_oracle_quotes = prices(expected[:n] + shop_residual, params, game)
    own_oracle_quotes = prices(expected[:n] + own_residual, params, game)
    rival_oracle_quotes = prices(expected[:n] + rival_residual, params, game)
    care_quotes = {
        str(rate): prices(
            expected[:n]
            + np.cumsum(care_bank_adjustment(obs, game, rate)[day + 1 : day + 1 + n], axis=0),
            params,
            game,
        ).tolist()
        for rate in (0.8, 1.0)
    }
    free = [
        (x, y)
        for y, row in enumerate(obs["farms"][seat]["tiles"])
        for x, tile in enumerate(row)
        if tile is None
    ]
    target = (
        min(
            free,
            key=lambda p: (
                min(abs(p[0] - x) + abs(p[1] - y) for x, y in ((4, 4), (5, 4), (4, 5), (5, 5))),
                p[1],
                p[0],
            ),
        )
        if free
        else None
    )
    scenarios = []
    # The early-cohort function's own inventory addition is retained here.
    _, _, paths, own_arrivals = cohort_namespace["forecast_inventory"](
        obs, cohort_namespace["CROPS"], cohort_namespace["ANIMALS"], cohort_namespace["SHOPS"]
    )
    for berry_target in (0, 17, 34):
        extra, dates = future_berries(obs, berry_target, game)
        projected = {
            item: np.array(paths[item]) + np.cumsum(extra[day + 1 :, j])
            for j, item in enumerate(game.PRODUCTS)
        }
        values = (
            None
            if target is None
            else cohort_namespace["crop_opportunity_values"](
                obs, cohort_namespace["PARAMS"], Counter(), projected, own_arrivals, target
            )
        )
        scenarios.append(
            dict(
                berry_target=berry_target,
                added_cohorts=dates,
                new_supply=extra.sum(axis=0).tolist(),
                values=values,
                choice=None if values is None else max(values, key=values.get),
            )
        )
    categorized = {}
    for player, label in ((seat, "own"), (1 - seat, "rival")):
        for span, final in (("next8", day + 8), ("remaining", 29)):
            rows = [row for row in harvests if row["seat"] == player and day < row["day"] <= final]
            categorized[f"{label}_{span}_all"] = dict(
                sum((Counter({row["product"]: row["units"]}) for row in rows), Counter())
            )
            categorized[f"{label}_{span}_new_assets"] = dict(
                sum(
                    (Counter({row["product"]: row["units"]}) for row in rows if row["born"] >= day),
                    Counter(),
                )
            )
    return dict(
        day=day,
        seat=seat,
        target=target,
        projected_next8_arrivals={
            label: dict(
                zip(
                    game.PRODUCTS,
                    inherited[player][day + 1 : day + 9].sum(axis=0).tolist(),
                    strict=True,
                )
            )
            for player, label in ((seat, "own"), (1 - seat, "rival"))
        },
        measured_next8_net_market_flow={
            label: dict(
                zip(
                    game.PRODUCTS,
                    flows[player, day + 1 : day + 9].sum(axis=0).tolist(),
                    strict=True,
                )
            )
            for player, label in ((seat, "own"), (1 - seat, "rival"))
        },
        public_assets={
            label: dict(
                Counter(
                    tile.get("crop", tile.get("animal", tile["kind"]))
                    for row in obs["farms"][player]["tiles"]
                    for tile in row
                    if isinstance(tile, dict)
                )
            )
            for player, label in ((seat, "own"), (1 - seat, "rival"))
        },
        initial_inventory=initial.tolist(),
        forecast_closing_prices=predicted_quotes.tolist(),
        actual_closing_prices=actual_quotes.tolist(),
        oracle_shop_only_prices=shop_oracle_quotes.tolist(),
        oracle_own_net_only_prices=own_oracle_quotes.tolist(),
        oracle_rival_net_only_prices=rival_oracle_quotes.tolist(),
        public_care_bank_prices=care_quotes,
        omitted_checkpoint_day_inventory=omitted_checkpoint_day.tolist(),
        own_net_inventory_residual=own_residual.tolist(),
        rival_net_inventory_residual=rival_residual.tolist(),
        shop_inventory_residual=shop_residual.tolist(),
        harvested=categorized,
        public_scenarios=scenarios,
    )


def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    source = gzip.decompress(Path(f"reports/sources/{PARENT}.py.gz").read_bytes()).decode()
    assert hashlib.sha256(source.encode()).hexdigest() == PARENT
    cohort_source = gzip.decompress(Path(f"reports/sources/{COHORT}.py.gz").read_bytes())
    assert hashlib.sha256(cohort_source).hexdigest() == COHORT
    namespace = {}
    exec(cohort_source, namespace)
    output = dict(
        parent_sha256=PARENT,
        ranking_model_sha256=COHORT,
        environment_version=version("kaggle-environments"),
        interpreter_sha256=hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        products=game.PRODUCTS,
        method="Closing forecasts are compared with observed closing inventories for each labeled future day. Separate oracle interventions use future recorded trades or shops for diagnosis only; neither enters the public rival-expansion scenarios. Inventory error is reconciled exactly into omitted current day, own net flows, rival net flows and shop draws. New-asset harvests establish production provenance but are not equated with market sales.",
        inputs={},
        public_cohort_timelines=[],
        cases=[],
    )
    for seed in range(5000, 5008):
        for seat in (0, 1):
            path = Path(
                f"reports/replays/breakthrough/{PARENT}-reference-mooman-main-{seed}-{seat}.json"
            )
            raw = path.read_bytes()
            output["inputs"][str(path)] = hashlib.sha256(raw).hexdigest()
            replay = json.loads(raw)
            output["configuration"] = replay["configuration"]
            seen = [set(), set()]
            for step in replay["steps"]:
                for player, farm in enumerate(step[0]["observation"]["farms"]):
                    for y, row in enumerate(farm["tiles"]):
                        for x, tile in enumerate(row):
                            if isinstance(tile, dict) and ("crop" in tile or "animal" in tile):
                                seen[player].add(
                                    (
                                        x,
                                        y,
                                        tile.get("crop", tile.get("animal")),
                                        tile.get("planted_day", tile.get("placed_day")),
                                    )
                                )
            output["public_cohort_timelines"].append(
                dict(
                    seed=seed,
                    seat=seat,
                    births={
                        label: {
                            product: dict(
                                sorted(
                                    Counter(
                                        born for _, _, item, born in seen[player] if item == product
                                    ).items()
                                )
                            )
                            for product in sorted({row[2] for row in seen[player]})
                        }
                        for player, label in ((seat, "own"), (1 - seat, "rival"))
                    },
                )
            )
            flows, harvests, verified = telemetry(path, game)
            assert verified == 1438
            for day in CHECKPOINTS:
                result = checkpoint(replay, source, namespace, flows, harvests, day, seat, game)
                result.update(seed=seed, verified_cash_transitions=verified)
                output["cases"].append(result)
            print(seed, seat, "verified", flush=True)
    path = Path("reports/results/forecast-expansion-diagnostic.json.gz")
    path.write_bytes(
        gzip.compress((json.dumps(output, separators=(",", ":")) + "\n").encode(), mtime=0)
    )
    print(path)


if __name__ == "__main__":
    main()
