"""Per-commodity price forecaster.

The forecast is built from three pieces:

1. **Analytical price curve.** :func:`market_price` is the deterministic
   ``price = base + sign * amp * f(|inv - I0|)`` map from ``kaggriculture.py``,
   transcribed here so the tracker does not import the simulator on the
   1s-per-turn hot path.
2. **Deterministic town consumption.** Town center and unlocked shops draw
   from the market on fixed intervals. Given a horizon we can enumerate the
   exact inventory drop they will cause.
3. **Smoothed net trade rate.** Between consecutive observations the market
   inventory delta minus town consumption is the net flow from both players.
   An exponentially-weighted running rate captures the trend; the forecaster
   extrapolates that rate over the horizon.

The output of :meth:`PriceForecaster.predict` is a ``dict[str, float]`` price
per commodity, ready to drop into
``kaggriculture.planning.replanner.DynamicReplanner``'s ``price_map`` input.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from kaggriculture.env.constants import (
    DEFAULT_CONFIG,
    HINGE_GAIN,
    MARKET_PARAMS,
    PRICE_FLOOR,
    PRODUCTS,
)
from kaggriculture.env.observation import Observation
from kaggriculture.opponent.inference import town_consumption_between


def _shape(func: str, x: float, T: float | None = None) -> float:
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "log10":
        return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0:
            return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    raise ValueError(f"unknown shape function: {func!r}")


def market_price(item: str, inventory: int | float) -> int:
    """Deterministic price given a market inventory.

    Mirrors ``kaggriculture.py``'s ``market_price`` exactly, floored at
    :data:`PRICE_FLOOR`.
    """
    if item not in MARKET_PARAMS:
        raise KeyError(f"unknown commodity {item!r}")
    p = MARKET_PARAMS[item]
    base = p["base"]
    I0 = p["I0"]
    T = p["T"]
    if inventory < I0:
        amp = p["below_target"] * base / _shape(p["below_func"], T, T)
        price = base + amp * _shape(p["below_func"], I0 - inventory, T)
    else:
        amp = p["above_target"] * base / _shape(p["above_func"], T, T)
        price = base - amp * _shape(p["above_func"], inventory - I0, T)
    return max(PRICE_FLOOR, round(price))


def project_inventory(
    current_inventory: dict[str, int],
    unlocked_shops: Iterable[str],
    prev_step: int,
    horizon_steps: int,
    *,
    trade_rate: dict[str, float] | None = None,
    shop_interval: int = int(DEFAULT_CONFIG["townShopSellInterval"]),
    center_interval: int = int(DEFAULT_CONFIG["townCenterSellInterval"]),
) -> dict[str, float]:
    """Project market inventory ``horizon_steps`` into the future.

    ``trade_rate`` is the smoothed *net inflow per step* from player sells
    minus buys, one value per commodity. Positive rates raise the projected
    inventory. Absent commodities default to zero drift.

    The projection assumes ``unlocked_shops`` does not change over the
    horizon. Shops unlock only at the end-of-day boundary every three days,
    so the assumption is exact for horizons up to two days and pessimistic
    for longer horizons.
    """
    if horizon_steps < 0:
        raise ValueError(f"horizon_steps must be >= 0, got {horizon_steps}")
    now_step = prev_step + horizon_steps
    town = town_consumption_between(
        prev_step,
        now_step,
        unlocked_shops,
        shop_interval=shop_interval,
        center_interval=center_interval,
    )
    rate = trade_rate or {}
    return {
        item: current_inventory.get(item, 0)
        + rate.get(item, 0.0) * horizon_steps
        - town.get(item, 0)
        for item in PRODUCTS
    }


@dataclass
class PriceForecaster:
    """Online forecaster with an EWMA net-trade-rate estimator.

    ``smoothing`` (alpha in [0, 1]) controls how quickly the running trade
    rate absorbs new samples. A larger value reacts faster but is noisier;
    the default 0.2 is a reasonable starting point for daily-scale drift.
    """

    smoothing: float = 0.2
    turns_per_day: int = int(DEFAULT_CONFIG["turnsPerDay"])
    shop_interval: int = int(DEFAULT_CONFIG["townShopSellInterval"])
    center_interval: int = int(DEFAULT_CONFIG["townCenterSellInterval"])

    _rate: dict[str, float] = field(init=False)
    _prev_obs: Observation | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.smoothing <= 1.0:
            raise ValueError(f"smoothing must be in [0, 1], got {self.smoothing}")
        self._rate = dict.fromkeys(PRODUCTS, 0.0)

    @property
    def trade_rate(self) -> dict[str, float]:
        return dict(self._rate)

    def _step_of(self, obs: Observation) -> int:
        return obs.day * self.turns_per_day + obs.hour

    def update(self, obs: Observation) -> None:
        """Advance the smoothed trade rate by one observation."""
        if self._prev_obs is None:
            self._prev_obs = obs
            return
        prev = self._prev_obs
        prev_step = self._step_of(prev)
        now_step = self._step_of(obs)
        delta = now_step - prev_step
        if delta <= 0:
            self._prev_obs = obs
            return

        town = town_consumption_between(
            prev_step,
            now_step,
            prev.town.unlocked_shops,
            shop_interval=self.shop_interval,
            center_interval=self.center_interval,
        )
        for item in PRODUCTS:
            market_delta = obs.market.inventory[item] - prev.market.inventory[item]
            # Net trade contribution over this window = observed delta plus
            # what town consumed. Divide by window length to get per-step rate.
            trade_component = (market_delta + town[item]) / delta
            self._rate[item] = (
                self.smoothing * trade_component + (1.0 - self.smoothing) * self._rate[item]
            )
        self._prev_obs = obs

    def predict(self, obs: Observation, horizon_steps: int) -> dict[str, float]:
        """Predicted price per commodity ``horizon_steps`` after ``obs``."""
        if horizon_steps < 0:
            raise ValueError(f"horizon_steps must be >= 0, got {horizon_steps}")
        projected = project_inventory(
            current_inventory=obs.market.inventory,
            unlocked_shops=obs.town.unlocked_shops,
            prev_step=self._step_of(obs),
            horizon_steps=horizon_steps,
            trade_rate=self._rate,
            shop_interval=self.shop_interval,
            center_interval=self.center_interval,
        )
        return {item: float(market_price(item, projected[item])) for item in PRODUCTS}

    def predict_days(self, obs: Observation, horizon_days: int) -> dict[str, float]:
        return self.predict(obs, horizon_days * self.turns_per_day)

    def predict_horizons(
        self, obs: Observation, horizons_steps: Iterable[int]
    ) -> dict[int, dict[str, float]]:
        return {h: self.predict(obs, h) for h in horizons_steps}
