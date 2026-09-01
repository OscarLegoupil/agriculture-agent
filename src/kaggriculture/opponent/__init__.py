"""Opponent modelling.

Public state gives the opponent's farm tiles, market inventory, and unlocked
shops. Their private shed is hidden. This subpackage reconstructs the hidden
inventory from the observable ledger.
"""

from kaggriculture.opponent.inference import (
    CommodityEstimate,
    OpponentInventoryTracker,
    town_consumption_between,
)

__all__ = [
    "CommodityEstimate",
    "OpponentInventoryTracker",
    "town_consumption_between",
]
