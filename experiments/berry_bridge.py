"""Exchange four ripe opening wheat positions for an earlier berry cohort."""

from __future__ import annotations

import gzip
import hashlib
import inspect
from pathlib import Path

FLEET = "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7"
_BERRY_BRIDGES = {}


def berry_bridge_plan(obs, cash, seeds):
    """Commit only publicly observed ripe wheat, funded after labor and feed."""
    player, day, hour, step = obs["player"], obs["day"], obs["hour"], obs["step"]
    state = _BERRY_BRIDGES.get(player)
    if not state or step < state["step"] or step == 0:
        state = dict(step=step, targets=None)
        _BERRY_BRIDGES[player] = state
    state["step"] = step
    board = obs["farms"][player]["tiles"]
    half = len(board) // 2
    if day == 5 and hour < 14 and state["targets"] is None:
        plants = [
            (x, y, tile)
            for y, row in enumerate(board)
            for x, tile in enumerate(row)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT"
        ]
        wheat = [(x, y, tile) for x, y, tile in plants if tile["crop"] == "WHEAT"]
        existing = sum(tile["crop"] == "STRAWBERRY" for _, _, tile in plants)
        target_count = max(0, min(4 - existing, len(wheat) - 3))
        ripe = [
            (x, y, tile)
            for x, y, tile in wheat
            if x < half and y < half and day - tile["planted_day"] >= 2 and tile["yield_units"] > 0
        ]
        required_cash = max(0, target_count - seeds.get("STRAWBERRY", 0)) * 100
        # Current cash already excludes this turn's prescribed wages and feed.
        # No unexecuted market receipt is used to fund these seeds.
        if target_count and len(ripe) >= target_count and cash >= required_cash + 200:
            ripe.sort(
                key=lambda entry: (
                    abs(entry[0] - (half - 1)) + abs(entry[1] - (half - 1)),
                    entry[1],
                    entry[0],
                )
            )
            state["targets"] = {(x, y): tile["planted_day"] for x, y, tile in ripe[:target_count]}
        elif existing >= 4:
            state["targets"] = {}
    pending = {}
    for target, born in (state["targets"] or {}).items():
        tile = board[target[1]][target[0]]
        if tile is None or (
            isinstance(tile, dict) and tile.get("crop") == "WHEAT" and tile["planted_day"] == born
        ):
            pending[target] = born
    if state["targets"] is not None:
        state["targets"] = pending
    missing = max(0, len(pending) - seeds.get("STRAWBERRY", 0))
    buy = min(missing, max(0, int((cash - 200) // 100)))
    return pending, buy


def build(berries=4, cereal=False, arrival_replan=False, budget_seconds=0.065):
    if berries not in (0, 4):
        raise ValueError("The declared bridge comparison is four berries versus zero")
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{FLEET}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == FLEET
    source = raw.decode()
    if cereal:
        from experiments.daily_routes import build as fleet_build

        assert hashlib.sha256(fleet_build().encode()).hexdigest() == FLEET
        source = fleet_build(cereal=True)
    if budget_seconds not in (0.065, 0.150):
        raise ValueError("Use a declared search budget")
    source = source.replace(
        "deadline = time.perf_counter() + 0.065",
        f"deadline = time.perf_counter() + {budget_seconds:.3f}",
    )
    if arrival_replan:
        marker = '    state["step"] = step\n    plans = state["plans"]'
        assert source.count(marker) == 1
        source = source.replace(
            marker,
            """    state["step"] = step
    if state.get("workers", len(positions)) != len(positions):
        # Work already executed remains in the observation. Reservations are
        # disposable, so new arrivals can share the unexecuted obligations.
        state["plans"] = {}
        state.pop("observation_key", None)
    state["workers"] = len(positions)
    plans = state["plans"]""",
        )
    if not berries:
        compile(source, "arrival_replan_candidate", "exec")
        return source
    marker = '    if (\n        len(farm["unlocked_quadrants"]) < p["quadrants"]'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """    bridge_targets, bridge_buy = berry_bridge_plan(obs, cash, seeds)
    if bridge_buy:
        market.append(["BUY_SEED", "STRAWBERRY", bridge_buy])
        cash -= bridge_buy * 100
    if (
        len(farm["unlocked_quadrants"]) < p["quadrants"]""",
    )
    marker = '        expiry = tile["max_lifespan_step"]'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """        if (x, y) in bridge_targets and crop == "WHEAT" and seeds.get("STRAWBERRY", 0):
            task(x, y, "BRIDGE", 120, arg="STRAWBERRY")
            if not tile["watered_today"]:
                task(x, y, "WATER", 115)
            continue
        expiry = tile["max_lifespan_step"]""",
    )
    marker = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """        if (x, y) in bridge_targets:
            values["STRAWBERRY"] = max(values.values()) + 1
        crop = max(values, key=lambda c: values[c])""",
    )
    marker = (
        '            if "DIG" in choices:\n                operations.append((target, "DIG", None))'
    )
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """            if "BRIDGE" in choices and crop == "WHEAT":
                if not tile["watered_today"]:
                    operations.append((target, "WATER", None))
                operations.extend(((target, "HARVEST", None), (target, "PLANT", "STRAWBERRY"), (target, "WATER", None)))
                expected = ("BRIDGE", tile["planted_day"])
                required = True
                value = max(1, 8 * forecast["STRAWBERRY"] - (4 - tile["yield_units"]) * prices["WHEAT"] - 100)
            elif "DIG" in choices:
                operations.append((target, "DIG", None))""",
    )
    marker = '        if expected and expected[0] == "PLANT":'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """        if expected and expected[0] == "BRIDGE":
            if tile is not None and (
                kind != "PLANT"
                or tile["crop"] not in ("WHEAT", "STRAWBERRY")
                or (tile["crop"] == "WHEAT" and tile["planted_day"] != expected[1])
            ):
                return False
        if expected and expected[0] == "PLANT":""",
    )
    marker = "    claimed.update(route_claimed)"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """    tasks = [task for task in tasks if task[1] != "BRIDGE"]
    claimed.update(route_claimed)""",
    )
    source = source.replace(
        "def agent(",
        "_BERRY_BRIDGES = {}\n\n" + inspect.getsource(berry_bridge_plan) + "\n\ndef agent(",
    )
    compile(source, "berry_bridge_candidate", "exec")
    return source


if __name__ == "__main__":
    print(hashlib.sha256(build().encode()).hexdigest())
