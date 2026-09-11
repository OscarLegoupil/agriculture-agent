"""Prevent screens from evaluating a stale alias instead of the named policy."""

import importlib
from pathlib import Path

import pytest


def checker(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("strategy_screen").verify_entrypoint


def test_redefinition_does_not_move_python_namespace_insertion_order(monkeypatch):
    source = "def agent(obs): return 1\nphysical_agent = agent\ndef agent(obs): return 2\n"
    # These functions even have identical opcode bytes; constants differ.
    with pytest.raises(ValueError, match="Official loader"):
        checker(monkeypatch)(source)


def test_separate_physical_declaration_preserves_official_entrypoint(monkeypatch):
    checker(monkeypatch)(
        "def physical_agent(obs): return 1\ndef agent(obs): return physical_agent(obs) + 1\n"
    )
