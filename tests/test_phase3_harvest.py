"""The experimental annual order correction uses actual official transitions."""

import hashlib
import importlib
from pathlib import Path


def test_harvest_order_and_terminal_admission(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    module = importlib.import_module("phase3_harvest")
    assert (
        hashlib.sha256(module.build().encode()).hexdigest()
        == "0413a45398b4713d255f2c2fbfd587e045cccf9fcdb8d765495efced15f1d42e"
    )
    cases = module.check()
    assert len(cases) == 5
    assert [case["candidate"][0] for case in cases] == [
        "WATER",
        "WATER",
        "HARVEST",
        "WATER",
        "HARVEST",
    ]
