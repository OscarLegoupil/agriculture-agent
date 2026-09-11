"""Enumerate future shop draws using only a saved public decision checkpoint.

This is a cash-flow diagnostic, not a rollout or deployable performance claim.
Existing-asset production follows the frozen forecast's stated care assumptions.
New crop cohort yields use official WATER, FERTILIZE, HARVEST and daily refresh.
"""

import argparse
import ast
import gzip
import hashlib
import itertools
import json
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path

import numpy as np

CHAMPION = "c2b3162de26b82cb6057e94cb121b5655b7ee5c2e30659520f379f6ac7828b05"


def price_array(item, inventories, params, game):
    values, inverse = np.unique(inventories, return_inverse=True)
    quotes = np.array([game.market_price(item, float(value), params) for value in values])
    return quotes[inverse].reshape(inventories.shape)


def cohort(crop, born, delivery_lag, fertilizer, game):
    farm = dict(tiles=[[None]], farmer=[0, 0], hands=[])
    private = dict(seeds={}, shed={}, inventories=[{}])
    sales = np.zeros((30, len(game.PRODUCTS)))
    costs, actions, fertilizer_use = np.zeros(30), np.zeros(30), np.zeros(30)
    next_plant = born
    chosen = crop
    for day in range(born, 30):
        tile = farm["tiles"][0][0]
        if tile is None and day >= next_plant:
            if day + game.CROPS[chosen]["first_yield_day"] > 29:
                break
            private["seeds"][chosen] = 1
            game._apply_unit_action(farm, private, 0, ["PLANT", chosen], 1, day, 24, 100)
            costs[day] += game.CROPS[chosen]["seed"]
            actions[day] += 1
            tile = farm["tiles"][0][0]
        if tile is None:
            continue
        spec = game.CROPS[tile["crop"]]
        age = day - tile["planted_day"]
        active = (7 <= age <= 10) if chosen == "TOMATO" else (2 <= age <= spec["max_yield_day"])
        if fertilizer and active and day < 29 and tile["fertilized_until_day"] < day:
            private["inventories"][0]["FERTILIZER"] = 1
            game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 1, day, 24, 100)
            fertilizer_use[day] += 1
            actions[day] += 1.25
        game._apply_unit_action(farm, private, 0, ["WATER"], 1, day, 24, 100)
        actions[day] += 1
        harvest = (
            tile["yield_units"] > 0
            and age >= spec["first_yield_day"]
            and (spec["ongoing"] or age >= spec["max_yield_day"] or day == 29)
        )
        if harvest:
            units = tile["yield_units"]
            game._apply_unit_action(farm, private, 0, ["HARVEST"], 1, day, 24, 100)
            assert private["inventories"][0].get(chosen, 0) == units
            private["inventories"][0].clear()
            # The deployed fleet explicitly returns and sells on terminal day.
            # This assumes that final route fits; it never credits a day-30 sale.
            sales[min(29, day + delivery_lag), game.PRODUCTS.index(chosen)] += units
            actions[day] += 1.25  # harvest plus a quarter-share of a bulk DROP
            if not spec["ongoing"]:
                next_plant = day + 1
            elif age == spec["first_yield_day"] + (spec["max_yield"] - 1) * spec["interval"]:
                game._apply_unit_action(farm, private, 0, ["DIG"], 1, day, 24, 100)
                actions[day] += 1
                chosen, fertilizer, next_plant = "WHEAT", False, day + 1
        game._daily_refresh_plants(farm, day, 24)
    return sales, costs, actions, fertilizer_use


def forecast_parts(source, obs):
    namespace = {}
    exec(source, namespace)
    items = list(namespace["BASE"])
    recorded = []
    original = namespace["inventory_quote"]
    namespace["inventory_quote"] = lambda inv, spec: (recorded.append(inv), original(inv, spec))[1]
    forecast, _ = namespace["forecast_inventory"](
        obs, namespace["CROPS"], namespace["ANIMALS"], namespace["SHOPS"]
    )
    namespace["inventory_quote"] = original
    # Extract the existing forecaster's arrivals, stopping before price projection.
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "forecast_inventory"
    )
    stop = next(
        i
        for i, node in enumerate(function.body)
        if isinstance(node, ast.AnnAssign) and node.target.id == "traces"
    )
    function.body = [*function.body[:stop], ast.parse("return arrivals, animals").body[0]]
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, "public_asset_projection", "exec"), namespace)
    arrivals = []
    for farm in obs["farms"]:
        own = deepcopy(obs)
        own["farms"] = [farm]
        rows, animals = namespace["forecast_inventory"](
            own, namespace["CROPS"], namespace["ANIMALS"], namespace["SHOPS"]
        )
        matrix = np.array([[row[item] for item in items] for row in rows])
        matrix[obs["day"] + 1 :, items.index("FERTILIZER")] += animals * 0.5
        arrivals.append(matrix)
    return forecast, np.array(recorded).reshape(-1, len(items)), arrivals


