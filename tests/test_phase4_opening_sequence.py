"""The opening queue puts four existing-cap animals into the day-zero market queue."""

from copy import deepcopy

from kaggle_environments import make
from scripts.phase4_opening_sequence import build


def animal_orders(policy, turns=8):
    env = make("kaggriculture", configuration={"seed": 0}, debug=True)
    env.reset(2)
    passive = {"farmer": ["PASS"], "market": []}
    orders = []
    for turn in range(turns):
        action = policy(deepcopy(env.state[0].observation), dict(env.configuration))
        orders.extend((turn, order[1]) for order in action["market"] if order[0] == "BUY_ANIMAL")
        env.step([action, passive])
    return orders


def test_opening_queue_admits_existing_two_cow_two_sheep_opening_early():
    baseline_source = build().replace(
        "sum(stock[a] for a in ANIMALS) < (4 if day == 0 else 2)",
        "sum(stock[a] for a in ANIMALS) < 2",
    )
    baseline = {}
    queued = {}
    exec(baseline_source, baseline)
    exec(build(), queued)
    assert animal_orders(queued["agent"])[:4] == [
        (0, "COW"),
        (1, "COW"),
        (2, "SHEEP"),
        (3, "SHEEP"),
    ]
    assert animal_orders(baseline["agent"])[2:] == [(4, "SHEEP"), (7, "SHEEP")]
