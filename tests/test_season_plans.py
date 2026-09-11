"""Production-calendar admissions executed through the official environment."""

from copy import deepcopy

from experiments.season_plans import build


def test_directed_wool_admission_executes_and_inputs_wait_for_next_action():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    policy = {}
    exec(build("wool"), policy)
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    state = env.state[0].observation
    state.update(day=8, hour=0, step=192)
    farm = state.farms[0]
    farm["money"] = 15000
    for x in range(4):
        farm.tiles[0][x] = game._new_animal("COW", 0)
    for x in range(2):
        farm.tiles[1][x] = game._new_animal("COW", 0)
        farm.tiles[2][x] = game._new_animal("SHEEP", 0)
    action = policy["agent"](deepcopy(state), dict(env.configuration))
    buys = [a for a in action["market"] if a[0] == "BUY_ANIMAL"]
    assert buys == [["BUY_ANIMAL", "SHEEP", 1]]
    assert sum(a[0] == "HIRE" for a in action["market"]) >= 8
    # Execute the concrete order and an impossible same-action pickup.
    env.step([{"farmer": ["PICKUP", "SHEEP", 1], "market": buys}, {}])
    private = env.state[0].observation.private
    assert private.shed["SHEEP"] == 1
    assert private.inventories[0].get("SHEEP", 0) == 0


def test_calendar_cannot_spend_absent_working_capital():
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    state = deepcopy(env.state[0].observation)
    state.update(day=10, hour=8, step=248)
    state.farms[0]["money"] = 15
    for family in ("wool", "dairy", "balanced"):
        policy = {}
        exec(build(family), policy)
        action = policy["agent"](deepcopy(state), dict(env.configuration))
        assert not any(a[0].startswith("BUY") or a[0] == "HIRE" for a in action["market"])