def scenario_inventories(obs, cfg, expected, game):
    day = obs["day"]
    existing = obs["town"]["unlocked_shops"]
    unlock_days = [d for d in range(day + 1, 30) if d % cfg.get("townShopUnlockInterval", 3) == 0][
        : game.MAX_SHOP_INSTANCES - len(existing)
    ]
    names = sorted(game.SHOPS)
    paths = list(itertools.product(names, repeat=len(unlock_days)))
    # Retain the frozen model's daily demand discretization to isolate Jensen's
    # inequality from other forecast corrections. Config is checked explicitly.
    assert cfg.get("turnsPerDay", 24) == 24
    assert cfg.get("townShopSellInterval", 4) == 4
    assert cfg.get("townCenterSellInterval", 24) == 24
    additional = np.zeros((len(paths), 30 - day - 1, len(game.PRODUCTS)))
    average = np.zeros_like(additional[0])
    for offset, future in enumerate(range(day + 1, 30)):
        for date in unlock_days:
            if date <= future:
                for shop in names:
                    for product in game.SHOPS[shop]:
                        average[offset, game.PRODUCTS.index(product)] += (
                            12 if len(game.SHOPS[shop]) == 1 else 6
                        ) / len(names)
        for index, path in enumerate(paths):
            for date, shop in zip(unlock_days, path, strict=True):
                if date <= future:
                    for product in game.SHOPS[shop]:
                        additional[index, offset, game.PRODUCTS.index(product)] += (
                            12 if len(game.SHOPS[shop]) == 1 else 6
                        )
    deviations = np.cumsum(additional - average, axis=1)
    return expected[None, :, :] - deviations, unlock_days


def renewal_sites(farm, day, count=None, empty=True, commission_delay=1):
    positions = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile is None and empty:
                positions.append((day + commission_delay, x, y))
            elif isinstance(tile, dict) and tile.get("crop") == "WHEAT":
                positions.append((max(day + 1, tile["planted_day"] + 5), x, y))
    positions.sort(
        key=lambda point: (
            point[0],
            min(
                abs(point[1] - sx) + abs(point[2] - sy)
                for sx, sy in ((4, 4), (5, 4), (4, 5), (5, 5))
            ),
            point[2],
            point[1],
        )
    )
    return positions[:count]


