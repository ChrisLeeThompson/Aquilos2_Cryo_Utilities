"""Sputter coater hardware ops.

Wraps AutoScript's ``microscope.specimen.sputter_coater`` with a narrow,
intention-revealing surface. Two implementations live side by side:

* :class:`SputterOps` — real, backed by ``SdbMicroscopeClient.specimen.sputter_coater``.
* :class:`SimulatedSputterOps` — in-memory simulation for offline UI development.

This module targets the **magnetron plasma sputter coater** on the
Aquilos 2. Unlike the Hydra Bio MicroSputter (which is driven through
the plasma-FIB ion beam and a per-grid ``run(duration, grids)`` call),
the Aquilos magnetron is a self-contained device:

* :meth:`prepare` moves the stage to the sputter position, switches the
  chamber to sputter (argon) vacuum, and saves the prior state.
* :meth:`run` strikes the plasma and sputters for a duration — there is
  **no grid argument**; the whole specimen is coated.
* :meth:`recover` powers the magnetron down and restores the chamber /
  beam state that ``prepare`` saved.

``prepare`` / ``recover`` are supported on Aquilos systems (they are
not available on the Hydra Bio MicroSputter). The sputter current is
set directly via :attr:`current` (amperes); the activity converts the
user's milliamp value before assigning it.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# Simulated-mode caps so dev mode isn't tedious.
_SIM_SPUTTER_MAX_S = 5.0
_SIM_PREPARE_DURATION_S = 1.0
_SIM_RECOVER_DURATION_S = 1.0


class SputterOps:
    """Real sputter ops backed by ``SdbMicroscopeClient.specimen.sputter_coater``."""

    def __init__(self, sdb: Any) -> None:
        self._sdb = sdb

    @property
    def is_installed(self) -> bool:
        return bool(self._sdb.specimen.sputter_coater.is_installed)

    def prepare(self) -> None:
        """Prepare the magnetron for a sputter run.

        Moves the stage to the sputter position, switches the chamber to
        sputter (argon) vacuum, and saves the prior state so
        :meth:`recover` can restore it. Aquilos-only — not available on
        the Hydra Bio MicroSputter.
        """
        logger.info("Sputter coater: prepare")
        self._sdb.specimen.sputter_coater.prepare()
        logger.info("Sputter coater: prepare complete")

    def recover(self) -> None:
        """Power down the magnetron and restore the pre-prepare state.

        Restores the chamber vacuum mode/pressure/gas and any beam state
        that :meth:`prepare` saved. Aquilos-only.
        """
        logger.info("Sputter coater: recover")
        self._sdb.specimen.sputter_coater.recover()
        logger.info("Sputter coater: recover complete")

    @property
    def current(self) -> float:
        return float(self._sdb.specimen.sputter_coater.current.value)

    @current.setter
    def current(self, value: float) -> None:
        logger.info("Sputter coater: setting current to %.4e A", value)
        self._sdb.specimen.sputter_coater.current.value = float(value)

    def run(self, duration_s: int) -> None:
        logger.info("Sputter coater: run for %ds", duration_s)
        self._sdb.specimen.sputter_coater.run(duration_s)
        logger.info("Sputter coater: run complete")


# --- Simulated implementation -------------------------------------------


class SimulatedSputterOps:
    """Simulated sputter ops for offline development.

    * ``is_installed`` always True (so the activity doesn't trip the
      "not installed" early exit).
    * ``prepare()`` / ``recover()`` simulate their settle time and flip
      an ``_is_prepared`` flag so the activity's prepare → run → recover
      ordering is observable offline.
    * ``run()`` simulates its duration with ``time.sleep`` (capped) so
      the user-visible busy indicator is observable without waiting the
      full configured duration in dev.
    """

    def __init__(self) -> None:
        self._is_prepared: bool = False
        self._current: float = 0.030  # 30 mA, the default magnetron current

    @property
    def is_installed(self) -> bool:
        return True

    @property
    def is_prepared(self) -> bool:
        return self._is_prepared

    def prepare(self) -> None:
        logger.info(
            "Simulated sputter coater: prepare (simulated %.1fs)",
            _SIM_PREPARE_DURATION_S,
        )
        time.sleep(_SIM_PREPARE_DURATION_S)
        self._is_prepared = True
        logger.info("Simulated sputter coater: prepare complete")

    def recover(self) -> None:
        logger.info(
            "Simulated sputter coater: recover (simulated %.1fs)",
            _SIM_RECOVER_DURATION_S,
        )
        time.sleep(_SIM_RECOVER_DURATION_S)
        self._is_prepared = False
        logger.info("Simulated sputter coater: recover complete")

    @property
    def current(self) -> float:
        return self._current

    @current.setter
    def current(self, value: float) -> None:
        logger.info("Simulated sputter coater: setting current to %.4e A", value)
        self._current = float(value)

    def run(self, duration_s: int) -> None:
        sim_duration = min(float(duration_s), _SIM_SPUTTER_MAX_S)
        logger.info(
            "Simulated sputter coater: run requested %ds — simulating %.1fs",
            duration_s, sim_duration,
        )
        time.sleep(sim_duration)
        logger.info("Simulated sputter coater: run complete")


# Type alias for callers that accept either implementation.
SputterOpsLike = SputterOps | SimulatedSputterOps
