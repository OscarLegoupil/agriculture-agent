"""Larger batches must keep shared pickup reservations aligned with their size."""

from kaggle_environments.envs.kaggriculture import kaggriculture as game
from scripts.phase4_input_batches import build


def test_input_batch_candidate_compiles_and_changes_both_reservation_terms():
    source = build()
    assert 'batch_size = 6 if required == "WHEAT" else 8' in source
    assert '6 if required == "WHEAT" else 8' in source
    assert "demand_inputs[required] / batch_size" in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])


def test_official_pickup_keeps_a_six_wheat_batch_in_worker_inventory():
    farm = game._new_farm(10, 3000)
    farm["farmer"] = [4, 4]
    private = {"shed": {"WHEAT": 6}, "inventories": [{}], "seeds": {}}
    game._apply_unit_action(farm, private, 0, ["PICKUP", "WHEAT", 6], 10, 8, 24, 100)
    assert private["shed"]["WHEAT"] == 0
    assert private["inventories"][0]["WHEAT"] == 6