def evaluate(obs, cfg, source, delivery_lag, count, game, background, commission_delay=1):
    day, seat = obs["day"], obs["player"]
    forecast, expected, inherited = forecast_parts(source, obs)
    inventories, draws = scenario_inventories(obs, cfg, expected, game)
    assert np.allclose(inventories.mean(axis=0), expected)
    params = obs["market"].get("params") or game.MARKET_PARAMS
    positions = renewal_sites(obs["farms"][seat], day, count, commission_delay=commission_delay)
    if background != "finite_assets":
        additional = np.zeros((30, len(game.PRODUCTS)))
        own_sites = {(x, y) for _, x, y in positions}
        for player, farm in enumerate(obs["farms"]):
            index = 0
            for born, x, y in renewal_sites(farm, day, empty=False):
                if player == seat and (x, y) in own_sites:
                    continue
                tomato = background == "rival_tomato8" and player != seat and index < 8
                output, _, _, _ = cohort(
                    "TOMATO" if tomato else "WHEAT", born, delivery_lag, tomato, game
                )
                additional += output
                inherited[player] += output
                index += 1
        shift = np.cumsum(additional[day + 1 :], axis=0)
        expected += shift
        inventories += shift[None, :, :]
    variants = {}
    for crop, fertilizer in (
        ("WHEAT", False),
        ("CARROT", False),
        ("TOMATO", False),
        ("TOMATO", True),
    ):
        production = np.zeros((30, len(game.PRODUCTS)))
        costs, work, inputs = np.zeros(30), np.zeros(30), np.zeros(30)
        for born, x, y in positions:
            output, seed_cost, actions, fert = cohort(crop, born, delivery_lag, fertilizer, game)
            production += output
            costs += seed_cost
            work += actions
            inputs += fert
            # Amortized routing: four neighboring visits per depot round trip.
            active = actions > 0
            work[active] += (
                min(abs(x - sx) + abs(y - sy) for sx, sy in ((4, 4), (5, 4), (4, 5), (5, 5))) / 2
            )
        delta = np.cumsum(production[day + 1 :], axis=0)
        # Supply enters before end-of-day quotes; individual candidate sale units
        # are priced from pre-unit inventory, including the candidate's own impact.
        prior = np.concatenate([np.zeros_like(delta[:1]), delta[:-1]], axis=0)
        prices = inventories + prior[None, :, :]
        receipt = np.zeros(len(prices))
        point_receipt, blend_receipt = 0.0, 0.0
        opponent_impact = np.zeros(len(prices))
        own_impact = np.zeros(len(prices))
        own_point_impact = 0.0
        for offset, future in enumerate(range(day + 1, 30)):
            for item_index, item in enumerate(game.PRODUCTS):
                units = int(production[future, item_index])
                for unit in range(units):
                    quoted = price_array(item, prices[:, offset, item_index] + unit, params, game)
                    # This screen's selected crop paths stay above the floor, so
                    # every sale adds stock. Fail rather than misprice floor sales.
                    assert np.all(quoted > 1)
                    receipt += quoted
                    point_receipt += game.market_price(
                        item,
                        float(expected[offset, item_index] + prior[offset, item_index] + unit),
                        params,
                    )
                blend_receipt += units * forecast[item]
                if units or prior[offset, item_index]:
                    decline = price_array(
                        item, inventories[:, offset, item_index], params, game
                    ) - price_array(item, prices[:, offset, item_index], params, game)
                    opponent_impact += inherited[1 - seat][future, item_index] * decline
                    own_impact -= inherited[seat][future, item_index] * decline
                    own_point_impact += inherited[seat][future, item_index] * (
                        game.market_price(
                            item,
                            float(expected[offset, item_index] + prior[offset, item_index]),
                            params,
                        )
                        - game.market_price(item, float(expected[offset, item_index]), params)
                    )
        fert_quotes = np.stack(
            [
                price_array(
                    "FERTILIZER",
                    inventories[:, index, game.PRODUCTS.index("FERTILIZER")],
                    params,
                    game,
                )
                for index in range(inventories.shape[1])
            ],
            axis=1,
        )
        expenses = costs.sum() + 4 * work.sum() + (fert_quotes * inputs[day + 1 :]).sum(axis=1)
        variants[crop + ("_FERT" if fertilizer else "")] = dict(
            scenario_net=receipt - expenses + own_impact,
            gap_value=receipt - expenses + own_impact + opponent_impact,
            expected_net=float(point_receipt - expenses.mean() + own_point_impact),
            blend_net=float(blend_receipt - expenses.mean() + own_impact.mean()),
            own_existing_receipts_change=float(own_impact.mean()),
            receipts=float(receipt.mean()),
            seed_cost=float(costs.sum()),
            work_actions=float(work.sum()),
            max_daily_actions=float(work.max()),
            fertilizer_units=float(inputs.sum()),
            output=dict(
                zip(game.PRODUCTS, production.sum(axis=0).astype(int).tolist(), strict=True)
            ),
        )
    baseline_gap_value = variants["WHEAT"]["gap_value"].copy()
    gap = obs["farms"][1 - seat]["money"] - obs["farms"][seat]["money"]
    summary = {}
    for name, v in variants.items():
        gain = v["gap_value"] - baseline_gap_value
        net = v.pop("scenario_net")
        v.pop("gap_value")
        summary[name] = dict(
            **v,
            scenario_mean_net=float(net.mean()),
            net_p10=float(np.quantile(net, 0.1)),
            net_p90=float(np.quantile(net, 0.9)),
            delta_wheat_mean=float(gain.mean()),
            delta_wheat_p10=float(np.quantile(gain, 0.1)),
            delta_wheat_p90=float(np.quantile(gain, 0.9)),
            probability_delta_closes_current_gap=float(np.mean(gain >= gap)),
        )
    return dict(
        day=day,
        seat=seat,
        current_gap=gap,
        scenario_count=len(inventories),
        remaining_unlock_days=draws,
        delivery_lag=delivery_lag,
        commission_delay=commission_delay,
        background=background,
        sites=positions,
        current_forecast=forecast,
        variants=summary,
    )


