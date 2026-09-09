"""Instrument official state transitions without changing their semantics."""

from collections import Counter
from copy import deepcopy


class Telemetry:
    def __init__(self, env, seat):
        self.env, self.seat = env, seat
        self.actions, self.ledger, self.losses = Counter(), Counter(), Counter()
        self.farm = self.private = None
        self.originals = {}

    def __enter__(self):
        from kaggle_environments.envs.kaggriculture import kaggriculture as game

        self.game = game
        self.interpreter = self.env.interpreter

        def interpreter(state, env):
            if state[0].observation.farms:
                self.farm = state[0].observation.farms[self.seat]
                self.private = state[self.seat].observation.private
            return self.interpreter(state, env)

        self.env.interpreter = interpreter
        for name, wrapper in (
            ("_apply_unit_action", self.unit),
            ("_commit_unit", self.commit),
            ("_do_hire", self.hire),
            ("_do_buy_land", self.land),
            ("_end_of_day", self.refresh),
        ):
            self.originals[name] = getattr(game, name)
            setattr(game, name, wrapper)
        return self

    def __exit__(self, *args):
        for name, function in self.originals.items():
            setattr(self.game, name, function)
        self.env.interpreter = self.interpreter

    def unit(self, farm, private, idx, action, *rest):
        function = self.originals["_apply_unit_action"]
        if farm is not self.farm:
            return function(farm, private, idx, action, *rest)
        pos = self.game._farmer_position(farm, idx)
        if pos is None:
            return function(farm, private, idx, action, *rest)
        x, y = pos

        def snapshot():
            return (
                tuple(self.game._farmer_position(farm, idx)),
                deepcopy(farm["tiles"][y][x]),
                dict(private["inventories"][idx]),
                dict(private["shed"]),
                dict(private["seeds"]),
            )

        before = snapshot()
        result = function(farm, private, idx, action, *rest)
        op = action[0] if action else "PASS"
        changed = before != snapshot()
        prefix = "success:" if changed else "idle:" if op == "PASS" else "failed:"
        self.actions[prefix + op] += 1
        return result

    def commit(self, op, item, price, farm, private, *rest):
        result = self.originals["_commit_unit"](op, item, price, farm, private, *rest)
        if farm is self.farm and result:
            self.ledger[("income:" if op == "SELL" else "expense:") + item] += price
            self.ledger["units:" + op + ":" + item] += 1
        return result

    def hire(self, farm, private, *rest):
        cash, count = farm["money"], len(farm["hands"])
        result = self.originals["_do_hire"](farm, private, *rest)
        if farm is self.farm:
            self.ledger["expense:labor"] += cash - farm["money"]
            self.ledger["hires"] += len(farm["hands"]) - count
        return result

    def land(self, farm, *rest):
        cash, count = farm["money"], len(farm["unlocked_quadrants"])
        result = self.originals["_do_buy_land"](farm, *rest)
        if farm is self.farm:
            self.ledger["expense:land"] += cash - farm["money"]
            self.ledger["land_purchases"] += len(farm["unlocked_quadrants"]) - count
        return result

    def refresh(self, state, env, day):
        before = deepcopy(self.farm["tiles"])
        total = sum(self.private["shed"].values()) + sum(
            sum(i.values()) for i in self.private["inventories"]
        )
        result = self.originals["_end_of_day"](state, env, day)
        self.losses["overflow_units"] += max(0, total - env.configuration.shedCapacity)
        for y, row in enumerate(before):
            for x, tile in enumerate(row):
                after = self.farm["tiles"][y][x]
                if isinstance(tile, dict) and isinstance(after, dict):
                    if "animal" in tile and "animal" not in after:
                        self.losses["terminal_escapes" if day >= 28 else "animal_escapes"] += 1
                    if tile.get("kind") == "PLANT" and after.get("kind") == "WEED":
                        self.losses["terminal_abandonment" if day >= 28 else "water_deaths"] += 1
        return result
