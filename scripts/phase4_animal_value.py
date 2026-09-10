"""Finite animal-cohort receipts with explicit placement and sale dates."""

import gzip
import hashlib
import inspect
import math
from pathlib import Path


def cohort_plan(placed_day, animal_data, last_sale_day=29):
    """Ideal daily feeding and useful care, same-production-day harvest/sale.

    Placement is a scenario input, not predicted from future state. No terminal
    animal resale or future shop realization is credited. Transport is excluded.
    """
    _, first, interval, cap, _, _ = animal_data
    events = list(range(placed_day + first, last_sale_day + 1, interval))
    if not events:
        return {"events": [], "feed_days": [], "care_days": []}
    last = events[-1]
    feed_days, care_days, receipts = [], [], []
    pending = 0
    for work_day in range(placed_day, last):
        feed_days.append(work_day)
        production_day = work_day + 1
        if production_day in events:
            receipts.append(
                {
                    "production_day": production_day,
                    "sale_day": production_day,
                    "units": min(cap, 1 + pending),
                }
            )
            pending = 0
        # Today's care is accumulated only after the production above.
        if any(event > production_day for event in events) and pending < cap - 1:
            care_days.append(work_day)
            pending += 1
    return {"events": receipts, "feed_days": feed_days, "care_days": care_days}


def value_plan(
    plan,
    animal_data,
    product_quote,
    feed_quote,
    cash_per_action=0.0,
    travel_actions=0,
    initial_actions=3,
):
    """Cash-flow sensitivity, not optimized labor or a deployment guarantee.

    Prices are cash/unit; cash_per_action is a stated opportunity-cost input.
    initial_actions covers build/pickup/place; feed pickups use batches of three.
    Each receipt needs harvest and DROP, with travel provided separately.
    """
    feeds = len(plan["feed_days"])
    receipts = sum(event["units"] for event in plan["events"]) * product_quote
    actions = initial_actions + feeds + len(plan["care_days"]) + math.ceil(feeds / 3)
    actions += 2 * len(plan["events"]) + travel_actions
    return {
        "receipts": receipts,
        "animal_cost": animal_data[0],
        "feed_cost": feeds * feed_quote,
        "service_actions": actions,
        "action_opportunity_cost": actions * cash_per_action,
        "net_cash_value": receipts
        - animal_data[0]
        - feeds * feed_quote
        - actions * cash_per_action,
    }


def build():
    """Isolate startup-yield accounting; preserve incumbent costs and admission."""
    digest = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    old = "            events = max(0, 1 + (28 - day - first) // interval)\n            revenue = events * (interval + 1) * forecast[product]"
    new = '            plan = cohort_plan(day + 1, ANIMALS[animal])\n            revenue = sum(event["units"] for event in plan["events"]) * forecast[product]'
    assert source.count(old) == 1
    source = source.replace(old, new)
    source = source.replace("def agent(obs:", inspect.getsource(cohort_plan) + "\n\ndef agent(obs:")
    compile(source, "first_cohort_receipts", "exec")
    return source