def selector_probe(source, replay, day, seat):
    marker = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(marker) == 1
    traced = source.replace(
        marker,
        "        _CHOICES.append(dict(cell=(x,y), values=dict(values), planned=dict(planned), forecast=dict(forecast), use_fert=use_fert, cash=cash, animals=len(animals)))\n"
        + marker,
    )
    for hour in range(24):
        state = replay["steps"][day * 24 + hour]
        obs = deepcopy(state[0]["observation"])
        obs.update(deepcopy(state[seat]["observation"]))
        obs["player"] = seat
        ns = {"_CHOICES": []}
        exec(traced, ns)
        action = ns["agent"](obs, replay["configuration"])
        if not ns["_CHOICES"]:
            continue
        choice = ns["_CHOICES"][0]
        forecasts, traces = ns["forecast_inventory"](obs, ns["CROPS"], ns["ANIMALS"], ns["SHOPS"])
        factor = 2 if choice["planned"].get("WHEAT", 0) < 24 and choice["animals"] else 1
        no_feed = dict(choice["values"])
        no_feed["WHEAT"] /= factor
        unblend, timing = {}, {}
        for crop, (_, first, last, interval, cap) in ns["CROPS"].items():
            future_price = 2 * forecasts[crop] - obs["market"]["prices"][crop]
            events = (
                list(range(day + first, min(29, day + first + (cap - 1) * interval) + 1, interval))
                if interval
                else [min(29, day + last)]
            )
            exact = (
                np.mean([traces[crop][date - day - 1] for date in events])
                if events
                else forecasts[crop]
            )
            for scores, price in (
                (unblend, future_price),
                (timing, 0.5 * obs["market"]["prices"][crop] + 0.5 * exact),
            ):
                scores[crop] = ns["crop_value"](
                    crop,
                    day,
                    price / (1 + choice["planned"].get(crop, 0) * 0.025),
                    obs["market"]["prices"]["FERTILIZER"],
                    choice["use_fert"] and interval > 0,
                )
                if crop == "WHEAT":
                    scores[crop] *= factor
        both = dict(unblend)
        both["WHEAT"] /= factor
        return dict(
            day=day,
            hour=hour,
            seat=seat,
            **choice,
            no_feed_multiplier=no_feed,
            no_price_blend=unblend,
            neither=both,
            cohort_timing_only=timing,
            observed_seed_orders=[order for order in action["market"] if order[0] == "BUY_SEED"],
        )
    return dict(day=day, seat=seat, no_crop_admission=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/shop-option-diagnostic.json.gz")
    )
    args = parser.parse_args()
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    source_path = Path("data/interim/strategy-screen") / CHAMPION / "main.py"
    source = source_path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == CHAMPION
    records = []
    selectors = []
    for seed in (5001, 5002, 5007):
        for seat in (0, 1):
            path = next(
                Path("reports/replays/breakthrough").glob(f"{CHAMPION}*mooman*{seed}-{seat}.json")
            )
            raw = path.read_bytes()
            replay = json.loads(raw)
            for day in (15, 18):
                selector = selector_probe(source.decode(), replay, day, seat)
                selector["seed"] = seed
                selectors.append(selector)
                # No replay content after this checkpoint enters the evaluation.
                step = replay["steps"][day * 24]
                obs = deepcopy(step[0]["observation"])
                obs.update(deepcopy(step[seat]["observation"]))
                obs["player"] = seat
                for lag in (0, 1):
                    for background in ("finite_assets", "wheat_renewal", "rival_tomato8"):
                        for commission_delay in (0, 1) if day == 18 else (1,):
                            row = evaluate(
                                obs,
                                replay["configuration"],
                                source.decode(),
                                lag,
                                8,
                                game,
                                background,
                                commission_delay,
                            )
                            row.update(
                                seed=seed,
                                replay_path=str(path),
                                replay_sha256=hashlib.sha256(raw).hexdigest(),
                            )
                            records.append(row)
            print(json.dumps(dict(seed=seed, seat=seat, completed=len(records))), flush=True)
    result = dict(
        source_sha256=CHAMPION,
        diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        environment_version=version("kaggle-environments"),
        configuration=replay["configuration"],
        interpreter_sha256=hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        method="Exact equally weighted remaining shop enumeration. Inherited finite existing-asset forecast, plus sensitivities retaining all other current wheat slots or eight current rival wheat sites switching to fertilized tomatoes. These are prescribed public-asset scenarios, not reacting opponents. Official new crop transitions, one-day turnover, eight earliest wheat/empty sites; empty sites test immediate or next-day commissioning. Delivery lag 0/1 with same-day terminal sale is assumed, not jointly scheduled. Labor shadow4/action with one-fourth bulk delivery and amortized routing; full seed and fertilizer opportunity cost. No actual future shops or private opponent inventory. Closing probability refers only to rotation advantage over wheat offsetting current observed deficit, not a win probability. Current forecaster's daily demand discretization and existing-care assumptions are retained deliberately to isolate uncertainty effects. Existing asset revenue impact assumes its sale before the new cohort each day; current-unit feedback is charged to new cohort sales, prior-unit feedback to all affected assets. Selector witnesses use the first actually free crop-admission cell in each requested day, not future observations to choose at dawn.",
        records=records,
        selectors=selectors,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(result, indent=2) + "\n").encode()
    args.output.write_bytes(
        gzip.compress(content, mtime=0) if args.output.suffix == ".gz" else content
    )


if __name__ == "__main__":
    main()
