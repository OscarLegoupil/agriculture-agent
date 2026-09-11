"""Preserve harvested wheat cells with short, observed worker commitments.

Activation starts after the bridge-crop opening. A contract replaces only wheat
that the incumbent chose to harvest, and ends after planting and watering that
same cell. Failed work, movement, missed observations, and daily resets discard
it. The incumbent remains the fallback and chooses every other investment.
"""

import gzip
import hashlib
import inspect
from copy import deepcopy
from pathlib import Path

from kaggriculture.agent.competitive import (
    ANIMALS,
    CROPS,
    crop_value,
    default_price_parameters,
    distance,
    inventory_quote,
)

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def wheat_uncommitted_cash(obs, cfg, orders):
    """Reserve incumbent purchases without crediting unexecuted sale proceeds.

    Purchased-product quotes use the end of our requested quantity as a
    conservative own-impact estimate. Opponent orders can still change prices;
    a failed seed purchase simply prevents the observed planting commitment.
    """
    farm = obs["farms"][obs["player"]]
    cash = farm["money"]
    hires = farm["hires_today"]
    land = len(farm["unlocked_quadrants"]) - 1
    inventories = dict(obs["market"]["inventory"])
    parameters = obs["market"].get("params") or default_price_parameters()
    for order in orders:
        if order[0] == "HIRE":
            a, b = 1, 1
            for _ in range(hires):
                a, b = b, a + b
            cash -= a * cfg.get("farmHandCostMult", 1)
            hires += 1
        elif order[0] == "BUY_LAND":
            if land < 3:
                cash -= (1000, 2000, 4000)[land]
                land += 1
        elif order[0] == "BUY_SEED":
            cash -= CROPS[order[1]][0] * order[2]
        elif order[0] == "BUY_ANIMAL":
            cash -= ANIMALS[order[1]][0] * order[2]
        elif order[0] == "BUY_PRODUCT":
            item, quantity = order[1:3]
            inventories[item] -= quantity
            price = max(
                obs["market"]["prices"][item],
                inventory_quote(inventories[item], parameters[item]),
            )
            cash -= price * quantity
    return cash


