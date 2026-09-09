from copy import deepcopy

import pytest
from kaggle_environments import make
from scripts.package_submission import build
from scripts.summarize_benchmark import summarize
from scripts.telemetry import Telemetry


def test_packaging_is_byte_deterministic(tmp_path):
    first = build(tmp_path / "first")
    second = build(tmp_path / "second")
    assert first == second
    assert (tmp_path / "first/main.py").read_bytes() == (tmp_path / "second/main.py").read_bytes()


def test_telemetry_preserves_trajectory_and_reconciles_cash():
    ordinary = make("kaggriculture", configuration={"seed": 17, "episodeSteps": 96})
    ordinary.run(["starter", "pass"])
    measured = make("kaggriculture", configuration={"seed": 17, "episodeSteps": 96})
    with Telemetry(measured, 0) as telemetry:
        measured.run(["starter", "pass"])
    for expected, actual in zip(ordinary.steps, measured.steps, strict=True):
        assert expected[0].observation.farms == actual[0].observation.farms
        assert expected[0].observation.private == actual[0].observation.private
    income = sum(v for k, v in telemetry.ledger.items() if k.startswith("income:"))
    expense = sum(v for k, v in telemetry.ledger.items() if k.startswith("expense:"))
    assert measured.state[0].reward == 3000 + income - expense
    assert telemetry.actions["success:PLANT"] > 0


def test_score_handles_draws_errors_and_seed_clusters():
    rows = [
        dict(
            opponent="reference-gzm",
            seed=seed,
            seat=seat,
            cash=cash,
            opponent_cash=10,
            statuses=["DONE", "DONE"],
        )
        for seed, cash in ((1, 10), (2, 20))
        for seat in (0, 1)
    ]
    result = summarize(rows, primary=["reference-gzm"])
    assert result["primary"]["score"] == 0.75
    assert result["primary"]["ci95"] == [0.5, 1.0]
    assert not result["primary"]["gate_passed"]
    error_rows = deepcopy(rows)
    error_rows[0]["statuses"][0] = "ERROR"
    assert summarize(error_rows)["opponents"]["reference-gzm"]["errors"] == 1
    with pytest.raises(ValueError, match="both seats"):
        summarize(rows[:-1], primary=["reference-gzm"])


def test_reference_variants_do_not_get_independent_primary_votes():
    rows = [dict(opponent="data/raw/reference-lonespear/main_bigherd.py", seed=0, seat=seat,
                 cash=100, opponent_cash=50, statuses=["DONE", "DONE"]) for seat in (0,1)]
    assert "primary" not in summarize(rows)
