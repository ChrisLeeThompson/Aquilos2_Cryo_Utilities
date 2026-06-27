"""Chamber vacuum hardware ops.

Wraps AutoScript's ``microscope.vacuum`` with a narrow,
intention-revealing surface. Two implementations live side by side:

* :class:`VacuumOps` — real, backed by ``SdbMicroscopeClient.vacuum``.
* :class:`SimulatedVacuumOps` — in-memory simulation for offline UI
  development.

The Aquilos 2 uses **argon** to create a low chamber vacuum, both for
the Argon Purge activity (cycling the chamber through 30 / 15 / 10 Pa)
and for the magnetron Sputter Coat (pump to the sputter pressure, run,
then recover to high vacuum). Both procedures drive the chamber through
:meth:`pump_sputter_vacuum` / :meth:`pump_pressure` /
:meth:`pump_high_vacuum` and read :attr:`chamber_pressure` to know when
the chamber has equilibrated.

AutoScript types (``VacuumSettings``, ``VacuumMode``, ``VacuumGasType``)
are imported lazily inside the methods that need them — the same idiom
:class:`StageOps.make_position` uses — so this module stays importable
on machines without AutoScript installed (simulation-only dev).

Pressures are in **pascals** throughout (matching
``microscope.vacuum.chamber_pressure.value``).
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class VacuumOps:
    """Real vacuum ops backed by ``SdbMicroscopeClient.vacuum``."""

    def __init__(self, sdb: Any) -> None:
        self._sdb = sdb

    # --- Telemetry --------------------------------------------------------

    @property
    def chamber_pressure(self) -> float:
        """Current chamber pressure in pascals (read-only)."""
        return float(self._sdb.vacuum.chamber_pressure.value)

    @property
    def chamber_state(self) -> str:
        """Current chamber vacuum state (e.g. ``"Pumped"`` / ``"Pumping"``)."""
        return str(self._sdb.vacuum.chamber_state)

    # --- Pump / vent ------------------------------------------------------

    def pump_sputter_vacuum(self, pressure_pa: float) -> None:
        """Pump to ``pressure_pa`` in sputter (argon) vacuum mode.

        Used by the Argon Purge activity to set each step of its
        pressure sequence (30 / 15 / 10 Pa) with the gas explicitly
        set to argon. The call returns once the requested state change
        has been issued; the caller polls :attr:`chamber_pressure` to
        learn when the chamber has settled.
        """
        from autoscript_sdb_microscope_client.enumerations import (
            VacuumGasType,
            VacuumMode,
        )
        from autoscript_sdb_microscope_client.structures import VacuumSettings

        logger.info(
            "Vacuum: pump SPUTTER_VACUUM (argon) to %.2f Pa", pressure_pa
        )
        self._sdb.vacuum.pump(
            VacuumSettings(
                mode=VacuumMode.SPUTTER_VACUUM,
                gas=VacuumGasType.ARGON,
                pressure=float(pressure_pa),
            )
        )

    def pump_pressure(self, pressure_pa: float) -> None:
        """Pump to ``pressure_pa`` leaving mode/gas as already configured.

        Used by Sputter Coat *after* ``sputter_coater.prepare()`` has
        already switched the chamber to sputter vacuum and set the gas
        to argon — so only the target pressure is specified here,
        mirroring the v2.5 sequence.
        """
        from autoscript_sdb_microscope_client.structures import VacuumSettings

        logger.info("Vacuum: pump to %.2f Pa (mode/gas unchanged)", pressure_pa)
        self._sdb.vacuum.pump(VacuumSettings(pressure=float(pressure_pa)))

    def pump_high_vacuum(self) -> None:
        """Return the chamber to high vacuum (the base safe state)."""
        from autoscript_sdb_microscope_client.enumerations import VacuumMode
        from autoscript_sdb_microscope_client.structures import VacuumSettings

        logger.info("Vacuum: pump HIGH_VACUUM")
        self._sdb.vacuum.pump(VacuumSettings(mode=VacuumMode.HIGH_VACUUM))

    def vent(self) -> None:
        """Vent the chamber to atmospheric pressure."""
        logger.info("Vacuum: vent")
        self._sdb.vacuum.vent()


# --- Simulated implementation -------------------------------------------


# Sim chamber pressure at "high vacuum" — the steady state when no
# low-vacuum activity is running (pascals). Much lower than any sputter
# setpoint, so a pump-to-pressure always has to raise the chamber.
_SIM_HIGH_VACUUM_PA = 1.0e-3

# Exponential approach time constant (seconds) used when advancing the
# simulated pressure toward its target on each read. Tuned so that a
# 2 s poll interval moves the pressure ~75% of the way to target,
# letting an activity's pressure-equilibration / 15-Pa-tolerance loop
# converge within a few polls instead of running to its iteration cap.
_SIM_PRESSURE_TAU_S = 1.5

# When a pump-to-pressure is requested and the chamber is currently
# *below* the target (the common case: pumping argon up from high
# vacuum to a 10-30 Pa setpoint), seed the simulated pressure above the
# target by this factor so the caller's "wait until at/under target"
# poll loop has something to watch decay. Independent of the real
# hardware's poll cap.
_SIM_PUMP_UP_FACTOR = 3.0


class SimulatedVacuumOps:
    """Simulated vacuum ops for offline development.

    Models a single chamber pressure that relaxes exponentially toward
    the most recently requested target each time it is read. The decay
    is time-based (via :func:`time.monotonic`) so it behaves correctly
    regardless of how often the pressure is polled — the activity's
    2 s poll loop and a future charting reader can both read it without
    fighting over a per-read step counter.
    """

    def __init__(self) -> None:
        self._pressure: float = _SIM_HIGH_VACUUM_PA
        self._target: float = _SIM_HIGH_VACUUM_PA
        self._last_update: float = time.monotonic()

    def _advance(self) -> None:
        """Relax the simulated pressure toward the target by elapsed time."""
        import math

        now = time.monotonic()
        dt = max(0.0, now - self._last_update)
        self._last_update = now
        alpha = 1.0 - math.exp(-dt / _SIM_PRESSURE_TAU_S)
        self._pressure += (self._target - self._pressure) * alpha

    def _set_target(self, target_pa: float, *, pump_up_if_below: bool) -> None:
        # Advance to "now" first so the pressure reflects the state at
        # the moment the new target is requested, then retarget.
        self._advance()
        self._target = float(target_pa)
        if pump_up_if_below and self._pressure < self._target:
            self._pressure = self._target * _SIM_PUMP_UP_FACTOR
        self._last_update = time.monotonic()

    # --- Telemetry --------------------------------------------------------

    @property
    def chamber_pressure(self) -> float:
        self._advance()
        return self._pressure

    @property
    def chamber_state(self) -> str:
        # Crude but adequate for offline UI: "Pumped" once close to the
        # target, "Pumping" while still settling.
        self._advance()
        close = abs(self._pressure - self._target) <= max(
            0.5, 0.05 * self._target
        )
        return "Pumped" if close else "Pumping"

    # --- Pump / vent ------------------------------------------------------

    def pump_sputter_vacuum(self, pressure_pa: float) -> None:
        logger.info(
            "Simulated vacuum: pump SPUTTER_VACUUM (argon) to %.2f Pa",
            pressure_pa,
        )
        self._set_target(pressure_pa, pump_up_if_below=True)

    def pump_pressure(self, pressure_pa: float) -> None:
        logger.info("Simulated vacuum: pump to %.2f Pa", pressure_pa)
        self._set_target(pressure_pa, pump_up_if_below=True)

    def pump_high_vacuum(self) -> None:
        logger.info("Simulated vacuum: pump HIGH_VACUUM")
        self._set_target(_SIM_HIGH_VACUUM_PA, pump_up_if_below=False)

    def vent(self) -> None:
        logger.info("Simulated vacuum: vent")
        # Atmospheric-ish; not used by the current activities but kept
        # for parity with the real facade.
        self._set_target(1.0e5, pump_up_if_below=False)


# Type alias for callers that accept either implementation.
VacuumOpsLike = VacuumOps | SimulatedVacuumOps