def wheat_service(obs, cfg, base_policy, memory, start_day):
    """Execute an acknowledged HARVEST → PLANT → WATER service cycle."""
    if not obs.get("farms") or obs.get("player") not in (0, 1):
        return base_policy(obs, cfg)
    seat, day, hour, step = (obs[k] for k in ("player", "day", "hour", "step"))
    signature = (step, day, hour, obs["farms"], obs["private"], obs["market"], obs["town"], cfg)
    previous = memory.get(seat)
    if previous and previous["signature"] == signature:
        return deepcopy(previous["action"])
    consecutive = previous and previous["step"] + 1 == step and previous["day"] == day
    plans = previous["plans"] if consecutive else {}
    farm = obs["farms"][seat]
    board = farm["tiles"]
    private = obs["private"]
    positions = [tuple(farm["farmer"]), *map(tuple, farm["hands"])]
    seed_count = private["seeds"].get("WHEAT", 0)
    overrides, following = {}, {}
    planned_obs = deepcopy(obs) if plans else obs
    planned_farm = planned_obs["farms"][seat]

    for worker, plan in sorted(plans.items()):
        target = plan["position"]
        if worker >= len(positions) or positions[worker] != target:
            continue
        tile = board[target[1]][target[0]]
        if plan["stage"] == "harvest":
            carried = private["inventories"][worker].get("WHEAT", 0)
            if tile is not None or carried < plan["carried"] + plan["yield"] or seed_count <= 0:
                continue
            # Tell ordinary task generation this cell and seed are reserved.
            # The real observation remains unchanged until PLANT succeeds.
            overrides[worker] = ["PLANT", "WHEAT"]
            seed_count -= 1
            planned_obs["private"]["seeds"]["WHEAT"] = seed_count
            planned_farm["tiles"][target[1]][target[0]] = {
                "kind": "PLANT",
                "crop": "WHEAT",
                "planted_day": day,
                "watered_today": True,
                "consecutive_unwatered": 0,
                "yield_units": 1,
                "fertilized_until_day": -1,
                "max_lifespan_step": (day + CROPS["WHEAT"][2] + 1) * cfg.get("turnsPerDay", 24),
            }
            following[worker] = {"stage": "plant", "position": target, "planted_day": day}
        elif (
            isinstance(tile, dict)
            and tile.get("crop") == "WHEAT"
            and tile["planted_day"] == plan["planted_day"]
            and not tile["watered_today"]
        ):
            overrides[worker] = ["WATER"]
            planned_farm["tiles"][target[1]][target[0]]["watered_today"] = True

    result = deepcopy(base_policy(planned_obs, cfg))
    actions = [result.get("farmer", ["PASS"]), *result.get("hands", [])]
    actions += [["PASS"] for _ in range(max(0, len(positions) - len(actions)))]
    for worker, action in overrides.items():
        actions[worker] = action
    # Keep a defensive shared-seed check even if the base scheduler changes.
    remaining_seeds = private["seeds"].get("WHEAT", 0) - sum(
        action == ["PLANT", "WHEAT"] for action in overrides.values()
    )
    for worker, action in enumerate(actions):
        if worker not in overrides and action == ["PLANT", "WHEAT"]:
            if remaining_seeds <= 0:
                actions[worker] = ["PASS"]
            else:
                remaining_seeds -= 1

    if (
        start_day <= day <= 26
        and hour + 2 < cfg.get("turnsPerDay", 24)
        and obs["market"]["prices"]["WHEAT"] > CROPS["WHEAT"][0]
        and crop_value("WHEAT", day, obs["market"]["prices"]["WHEAT"], 0, False) > 0
    ):
        prospects, targets = [], set()
        for worker, action in enumerate(actions[: len(positions)]):
            position = positions[worker]
            tile = board[position[1]][position[0]]
            if (
                worker not in overrides
                and action == ["HARVEST"]
                and position not in targets
                and isinstance(tile, dict)
                and tile.get("crop") == "WHEAT"
                and tile["yield_units"] > 0
                and day - tile["planted_day"] >= CROPS["WHEAT"][1]
            ):
                # Two local actions must not consume the final departure for an
                # already-starving animal that this new feed could rescue.
                unsafe = any(
                    isinstance(t, dict)
                    and "animal" in t
                    and not t["fed_today"]
                    and t["consecutive_unfed"] > 0
                    and hour + 1 + distance(position, (x, y)) < cfg.get("turnsPerDay", 24)
                    and hour + 3 + distance(position, (x, y)) >= cfg.get("turnsPerDay", 24)
                    for y, row in enumerate(board)
                    for x, t in enumerate(row)
                )
                if not unsafe:
                    prospects.append(worker)
                    targets.add(position)
        market = result.setdefault("market", [])
        purchase = next((o for o in market if o[:2] == ["BUY_SEED", "WHEAT"]), None)
        purchased = sum(o[2] for o in market if o[:2] == ["BUY_SEED", "WHEAT"])
        available = (
            max(0, private["seeds"].get("WHEAT", 0) - sum(a == ["PLANT", "WHEAT"] for a in actions))
            + purchased
        )
        shortfall = max(0, len(prospects) - available)
        affordable = max(0, int(wheat_uncommitted_cash(obs, cfg, market) // CROPS["WHEAT"][0]))
        buy = min(shortfall, affordable)
        if buy and (purchase is not None or len(market) < cfg.get("maxMarketOrdersPerTurn", 10)):
            if purchase is None:
                market.append(["BUY_SEED", "WHEAT", buy])
            else:
                purchase[2] += buy
            available += buy
        for worker in prospects[:available]:
            target = positions[worker]
            following[worker] = {
                "stage": "harvest",
                "position": target,
                "carried": private["inventories"][worker].get("WHEAT", 0),
                "yield": board[target[1]][target[0]]["yield_units"],
            }
    result["farmer"], result["hands"] = actions[0], actions[1:]
    memory[seat] = {
        "step": step,
        "day": day,
        "plans": following,
        "signature": deepcopy(signature),
        "action": deepcopy(result),
    }
    return result


def build(start_day=10, enabled=True):
    """Return a standalone candidate; disabled output is the exact incumbent."""
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    if not enabled:
        return raw.decode()
    if not 0 <= start_day <= 26:
        raise ValueError("start_day must leave a finite-season wheat opportunity")
    source = raw.decode()
    assert source.count("def agent(obs:") == 1
    source = source.replace("def agent(obs:", "def _wheat_base_agent(obs:")
    source += "\n\nfrom copy import deepcopy\n\n_WHEAT_SERVICE_MEMORY = {}\n\n"
    source += inspect.getsource(wheat_uncommitted_cash) + "\n\n" + inspect.getsource(wheat_service)
    source += (
        "\n\ndef agent(obs, configuration=None):\n"
        "    return wheat_service(obs, configuration or {}, _wheat_base_agent,\n"
        f"                         _WHEAT_SERVICE_MEMORY, {int(start_day)})\n"
    )
    compile(source, "wheat_service", "exec")
    return source
